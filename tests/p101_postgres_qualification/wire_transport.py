"""P101 extension of INFRA-3: one verified TLS socket, extended-query parameters.

No network at import. Only LiveConnector (armed by the EXEC-1 kernel) opens it.
INFRA-3's published read-only transport and guards are not modified.
"""

from datetime import datetime
import json
import math
import re
import socket
import struct
from time import monotonic
from types import SimpleNamespace

from psycopg.pq import TransactionStatus as TS

from b2b_postgres_qualification import transport as infra, collectors
from b2b_postgres_qualification.contracts import Offline


class WireError(Exception):
    def __init__(self, sqlstate=None):
        self.sqlstate = sqlstate
        super().__init__('P101_WIRE_FAILED')


def fail(code=None):
    # Deliberately called outside except blocks; never preserve server diagnostics.
    raise WireError(code) from None


def encode(value):
    if value is None:
        return struct.pack('!i', -1)
    if type(value) is bool:
        text = 'true' if value else 'false'
    elif type(value) is int:
        text = str(value)
    elif type(value) is float:
        infra._check(math.isfinite(value))
        text = repr(value)
    elif type(value) is datetime:
        text = value.isoformat()
    else:
        infra._check(type(value) is str)
        text = value
    raw = text.encode('utf8')
    infra._check(b'\0' not in raw and len(raw) <= 16384)
    return struct.pack('!i', len(raw)) + raw


def bound(sql, params):
    """Only fixed plan templates use %s, never values interpolated into SQL."""
    infra._check(type(sql) is str and '\0' not in sql and len(sql.encode()) <= 131072)
    if params is None:
        return sql, ()  # Preserve native DDL and PL/pgSQL %ROWTYPE verbatim.
    infra._check(type(params) is tuple and len(params) <= 64)
    parts = sql.split('%s')
    infra._check(len(parts) == len(params) + 1)
    return ''.join(part + (f'${i+1}' if i < len(params) else '') for i, part in enumerate(parts)), params


def description(body):
    infra._check(len(body) >= 2)
    count, offset, columns = struct.unpack('!H', body[:2])[0], 2, []
    infra._check(1 <= count <= 64)
    for _ in range(count):
        end = body.index(b'\0', offset)
        name = body[offset:end].decode('utf8')
        infra._check(name and len(name) <= 128 and end + 19 <= len(body))
        _, _, oid, _, _, fmt = struct.unpack('!IhIhih', body[end+1:end+19])
        infra._check(fmt == 0 and oid in (16, 18, 19, 20, 21, 23, 25, 26, 114, 700, 701, 1043, 1009, 3802))
        columns.append((name, oid))
        offset = end + 19
    infra._check(offset == len(body) and len(set(name for name, _ in columns)) == count)
    return columns


def data_row(body, columns):
    infra._check(len(body) >= 2 and struct.unpack('!H', body[:2])[0] == len(columns))
    result, offset = {}, 2
    for name, oid in columns:
        infra._check(offset + 4 <= len(body))
        size = struct.unpack('!i', body[offset:offset+4])[0]
        offset += 4
        infra._check(size >= -1 and offset + max(size, 0) <= len(body))
        value = None
        if size >= 0:
            value = body[offset:offset+size].decode('utf8')
            offset += size
            if oid == 16:
                infra._check(value in ('t', 'f'))
                value = value == 't'
            elif oid in (20, 21, 23, 26):
                infra._check(re.fullmatch('-?[0-9]+', value) is not None)
                value = int(value)
            elif oid in (700, 701):
                value = float(value)
                infra._check(math.isfinite(value))
            elif oid in (114, 3802):
                value = json.loads(value, object_pairs_hook=collectors._json_object,
                    parse_constant=lambda _: fail())
            elif oid == 1009:
                # The only text[] collected is proconfig; decode through SQL JSON instead.
                fail()
        result[name] = value
    infra._check(offset == len(body))
    return result


def error_code(body):
    infra._check(body.endswith(b'\0'))
    fields, offset = {}, 0
    while offset < len(body)-1:
        key, end = body[offset:offset+1], body.index(b'\0', offset+1)
        infra._check(key not in fields)
        # Discard messages, detail, context, schema, table, source, etc.
        fields[key] = body[offset+1:end] if key == b'C' else None
        offset = end + 1
    infra._check(offset == len(body)-1 and re.fullmatch(b'[0-9A-Z]{5}', fields.get(b'C') or b''))
    return fields[b'C'].decode('ascii')


