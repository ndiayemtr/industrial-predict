"""Concrete DB-API PostgreSQL commands for the existing EXEC-1 kernel.

There is NO qualified live connector: the only admitted connection implementation
is the non-network script double. This is SQL implementation, not SQL qualification.
"""

from copy import deepcopy
from hashlib import sha256
import re
from uuid import uuid4
from datetime import datetime, timezone

from psycopg.pq import TransactionStatus as TS

from b2b_postgres_qualification import collectors, evidence, validation as v
from b2b_postgres_qualification.contracts import Offline, ExecutionDisabled, Observation, deny
from p101_postgres_qualification import compiler, plans, scenario
from p101_postgres_qualification.offline_dbapi import OfflineChannelPool, ScriptedConnection


BEGIN_RW = 'BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE, READ WRITE'
BEGIN_RO = 'BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'
TRANSACTION_SQL = "SELECT current_setting('transaction_isolation') AS isolation,current_setting('transaction_read_only') AS read_only,pg_backend_pid() AS pid"
SET_TIMEOUTS = ("SET LOCAL statement_timeout='5s'", "SET LOCAL lock_timeout='1s'", "SET LOCAL TIME ZONE 'UTC'")
LOCK_SOURCES = 'LOCK TABLE public.companies,public.sites,public.equipments,public.sensors,public.measurements IN SHARE ROW EXCLUSIVE MODE'
TABLES = ('companies', 'sites', 'equipments', 'sensors', 'measurements', 'maintenance_records',
    'maintenance_recommendations', 'prediction_records', 'p101_prediction_operations')
BUSINESS_SQL = 'SELECT ' + ','.join(f'(SELECT count(*) FROM public.{name}) AS {name}' for name in TABLES)
SEED_SELECTS = {table: f'SELECT row_to_json(t) AS record FROM public.{table} t WHERE id=%s FOR SHARE'
    for table in TABLES[:5]}
COLUMNS_SQL = """SELECT c.relname AS table_name,a.attname AS name,
 format_type(a.atttypid,a.atttypmod) AS type,NOT a.attnotnull AS nullable,
 pg_get_expr(d.adbin,d.adrelid) AS default,a.attidentity AS identity,a.attgenerated AS generated
 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
 JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
 WHERE n.nspname='public' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum"""
INDEXES_SQL = """SELECT t.relname AS table_name,i.relname AS name,x.indisvalid AS valid,
 x.indisready AS ready,pg_get_indexdef(i.oid) AS definition FROM pg_index x
 JOIN pg_class t ON t.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid
 JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' ORDER BY t.relname,i.relname"""
SEQUENCES_SQL = """SELECT c.relname AS name,s.seqstart,s.seqincrement,s.seqmin,s.seqmax,s.seqcache,s.seqcycle
 FROM pg_sequence s JOIN pg_class c ON c.oid=s.seqrelid JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' ORDER BY c.relname"""
OWNERS_SQL = """SELECT c.relname AS name,c.relkind AS kind,pg_get_userbyid(c.relowner) AS owner
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname"""
ACL_SQL = """SELECT 'relation' AS kind,c.relname AS name,COALESCE(c.relacl::text,'') AS acl
 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
 UNION ALL SELECT 'schema',nspname,COALESCE(nspacl::text,'') FROM pg_namespace WHERE nspname='public'
 UNION ALL SELECT 'database',datname,COALESCE(datacl::text,'') FROM pg_database WHERE datname=current_database()
 UNION ALL SELECT 'function',p.proname,COALESCE(p.proacl::text,'') FROM pg_proc p
 JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' ORDER BY kind,name"""


class SqlFailure(Exception):
    def __init__(self, phase, sqlstate=None):
        self.phase, self.sqlstate = phase, sqlstate
        super().__init__('P101_QUALIFICATION_SQL_FAILED')


class CommitUncertain(SqlFailure):
    pass


class CommitRejected(SqlFailure):
    pass


