"""Future operator CLI; every mutating/connection operation needs explicit acknowledgement."""

import argparse
import json
from pathlib import Path

from app.p101_local_demo.setup_config import ROOT, ROLES, SetupError, compose_files, load_settings


def render(settings):
    """Future private files only: refuse symlinks and divergent existing contents."""
    files = compose_files(settings)
    root = Path(settings.private_root)
    # Prevalidate the complete set before creating any file. OS ACLs remain an operator prerequisite.
    for name, content in files.items():
        path = root / name
        if path.resolve() != path or (path.exists() and path.read_text(encoding='utf-8') != content):
            raise SetupError('Private generated file differs; explicit review required')
    for name, content in files.items():
        path = root / name
        if not path.exists():
            with path.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--instance')
    parser.add_argument('operation', choices=('check-config', 'render', 'roles', 'migrate', 'bootstrap', 'seal', 'verify'))
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
        if args.operation == 'check-config':
            print('Explicit local configuration valid; no connection attempted')
            return 0
        from app.p101_local_demo.provisioning import (
            create_roles, migrate, require_execution, seal, transaction,
        )
        require_execution(settings, args.execute, args.instance)
        if args.operation == 'render':
            render(settings)
        else:
            role = ROLES[0] if args.operation in ('roles', 'seal') else ROLES[1]
            if args.operation == 'verify':
                role = ROLES[3]
            with transaction(settings, role, execute=args.execute, instance=args.instance) as connection:
                if args.operation == 'roles': create_roles(connection, settings)
                elif args.operation == 'migrate': migrate(connection, settings)
                elif args.operation == 'seal': seal(connection, settings)
                else:
                    reference = json.loads((ROOT / 'tests/p101_anomaly/fixtures/p101-temperature-v1.json').read_text(encoding='utf-8'))
                    if args.operation == 'bootstrap':
                        from app.p101_local_demo.bootstrap import bootstrap
                        bootstrap(connection, settings, reference)
                    else:
                        from app.p101_local_demo.reader import adapt_rows, read_rows
                        adapt_rows(read_rows(connection, settings.destination(role)), reference)
        print('Local preparation operation completed; no prediction computed or persisted')
        return 0
    except Exception:
        print('Local operation refused or failed. Inspect state before retry; commit may be uncertain.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