class WireConnection(infra._Connection):
    def __init__(self, owner, raw, deadline, readonly):
        super().__init__(owner, raw, deadline)
        self.readonly = readonly
        self.autocommit, self.closed, self.broken = True, False, False
        self.info = SimpleNamespace(backend_pid=None, transaction_status=TS.UNKNOWN)
        self.role = None

    @property
    def socket(self):
        return self._socket

    def _startup(self, database, role, password):
        # Reuse INFRA-3's complete SCRAM state machine and signature check unchanged.
        # Its immutable OPTIONS enforces default RO; flip RW only after authentication
        # with the single fixed SET below. No global/module option mutation.
        super()._startup(database, role, password)
        self.info.backend_pid, self.info.transaction_status, self.role = self._pid, TS.IDLE, role
        if not self.readonly:
            self._roundtrip('SET default_transaction_read_only=off', None)

    def cursor(self):
        infra._check(not self.closed and not self.broken)
        return WireCursor(self)

    def _roundtrip(self, sql, params):
        self._owner.binding(self)
        self._owner.authorize(self, sql)
        query, values = bound(sql, params)
        self._packet(b'P', b'\0' + query.encode('utf8') + b'\0' + struct.pack('!H', 0))
        self._packet(b'B', b'\0\0' + struct.pack('!HH', 0, len(values))
            + b''.join(encode(value) for value in values) + struct.pack('!H', 0))
        self._packet(b'D', b'P\0')
        self._packet(b'E', b'\0' + struct.pack('!I', 0))
        self._packet(b'S', b'')
        columns, rows, tag, code, state, total = None, [], None, None, 0, 0
        for _ in range(8192):
            kind, body = self._message()
            total += len(body)
            infra._check(total <= 4194304)
            if kind == b'E':
                infra._check(code is None)
                code = error_code(body)
            elif kind == b'Z':
                infra._check(body in (b'I', b'T', b'E') and (code is not None or state == 4))
                self.info.transaction_status = {b'I': TS.IDLE, b'T': TS.INTRANS, b'E': TS.INERROR}[body]
                if code is not None:
                    return None, None, code
                return rows, tag, None
            elif code is not None:
                fail()  # After ErrorResponse only ReadyForQuery is admitted.
            elif kind == b'N':
                # DDL can emit notices. Validate bounded field format, then discard.
                error_code(body)
            elif kind == b'S':
                parts = body.split(b'\0')
                infra._check(len(parts) == 3 and parts[-1] == b'' and 0 < len(parts[0]) <= 128)
                infra._check(parts[0] != b'client_encoding' or parts[1] == b'UTF8')
            elif state == 0 and kind == b'1' and body == b'':
                state = 1
            elif state == 1 and kind == b'2' and body == b'':
                state = 2
            elif state == 2 and kind in (b'T', b'n'):
                columns = description(body) if kind == b'T' else None
                infra._check(kind != b'n' or body == b'')
                state = 3
            elif state == 3 and kind == b'D' and columns is not None:
                infra._check(len(rows) < 2048)
                rows.append(data_row(body, columns))
            elif state == 3 and kind == b'C':
                infra._check(body.endswith(b'\0') and body.count(b'\0') == 1 and len(body) <= 128)
                tag = body[:-1].decode('ascii')
                infra._check(re.fullmatch('[A-Z][A-Z0-9 ]*', tag) is not None)
                state = 4
            else:
                fail()  # COPY, multiple statements, suspension, async notifications, etc.
        fail()

    def close(self):
        if not self.closed:
            self.closed = self._closed = True
            self._authenticated = False
            self.info.transaction_status = TS.UNKNOWN
            self._socket.close()


class WireCursor(Offline):
    def __init__(self, connection):
        self.connection, self.rows, self.closed = connection, [], False
        self.statusmessage, self.rowcount = None, -1

    def execute(self, sql, params=None):
        infra._check(not self.closed)
        failed, code = False, None
        try:
            rows, tag, code = self.connection._roundtrip(sql, params)
        except Exception:
            failed = True
        if failed:
            self.connection.broken = True
            try:
                self.connection.close()
            except Exception:
                pass
            fail()
        if code is not None:
            fail(code)
        self.rows, self.statusmessage = rows, tag
        self.rowcount = int(tag.rsplit(' ', 1)[1]) if re.fullmatch('(SELECT|UPDATE|DELETE) [0-9]+|INSERT [0-9]+ [0-9]+', tag) else -1

    def fetchmany(self, count):
        infra._check(not self.closed and type(count) is int and 0 <= count <= 2049)
        rows, self.rows = self.rows[:count], self.rows[count:]
        return rows

    def close(self):
        self.closed, self.rows = True, []


