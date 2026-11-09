"""Sealed in-memory backend for EXEC-1 algorithms; NEVER sends SQL to a server.

DDL is recorded, not interpreted or qualified. Socket and TLS facts are doubles.
No generic callback/driver injection. Live adapters are deliberately not accepted.
"""

from copy import deepcopy

from b2b_postgres_qualification import validation as v
from b2b_postgres_qualification.collectors import TlsBinding
from b2b_postgres_qualification.contracts import Offline
from p101_postgres_qualification import plans, scenario


class _Socket:
    def __init__(self, handle, certificate):
        self.handle, self.certificate = handle, certificate

    def fileno(self):
        return self.handle

    def getpeercert(self, *, binary_form):
        return self.certificate


class _Session(Offline):
    def __init__(self, backend, role, readonly, pid):
        self.owner, self.role, self.readonly, self.pid = backend, role, readonly, pid
        self.socket = _Socket(pid, backend.certificate)
        self.closed, self.active = False, False
        self.pending_schema, self.pending_pair = False, ()
        self.seed = []
        self.revisions = []


class SimulatedBackend(Offline):
    def __init__(self, campaign, resources, certificate, catalogue, release, *, installed=False):
        self.campaign, self.resources = campaign, deepcopy(resources)
        self.certificate, self.catalogue_snapshot, self.release = certificate, deepcopy(catalogue), release
        self.installed, self.pair, self.fixture_rows = installed, (), []
        self.events, self.sessions, self.sequences = [], [], {}
        self.identity_changes, self.counts_changes = {}, {}
        self.commit_fault, self.read_fault, self.close_fault = None, False, False
        self.alias_socket, self.alias_pid = False, False
        self.auth_method, self.tls_verified = 'scram-sha-256', True

    def engine_inventory(self):
        return deepcopy(self.resources)

    def open(self, role, readonly):
        session = _Session(self, role, readonly, 100 + len(self.sessions))
        if self.sessions and readonly:
            if self.alias_socket:
                session.socket = self.sessions[0].socket
            if self.alias_pid:
                session.pid = self.sessions[0].pid
        self.sessions.append(session)
        self.events.append(('open', role, readonly))
        return session

    def _own(self, session):
        v.require(type(session) is _Session and session.owner is self and not session.closed)

    def identity(self, session):
        self._own(session)
        c = self.campaign
        return dict(database=c.database, session_role=session.role, role=session.role,
            address=c.server_address, port=c.port, version=str(c.server_version_num),
            cluster=c.cluster_name, instance=c.instance_id, dev_marker=None,
            read_only='on' if session.readonly else 'off', pid=session.pid, elevated=False) | self.identity_changes

    def binding(self, session):
        self._own(session)
        return TlsBinding(session, session.socket.fileno(), self.tls_verified, self.auth_method,
            self.campaign.host, session.socket.getpeercert(binary_form=True), ())

    def socket_object(self, session):
        self._own(session)
        return session.socket

    def begin(self, session):
        self._own(session)
        v.require(not session.active)
        session.active = True
        self.events.append(('begin', session.pid, session.readonly))

    def empty_counts(self, session):
        self._own(session)
        return dict(plans.EMPTY_COUNTS) | ({'relations': 1} if self.installed else {}) | self.counts_changes

    def business_empty(self, session):
        self._own(session)
        return not self.fixture_rows and not self.pair

    def start_migrations(self, session, release):
        self._own(session)
        v.require(session.active and not session.readonly and not self.installed
            and plans.exact_equal(release, self.release))
        self.events.append(('version_create', release.version_create))

    def apply_revision(self, session, revision):
        self._own(session)
        v.require(session.active and not session.readonly)
        index = len(session.revisions)
        v.require(index < 14 and plans.exact_equal(revision, self.release.revisions[index]))
        for sql in revision.statements:
            self.events.append(('ddl', revision.revision, sql))
        self.events.append(('version', revision.revision, self.release.version_steps[index]))
        session.revisions.append(revision.revision)
        session.pending_schema = len(session.revisions) == 14

    def catalogue(self, session):
        self._own(session)
        v.require(self.installed or session.pending_schema)
        value = deepcopy(self.catalogue_snapshot)
        if session.readonly and self.read_fault:
            value['revision'] = 'wrong'
        return value

    def execute(self, session, step):
        self._own(session)
        v.require(session.active and not session.readonly and type(step) is scenario.Statement)
        # Kernel supplies only freshly regenerated seed/pair statements. This
        # backend has no SQL engine: every event is a simulation, never an effect.
        self.events.append(('statement', step.sql, step.parameters))
        if step.returns is not None:
            key = 'measurement' if step.returns.startswith('measurement_') else step.returns
            value = self.sequences.get(key, 0) + 1
            self.sequences[key] = value
            if step.sql.startswith('INSERT INTO public.') and step.returns not in ('operation_id',):
                session.seed.append(step)
            return value
        return None

    def verify_seed(self, session, expected_steps):
        self._own(session)
        v.require(plans.exact_equal(tuple(session.seed), tuple(expected_steps)))

    def stage_pair(self, session, operation, prediction_id, operation_id):
        self._own(session)
        v.require(session.active and not session.readonly and not session.pending_pair and not self.pair)
        session.pending_pair = (scenario._rows(operation, prediction_id, operation_id),)

    def commit(self, session):
        self._own(session)
        v.require(session.active and not session.readonly)
        self.events.append(('commit_attempt', session.pid))
        if self.commit_fault == 'before':
            raise OSError('synthetic lost commit acknowledgement')
        if session.pending_schema:
            self.installed = True
        if session.pending_pair:
            self.pair, self.fixture_rows = deepcopy(session.pending_pair), deepcopy(session.seed)
        session.active = False
        if self.commit_fault == 'after':
            raise OSError('synthetic lost commit acknowledgement')

    def read_pair(self, session, key):
        self._own(session)
        v.require(session.active and session.readonly)
        self.events.append(('independent_read', session.pid, scenario.PAIR_SQL))
        if self.read_fault:
            return ()
        return deepcopy(tuple(pair for pair in self.pair if pair[0]['idempotency_key'] == key))

    def rollback(self, session):
        self._own(session)
        self.events.append(('rollback', session.pid))
        session.active, session.pending_schema, session.pending_pair = False, False, ()

    def close(self, session):
        self._own(session)
        session.closed = True
        session.socket.handle = -1
        self.events.append(('close', session.pid))
        if self.close_fault:
            raise OSError('synthetic close failure')
