"""Explicit, read-only PostgreSQL v3 transport. Importing this module performs no I/O.

Not a general DB-API driver, migration executor, approval or real attestation.
Only the collector's fixed metadata statements are admitted.
"""

import base64
from functools import wraps
import hashlib
import hmac
import secrets
import socket
import ssl
import struct
from time import monotonic

from b2b_postgres_qualification import collectors as c, validation as v
from b2b_postgres_qualification.contracts import Offline, Rejected, deny
from b2b_postgres_qualification.evidence import _policy


OPTIONS = "-c default_transaction_read_only=on -c statement_timeout=3000 -c lock_timeout=1000"
QUERIES = frozenset((c.IDENTITY_SQL, c.REVISION_SQL, c.PRIVILEGES_SQL, c.COLUMNS_SQL,
    "BEGIN TRANSACTION READ ONLY", "SET LOCAL statement_timeout='3s'",
    "SET LOCAL lock_timeout='1s'", "ROLLBACK"))
MAX_PACKET = 65536


def _public(function):
    """Discard underlying errors (including server diagnostics and cleanup errors)."""
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            pass
        deny(Rejected)
    return call


def _check(value):
    if not value:
        raise ValueError()


def _context(ca_der):
    # No OS trust store, environment, PEM file, client key or TLS downgrade path.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.hostname_checks_common_name = False
    context.load_verify_locations(cadata=ssl.DER_cert_to_PEM_cert(ca_der))
    _check(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED)
    return context


def _b64(value):
    return base64.b64encode(value)


class _Scram(Offline):
    """Bounded SCRAM-SHA-256; printable ASCII passwords only (no SASLprep ambiguity)."""

    def __init__(self, password):
        self._password = password.encode('ascii')
        self._nonce = _b64(secrets.token_bytes(24))
        self._first = b'n=,r=' + self._nonce
        self.first = b'n,,' + self._first

    def continue_(self, message):
        _check(len(message) <= 2048)
        parts = message.split(b',')
        _check(len(parts) == 3 and [p[:2] for p in parts] == [b'r=', b's=', b'i='])
        nonce, salt, iterations = (p[2:] for p in parts)
        _check(nonce.startswith(self._nonce) and len(nonce) > len(self._nonce))
        _check(all(33 <= ch <= 126 and ch != 44 for ch in nonce))
        _check(iterations.isdigit() and len(iterations) <= 6)
        iterations = int(iterations)
        _check(4096 <= iterations <= 100000)
        salt = base64.b64decode(salt, validate=True)
        _check(8 <= len(salt) <= 128)
        salted = hashlib.pbkdf2_hmac('sha256', self._password, salt, iterations)
        self._password = b''
        key = hmac.digest(salted, b'Client Key', 'sha256')
        final = b'c=biws,r=' + nonce
        auth = self._first + b',' + message + b',' + final
        signature = hmac.digest(hashlib.sha256(key).digest(), auth, 'sha256')
        self._expected = hmac.digest(hmac.digest(salted, b'Server Key', 'sha256'), auth, 'sha256')
        return final + b',p=' + _b64(bytes(a ^ b for a, b in zip(key, signature)))

    def finish(self, message):
        _check(message.startswith(b'v=') and len(message) <= 128)
        _check(hmac.compare_digest(base64.b64decode(message[2:], validate=True), self._expected))
        self._expected = b''


