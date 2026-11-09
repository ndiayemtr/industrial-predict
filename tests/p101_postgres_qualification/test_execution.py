"""One EXEC-1 offline campaign; no server, network, Docker or revision execution."""

from dataclasses import replace
import ast
from datetime import timedelta
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app import general_migrations as general
from b2b_postgres_qualification.authority import TrustedKey
from b2b_postgres_qualification.contracts import Rejected, ExecutionDisabled
from b2b_postgres_qualification.test_authority_evidence import NOW, certificates, campaign, policy, base_campaign
from p101_postgres_qualification import compiler, execution as ex, execution_authority as auth, plans
from p101_postgres_qualification.simulated_backend import SimulatedBackend
from p101_postgres_qualification.test_runner import catalogue


@pytest.fixture(scope='module', autouse=True)
def no_live_operations():
    def forbidden(*args, **kwargs):
        raise AssertionError('No real I/O or migration execution permitted')
    with pytest.MonkeyPatch.context() as monkeypatch:
        for name in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection',
                     'socket.getaddrinfo', 'subprocess.run', 'subprocess.Popen', 'os.system',
                     'psycopg.connect', 'psycopg.Connection.connect', 'sqlalchemy.create_engine',
                     'sqlalchemy.engine.Engine.connect', 'alembic.command.upgrade',
                     'alembic.command.stamp', 'alembic.command.downgrade'):
            monkeypatch.setattr(name, forbidden)
        yield


@pytest.fixture(scope='module')
def release():
    return compiler.compile_release()


@pytest.fixture
def case(campaign, policy, certificates, release, tmp_path):
    root = tmp_path / 'p101q-exec-reservations'
    root.mkdir()
    reservations = auth.ReplayReservations(root)
    private = Ed25519PrivateKey.generate()
    key = TrustedKey('test-authority', 'test-key', private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw),
        NOW - timedelta(days=1), NOW + timedelta(days=1), False)
    resources = ex.resource_inventory(campaign, policy, runner_image_id='3' * 64)
    cat = catalogue()
    executor = ex.CampaignExecutor(campaign, policy, expected_campaign=campaign, resources=resources,
        trusted_keys=(key,), reservations=reservations, catalogue_sha256=plans.fingerprint(cat), clock=lambda: NOW)
    backend = SimulatedBackend(campaign, resources, certificates[1](campaign.host), cat, release)
    return SimpleNamespace(executor=executor, backend=backend, private=private, key=key,
        root=root, campaign=campaign, policy=policy, reservations=reservations)


def signed(case, operation='migrate', **changes):
    values = dict(authority_id='test-authority', key_id='test-key', approval_id=str(uuid4()),
        issued_at=NOW - timedelta(seconds=1), expires_at=NOW + timedelta(minutes=5))
    values.update(case.executor.expected_bindings(operation))
    values.update(changes)
    intent = auth.Intent(**values)
    return intent, case.private.sign(auth.signing_bytes(intent))


def test_compiler_renders_only_fourteen_exact_revisions_and_version_tracking(release):
    assert len(release.revisions) == len(release.version_steps) == 14
    assert tuple(r.revision for r in release.revisions) == tuple(p.revision for p in plans.PUBLICATIONS)
    assert tuple(r.source_sha256 for r in release.revisions) == tuple(p.sha256 for p in plans.PUBLICATIONS)
    assert 'public.alembic_version' in release.version_create
    assert 'INSERT INTO public.alembic_version' in release.version_steps[0]
    assert 'UPDATE public.alembic_version' in release.version_steps[-1]
    sql = '\n'.join(release.revisions[-1].statements)
    for name in (*plans.P101_CONSTRAINTS, *plans.P101_FUNCTIONS, *plans.P101_TRIGGERS):
        assert name in sql
    assert sql.count('DEFERRABLE INITIALLY DEFERRED') >= 3
    assert sql.count('CREATE FUNCTION') == 3 and len(release.sha256) == 64
    assert not release.execution_authorized and not release.real_attested


