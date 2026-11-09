"""Non-network DB-API script double. Data responses only, no callback or driver.

This module cannot open sockets or delegate to psycopg. EXEC-2's only admitted
channel source is this concrete offline pool; a real connector stays disabled.
"""

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace

from psycopg.pq import TransactionStatus as TS

from b2b_postgres_qualification.contracts import Offline


@dataclass(frozen=True, repr=False)
class Response(Offline):
    rows: tuple = ()
    rowcount: int = -1
    sqlstate: str | None = None
    lost_ack: bool = False
    end_status: object = None
    command_tag: str | None = None


class ScriptedError(Exception):
    def __init__(self, sqlstate):
        self.sqlstate = sqlstate
        super().__init__('SYNTHETIC-PRIVATE-DRIVER-DIAGNOSTIC')


class _Socket:
    def __init__(self, handle, certificate):
        self.handle, self.certificate = handle, certificate

    def fileno(self):
        return self.handle

    def getpeercert(self, *, binary_form):
        return self.certificate


class _Cursor:
    def __init__(self, connection):
        self.connection, self.rowcount, self.rows, self.closed = connection, -1, [], False
        self.statusmessage = None

    def execute(self, sql, parameters=None):
        c = self.connection
        if c.closed or self.closed:
            raise ScriptedError(None)
        c.events.append((sql, deepcopy(parameters)))
        key = (sql, parameters)
        # Exact SQL + bound parameter tuple, no matching by prefix or arbitrary callback.
        if key not in c.responses:
            raise ScriptedError('XX000')
        queue = c.responses[key]
        response = queue[0] if len(queue) == 1 else queue.popleft()
        if type(response) is not Response:
            raise ScriptedError('XX000')
        self.rows, self.rowcount = list(deepcopy(response.rows)), response.rowcount
        self.statusmessage = response.command_tag
        if response.end_status is not None:
            c.info.transaction_status = response.end_status
        if response.lost_ack:
            c.broken = True
            raise OSError('SYNTHETIC-PRIVATE-DRIVER-DIAGNOSTIC')
        if response.sqlstate is not None:
            raise ScriptedError(response.sqlstate)

    def fetchmany(self, count):
        rows, self.rows = self.rows[:count], self.rows[count:]
        return rows

    def close(self):
        self.closed = True


class ScriptedConnection(Offline):
    def __init__(self, pid, certificate, verified_host):
        self.autocommit, self.closed, self.broken = True, False, False
        self.info = SimpleNamespace(backend_pid=pid, transaction_status=TS.IDLE)
        self.socket = _Socket(pid, certificate)
        self.verified_host, self.tls_verified, self.auth_method = verified_host, True, 'scram-sha-256'
        self.responses, self.events = {}, []
        self.close_calls, self.close_error = 0, False

    def add(self, sql, parameters=None, *responses):
        self.responses[(sql, parameters)] = deque(responses)

    def cursor(self):
        return _Cursor(self)

    def close(self):
        self.close_calls += 1
        self.closed, self.socket.handle = True, -1
        if self.close_error:
            raise OSError('SYNTHETIC-PRIVATE-DRIVER-DIAGNOSTIC')


class OfflineChannelPool(Offline):
    def __init__(self, connections):
        if type(connections) is not tuple or not all(type(c) is ScriptedConnection for c in connections):
            raise ValueError('OFFLINE_CONNECTIONS_REQUIRED')
        self._connections = deque(connections)

    def open(self):
        if not self._connections:
            raise ScriptedError(None)
        connection = self._connections.popleft()
        if type(connection) is not ScriptedConnection:
            raise ScriptedError(None)
        return connection