class _Connection(Offline):
    def __init__(self, owner, raw, deadline):
        self._owner, self._socket, self._deadline = owner, raw, deadline
        self._closed, self._authenticated = False, False
        self._certificate, self._pid = None, None

    def _budget(self):
        remaining = self._deadline - monotonic()
        _check(not self._closed and remaining > 0)
        self._socket.settimeout(min(3, remaining))

    def _read(self, count):
        result = bytearray()
        while len(result) < count:
            self._budget()
            block = self._socket.recv(count - len(result))
            _check(block)
            result.extend(block)
        return bytes(result)

    def _send(self, value):
        self._budget()
        self._socket.sendall(value)

    def _message(self):
        kind, size = struct.unpack('!cI', self._read(5))
        _check(4 <= size <= MAX_PACKET)
        return kind, self._read(size - 4)

    def _packet(self, kind, body):
        self._send(kind + struct.pack('!I', len(body) + 4) + body)

    def _startup(self, database, role, password):
        values = ('user', role, 'database', database, 'client_encoding', 'UTF8', 'options', OPTIONS)
        body = struct.pack('!I', 196608) + b'\0'.join(x.encode('ascii') for x in values) + b'\0\0'
        self._send(struct.pack('!I', len(body) + 4) + body)
        state, scram = 0, None
        for _ in range(128):
            kind, body = self._message()
            if kind == b'R':
                _check(len(body) >= 4)
                code, data = struct.unpack('!I', body[:4])[0], body[4:]
                if code == 10 and state == 0:
                    _check(data.endswith(b'\0\0') and b'SCRAM-SHA-256' in data[:-2].split(b'\0'))
                    scram = _Scram(password)
                    self._packet(b'p', b'SCRAM-SHA-256\0' + struct.pack('!I', len(scram.first)) + scram.first)
                    state = 1
                elif code == 11 and state == 1:
                    self._packet(b'p', scram.continue_(data))
                    state = 2
                elif code == 12 and state == 2:
                    scram.finish(data)
                    state = 3
                elif code == 0 and state == 3:
                    _check(not data)
                    state = 4
                else:
                    raise ValueError()  # Includes trust, cleartext, MD5 and reordered SCRAM.
            elif kind == b'K' and state == 4:
                _check(len(body) == 8 and self._pid is None)
                self._pid = struct.unpack('!I', body[:4])[0]  # Never retain cancellation secret.
            elif kind == b'S' and state == 4:
                _check(body.endswith(b'\0'))
            elif kind == b'Z':
                _check(state == 4 and body == b'I' and self._pid and self._pid > 0)
                self._authenticated = True
                return
            else:
                raise ValueError()  # Discard errors/notices, never expose payloads.
        raise ValueError()

    def _query(self, query):
        _check(query in QUERIES and self._authenticated)
        self._owner.tls_binding(self)
        self._packet(b'Q', query.encode('utf8') + b'\0')
        columns, rows, complete, total = None, [], False, 0
        for _ in range(256):
            kind, body = self._message()
            total += len(body)
            _check(total <= 262144)
            if kind == b'T':
                _check(columns is None and not complete and len(body) >= 2)
                count, offset, columns = struct.unpack('!H', body[:2])[0], 2, []
                _check(1 <= count <= 64)
                for _ in range(count):
                    end = body.index(b'\0', offset)
                    name = body[offset:end].decode('utf8')
                    _check(name and len(name) <= 128 and end + 19 <= len(body))
                    _, _, oid, _, _, fmt = struct.unpack('!IhIhih', body[end+1:end+19])
                    _check(fmt == 0 and oid in (16, 19, 20, 21, 23, 25, 1043))
                    columns.append((name, oid))
                    offset = end + 19
                _check(offset == len(body) and len({n for n, _ in columns}) == count)
            elif kind == b'D':
                _check(columns is not None and not complete and len(rows) < 64 and len(body) >= 2)
                _check(struct.unpack('!H', body[:2])[0] == len(columns))
                row, offset = {}, 2
                for name, oid in columns:
                    _check(offset + 4 <= len(body))
                    size = struct.unpack('!i', body[offset:offset+4])[0]
                    offset += 4
                    _check(size >= -1 and offset + max(0, size) <= len(body))
                    value = None
                    if size != -1:
                        value = body[offset:offset+size].decode('utf8')
                        if oid == 16:
                            _check(value in ('t', 'f'))
                            value = value == 't'
                        elif oid in (20, 21, 23):
                            value = int(value)
                        offset += size
                    row[name] = value
                _check(offset == len(body))
                rows.append(row)
            elif kind == b'C':
                _check(not complete and body.endswith(b'\0'))
                complete = True
            elif kind == b'Z':
                expected = b'T' if query.startswith(('BEGIN ', 'SET LOCAL ')) else b'I' if query == 'ROLLBACK' else None
                _check(complete and body in (b'I', b'T') and (expected is None or body == expected))
                self._budget()
                return rows
            else:
                raise ValueError()
        raise ValueError()

    @_public
    def cursor(self):
        _check(not self._closed)
        return _Cursor(self)

    @_public
    def rollback(self):
        try:
            self._query('ROLLBACK')
        except Exception:
            self.close()
            raise

    @_public
    def close(self):
        if not self._closed:
            self._closed = True
            self._authenticated = False
            # No TLS unwrap or second cancellation connection; bounded OS close only.
            self._socket.close()