def test_compiler_preserves_approved_p101_literal_sql_without_dbapi_escaping(release):
    # Independent source comparison: a simulated DDL recorder cannot detect a
    # pyformat '%%ROWTYPE' corruption or an altered function/trigger body.
    source = (general.BACKEND / plans.P101.path).read_text(encoding='utf-8')
    tree = ast.parse(source)
    upgrade = next(node for node in tree.body if type(node) is ast.FunctionDef and node.name == 'upgrade')
    literals = [ast.literal_eval(node.value.args[0]) for node in upgrade.body
        if type(node) is ast.Expr and type(node.value) is ast.Call
        and type(node.value.func) is ast.Attribute and type(node.value.func.value) is ast.Name
        and node.value.func.value.id == 'op' and node.value.func.attr == 'execute']
    rendered = release.revisions[-1].statements
    assert len(literals) == 7  # Three functions and four triggers, individually preserved.
    for literal in literals:
        assert literal.strip() + ';' in rendered
    validate = next(sql for sql in rendered if sql.startswith('CREATE FUNCTION public.p101_operation_validate'))
    assert 'public.prediction_records%ROWTYPE' in validate
    assert '%%ROWTYPE' not in validate


@pytest.mark.parametrize('body', ["__import__('os').system('no')", "op.get_bind().execute('no')",
    "op.execute(__import__('os').getcwd())", "op.execute('no', **{})", "op.commit()"])
def test_decoder_never_executes_arbitrary_python(body):
    with pytest.raises((Rejected, ValueError)):
        compiler._decode_upgrade('def upgrade():\n    ' + body)


def test_source_alteration_refused_before_any_session(case, monkeypatch):
    original = general._read
    def altered(path):
        text = original(path)
        return text + '\n# changed\n' if path.name == 'p101_0001_operations.py' else text
    monkeypatch.setattr(general, '_read', altered)
    with pytest.raises(Rejected): compiler.compile_release()
    assert not case.backend.sessions


def test_unknown_revision_is_not_discovered_or_compiled(monkeypatch):
    snapshot = general.inspect_sources()
    unknown = general.RevisionDescription('unknown', 'p101_0001_operations', 'unapproved.py')
    monkeypatch.setattr(general, 'inspect_sources', lambda: replace(snapshot, revisions=(*snapshot.revisions, unknown)))
    with pytest.raises(Rejected): compiler.compile_release()


def test_backend_cannot_reorder_the_approved_release(case):
    intent, signature = signed(case)
    case.backend.release = replace(case.backend.release, revisions=tuple(reversed(case.backend.release.revisions)))
    with pytest.raises(Rejected): case.executor.run_simulated(case.backend, intent, signature)
    assert not case.backend.events


def test_migration_kernel_owns_one_transaction_and_verifies_after_ack(case, release):
    intent, signature = signed(case)
    result = case.executor.run_simulated(case.backend, intent, signature)
    assert result.status == 'simulated_commit_confirmed' and result.commit_status == 'confirmed'
    assert not result.real_attested and not result.execution_authorized
    assert not result.cleanup_failed and not result.recording_failed
    events = case.backend.events
    assert [event[1] for event in events if event[0] == 'version'] == [r.revision for r in release.revisions]
    assert sum(event[0] == 'commit_attempt' for event in events) == 1
    assert len(case.backend.sessions) == 2 and all(s.closed for s in case.backend.sessions)
    assert case.backend.sessions[0].pid != case.backend.sessions[1].pid
    assert case.backend.installed
    assert auth.ReplayReservations(case.root).inspect(intent.campaign_sha256, 'migrate') == result.status


def test_atomic_seed_pair_and_independent_read_execute_real_algorithm_on_double(case):
    case.backend.installed = True
    intent, signature = signed(case, 'first-pair')
    result = case.executor.run_simulated(case.backend, intent, signature)
    assert result.status == 'simulated_commit_confirmed', result.status
    assert result.commit_status == 'confirmed' and not result.recording_failed
    assert len(case.backend.fixture_rows) == 15 and len(case.backend.pair) == 1
    journal, prediction = case.backend.pair[0]
    assert journal['id'] == prediction['p101_operation_id']
    assert journal['prediction_id'] == prediction['id']
    assert sha256(journal['result_details_json'].encode()).hexdigest() == journal['result_sha256']
    statements = [event[1] for event in case.backend.events if event[0] == 'statement']
    journal_index = next(i for i, sql in enumerate(statements) if sql.startswith('INSERT INTO public.p101_prediction_operations'))
    prediction_index = next(i for i, sql in enumerate(statements) if sql.startswith('INSERT INTO public.prediction_records'))
    assert journal_index < prediction_index
    assert sum(event[0] == 'commit_attempt' for event in case.backend.events) == 1
    assert sum(event[0] == 'independent_read' for event in case.backend.events) == 1
    assert not any(sql.startswith(('UPDATE ', 'DELETE ')) for sql in statements)


