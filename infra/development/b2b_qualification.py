"""Explicit isolated campaign context. No I/O on import, no DEV fallback.

The SQL role labels remain fixed by the approved function bodies. They denote
new roles in a separately attested ephemeral cluster, never DEV credentials.
"""
from datetime import datetime, timezone
import ipaddress
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

from sqlalchemy.engine import URL
from cryptography import x509

import b2b_policy as policy
import b2b_activation as activation
import b2b_locks as locks

CAMPAIGN = 'auth-b2b-dev-5b-4h-3'
CONTAINER = 'industrial-predict-b2b-deploy-qual-4h3-20261114'
VOLUME = CONTAINER + '-data'
DATABASE = 'b2b_deploy_qual_4h3'
RESTORE = 'b2b_deploy_restore_4h3'
CLUSTER = 'industrial-predict-b2b-qual-4h3'
IMAGE = 'sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317'
PORT = 55443
REPO = Path(__file__).resolve().parents[2]
DEV_ROOT = Path('D:/integration/industrial-predict/development').resolve()
INSPECT = ('{"id":{{json .Id}},"name":{{json .Name}},"image":{{json .Image}},'
           '"labels":{{json .Config.Labels}},"mounts":{{json .Mounts}},'
           '"network":{{json .HostConfig.NetworkMode}},"bindings":{{json .HostConfig.PortBindings}},'
           '"ports":{{json .NetworkSettings.Ports}},"running":{{json .State.Running}},'
           '"privileged":{{json .HostConfig.Privileged}},"tmpfs":{{json .HostConfig.Tmpfs}},'
           '"pid_mode":{{json .HostConfig.PidMode}},"ipc_mode":{{json .HostConfig.IpcMode}}}')


def require(value, message='Qualification rejected'):
    if not value:
        raise ValueError(message)


