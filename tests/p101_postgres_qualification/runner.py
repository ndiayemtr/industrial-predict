"""Offline report CLI. Build, migration, insertion and live reading stay disabled."""

import argparse
import json
from pathlib import Path
from hashlib import sha256

from b2b_postgres_qualification.contracts import ExecutionDisabled, deny
from p101_postgres_qualification.plans import PUBLICATIONS


ROOT = Path(__file__).resolve().parents[2]
DEPENDENCIES = ROOT / 'infra/p101-qualification-runner/dependencies.json'

SOURCE_PATHS = (
    'backend/app/__init__.py', 'backend/app/general_migrations.py',
    'backend/app/anomaly_detection/__init__.py', 'backend/app/anomaly_detection/p101_canonical.py',
    'backend/app/anomaly_detection/statistical_detector.py',
    'backend/app/p101_persistence/__init__.py', 'backend/app/p101_persistence/contracts.py',
    'backend/app/p101_persistence/canonical.py',
    *(f'backend/app/p101_dev/{name}.py' for name in
        ('__init__', 'adapter', 'canonical', 'contracts', 'evaluation', 'preparation')),
    *(f'tests/b2b_postgres_qualification/{name}.py' for name in
        ('contracts', 'validation', 'evidence', 'collectors', 'transport')),
    *(f'tests/p101_postgres_qualification/{name}' for name in
        ('plans.py', 'scenario.py', 'runner.py', 'fixture.json')),
    *(f'backend/{p.path}' for p in PUBLICATIONS),
    'backend/general_migrations/revision_manifest.json',
    'backend/general_migrations/versions/.gitkeep',
    'backend/general_migrations/env.py', 'backend/general_migrations/alembic.ini',
    'infra/p101-qualification-runner/dependencies.json',
)


def source_manifest():
    """Fixed paths only; diagnostic hashes, never release approval or an archive."""
    entries = []
    for name in SOURCE_PATHS:
        path = ROOT / name
        if path.is_symlink() or path.resolve() != path or not path.is_file():
            deny(ExecutionDisabled)
        content = path.read_text(encoding='utf-8').replace('\r\n', '\n').encode('utf-8')
        entries.append(dict(path=name, sha256=sha256(content).hexdigest()))
    return entries


def report():
    # Fixed public metadata only: never serialize Campaign, credentials or payloads.
    dependencies = json.loads(DEPENDENCIES.read_text(encoding='utf-8'))
    return dict(format='p101-qualification-preparation-v1', execution_enabled=False,
        build_enabled=False, real_attested=False,
        revisions=[p.revision for p in PUBLICATIONS],
        build_blockers=dependencies['blockers'],
        execution_blockers=[
            'campaign_bound_operational_approval_missing',
            'immutable_14_revision_loader_not_qualified',
            'live_empty_database_and_catalogue_profiles_not_qualified',
            'bound_rw_transport_and_independent_pair_reader_missing',
            'durable_no_retry_ledger_for_p101_operation_missing',
        ])


def request_build(*args, **kwargs):
    deny(ExecutionDisabled)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Offline P101 qualification preparation only')
    parser.add_argument('action', choices=('report', 'build', 'migrate', 'scenario', 'verify'))
    args = parser.parse_args(argv)
    if args.action != 'report':
        # Refuse before driver/transport/filesystem setup or any callback.
        deny(ExecutionDisabled)
    print(json.dumps(report(), sort_keys=True, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