@pytest.mark.parametrize('field,value', [('campaign_sha256', 'f' * 64), ('resources_sha256', 'e' * 64),
    ('content_sha256', 'd' * 64), ('initial_state_sha256', 'c' * 64), ('catalogue_sha256', 'b' * 64)])
def test_signed_but_unbound_intention_is_not_authorized(case, field, value):
    intent, signature = signed(case, **{field: value})
    with pytest.raises(Rejected): case.executor.run_simulated(case.backend, intent, signature)
    assert not case.backend.events


@pytest.mark.parametrize('fault', ['invalid_signature', 'unknown_key', 'revoked', 'expired'])
def test_real_crypto_authorization_refusals(case, fault):
    intent, signature = signed(case)
    if fault == 'invalid_signature': signature = b'x' * 64
    if fault == 'unknown_key':
        intent, signature = signed(case, key_id='unknown-key')
    if fault == 'revoked': case.executor.keys = (replace(case.key, revoked=True),)
    if fault == 'expired':
        intent, signature = signed(case, issued_at=NOW-timedelta(minutes=2), expires_at=NOW-timedelta(minutes=1))
    with pytest.raises(Rejected): case.executor.run_simulated(case.backend, intent, signature)
    assert not case.backend.events


@pytest.mark.parametrize('change', [dict(database='industrial_predict_dev'), dict(host='localhost'),
    dict(instance_id='fb3284bd-fb7b-4c22-b620-96a1564b1d0c'), dict(subnet='172.30.91.0/28'),
    dict(instance_id='77777777-7777-4777-8777-777777777777')])
def test_forbidden_and_unknown_campaigns(case, change):
    unknown = replace(case.campaign, **change)
    with pytest.raises(Rejected):
        ex.CampaignExecutor(unknown, case.policy, expected_campaign=case.campaign,
            resources=case.executor.resources, trusted_keys=(case.key,), reservations=case.reservations,
            catalogue_sha256=case.executor.catalogue_sha256, clock=lambda: NOW)


def test_engine_identity_refused_before_session_or_mutation(case):
    intent, signature = signed(case)
    case.backend.resources['engine_id'] = 'different-engine'
    with pytest.raises(Rejected): case.executor.run_simulated(case.backend, intent, signature)
    assert not case.backend.events
    assert case.reservations.inspect(intent.campaign_sha256, intent.operation) == 'absent'


@pytest.mark.parametrize('field,value', [('database', 'industrial_predict_dev'), ('address', '127.0.0.1'),
    ('instance', 'wrong'), ('role', 'postgres'), ('elevated', True), ('cluster', 'wrong')])
def test_sql_identity_mismatch_never_reaches_ddl_or_commit(case, field, value):
    intent, signature = signed(case)
    case.backend.identity_changes[field] = value
    report = case.executor.run_simulated(case.backend, intent, signature)
    assert report.commit_status == 'not_attempted'
    assert not any(event[0] in ('ddl', 'commit_attempt') for event in case.backend.events)
    assert all(session.closed for session in case.backend.sessions)


def test_nonempty_database_refused_without_cleanup_ddl(case):
    intent, signature = signed(case)
    case.backend.counts_changes['relations'] = 1
    report = case.executor.run_simulated(case.backend, intent, signature)
    assert report.status == 'simulated_rollback_confirmed' and report.commit_status == 'not_attempted'
    assert not any(event[0] == 'ddl' for event in case.backend.events)


@pytest.mark.parametrize('fault', ['auth', 'unverified', 'wrong_host'])
def test_tls_and_authentication_refusals_precede_begin(case, certificates, fault):
    intent, signature = signed(case)
    if fault == 'auth': case.backend.auth_method = 'trust'
    if fault == 'unverified': case.backend.tls_verified = False
    if fault == 'wrong_host': case.backend.certificate = certificates[1]('wrong.invalid')
    report = case.executor.run_simulated(case.backend, intent, signature)
    assert report.status == 'refused' and report.commit_status == 'not_attempted'
    assert not any(event[0] in ('begin', 'rollback', 'ddl', 'commit_attempt') for event in case.backend.events)
    assert all(session.closed for session in case.backend.sessions)


