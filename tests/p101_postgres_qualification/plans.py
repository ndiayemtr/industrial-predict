"""Closed preparation plans. No revision loader, SQL executor or approval issuer."""

import ast
from dataclasses import dataclass, fields, is_dataclass
from hashlib import sha256
import json

from app import general_migrations as general
from b2b_postgres_qualification import validation as b2b
from b2b_postgres_qualification.contracts import Offline, Publication, ExecutionDisabled, deny


P101 = Publication('p101_0001_operations', 'b2b_0002_analyze',
    'general_migrations/versions/p101_0001_operations.py',
    'db3876b5cc2be0cff37f20ecebabe51821b5289fec1a8ceed96651b091cca46f')
PUBLICATIONS = (*b2b.PUBLICATIONS, P101)

# Future metadata collection, not executed by this module. Search all user schemas,
# including hidden empty schemas, relations, routines/types and nonstandard extensions.
EMPTY_SQL = """SELECT
 (SELECT count(*) FROM pg_namespace WHERE nspname='public') AS public_schemas,
 (SELECT count(*) FROM pg_namespace WHERE nspname <> 'public'
  AND nspname <> 'information_schema' AND nspname !~ '^pg_') AS extra_schemas,
 (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_') AS relations,
 (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_') AS routines,
 (SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
  WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_') AS types,
 (SELECT count(*) FROM pg_extension WHERE extname <> 'plpgsql') AS extra_extensions,
 (SELECT count(*) FROM pg_largeobject_metadata) AS large_objects,
 (SELECT count(*) FROM pg_event_trigger) AS event_triggers,
 (SELECT count(*) FROM pg_foreign_server) AS foreign_servers,
 (SELECT count(*) FROM pg_publication) AS publications,
 (SELECT count(*) FROM pg_subscription) AS subscriptions"""
EMPTY_COUNTS = dict(public_schemas=1, extra_schemas=0, relations=0, routines=0,
    types=0, extra_extensions=0, large_objects=0, event_triggers=0,
    foreign_servers=0, publications=0, subscriptions=0)

CATALOG_SQL = """SELECT n.nspname AS schema_name,c.relname,k.conname,k.contype,
 k.convalidated,k.condeferrable,k.condeferred,pg_get_constraintdef(k.oid,true) AS definition
 FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
 JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' ORDER BY c.relname,k.conname"""
TRIGGERS_SQL = """SELECT c.relname,t.tgname,t.tgenabled,t.tgdeferrable,t.tginitdeferred,
 pg_get_triggerdef(t.oid,true) AS definition FROM pg_trigger t
 JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname"""
FUNCTIONS_SQL = """SELECT p.proname,p.prosecdef,p.proconfig,pg_get_functiondef(p.oid) AS definition
 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
 WHERE n.nspname='public' ORDER BY p.proname,p.oid"""

P101_CONSTRAINTS = {
    'uq_prediction_records_p101_pair': 'u', 'uq_p101_operations_key': 'u',
    'uq_p101_operations_business': 'u', 'uq_p101_operations_prediction': 'u',
    'uq_p101_operations_pair': 'u', 'fk_p101_operations_prediction': 'f',
    'fk_prediction_records_p101_operation': 'f',
    **{'ck_p101_operations_' + suffix: 'c' for suffix in
        ('ids', 'hashes', 'model', 'state', 'score', 'actor', 'times', 'result', 'key', 'payload')},
}
P101_FUNCTIONS = ('p101_operation_append_only', 'p101_prediction_immutable', 'p101_operation_validate')
P101_TRIGGERS = ('p101_operations_no_mutation', 'p101_operations_no_truncate',
    'p101_predictions_no_mutation', 'p101_operations_prediction_matches')


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=True).encode('ascii')).hexdigest()


def exact_equal(left, right):
    """Avoid bool/int and nested mutable payload equality ambiguities."""
    if type(left) is not type(right):
        return False
    if is_dataclass(left):
        return all(exact_equal(getattr(left, f.name), getattr(right, f.name)) for f in fields(left))
    if type(left) is dict:
        return left.keys() == right.keys() and all(exact_equal(left[k], right[k]) for k in left)
    if type(left) in (tuple, list):
        return len(left) == len(right) and all(exact_equal(a, b) for a, b in zip(left, right))
    return left == right


def require_campaign(campaign, expected_campaign):
    """Compare with separately supplied inventory; this is NOT authenticated approval."""
    b2b.validate_campaign(campaign)
    b2b.validate_campaign(expected_campaign)
    b2b.require(b2b.destination_fingerprint(campaign) == b2b.destination_fingerprint(expected_campaign))


@dataclass(frozen=True, slots=True, repr=False)
class MigrationPlan(Offline):
    campaign_sha256: str
    publications: tuple[Publication, ...]
    source_snapshot_sha256: str
    declarations: tuple[tuple[str, tuple[str, ...]], ...]
    initial_revision: None = None
    final_revision: str = 'p101_0001_operations'


