"""EXEC-1 kernel reused by EXEC-2's concrete SQL commands on sealed doubles.

Compilation, crypto authorization, replay files and transaction algorithms are
implemented. REAL-1 prepares execute_approved, but LiveGuard refuses real execution
until authenticated Docker collection provenance is available. run_live still
refuses before touching supplied objects. No default network.
"""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic
from uuid import uuid4

from b2b_postgres_qualification import validation as v, evidence
from b2b_postgres_qualification.contracts import Offline, ExecutionDisabled, Observation, deny
from b2b_postgres_qualification.collectors import TlsBinding
from p101_postgres_qualification import compiler, plans, scenario, runner
from p101_postgres_qualification.execution_authority import Intent, ReplayReservations, verify_signature
from p101_postgres_qualification.simulated_backend import SimulatedBackend
from p101_postgres_qualification.sql_backend import PostgresBackend, CommitRejected
from p101_postgres_qualification.wire_transport import LiveConnector


EXECUTION_SOURCES = tuple('tests/p101_postgres_qualification/' + name for name in
    ('compiler.py', 'execution_authority.py', 'simulated_backend.py', 'execution.py',
     'sql_backend.py', 'offline_dbapi.py', 'wire_transport.py', 'live_authority.py',
     'privileges.py', 'resources.py', 'operator.py')) + (
    'tests/b2b_postgres_qualification/authority.py', 'tests/b2b_postgres_qualification/durable.py',
    'infra/p101-qualification-runner/exec1-dependencies.json',
    'infra/p101-qualification-runner/exec2-dependencies.json',
    'infra/p101-qualification-runner/real1-dependencies.json')


def resource_inventory(campaign, policy, *, runner_image_id, registry=None):
    """Expected normalized inventory, not Docker discovery or approval."""
    v.validate_campaign(campaign)
    evidence._policy(campaign, policy)
    v.digest(runner_image_id)
    result = dict(context=policy.context_name, endpoint_sha256=policy.endpoint_sha256,
        engine_id=campaign.engine_id, postgres_id=campaign.container_id, runner_id=campaign.runner_id,
        postgres_image_id=policy.image_id_sha256, postgres_repo_digest=campaign.image_sha256,
        runner_image_id=runner_image_id, network_id=campaign.network_id, network=campaign.network_name,
        subnet=campaign.subnet, address=campaign.server_address, internal=True, driver='bridge',
        members=sorted((campaign.container_id, campaign.runner_id)), ports=[],
        volume=campaign.volume_name, volume_created_at=policy.volume_created_at.isoformat(),
        privileged=False, readonly_roots=True, restart='no', extra_mounts=[],
        postgres_memory=1073741824, runner_memory=536870912, nano_cpus=1000000000)
    if registry is not None:
        v.require(type(registry) is dict and set(registry) == {'volume', 'created_at', 'mount_target'})
        from datetime import datetime
        created = datetime.fromisoformat(registry['created_at'])
        v.utc(created)
        v.require(registry['volume'] == campaign.database + '_exec_registry'
            and registry['mount_target'] == '/var/lib/p101-qualification'
            and registry['volume'] != campaign.volume_name)
        result['registry'] = deepcopy(registry)
        result['extra_mounts'] = [dict(type='volume', name=registry['volume'], destination=registry['mount_target'], rw=True)]
    return result


def _program_digest():
    entries = runner.source_manifest()
    for name in EXECUTION_SOURCES:
        path = runner.ROOT / name
        v.require(path.resolve() == path and not path.is_symlink())
        source = path.read_text(encoding='utf-8').replace('\r\n', '\n').encode('utf-8')
        entries.append(dict(path=name, sha256=sha256(source).hexdigest()))
    return plans.fingerprint(entries)


@dataclass(frozen=True, slots=True, repr=False)
class ExecutionReport(Offline):
    operation: str
    status: str
    commit_status: str
    evidence_sha256: str
    cleanup_failed: bool
    recording_failed: bool
    operation_key: str | None = None