class LiveConnector(Offline):
    """No public enable flag: an authenticated lease is checked before every open."""
    def __init__(self, guard, credentials):
        from p101_postgres_qualification.live_authority import LiveGuard
        infra._check(type(guard) is LiveGuard and type(credentials) is dict)
        self.guard, self._credentials = guard, dict(credentials)
        self._armed = False
        from p101_postgres_qualification import sql_backend as db, compiler, plans, scenario, privileges
        c = guard.executor.campaign
        self._reads = frozenset((collectors.IDENTITY_SQL, collectors.REVISION_SQL, privileges.SQL,
            db.TRANSACTION_SQL, db.COLUMNS_SQL, db.INDEXES_SQL, db.SEQUENCES_SQL, db.OWNERS_SQL, db.ACL_SQL, db.RLS_SQL,
            plans.CATALOG_SQL, db.LIVE_FUNCTIONS_SQL, plans.TRIGGERS_SQL, scenario.PAIR_SQL))
        common = (db.BEGIN_RW, *db.SET_TIMEOUTS, 'ROLLBACK', 'COMMIT', 'SET default_transaction_read_only=off')
        if guard.intent.operation == 'migrate':
            release = compiler.compile_release()
            operations = (release.version_create, *release.version_steps,
                *(sql for revision in release.revisions for sql in revision.statements),
                *privileges.grant_plan(c)[1:], plans.EMPTY_SQL)
        else:
            ids = scenario.FixtureIds(1, 2, 3, 4, tuple(range(1, 12)))
            operation = scenario.prepare_operation(c, ids, expected_campaign=c)
            operations = (db.LIVE_LOCK, db.BUSINESS_SQL,
                *(step.sql for step in scenario.seed_plan(c, expected_campaign=c)),
                *(step.sql for step in scenario.pair_plan(c, operation, expected_campaign=c)[1:-1]),
                *(sql.removesuffix(' FOR SHARE') for sql in db.SEED_SELECTS.values()))
        self._writes = frozenset((*common, *operations))

    def authorize(self, connection, sql):
        from p101_postgres_qualification import sql_backend as db
        infra._check(self._armed and type(connection) is WireConnection and connection._owner is self
            and sql in self._reads | (frozenset((db.BEGIN_RO, *db.SET_TIMEOUTS, 'ROLLBACK')) if connection.readonly else self._writes))

    def binding(self, connection):
        infra._check(type(connection) is WireConnection and connection._owner is self)
        connection._budget()
        sock, c = connection.socket, self.guard.executor.campaign
        infra._check(connection._authenticated and sock.fileno() > 0
            and sock.getpeername() == (c.server_address, c.port) and sock.version() in ('TLSv1.2', 'TLSv1.3')
            and sock.getpeercert(binary_form=True) == connection._certificate)
        return collectors.TlsBinding(connection, sock.fileno(), True, 'scram-sha-256', c.host,
            connection._certificate, ())

    def open(self, role, readonly):
        self.guard.check()
        infra._check(self._armed)
        infra._check(self.guard.executor.reservations.inspect(self.guard.intent.campaign_sha256,
            self.guard.intent.operation) == 'uncertain')
        c, policy = self.guard.executor.campaign, self.guard.executor.policy
        expected_role = c.roles[3] if readonly else c.roles[1] if self.guard.intent.operation == 'migrate' else c.database + '_p101_writer'
        infra._check(role == expected_role and type(readonly) is bool)
        password = self._credentials[role]
        infra._check(type(password) is str and 1 <= len(password) <= 4096 and all(33 <= ord(ch) <= 126 for ch in password))
        context = infra._context(policy.trusted_ca_der)
        raw, connection, failed = None, None, False
        try:
            raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection = WireConnection(self, raw, monotonic() + 30, readonly)
            connection._budget()
            raw.connect((c.server_address, c.port))
            infra._check(raw.getpeername() == (c.server_address, c.port))
            connection._send(struct.pack('!II', 8, 80877103))
            infra._check(connection._read(1) == b'S')
            tls = context.wrap_socket(raw, server_hostname=c.host, do_handshake_on_connect=False)
            connection._socket = tls
            connection._budget()
            tls.do_handshake()
            infra._check(tls.version() in ('TLSv1.2', 'TLSv1.3'))
            connection._certificate = tls.getpeercert(binary_form=True)
            infra._check(type(connection._certificate) is bytes and 0 < len(connection._certificate) <= 16384)
            connection._startup(c.database, role, password)
            self.binding(connection)
        except Exception:
            failed = True
        if failed:
            try:
                if connection is not None:
                    connection.close()
                elif raw is not None:
                    raw.close()
            except Exception:
                pass
            fail()
        return connection