@b2b.guarded
def prepare_migrations(campaign, *, expected_campaign, publications=PUBLICATIONS):
    require_campaign(campaign, expected_campaign)
    b2b.require(type(publications) is tuple and publications == PUBLICATIONS)
    # Existing guard verifies every source/hash/parent and independent AST anchors.
    # It never imports a revision or returns an executable Alembic configuration.
    snapshot = general.inspect_sources()
    graph = {item.revision: item for item in snapshot.revisions}
    hashes = {item.path: item.sha256 for item in snapshot.sources}
    b2b.require(len(graph) == 14 and len(PUBLICATIONS) == 14)
    declarations = []
    previous = None
    for publication in PUBLICATIONS:
        revision = graph[publication.revision]
        b2b.require(publication.parent == previous and revision.parent == previous
            and revision.path == publication.path and hashes[publication.path] == publication.sha256)
        path = general.BACKEND / publication.path
        source = path.read_text(encoding='utf-8').replace('\r\n', '\n')
        b2b.require(sha256(source.encode()).hexdigest() == publication.sha256)
        tree = ast.parse(source)
        upgrades = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'upgrade']
        b2b.require(len(upgrades) == 1)
        # Store inert AST descriptions, not Python functions or calls to op.*.
        declarations.append((publication.revision,
            tuple(ast.dump(node, include_attributes=False) for node in upgrades[0].body)))
        previous = publication.revision
    content = [(item.path, item.sha256) for item in snapshot.sources]
    return MigrationPlan(b2b.destination_fingerprint(campaign), PUBLICATIONS,
        fingerprint(content), tuple(declarations))


@b2b.guarded
def review_empty_declaration(campaign, *, expected_campaign, identity, counts, revision):
    """Injected pre-bootstrap metadata only, never proof of an actually empty DB."""
    require_campaign(campaign, expected_campaign)
    expected = dict(database=campaign.database, host=campaign.host, address=campaign.server_address,
        port=campaign.port, cluster=campaign.cluster_name, instance=campaign.instance_id,
        version=campaign.server_version_num, role=campaign.roles[1], dev_marker=None,
        sslmode='verify-full', ca_sha256=campaign.ca_sha256)
    b2b.require(type(identity) is dict and identity == expected
        and all(type(identity[k]) is type(value) for k, value in expected.items()))
    b2b.require(type(counts) is dict and exact_equal(counts, EMPTY_COUNTS) and revision is None)
    return fingerprint(dict(identity=identity, counts=counts, revision=revision))


@b2b.guarded
def review_catalogue_declaration(catalogue, *, expected_sha256):
    """Compare a complete injected snapshot to an independent reviewed baseline.

    No baseline is provided/derived automatically from the observed DB. No live
    catalogue collector is installed. This comparison cannot enable execution.
    """
    b2b.digest(expected_sha256)
    b2b.require(type(catalogue) is dict and set(catalogue) == {'revision', 'columns',
        'constraints', 'indexes', 'functions', 'triggers', 'sequences', 'ownership', 'acl'})
    b2b.require(catalogue['revision'] == 'p101_0001_operations')
    for section in ('columns', 'constraints', 'indexes', 'functions', 'triggers', 'sequences', 'ownership', 'acl'):
        b2b.require(type(catalogue[section]) is list and catalogue[section])
    constraints = catalogue['constraints']
    b2b.require(all(type(row) is dict and type(row.get('name')) is str for row in constraints))
    for name, kind in P101_CONSTRAINTS.items():
        matches = [row for row in constraints if row['name'] == name]
        b2b.require(len(matches) == 1)
        row = matches[0]
        b2b.require(row.get('type') == kind and row.get('validated') is True
            and type(row.get('definition')) is str and row['definition'])
        if kind == 'f':
            b2b.require(row.get('deferrable') is True and row.get('deferred') is True)
    for name in P101_FUNCTIONS:
        matches = [row for row in catalogue['functions'] if row.get('name') == name]
        b2b.require(len(matches) == 1 and matches[0].get('security_definer') is False
            and matches[0].get('search_path') == 'pg_catalog, pg_temp')
    for name in P101_TRIGGERS:
        matches = [row for row in catalogue['triggers'] if row.get('name') == name]
        b2b.require(len(matches) == 1 and matches[0].get('enabled') == 'O')
        if name == 'p101_operations_prediction_matches':
            b2b.require(matches[0].get('deferrable') is True and matches[0].get('deferred') is True)
    # Full definitions/columns/indexes/ACL/owners, including historical objects,
    # must match the independently supplied baseline, not merely the names above.
    b2b.require(fingerprint(catalogue) == expected_sha256)
    return expected_sha256


def request_migration_execution(*args, **kwargs):
    """No loader, connection use or callback invocation, even with approved-looking inputs."""
    deny(ExecutionDisabled)