class Qualification:
    restore_database = RESTORE

    @classmethod
    def load(cls, filename, campaign):
        require(campaign == CAMPAIGN, 'Explicit qualification campaign required')
        path = Path(filename)
        # Refuse private DEV paths before opening any file.
        resolved = path.resolve()
        require(not resolved.is_relative_to(DEV_ROOT) and not resolved.is_relative_to(REPO), 'Forbidden qualification path')
        require(path.name == 'qualification.json' and resolved.parent.name == CONTAINER and not path.is_symlink(), 'Dedicated qualification directory required')
        raw = policy.read_json(resolved)
        value = cls(raw, resolved)
        value.validate()
        return value

    def __init__(self, raw, path):
        require(type(raw) is dict and not {'_path', '_directory'} & raw.keys(), 'Internal qualification paths cannot be supplied')
        self.path = Path(path).resolve()
        self.config = {**raw, '_path': str(self.path), '_directory': str(self.path.parent)}

    def validate(self):
        c = self.config
        fixed = {'format': 'b2b-isolated-qualification-v1', 'enabled': True,
                 'qualification_campaign': CAMPAIGN, 'synthetic_only': True,
                 'mode': 'isolated-qualification', 'runtime_profile': activation.PREPARATION,
                 'db_host': '127.0.0.1', 'db_port': PORT, 'database': DATABASE,
                 'cluster_name': CLUSTER, 'container': CONTAINER, 'volume': VOLUME, 'image_id': IMAGE}
        dynamic = {'database_oid', 'restore_database_oid', 'instance_id', 'restore_instance_id',
                   'cluster_identifier', 'container_id', 'volume_created_at', 'run_id',
                   'ca_sha256', 'server_certificate_sha256', '_path', '_directory'}
        require(set(c) == set(fixed) | dynamic, 'Unexpected qualification configuration')
        require(all(type(c[k]) is type(v) and c[k] == v for k, v in fixed.items()), 'Qualification destination mismatch')
        require(self.path.name == 'qualification.json' and self.path.parent.name == CONTAINER
                and not self.path.is_relative_to(DEV_ROOT) and not self.path.is_relative_to(REPO), 'Forbidden qualification directory')
        require(c['_path'] == str(self.path) and c['_directory'] == str(self.path.parent), 'Qualification path mismatch')
        dev = policy.policy()['destination']
        for field in ('database_oid', 'restore_database_oid'):
            require(type(c[field]) is int and c[field] > 0 and c[field] != dev['database_oid'], 'Forbidden database OID')
        require(c['database_oid'] != c['restore_database_oid'], 'Source/restore overlap')
        for field in ('instance_id', 'restore_instance_id', 'run_id'):
            require(type(c[field]) is str and str(uuid.UUID(c[field])) == c[field] and c[field] != dev['instance_id'], 'Invalid campaign UUID')
        require(len({c[k] for k in ('instance_id', 'restore_instance_id', 'run_id')}) == 3, 'Campaign UUID overlap')
        require(type(c['cluster_identifier']) is str and re.fullmatch(r'[1-9][0-9]{0,19}', c['cluster_identifier'])
                and c['cluster_identifier'] not in (dev['cluster_identifier'], '7673083456081215526'), 'Forbidden cluster')
        for field in ('container_id', 'ca_sha256', 'server_certificate_sha256'):
            require(type(c[field]) is str and re.fullmatch('[0-9a-f]{64}', c[field]), 'Invalid campaign fingerprint')
        require(type(c['volume_created_at']) is str and bool(c['volume_created_at']), 'Missing volume creation identity')
        return self

    def file(self, name):
        require(name in ('ca.crt', 'server.crt', 'admin-password.txt', 'migrator-password.txt', 'app-password.txt'), 'Unknown qualification file')
        path = self.path.parent / name
        require(path.is_file() and not path.is_symlink() and path.resolve().parent == self.path.parent, 'Unsafe qualification file')
        return path

    def transport(self):
        self.validate()
        require(not any(k.upper().startswith('PG') for k in os.environ), 'Ambient libpq settings forbidden')
        ca, cert = self.file('ca.crt').read_bytes(), self.file('server.crt').read_bytes()
        require(policy.digest(ca) == self.config['ca_sha256'] and policy.digest(cert) == self.config['server_certificate_sha256'], 'Qualification certificate fingerprint mismatch')
        authority = x509.load_pem_x509_certificate(ca)
        server = x509.load_pem_x509_certificate(cert)
        server.verify_directly_issued_by(authority)
        now = datetime.now(timezone.utc)
        for item in (authority, server):
            require(item.not_valid_before_utc <= now <= item.not_valid_after_utc, 'Expired qualification certificate')
        require(authority.extensions.get_extension_for_class(x509.BasicConstraints).value.ca, 'CA required')
        require(not server.extensions.get_extension_for_class(x509.BasicConstraints).value.ca, 'Server certificate must not be CA')
        require(ipaddress.ip_address('127.0.0.1') in server.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.IPAddress), 'Qualification IP SAN required')
        return {'sslmode': 'verify-full', 'sslrootcert': str(self.file('ca.crt')),
                'connect_timeout': 3, 'gssencmode': 'disable', 'options': '-c search_path=public -c timezone=UTC'}

    def labels(self):
        return {'industrial-predict.qualification': CAMPAIGN, 'industrial-predict.run': self.config['run_id']}

    def docker(self, *arguments):
        executable = shutil.which('docker')
        require(executable is not None, 'Docker client required, no installation fallback')
        try:
            result = subprocess.run([executable, *arguments], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    timeout=10, check=False)
            require(result.returncode == 0, 'Qualification Docker inspection failed')
            return result.stdout
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError('Qualification Docker inspection failed; no retry') from None

    def verify_resources(self):
        self.validate()
        c = self.config
        # Resolve only the campaign's exact name before inspecting a supplied ID.
        actual = self.docker('container', 'ls', '-a', '--no-trunc', '--filter', 'name=^/' + CONTAINER + '$', '--format', '{{.ID}}').decode().strip()
        require(actual == c['container_id'], 'Campaign container ID mismatch')
        image = policy.parse_json(self.docker('image', 'inspect', IMAGE).decode())
        require(len(image) == 1 and image[0]['Id'] == IMAGE and image[0]['Os'] == 'linux' and image[0]['Architecture'] == 'amd64', 'Image mismatch')
        container = policy.parse_json(self.docker('container', 'inspect', actual, '--format', INSPECT).decode())
        volume = policy.parse_json(self.docker('volume', 'inspect', VOLUME).decode())
        self.check_resources(container, volume, image[0].get('Config', {}).get('Labels'))
        return actual

    def check_resources(self, container, volumes, image_labels=None):
        c = self.config
        inherited = image_labels or {}
        require(type(inherited) is dict and not inherited.keys() & self.labels().keys(), 'Unexpected inherited campaign labels')
        require(container['id'] == c['container_id'] and container['name'] == '/' + CONTAINER
                and container['image'] == IMAGE and container['labels'] == {**inherited, **self.labels()}, 'Container identity mismatch')
        require(container['running'] is True and container['network'] == 'none' and not container['bindings']
                and all(not v for v in (container['ports'] or {}).values()), 'Container network/ports mismatch')
        require(container['privileged'] is False and not container['tmpfs'] and container['pid_mode'] == ''
                and container['ipc_mode'] == 'private', 'Unexpected container isolation options')
        require(len(volumes) == 1, 'Unexpected volume inventory')
        v = volumes[0]
        require(v['Name'] == VOLUME and v['Labels'] == self.labels() and v['CreatedAt'] == c['volume_created_at']
                and v['Driver'] == 'local' and v['Scope'] == 'local' and not v['Options'], 'Volume identity mismatch')
        mounts = container['mounts']
        require(len(mounts) == 1, 'Unexpected mount')
        m = mounts[0]
        require(m['Type'] == 'volume' and m['Name'] == VOLUME and m['Source'] == v['Mountpoint']
                and m['Destination'] == '/var/lib/postgresql/data' and m['RW'] is True, 'Unexpected data mount')

    def approved(self):
        return {'profile': str(self.path), 'destination': {k: self.config[k] for k in
            ('mode', 'db_host', 'db_port', 'database', 'database_oid', 'cluster_identifier', 'instance_id', 'container')}}

    def restore_inventory(self):
        self.validate()
        return {**self.config, 'database': RESTORE, 'database_oid': self.config['restore_database_oid'],
                'instance_id': self.config['restore_instance_id']}

    def plan(self):
        return {'operation': 'isolated-b2b-locks-qualification-v1', 'campaign': CAMPAIGN,
                'campaign_identity': {k: self.config[k] for k in ('run_id', 'container_id', 'volume', 'volume_created_at', 'image_id', 'ca_sha256', 'server_certificate_sha256', 'restore_database_oid', 'restore_instance_id')},
                'qualification_sources': {p.name: policy.file_digest(p) for p in
                    (Path(__file__), Path(__file__).with_name('b2b_qualification_relay.py'))}}

    def render(self, captured):
        """Replace only pinned DEV guard preludes, never function bodies or ACLs."""
        c = self.config
        result = {}
        for name, source in captured.items():
            boundary = 'CREATE ROLE ui47_b2b_lock_owner' if name == 'b2b-lock-install.review.sql' else '-- Named-role ACL assertion:'
            require(source.count(boundary) == (1 if name == 'b2b-lock-install.review.sql' else 2), 'Unexpected approved SQL framing')
            tail = boundary + source.split(boundary, 1)[1]
            role = 'ui47_admin' if name == 'b2b-lock-install.review.sql' else 'ui47_migrator'
            guard = f"""SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='15s';
DO $qualification$ BEGIN
 IF current_user<>'{role}' OR session_user<>'{role}'
 OR ('{role}'='ui47_admin' AND NOT (SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname=current_user))
 OR current_database()<>'{DATABASE}'
 OR (SELECT oid FROM pg_catalog.pg_database WHERE datname=current_database())<>{c['database_oid']}
 OR current_setting('cluster_name')<>'{CLUSTER}'
 OR current_setting('server_version_num')<>'170010'
 OR current_setting('app.development_instance_id',true) IS DISTINCT FROM '{c['instance_id']}'
 OR (SELECT system_identifier::text FROM pg_catalog.pg_control_system())<>'{c['cluster_identifier']}'
 OR inet_server_port() IS DISTINCT FROM {PORT}
 OR (SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid=pg_backend_pid()) IS DISTINCT FROM true
 OR (SELECT version_num FROM public.alembic_version) IS DISTINCT FROM 'b2b_0002_analyze'
 THEN RAISE EXCEPTION 'Qualification identity rejected'; END IF;
END; $qualification$;
"""
            result[name] = guard + tail
        install = result['b2b-lock-install.review.sql']
        for f in locks.FUNCTIONS:
            require(install.count('$body$' + f['body'] + '$body$') == 1, 'Approved function bytes changed')
        require(all('industrial_predict_dev' not in sql and '7697614558579179559' not in sql for sql in result.values()), 'DEV identity in qualification SQL')
        return result

    def manager(self, base):
        return Manager(base, self)