def _fail(kind, phase, sqlstate=None):
    # Called outside the driver's except block: no driver diagnostic/cause survives.
    error = kind(phase, sqlstate)
    error.__cause__ = error.__context__ = None
    error.__suppress_context__ = True
    raise error


class PsycopgBoundConnector(Offline):
    def open(self, *args, **kwargs):
        # psycopg 3.3.4 exposes ssl_in_use/socket, not same-channel peer DER capture.
        # Neither a second TLS probe nor an asserted verification flag fills this gap.
        deny(ExecutionDisabled)


class SqlSession(Offline):
    def __init__(self, owner, connection, role, readonly):
        self.owner, self.raw, self.role, self.readonly = owner, connection, role, readonly
        self.physical, self.socket = connection, connection.socket
        self.pid = connection.info.backend_pid
        self.state, self.closed = 'idle', False
        self.revision_index, self.seed_index, self.body_index = 0, 0, 0
        self.values, self.seed_steps, self.seed_rows = {}, [], []
        self.operation, self.body, self.locked, self.ready = None, (), False, False


class PostgresBackend(Offline):
    @v.guarded
    def __init__(self, campaign, policy, *, expected_campaign, resources, release, operation, connector, clock):
        plans.require_campaign(campaign, expected_campaign)
        evidence._policy(campaign, policy)
        v.require(type(connector) is OfflineChannelPool and callable(clock))
        v.require(operation in ('migrate', 'first-pair') and plans.exact_equal(release, compiler.compile_release()))
        self.campaign, self.policy, self.resources = campaign, policy, deepcopy(resources)
        self.release, self.operation, self.connector, self.clock = release, operation, connector, clock
        self.sessions = []
        self.expected_operation = None

    def engine_inventory(self):
        return deepcopy(self.resources)  # Injected offline inventory, not live Docker evidence.

    def _own(self, session):
        v.require(type(session) is SqlSession and session.owner is self and not session.closed
            and type(session.raw) is ScriptedConnection and session.raw is session.physical
            and session.raw.socket is session.socket and session.pid == session.raw.info.backend_pid)

    def _call(self, session, sql, params=None, *, rows=False, limit=2, affected=None, expected_tag=None):
        self._own(session)
        v.require(not session.raw.closed and not session.raw.broken)
        cursor, failure, result = None, None, []
        try:
            cursor = session.raw.cursor()
            # Native compiled DDL is NEVER run through DB-API '%' interpolation.
            if params is None:
                cursor.execute(sql)
            else:
                cursor.execute(sql, params)
            if expected_tag is not None:
                v.require(cursor.statusmessage == expected_tag)
            if affected is not None:
                v.require(cursor.rowcount == affected)
            if rows:
                result = cursor.fetchmany(limit + 1)
                v.require(type(result) is list and len(result) <= limit and all(type(row) is dict for row in result))
        except Exception as error:
            code = getattr(error, 'sqlstate', None)
            failure = code if type(code) is str and re.fullmatch('[0-9A-Z]{5}', code) else ''
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    failure = ''
        if failure is not None:
            if session.state == 'active':
                session.state = 'failed'
            _fail(SqlFailure, 'statement', failure or None)
        return result

    @v.guarded
    def open(self, role, readonly):
        v.require(type(self.connector) is OfflineChannelPool and type(readonly) is bool)
        allowed = self.campaign.roles[3] if readonly else self.campaign.roles[1 if self.operation == 'migrate' else 2]
        v.require(role == allowed)
        raw = self.connector.open()
        # Reusing the same physical DB-API object is refused before closing or querying it.
        v.require(not any(session.raw is raw for session in self.sessions))
        session = None
        try:
            v.require(type(raw) is ScriptedConnection and raw.autocommit is True and not raw.closed
                and not raw.broken and raw.info.transaction_status == TS.IDLE
                and type(raw.info.backend_pid) is int and raw.info.backend_pid > 0)
            session = SqlSession(self, raw, role, readonly)
            self.sessions.append(session)
            self.binding(session)  # Validate the channel/certificate before SQL metadata.
            return session
        except Exception:
            if session is not None:
                session.closed = True
            raw.close()
            raise

    def binding(self, session):
        self._own(session)
        raw = session.raw
        v.require(raw.tls_verified is True and raw.auth_method == 'scram-sha-256'
            and raw.verified_host == self.campaign.host and raw.socket.fileno() > 0)
        certificate = raw.socket.getpeercert(binary_form=True)
        now = self.clock()
        v.utc(now)
        obs = Observation('tls', self.campaign.campaign_id, v.destination_fingerprint(self.campaign),
            'synthetic', 'exec2-scripted-channel', now, now, str(uuid4()), ())
        packet = evidence.EvidencePacket(obs, tuple(sorted(dict(peer_certificate_sha256=sha256(certificate).hexdigest(),
            chain_verified='true', hostname_verified='true').items())), certificate, ())
        evidence._tls_adapter(self.campaign, self.policy, packet, now)
        return collectors.TlsBinding(session, raw.socket.fileno(), True, raw.auth_method, raw.verified_host, certificate, ())

    def socket_object(self, session):
        self._own(session)
        return session.raw.socket

    def identity(self, session):
        rows = self._call(session, collectors.IDENTITY_SQL, rows=True)
        v.require(len(rows) == 1)
        row = dict(rows[0])
        v.require(row.pop('default_read_only') == ('on' if session.readonly else 'off'))
        v.require(row.get('pid') == session.pid == session.raw.info.backend_pid)
        c = self.campaign
        expected = dict(database=c.database, session_role=session.role, role=session.role,
            address=c.server_address, port=c.port, version=str(c.server_version_num),
            cluster=c.cluster_name, instance=c.instance_id, dev_marker=None,
            read_only='on' if session.readonly else 'off', pid=session.pid, elevated=False)
        v.require(plans.exact_equal(row, expected))
        return row

    def begin(self, session):
        self._own(session)
        v.require(session.state == 'idle' and session.raw.info.transaction_status == TS.IDLE)
        self._call(session, BEGIN_RO if session.readonly else BEGIN_RW)
        session.state = 'active'
        for sql in SET_TIMEOUTS:
            self._call(session, sql)
        rows = self._call(session, TRANSACTION_SQL, rows=True)
        expected = dict(isolation='repeatable read' if session.readonly else 'serializable',
            read_only='on' if session.readonly else 'off', pid=session.pid)
        v.require(plans.exact_equal(rows, [expected]) and session.raw.info.transaction_status == TS.INTRANS)

    def empty_counts(self, session):
        v.require(session.state == 'active' and not session.readonly)
        rows = self._call(session, plans.EMPTY_SQL, rows=True)
        v.require(len(rows) == 1)
        return rows[0]

    def start_migrations(self, session, release):
        v.require(self.operation == 'migrate' and session.state == 'active' and not session.readonly
            and session.revision_index == 0 and plans.exact_equal(release, self.release))
        self._call(session, self.release.version_create)
        session.revision_index = -1

    def apply_revision(self, session, revision):
        index = max(session.revision_index, 0)
        v.require(self.operation == 'migrate' and session.state == 'active' and not session.readonly
            and session.revision_index != 0 and index < 14
            and plans.exact_equal(revision, self.release.revisions[index]))
        for sql in revision.statements:
            self._call(session, sql)
        self._call(session, self.release.version_steps[index], affected=1)
        session.revision_index = index + 1

    def catalogue(self, session):
        revision = self._call(session, collectors.REVISION_SQL, rows=True)
        v.require(len(revision) == 1 and set(revision[0]) == {'version_num'})
        constraints = self._call(session, plans.CATALOG_SQL, rows=True, limit=512)
        functions = self._call(session, plans.FUNCTIONS_SQL, rows=True, limit=128)
        triggers = self._call(session, plans.TRIGGERS_SQL, rows=True, limit=128)
        normalized = dict(revision=revision[0]['version_num'], constraints=[dict(schema=row['schema_name'],
            table=row['relname'], name=row['conname'], type=row['contype'], validated=row['convalidated'],
            deferrable=row['condeferrable'], deferred=row['condeferred'], definition=row['definition']) for row in constraints],
            functions=[dict(name=row['proname'], security_definer=row['prosecdef'],
                search_path=next((value.split('=', 1)[1] for value in (row['proconfig'] or []) if value.startswith('search_path=')), None),
                config=row['proconfig'], definition=row['definition']) for row in functions],
            triggers=[dict(table=row['relname'], name=row['tgname'], enabled=row['tgenabled'],
                deferrable=row['tgdeferrable'], deferred=row['tginitdeferred'], definition=row['definition']) for row in triggers])
        for name, sql in (('columns', COLUMNS_SQL), ('indexes', INDEXES_SQL), ('sequences', SEQUENCES_SQL),
                          ('ownership', OWNERS_SQL), ('acl', ACL_SQL)):
            normalized[name] = self._call(session, sql, rows=True, limit=1024)
        return normalized

    def business_empty(self, session):
        v.require(self.operation == 'first-pair' and session.state == 'active' and not session.readonly)
        self._call(session, LOCK_SOURCES)
        rows = self._call(session, BUSINESS_SQL, rows=True)
        empty = len(rows) == 1 and plans.exact_equal(rows[0], dict.fromkeys(TABLES, 0))
        session.locked = empty
        return empty

    def execute(self, session, step):
        self._own(session)
        v.require(self.operation == 'first-pair' and session.state == 'active' and not session.readonly
            and session.locked and type(step) is scenario.Statement)
        if session.seed_index < 15:
            original = scenario.seed_plan(self.campaign, expected_campaign=self.campaign)[session.seed_index]
        else:
            v.require(session.operation is not None and session.body_index < len(session.body))
            original = session.body[session.body_index]
        params = tuple(session.values[value.name] if type(value) is scenario.Reference else value for value in original.parameters)
        v.require(plans.exact_equal(step, scenario.Statement(original.sql, params, original.returns)))
        result = None
        if step.returns is not None:
            rows = self._call(session, step.sql, step.parameters if step.parameters else None, rows=True, affected=1)
            v.require(len(rows) == 1 and set(rows[0]) == {'id'} and type(rows[0]['id']) is int
                and 0 < rows[0]['id'] <= 2147483647)
            result = rows[0]['id']
            session.values[step.returns] = result
        else:
            self._call(session, step.sql, step.parameters if step.parameters else None,
                affected=1 if step.sql.startswith('INSERT ') else None)
        if session.seed_index < 15:
            session.seed_index += 1
            session.seed_steps.append(step)
            session.seed_rows.append((result, step))
        else:
            session.body_index += 1
        return result

    def verify_seed(self, session, expected_steps):
        v.require(session.state == 'active' and session.seed_index == 15
            and plans.exact_equal(tuple(session.seed_steps), tuple(expected_steps)))
        for identifier, step in session.seed_rows:
            table = step.sql.split('public.', 1)[1].split(' ', 1)[0]
            columns = step.sql.split('(', 1)[1].split(')', 1)[0].split(',')
            expected = dict(zip(columns, step.parameters)) | {'id': identifier}
            rows = self._call(session, SEED_SELECTS[table], (identifier,), rows=True)
            v.require(len(rows) == 1 and set(rows[0]) == {'record'} and type(rows[0]['record']) is dict)
            actual = deepcopy(rows[0]['record'])
            for name, value in expected.items():
                if type(value) is datetime:
                    v.require(type(actual.get(name)) is str)
                    parsed = datetime.fromisoformat(actual[name].replace('Z', '+00:00'))
                    v.require((parsed.tzinfo is None) == (value.tzinfo is None))
                    actual[name] = parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else parsed
                elif name == 'value':
                    v.require(type(actual.get(name)) in (int, float) and type(value) in (int, float))
                    actual[name], expected[name] = float(actual[name]), float(value)
            v.require(plans.exact_equal(actual, expected))
        values = session.values
        ids = scenario.FixtureIds(values['company'], values['site'], values['equipment'], values['sensor'],
            tuple(values[f'measurement_{index}'] for index in range(11)))
        session.operation = scenario.prepare_operation(self.campaign, ids, expected_campaign=self.campaign)
        session.body = scenario.pair_plan(self.campaign, session.operation, expected_campaign=self.campaign)[1:-1]

    def stage_pair(self, session, operation, prediction_id, operation_id):
        v.require(session.state == 'active' and not session.readonly and session.body_index == len(session.body)
            and plans.exact_equal(operation, session.operation)
            and session.values.get('prediction_id') == prediction_id and session.values.get('operation_id') == operation_id)
        actual = self._pair(session, operation.key)
        v.require(plans.exact_equal(actual, (scenario._rows(operation, prediction_id, operation_id),)))
        session.ready = True  # Never fabricate persisted rows as SimulatedBackend does.
        self.expected_operation = operation

    def _pair(self, session, key):
        v.digest(key)
        raw = self._call(session, scenario.PAIR_SQL, (key,), rows=True)
        return scenario.normalize_pair_observation(raw)

    def read_pair(self, session, key):
        v.require(session.readonly and session.state == 'active' and self.expected_operation is not None
            and key == self.expected_operation.key)
        return self._pair(session, key)

    def verify_observer(self, writer, reader, operation):
        return QualificationObserver(self).verify(writer, reader, operation)

    def commit(self, session):
        self._own(session)
        v.require(not session.readonly and session.state == 'active' and session.raw.info.transaction_status == TS.INTRANS
            and (session.revision_index == 14 if self.operation == 'migrate' else session.ready))
        session.state = 'committing'  # Set BEFORE the one and only send.
        failure = None
        try:
            self._call(session, 'COMMIT', expected_tag='COMMIT')
        except SqlFailure as error:
            failure = error.sqlstate or ''
        if failure is not None:
            rejected = failure[:2] in ('23', '40') and not session.raw.broken and session.raw.info.transaction_status == TS.IDLE
            session.state = 'rolled_back' if rejected else 'uncertain'
            _fail(CommitRejected if rejected else CommitUncertain, 'commit', failure or None)
        if session.raw.info.transaction_status != TS.IDLE:
            session.state = 'uncertain'
            _fail(CommitUncertain, 'commit')
        session.state = 'committed'

    def rollback(self, session):
        self._own(session)
        v.require(session.state in ('active', 'failed') and not session.raw.broken)
        self._call(session, 'ROLLBACK', expected_tag='ROLLBACK')
        v.require(session.raw.info.transaction_status == TS.IDLE)
        session.state = 'rolled_back'

    def close(self, session):
        v.require(type(session) is SqlSession and session.owner is self)
        if session.closed:
            return
        session.closed = True  # Never retry a descriptor whose close is ambiguous.
        failed = False
        try:
            session.raw.close()
        except Exception:
            failed = True
        if failed:
            _fail(SqlFailure, 'close')


class QualificationObserver(Offline):
    def __init__(self, backend):
        v.require(type(backend) is PostgresBackend)
        self.backend = backend

    @v.guarded
    def verify(self, writer, reader, operation):
        backend = self.backend
        backend._own(writer)
        backend._own(reader)
        v.require(writer.state == 'committed' and reader.state == 'active' and reader.readonly
            and writer.raw is not reader.raw and writer.socket is not reader.socket
            and writer.socket.fileno() != reader.socket.fileno())
        backend.binding(writer)
        backend.binding(reader)
        v.require(backend.identity(writer)['pid'] != backend.identity(reader)['pid']
            and plans.exact_equal(operation, backend.expected_operation))
        rows = backend.read_pair(reader, operation.key)
        v.require(plans.exact_equal(rows, (scenario._rows(operation,
            writer.values['prediction_id'], writer.values['operation_id']),)))
        return scenario.review_pair(backend.campaign, operation, expected_campaign=backend.campaign,
            writer_connection_id=str(uuid4()), reader_connection_id=str(uuid4()),
            rows=rows)