class _Cursor(Offline):
    def __init__(self, connection):
        self._connection, self._rows, self._closed = connection, [], False

    @_public
    def execute(self, query):
        try:
            _check(not self._closed and type(query) is str)
            self._rows = self._connection._query(query)
        except Exception:
            self._connection.close()
            raise

    @_public
    def fetchone(self):
        _check(not self._closed)
        return self._rows.pop(0) if self._rows else None

    @_public
    def fetchall(self):
        _check(not self._closed)
        result, self._rows = self._rows, []
        return result

    @_public
    def close(self):
        self._closed, self._rows = True, []


class ReadOnlyPostgresTransport(Offline):
    """BoundPostgresTransport for one independently supplied campaign/policy.

    Explicit open_readonly is the only network entry point. No injected driver,
    environment configuration, DSN, default CA or execution-authority switch.
    """

    @_public
    def __init__(self, campaign, policy):
        v.validate_campaign(campaign)
        _policy(campaign, policy)
        self._campaign, self._policy = campaign, policy

    @_public
    def open_readonly(self, *, host, port, database, role, password, ca_der, timeout, options):
        campaign, policy = self._campaign, self._policy
        _check(type(host) is str and host == campaign.host and type(port) is int and port == campaign.port)
        _check(type(database) is str and database == campaign.database and type(role) is str and role in campaign.roles)
        _check(type(ca_der) is bytes and ca_der == policy.trusted_ca_der)
        _check(type(timeout) in (int, float) and 0 < timeout <= 3 and type(options) is str and options == OPTIONS)
        _check(type(password) is str and 1 <= len(password) <= 4096 and all(33 <= ord(ch) <= 126 for ch in password))
        context = _context(ca_der)  # Parse trust before opening any socket.
        raw, connection = None, None
        deadline = monotonic() + timeout
        try:
            # Numeric campaign IP: no DNS, search domain, multi-host or ambient fallback.
            raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection = _Connection(self, raw, deadline)
            connection._budget()
            raw.connect((campaign.server_address, port))
            _check(raw.getpeername() == (campaign.server_address, port))
            connection._send(struct.pack('!II', 8, 80877103))
            _check(connection._read(1) == b'S')
            connection._budget()
            tls = context.wrap_socket(raw, server_hostname=host, do_handshake_on_connect=False)
            connection._socket = tls  # Transfer ownership before handshake can fail.
            connection._budget()
            tls.do_handshake()
            _check(tls.version() in ('TLSv1.2', 'TLSv1.3'))
            connection._certificate = tls.getpeercert(binary_form=True)
            _check(type(connection._certificate) is bytes and 0 < len(connection._certificate) <= 16384)
            connection._startup(database, role, password)
            # Establish SQL identity on this authenticated socket before returning it.
            rows = connection._query(c.IDENTITY_SQL)
            _check(len(rows) == 1)
            row = rows[0]
            expected = dict(database=database, session_role=role, role=role,
                address=campaign.server_address, port=port, version=str(campaign.server_version_num),
                cluster=campaign.cluster_name, instance=campaign.instance_id,
                read_only='on', default_read_only='on', pid=connection._pid, elevated=False)
            _check(all(type(row.get(key)) is type(value) and row[key] == value for key, value in expected.items()))
            _check('dev_marker' in row and row['dev_marker'] in (None, ''))
            # Collection lifetime bound, including statements and rollback; no deadline reset.
            connection._deadline = min(monotonic() + 7, deadline + 7)
            return connection
        except Exception:
            if connection is not None:
                connection.close()
            elif raw is not None:
                raw.close()
            raise

    @_public
    def tls_binding(self, connection):
        _check(type(connection) is _Connection and connection._owner is self)
        try:
            connection._budget()
            sock = connection._socket
            _check(connection._authenticated and sock.fileno() > 0)
            _check(sock.getpeername() == (self._campaign.server_address, self._campaign.port))
            _check(sock.version() in ('TLSv1.2', 'TLSv1.3'))
            _check(sock.getpeercert(binary_form=True) == connection._certificate)
            return c.TlsBinding(connection, sock.fileno(), True, 'scram-sha-256',
                self._campaign.host, connection._certificate, ())
        except Exception:
            connection.close()
            raise