class Manager:
    """Transport/context adapter only: Deployment retains all transactions."""
    def __init__(self, base, qualification):
        self.base, self.q = base, qualification
        self.__file__ = base.__file__

    def __getattr__(self, name):
        return getattr(self.base, name)

    def runtime_connect_args(self, config):
        require(config == self.q.config, 'Qualification source context changed')
        args = self.q.transport()
        self.q.verify_resources()
        return args

    def db_url(self, config, role):
        require(config == self.q.config and role in ('admin', 'migrator', 'app'), 'Unexpected qualification role/context')
        password = self.q.file(role + '-password.txt').read_text(encoding='utf-8').strip()
        require(re.fullmatch('[0-9a-f]{64}', password), 'Malformed synthetic credential')
        return URL.create('postgresql+psycopg', username='ui47_' + role, password=password,
                          host='127.0.0.1', port=PORT, database=DATABASE)

    def inspect_connection(self, c, config, role='app', revision=True, *, expected_revision):
        require(config in (self.q.config, self.q.restore_inventory()), 'Unexpected qualification database')
        proof = self.base.inspect_connection(c, config, role, revision=revision,
            expected_revision=expected_revision, expected_cluster_name=CLUSTER)
        require(proof['version'].split()[0] == '17.10', 'Exact PostgreSQL 17.10 required')
        require(c.exec_driver_sql('SELECT inet_server_addr()::text,inet_server_port()').one() == ('127.0.0.1', PORT), 'Unexpected qualification backend transport')
        return proof

    def inspect_runtime_connection(self, c, config):
        self.runtime_connect_args(config)
        proof = self.inspect_connection(c, config, expected_revision='b2b_0002_analyze')
        require(c.exec_driver_sql('SELECT system_identifier::text FROM pg_catalog.pg_control_system()').scalar_one() == config['cluster_identifier'], 'Qualification cluster mismatch')
        require(c.exec_driver_sql('SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid=pg_backend_pid()').scalar_one() is True, 'Qualification TLS required')
        return {**proof, 'runtime_mode': activation.PREPARATION, 'business_routes_enabled': False}

    def b2b_pgtool(self, config, name, arguments):
        require(config == self.q.config and name in ('pg_dump', 'pg_restore'), 'Unexpected qualification tool')
        require(type(arguments) is list and all(type(a) is str for a in arguments), 'Unexpected client arguments')
        expected_db = DATABASE if name == 'pg_dump' else RESTORE
        databases = [a for a in arguments if a.startswith('--dbname=')]
        require(databases in ([], ['--dbname=' + expected_db]) and (name != 'pg_dump' or bool(databases)), 'Forbidden client database')
        allowed = ('--format=custom', '--list', '--single-transaction', '--exit-on-error')
        for arg in arguments:
            if arg in allowed or arg.startswith('--dbname='):
                continue
            if arg.startswith('--snapshot='):
                require(re.fullmatch('[0-9A-Fa-f-]+', arg[11:]), 'Invalid exported snapshot')
                continue
            path = Path(arg[7:] if arg.startswith('--file=') else arg)
            require(path.resolve().is_relative_to(self.q.path.parent / 'evidence') and not path.is_symlink(), 'Forbidden archive path')
        transport = self.runtime_connect_args(config)
        executable = shutil.which(name)
        require(executable is not None, 'PostgreSQL 17.10 tool unavailable')
        environment = {k: v for k, v in os.environ.items() if not k.upper().startswith('PG')}
        try:
            version = subprocess.run([executable, '--version'], capture_output=True, check=False, timeout=10)
            require(version.returncode == 0 and re.search(rb'\b17\.10\b', version.stdout), 'PostgreSQL tool version mismatch')
            environment.update(PGPASSWORD=self.db_url(config, 'migrator').password,
                PGSSLMODE='verify-full', PGSSLROOTCERT=transport['sslrootcert'], PGGSSENCMODE='disable',
                PGCONNECT_TIMEOUT='3', PGOPTIONS='-c search_path=public -c timezone=UTC')
            result = subprocess.run([executable, '--host=127.0.0.1', '--port=55443', '--username=ui47_migrator',
                '--no-password', *arguments], env=environment, capture_output=True, timeout=1800, check=False)
            require(result.returncode == 0, 'Qualification client failed; no retry')
            return result.stdout
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError('Qualification client transport failed; no retry') from None
        finally:
            environment.pop('PGPASSWORD', None)