def test_existing_fixture_rows_are_not_adopted_or_loaded(case):
    case.backend.installed = True
    case.backend.fixture_rows = ['unapproved existing rows']
    intent, signature = signed(case, 'first-pair')
    report = case.executor.run_simulated(case.backend, intent, signature)
    assert report.commit_status == 'not_attempted'
    assert not any(event[0] == 'statement' for event in case.backend.events)


def test_catalogue_mismatch_rolls_back_before_commit(case):
    intent, signature = signed(case)
    case.backend.catalogue_snapshot['constraints'][0]['definition'] = 'changed'
    report = case.executor.run_simulated(case.backend, intent, signature)
    assert report.status == 'simulated_rollback_confirmed' and not case.backend.installed
    assert not any(event[0] == 'commit_attempt' for event in case.backend.events)


def test_expired_approval_during_transaction_prevents_commit(case, monkeypatch):
    intent, signature = signed(case)
    now = [NOW]
    case.executor.clock = lambda: now[0]
    original = case.backend.apply_revision
    def apply(session, revision):
        original(session, revision)
        if revision.revision == 'p101_0001_operations':
            now[0] = intent.expires_at + timedelta(seconds=1)
    monkeypatch.setattr(case.backend, 'apply_revision', apply)
    report = case.executor.run_simulated(case.backend, intent, signature)
    assert report.status == 'simulated_rollback_confirmed'
    assert report.commit_status == 'not_attempted' and not case.backend.installed


@pytest.mark.parametrize('fault,installed', [('before', False), ('after', True)])
def test_uncertain_commit_retains_durable_claim_and_never_retries(case, fault, installed):
    intent, signature = signed(case)
    case.backend.commit_fault = fault
    report = case.executor.run_simulated(case.backend, intent, signature)
    assert report.status == report.commit_status == 'uncertain'
    assert case.backend.installed is installed
    assert auth.ReplayReservations(case.root).inspect(intent.campaign_sha256, intent.operation) == 'uncertain'
    # A new, validly signed approval does not release the operation's durable claim.
    next_intent, next_signature = signed(case)
    with pytest.raises(Rejected): case.executor.run_simulated(case.backend, next_intent, next_signature)
    assert sum(event[0] == 'commit_attempt' for event in case.backend.events) == 1


@pytest.mark.parametrize('fault', ['alias_socket', 'alias_pid', 'read_fault'])
def test_independence_is_not_a_different_uuid(case, fault):
    case.backend.installed = True
    setattr(case.backend, fault, True)
    intent, signature = signed(case, 'first-pair')
    report = case.executor.run_simulated(case.backend, intent, signature)
    assert report.status == 'simulated_commit_verification_failed'
    assert report.commit_status == 'confirmed'  # Do not invent rollback after acknowledged commit.
    assert len(case.backend.pair) == 1


def test_cleanup_failure_does_not_undo_known_commit(case):
    intent, signature = signed(case)
    case.backend.close_fault = True
    report = case.executor.run_simulated(case.backend, intent, signature)
    assert report.commit_status == 'confirmed' and report.cleanup_failed
    assert case.backend.installed


def test_missing_outcome_is_uncertain_after_reopening(case):
    intent, _ = signed(case)
    case.reservations.reserve(intent, envelope_sha256='f' * 64)
    reopened = auth.ReplayReservations(case.root)
    assert reopened.inspect(intent.campaign_sha256, intent.operation) == 'uncertain'
    with pytest.raises(Rejected): reopened.reserve(intent, envelope_sha256='f' * 64)


def test_live_or_callback_backends_cannot_enable_execution(case):
    poison = Mock(side_effect=AssertionError('Must not be invoked'))
    with pytest.raises(ExecutionDisabled): case.executor.run_live(backend=poison, approved=True)
    intent, signature = signed(case)
    with pytest.raises(Rejected): case.executor.run_simulated(poison, intent, signature)
    assert not poison.mock_calls


def test_reports_do_not_leak_payload_or_credentials(case):
    intent, signature = signed(case)
    report = case.executor.run_simulated(case.backend, intent, signature)
    assert len(report.evidence_sha256) == 64
    assert 'certificate' not in repr(report) and 'signature' not in repr(intent)
    assert not report.authenticated and not report.real_attested