class CampaignExecutor(Offline):
    @v.guarded
    def __init__(self, campaign, policy, *, expected_campaign, resources, trusted_keys,
                 reservations, catalogue_sha256, clock):
        plans.require_campaign(campaign, expected_campaign)
        evidence._policy(campaign, policy)
        v.require(type(reservations) is ReplayReservations and callable(clock))
        v.require(type(resources) is dict and resources.get('engine_id') == campaign.engine_id)
        v.require(plans.exact_equal(resources, resource_inventory(campaign, policy,
            runner_image_id=resources.get('runner_image_id'), registry=resources.get('registry'))))
        v.digest(catalogue_sha256)
        self.campaign, self.policy = campaign, policy
        self.resources, self.keys = deepcopy(resources), trusted_keys
        self.reservations, self.catalogue_sha256, self.clock = reservations, catalogue_sha256, clock

    def _empty_identity(self):
        c = self.campaign
        return dict(database=c.database, host=c.host, address=c.server_address, port=c.port,
            cluster=c.cluster_name, instance=c.instance_id, version=c.server_version_num,
            role=c.roles[1], dev_marker=None, sslmode='verify-full', ca_sha256=c.ca_sha256)

    @v.guarded
    def expected_bindings(self, operation):
        v.require(operation in ('migrate', 'first-pair'))
        release = compiler.compile_release()
        if operation == 'migrate':
            initial = plans.review_empty_declaration(self.campaign, expected_campaign=self.campaign,
                identity=self._empty_identity(), counts=dict(plans.EMPTY_COUNTS), revision=None)
        else:
            initial = plans.fingerprint(dict(catalogue=self.catalogue_sha256, business_empty=True))
        return dict(operation=operation, campaign_sha256=v.destination_fingerprint(self.campaign),
            resources_sha256=plans.fingerprint(self.resources),
            content_sha256=plans.fingerprint(dict(program=_program_digest(), release=release.sha256,
                fixture=scenario.FIXTURE_SHA256, operation=operation)),
            initial_state_sha256=initial, catalogue_sha256=self.catalogue_sha256)

    def _identity(self, backend, session, role, readonly):
        now = self.clock()
        v.utc(now)
        binding = backend.binding(session)
        v.require(type(binding) is TlsBinding and binding.connection is session
            and binding.driver_verified is True and binding.auth_method == 'scram-sha-256'
            and binding.verified_host == self.campaign.host and binding.socket_id > 0)
        socket = backend.socket_object(session)
        v.require(socket.fileno() == binding.socket_id
            and socket.getpeercert(binary_form=True) == binding.certificate_der)
        row = backend.identity(session)
        c = self.campaign
        expected = dict(database=c.database, session_role=role, role=role, address=c.server_address,
            port=c.port, version=str(c.server_version_num), cluster=c.cluster_name, instance=c.instance_id,
            dev_marker=None, read_only='on' if readonly else 'off', pid=session.pid, elevated=False)
        v.require(plans.exact_equal(row, expected))
        obs = Observation('tls', c.campaign_id, v.destination_fingerprint(c), 'synthetic',
            'exec1-simulation', now, now, str(uuid4()), ())
        packet = evidence.EvidencePacket(obs, tuple(sorted(dict(
            peer_certificate_sha256=sha256(binding.certificate_der).hexdigest(),
            chain_verified='true', hostname_verified='true').items())),
            binding.certificate_der, binding.intermediates_der)
        evidence._tls_adapter(c, self.policy, packet, now)
        return binding, row

    @v.guarded
    def run_simulated(self, backend, intent, signature):
        # No callback/protocol object can smuggle a live SQL sink into this API.
        v.require(type(backend) in (SimulatedBackend, PostgresBackend) and type(intent) is Intent)
        v.require(type(backend) is SimulatedBackend or backend.live is False)
        return self._execute(backend, intent, signature, live=False)

    @v.guarded
    def execute_approved(self, guard, *, credentials):
        """Explicit REAL-1 entry. No bool/DSN can replace the two signed envelopes."""
        from p101_postgres_qualification.live_authority import LiveGuard
        v.require(type(guard) is LiveGuard and guard.executor is self)
        guard.check()
        connector = LiveConnector(guard, credentials)
        backend = PostgresBackend(self.campaign, self.policy, expected_campaign=self.campaign,
            resources=self.resources, release=compiler.compile_release(), operation=guard.intent.operation,
            connector=connector, clock=self.clock)
        # _execute verifies approval and reserves before arming/opening any socket.
        return self._execute(backend, guard.intent, guard.signature, live=True)

    def _execute(self, backend, intent, signature, *, live):
        expected = self.expected_bindings(intent.operation)
        envelope = verify_signature(intent, signature, trusted_keys=self.keys,
            now=self.clock(), expected=expected)
        if not live:
            v.require(plans.exact_equal(backend.engine_inventory(), self.resources))
        v.require(plans.exact_equal(backend.campaign, self.campaign))
        release = compiler.compile_release()
        v.require(plans.exact_equal(release, backend.release))
        # The claim is immutable and precedes ALL SQL/session actions, not only COMMIT.
        self.reservations.reserve(intent, envelope_sha256=envelope)
        if live:
            backend.connector._armed = True
        writer, reader, commit_status = None, None, 'not_attempted'
        status, cleanup_failed, recording_failed = 'refused', False, False
        operation, transaction_started = None, False
        deadline = monotonic() + 30
        role = backend.writer_role if type(backend) is PostgresBackend else self.campaign.roles[1 if intent.operation == 'migrate' else 2]
        try:
            writer = backend.open(role, False)
            self._identity(backend, writer, role, False)
            backend.begin(writer)
            transaction_started = True
            if intent.operation == 'migrate':
                actual = plans.review_empty_declaration(self.campaign, expected_campaign=self.campaign,
                    identity=self._empty_identity(), counts=backend.empty_counts(writer), revision=None)
                v.require(actual == intent.initial_state_sha256)
                backend.start_migrations(writer, release)
                for revision in release.revisions:
                    v.require(monotonic() < deadline)
                    backend.apply_revision(writer, revision)
                if live:
                    backend.install_profiles(writer)
                plans.review_catalogue_declaration(backend.catalogue(writer), expected_sha256=self.catalogue_sha256)
            else:
                plans.review_catalogue_declaration(backend.catalogue(writer), expected_sha256=self.catalogue_sha256)
                v.require(backend.business_empty(writer))
                values, resolved_seed = {}, []
                for step in scenario.seed_plan(self.campaign, expected_campaign=self.campaign):
                    params = tuple(values[value.name] if type(value) is scenario.Reference else value for value in step.parameters)
                    resolved = scenario.Statement(step.sql, params, step.returns)
                    value = backend.execute(writer, resolved)
                    v.require(type(value) is int and 0 < value <= 2147483647)
                    values[step.returns] = value
                    resolved_seed.append(resolved)
                backend.verify_seed(writer, resolved_seed)
                ids = scenario.FixtureIds(values['company'], values['site'], values['equipment'], values['sensor'],
                    tuple(values[f'measurement_{index}'] for index in range(11)))
                operation = scenario.prepare_operation(self.campaign, ids, expected_campaign=self.campaign)
                steps = scenario.pair_plan(self.campaign, operation, expected_campaign=self.campaign)
                # Outer transaction already owns BEGIN/COMMIT; execute only its body.
                for step in steps[1:-1]:
                    v.require(monotonic() < deadline)
                    params = tuple(values[value.name] if type(value) is scenario.Reference else value for value in step.parameters)
                    value = backend.execute(writer, scenario.Statement(step.sql, params, step.returns))
                    if step.returns is not None:
                        v.require(type(value) is int and 0 < value <= 2147483647)
                        values[step.returns] = value
                backend.stage_pair(writer, operation, values['prediction_id'], values['operation_id'])
            # Recheck trust window and SQL identity before commit. The configured
            # resource object is not a Docker observation and is never compared as
            # proof for the live path; LiveGuard remains fail-closed without an
            # authenticated collector.
            verify_signature(intent, signature, trusted_keys=self.keys, now=self.clock(), expected=expected)
            self._identity(backend, writer, role, False)
            if live:
                backend.connector.guard.check()
            else:
                v.require(plans.exact_equal(backend.engine_inventory(), self.resources))
            v.require(monotonic() < deadline)
            commit_status = 'uncertain'  # BEFORE sending COMMIT; no rollback can resolve lost ACK.
            backend.commit(writer)
            commit_status = 'confirmed'
            reader = backend.open(self.campaign.roles[3], True)
            _, writer_identity = self._identity(backend, writer, role, False)
            _, reader_identity = self._identity(backend, reader, self.campaign.roles[3], True)
            v.require(reader is not writer and backend.socket_object(reader) is not backend.socket_object(writer)
                and writer_identity['pid'] != reader_identity['pid']
                and backend.socket_object(reader).fileno() != backend.socket_object(writer).fileno())
            backend.begin(reader)
            if operation is None:
                plans.review_catalogue_declaration(backend.catalogue(reader), expected_sha256=self.catalogue_sha256)
            elif type(backend) is PostgresBackend:
                backend.verify_observer(writer, reader, operation)
            else:
                scenario.review_pair(self.campaign, operation, expected_campaign=self.campaign,
                    writer_connection_id=str(uuid4()), reader_connection_id=str(uuid4()),
                    rows=backend.read_pair(reader, operation.key))
            self._identity(backend, reader, self.campaign.roles[3], True)
            backend.rollback(reader)
            status = 'simulated_commit_confirmed'
        except Exception as error:
            if type(error) is CommitRejected and commit_status == 'uncertain':
                commit_status, status = 'rejected', 'simulated_rollback_confirmed'
            elif commit_status == 'uncertain':
                status = 'uncertain'
            elif commit_status == 'confirmed':
                status = 'simulated_commit_verification_failed'
            elif writer is not None and transaction_started:
                try:
                    backend.rollback(writer)
                    status = 'simulated_rollback_confirmed'
                except Exception:
                    status = 'uncertain'
        finally:
            for session in (reader, writer):
                if session is not None:
                    try:
                        backend.close(session)
                    except Exception:
                        cleanup_failed = True
        if live:
            backend.connector._armed = False
            backend.connector._credentials.clear()
            status = status.removeprefix('simulated_')
        digest = plans.fingerprint(dict(operation=intent.operation, campaign=expected['campaign_sha256'],
            envelope=envelope, status=status, commit_status=commit_status, cleanup_failed=cleanup_failed,
            operation_key=operation.key if operation is not None else None, mode='live' if live else 'simulation'))
        try:
            self.reservations.finish(intent, envelope_sha256=envelope, status=status, evidence_sha256=digest)
        except Exception:
            recording_failed = True  # Retained claim still blocks every new attempt.
        return ExecutionReport(intent.operation, status, commit_status, digest, cleanup_failed, recording_failed,
            operation.key if operation is not None else None)

    def run_live(self, *args, **kwargs):
        # Legacy/default entry remains closed. REAL-1 uses execute_approved only.
        deny(ExecutionDisabled)
