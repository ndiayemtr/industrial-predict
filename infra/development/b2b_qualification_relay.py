"""Opaque byte relay. Explicit run only; no bind, Docker or SQL on import.

No TLS termination, logging of payloads, retry, port selection or resource
creation/deletion. The Windows listener and child streams belong to this run.
"""
import os
import shutil
import socket
import subprocess
import threading

from b2b_qualification import CAMPAIGN, PORT, Qualification, require

# Only the isolated container's own loopback. Never interpolate configuration.
# EOF on either direction closes the opposite stream; no TTY, text codecs or
# PowerShell pipeline. cat copies raw bytes; bash owns/cleans its reader child.
BRIDGE = ('exec 3<>/dev/tcp/127.0.0.1/55443 || exit 70; '
          'cat <&3 & reader=$!; cat >&3; status=$?; '
          'kill "$reader" 2>/dev/null || :; wait "$reader" 2>/dev/null || :; exit "$status"')


def write_all(stream, data):
    remaining = memoryview(data)
    while remaining:
        count = stream.write(remaining)
        if count is None or count <= 0:
            raise OSError('Qualification relay write failed')
        remaining = remaining[count:]


def pipe_command(docker, identifier):
    return [docker, 'exec', '-i', identifier, '/bin/bash', '-c', BRIDGE]


class Relay:
    def __init__(self, qualification):
        require(type(qualification) is Qualification, 'Explicit qualification required')
        self.q = qualification
        self.stop = threading.Event()
        self.failed = threading.Event()
        self.lock = threading.Lock()
        self.children, self.clients, self.workers = set(), set(), []
        self.listener = None

    def fail(self):
        self.failed.set()
        self.stop.set()

    def transfer(self, client):
        process = None
        sender = None
        try:
            identifier = self.q.verify_resources()  # Exact ID/labels/mount before every stream.
            docker = shutil.which('docker')
            require(docker is not None, 'Docker client unavailable')
            process = subprocess.Popen(pipe_command(docker, identifier), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
            with self.lock:
                self.children.add(process)
            def upload():
                try:
                    while not self.stop.is_set():
                        data = client.recv(65536)
                        if not data:
                            break
                        write_all(process.stdin, data)
                except (OSError, ValueError):
                    if not self.stop.is_set():
                        self.fail()
                finally:
                    try:
                        process.stdin.close()
                    except (OSError, ValueError):
                        if not self.stop.is_set():
                            self.fail()
            sender = threading.Thread(target=upload, daemon=True)
            sender.start()
            while not self.stop.is_set():
                data = process.stdout.read(65536)
                if not data:
                    break
                client.sendall(data)
            client.shutdown(socket.SHUT_RDWR)
            sender.join(3)
            require(not sender.is_alive(), 'Qualification relay stalled')
            require(process.wait(timeout=3) == 0, 'Qualification relay child failed')
        except Exception:
            if not self.stop.is_set():
                self.fail()
        finally:
            client.close()
            if process is not None:
                # Terminate only this run's own Popen handle; never docker stop.
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.fail()  # No kill/retry escalation or uncertain cleanup.
                for stream in (process.stdin, process.stdout):
                    if stream is not None:
                        stream.close()
                with self.lock:
                    self.children.discard(process)
            if sender is not None:
                sender.join(3)
            with self.lock:
                self.clients.discard(client)

    def monitor(self):
        while not self.stop.wait(1):
            try:
                self.q.verify_resources()
            except Exception:
                self.fail()  # A changed/stopped resource ends the campaign, no reconnect.

    def run(self):
        require(os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'), 'Windows exclusive loopback listener required')
        self.q.validate()
        self.q.transport()
        self.q.verify_resources()
        # Reuse the official interactive operator boundary; no stdin automation.
        import manage
        manage.b2b_confirm('QUALIFICATION-RELAY', {'campaign': CAMPAIGN, **self.q.plan()})
        self.q.verify_resources()
        monitor = None
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                self.listener = listener
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                listener.bind(('127.0.0.1', PORT))
                listener.listen(16)
                listener.settimeout(0.5)
                monitor = threading.Thread(target=self.monitor, daemon=True)
                monitor.start()
                while not self.stop.is_set():
                    try:
                        client, address = listener.accept()
                    except socket.timeout:
                        continue
                    with self.lock:
                        admitted = address[0] == '127.0.0.1' and len(self.clients) < 16
                        if admitted:
                            self.clients.add(client)
                    if not admitted:
                        client.close()
                        raise ValueError('Qualification relay peer/limit rejected')
                    worker = threading.Thread(target=self.transfer, args=(client,), daemon=True)
                    self.workers.append(worker)
                    worker.start()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop.set()
            with self.lock:
                clients, children = list(self.clients), list(self.children)
            for client in clients:
                try:
                    client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                client.close()
            for child in children:
                if child.poll() is None:
                    child.terminate()
            for worker in self.workers:
                worker.join(5)
                if worker.is_alive():
                    self.failed.set()
            if monitor is not None:
                monitor.join(12)
                if monitor.is_alive():
                    self.failed.set()
            self.listener = None
        require(not self.failed.is_set(), 'Qualification relay failed; stop, no retry or automatic resource deletion')
