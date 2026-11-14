"""DEV lock deployment helpers for manage.py; no import-time I/O or CLI.

Historical migration policy is unchanged. Receipts detect corruption, not a
malicious filesystem owner: private ACLs and reviewed interactive hashes matter.
No Docker, role impersonation, automatic retry or active-database restore.
"""
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

import b2b_policy as policy
import b2b_activation as activation
import b2b_locks as locks

REVISION = 'b2b_0002_analyze'
ARCHIVE = 'before-b2b-locks.dump'
RESTORE_DATABASE = 'industrial_predict_b2b_locks_restore'
ACTION_ROLES = {'install': 'admin', 'grant': 'migrator', 'rollback-acl': 'migrator', 'remove': 'admin'}
PINS = {
    'b2b_locks.py': 'e1f9e9ddb68654bf15037c5737d678d8117f82c7a53dfa6aed13237daaa84eb1',
    'b2b_activation.py': 'c7723f7ddd68bdc5618d8eee6dad093a1d57eb97953f1ddecf041105f22bbc35',
    'b2b-lock-install.review.sql': 'c1e125103007e0e9d1513c40c73332e796fddb9b4033465f50dae7bca48f6b44',
    'b2b-auth-grants.review.sql': 'ba28958f5e7043c5a434a35353f569c8ba787cd98e2821fdcd4213861eb1a31f',
    'b2b-auth-revoke.review.sql': '4b88bb30399d214129b1601250f375ba197acd7ae9cba45d9ce0af60cc7caf8c',
}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return policy.digest(policy.canonical(value))


def utcnow():
    return datetime.now(timezone.utc)


def executable(raw):
    """Peel only pinned review framing, never replace transaction keywords."""
    require(type(raw) is bytes and b'\r' not in raw and not raw.startswith(b'\xef\xbb\xbf'), 'SQL must be original UTF-8/LF bytes')
    source = raw.decode('utf-8', errors='strict')
    require(source.count('\nBEGIN;\n') == 1 and source.endswith('\nROLLBACK;\n'), 'Unexpected review framing')
    return source.split('\nBEGIN;\n', 1)[1][:-len('ROLLBACK;\n')]


def capture():
    root = Path(__file__).parent
    bodies = {}
    for name, expected in PINS.items():
        raw = (root / name).read_bytes()
        require(policy.digest(raw) == expected, 'Unapproved deployment source: ' + name)
        if name.endswith('.sql'):
            bodies[name] = executable(raw)
    return bodies


def seal(payload):
    return {'payload': payload, 'sha256': digest(payload)}


def read_receipt(path, *, fresh=True):
    require(path.is_file() and not path.is_symlink(), 'Missing or linked receipt')
    envelope = policy.read_json(path)
    require(set(envelope) == {'payload', 'sha256'} and digest(envelope['payload']) == envelope['sha256'], 'Receipt fingerprint mismatch')
    value = envelope['payload']
    require(value.get('format') == 'dev-locks-evidence-v1', 'Wrong receipt format')
    if fresh:
        try:
            age = utcnow() - datetime.fromisoformat(value['created_at'])
        except (ValueError, TypeError, KeyError):
            raise ValueError('Invalid receipt time') from None
        require(timedelta(0) <= age <= timedelta(hours=24), 'Expired/future receipt')
    return value, envelope['sha256']


def write_receipt(directory, stage, plan, **values):
    value = {'format': 'dev-locks-evidence-v1', 'stage': stage, 'created_at': utcnow().isoformat(),
             'plan_sha256': digest(plan), **values}
    import json
    with (directory / (stage + '.json')).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(seal(value), stream, sort_keys=True, indent=2)
    return value


def expected_acl(baseline, state):
    """Canonical ACL algebra, including owners' default ACLs; no raw NULL reset."""
    entries = {tuple(row) for row in baseline}
    if state == 'absent':
        return sorted(entries)
    require(state in ('closed', 'granted'), 'Unknown deployment state')
    def add(kind, name, column, grantee, grantor, privilege, option=False):
        entries.add((kind, name, column, grantee, grantor, privilege, option))
    add('schema', 'public', '', locks.OWNER, 'ui47_migrator', 'USAGE')
    for privilege in ('USAGE', 'CREATE'):
        add('schema', locks.SCHEMA, '', 'ui47_migrator', 'ui47_migrator', privilege)
    add('schema', locks.SCHEMA, '', locks.OWNER, 'ui47_migrator', 'USAGE')
    for table, (columns, key) in locks.OWNER_RIGHTS.items():
        for column in columns:
            add('column', 'public.' + table, column, locks.OWNER, 'ui47_migrator', 'SELECT')
        add('column', 'public.' + table, key, locks.OWNER, 'ui47_migrator', 'UPDATE')
    for f in locks.FUNCTIONS:
        # Use PostgreSQL's canonical type spellings in the ACL snapshot.
        name = f['signature']
        add('function', name, '', locks.OWNER, locks.OWNER, 'EXECUTE')
        add('function', name, '', 'ui47_migrator', locks.OWNER, 'EXECUTE', True)
    if state == 'granted':
        for table, rights in activation.matrix(activation.CANDIDATE).items():
            for privilege in rights['table']:
                add('table', 'public.' + table, '', 'ui47_app', 'ui47_migrator', privilege)
            for privilege, columns in rights['columns'].items():
                for column in columns:
                    add('column', 'public.' + table, column, 'ui47_app', 'ui47_migrator', privilege)
        add('schema', locks.SCHEMA, '', 'ui47_app', 'ui47_migrator', 'USAGE')
        for f in locks.FUNCTIONS:
            add('function', f['signature'], '', 'ui47_app', 'ui47_migrator', 'EXECUTE')
    return sorted(entries)


def inverse_sql():
    """Only seven new objects and the technical grants; caller first closes B."""
    result = []
    for f in locks.FUNCTIONS:
        result += [f"REVOKE EXECUTE ON FUNCTION {f['signature']} FROM ui47_migrator RESTRICT;",
                   f"DROP FUNCTION {f['signature']} RESTRICT;"]
    for table, (columns, key) in locks.OWNER_RIGHTS.items():
        result += [f'REVOKE SELECT ({",".join(columns)}) ON public.{table} FROM {locks.OWNER} RESTRICT;',
                   f'REVOKE UPDATE ({key}) ON public.{table} FROM {locks.OWNER} RESTRICT;']
    result += [f'REVOKE USAGE ON SCHEMA public,b2b_lock FROM {locks.OWNER} RESTRICT;',
               'DROP SCHEMA b2b_lock RESTRICT;', f'DROP ROLE {locks.OWNER};']
    return '\n'.join(result)


class Deployment:
    def __init__(self, manager, config):
        self.m, self.config = manager, config
        approved = policy.policy()
        require(Path(config['_path']).resolve() == Path(approved['profile']).resolve(), 'Unapproved private profile')
        require(Path(config['_directory']).resolve() == Path(config['_path']).resolve().parent, 'Profile directory mismatch')
        require(all(config.get(k) == v for k, v in approved['destination'].items()), 'Wrong DEV destination')
        activation.require_preparation(config)
        self.bodies = capture()
        self.plan = {'operation': 'dev-b2b-locks-v1', 'revision': REVISION,
            'destination': approved['destination'], 'sources': PINS,
            'executors': {Path(p).name: policy.file_digest(Path(p)) for p in (__file__, manager.__file__)},
            'functions': [{k: f[k] for k in ('signature', 'result', 'sha256')} for f in locks.FUNCTIONS],
            'restore_database': RESTORE_DATABASE, 'runtime_enabled': False,
            'inverse_sha256': policy.digest(inverse_sql().encode('utf-8'))}
        self.tables = (*manager.TABLES, *manager.B2B_TABLES, 'alembic_version')

    def directory(self, directory, *, existing=True):
        value = policy.private_directory(self.config, directory, existing=existing)
        require(not value.is_relative_to(self.m.REPO), 'Evidence cannot be in Git')
        require(value.parent.is_dir(), 'Private evidence parent must already exist')
        return value

    def restore_inventory(self):
        value = policy.read_json(Path(self.config['_directory']) / 'b2b-locks-restore.json')
        require(set(value) == {'database', 'database_oid', 'instance_id', 'cluster_identifier'}, 'Invalid restore inventory')
        require(value['database'] == RESTORE_DATABASE and value['database'] != self.config['database'], 'Restore database overlaps source')
        require(type(value['database_oid']) is int and value['database_oid'] > 0 and value['database_oid'] != self.config['database_oid'], 'Invalid restore OID')
        import re
        require(type(value['instance_id']) is str and re.fullmatch('[0-9a-f-]{36}', value['instance_id'])
                and value['instance_id'] != self.config['instance_id'], 'Invalid restore instance')
        require(value['cluster_identifier'] == self.config['cluster_identifier'], 'Unexpected restore cluster')
        return {**self.config, **value}

    def engine(self, role, inventory=None):
        require(role in ('admin', 'migrator', 'app'), 'Unknown SQL role')
        inventory = inventory or self.config
        require(inventory == self.config or inventory == self.restore_inventory(), 'Unapproved connection inventory')
        arguments = self.m.runtime_connect_args(self.config)  # CA/destination before password.
        url = self.m.db_url(self.config, role).set(database=inventory['database'])
        engine = create_engine(url, echo=False, hide_parameters=True, poolclass=NullPool, connect_args=arguments)
        if engine.echo or not engine.hide_parameters or engine.logger.isEnabledFor(logging.DEBUG):
            engine.dispose()
            raise ValueError('Unsafe SQL logging')
        return engine

    def identity(self, connection, role, inventory=None, *, empty=False):
        cfg = inventory or self.config
        proof = self.m.inspect_connection(connection, cfg, role, revision=not empty, expected_revision=REVISION)
        require(role != 'admin' or proof['superuser'] is True, 'Approved admin authority required')
        cluster = connection.exec_driver_sql('SELECT system_identifier::text FROM pg_catalog.pg_control_system()').scalar_one()
        ssl = connection.exec_driver_sql('SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid=pg_backend_pid()').scalar_one()
        require(cluster == cfg['cluster_identifier'] and ssl is True, 'Cluster/TLS mismatch')
        require(connection.exec_driver_sql("SELECT nspowner::regrole::text FROM pg_catalog.pg_namespace WHERE nspname='public'").scalar_one() == 'ui47_migrator', 'Public schema owner mismatch')
        safe = connection.exec_driver_sql("""SELECT
            EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='ui47_migrator' AND rolcanlogin
                AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members WHERE member='ui47_migrator'::regrole)
            AND NOT has_schema_privilege('ui47_app','public','CREATE')
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n,
                LATERAL aclexplode(COALESCE(n.nspacl,acldefault('n',n.nspowner))) x
                WHERE n.nspname='public' AND x.grantee=0 AND x.privilege_type='CREATE')
            AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_default_acl
                WHERE defaclrole IN ('ui47_migrator'::regrole,'ui47_admin'::regrole)
                AND (defaclnamespace=0 OR defaclnamespace IN
                    (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname IN ('public','b2b_lock'))))""").scalar_one()
        require(safe is True, 'Unsafe migrator/schema/default ACL policy')
        require(connection.exec_driver_sql("SELECT count(*) FROM pg_catalog.pg_event_trigger WHERE evtenabled<>'D'").scalar_one() == 0, 'Active event trigger forbidden')
        require(connection.exec_driver_sql("SELECT count(*) FROM pg_catalog.pg_largeobject_metadata").scalar_one() == 0, 'Uninventoried large objects')
        schemas = set(connection.exec_driver_sql("SELECT nspname FROM pg_catalog.pg_namespace WHERE nspname !~ '^pg_' AND nspname<>'information_schema'").scalars())
        require(schemas <= {'public', 'b2b_lock'} and 'public' in schemas, 'Unexpected user schema')
        tables = dict(connection.exec_driver_sql("SELECT schemaname||'.'||tablename,tableowner FROM pg_catalog.pg_tables WHERE schemaname !~ '^pg_' AND schemaname<>'information_schema'").all())
        if empty:
            require(not tables and schemas == {'public'}, 'Restore destination is not empty')
            require(connection.exec_driver_sql("SELECT count(*) FROM pg_catalog.pg_class WHERE relnamespace='public'::regnamespace").scalar_one() == 0, 'Residual restore relation')
            require(connection.exec_driver_sql("SELECT count(*) FROM pg_catalog.pg_proc WHERE pronamespace='public'::regnamespace").scalar_one() == 0, 'Residual restore routine')
            require(connection.exec_driver_sql("SELECT count(*) FROM pg_catalog.pg_type WHERE typnamespace='public'::regnamespace").scalar_one() == 0, 'Residual restore type')
        else:
            require(tables == {'public.' + t: 'ui47_migrator' for t in self.tables}, 'Table inventory/owner mismatch')
            seq = dict(connection.exec_driver_sql("SELECT sequencename,sequenceowner FROM pg_catalog.pg_sequences WHERE schemaname='public'").all())
            require(seq == {s: 'ui47_migrator' for s in self.m.BUSINESS_SEQUENCES | self.m.B2B_SEQUENCES}, 'Sequence inventory/owner mismatch')
        return proof

    def state(self, connection):
        pair = connection.exec_driver_sql("SELECT to_regnamespace('b2b_lock')::text,to_regrole('ui47_b2b_lock_owner')::text").one()
        if tuple(pair) == (None, None):
            activation._inspect_target_acl(connection, profile=activation.PREPARATION)
            return 'absent'
        require(tuple(pair) == ('b2b_lock', locks.OWNER), 'Partial lock deployment')
        access = connection.exec_driver_sql("SELECT has_schema_privilege('ui47_app','b2b_lock','USAGE')").scalar_one()
        # Reuse the fixed named-role checks after qualified admin/migrator identity.
        activation._inspect_target_acl(connection, profile=activation.CANDIDATE if access else activation.PREPARATION)
        return 'granted' if access else 'closed'

    def snapshot(self, connection):
        """Protected values: no raw identity/session rows or role passwords in receipts."""
        result = {'industrial': self.m.b2b_snapshot(connection), 'b2b_rows': {}}
        import hashlib
        keys = {'local_users': 'id', 'external_identities': 'id', 'company_memberships': 'id',
                'membership_permissions': 'membership_id,permission', 'application_sessions': 'secret_digest',
                'oidc_transactions': 'transaction_id', 'alembic_version': 'version_num'}
        for table, key in keys.items():
            fingerprint, count = hashlib.sha256(), 0
            for row in connection.exec_driver_sql(f'SELECT row_to_json(t)::text FROM public.{table} t ORDER BY {key}').scalars():
                raw = row.encode('utf-8'); fingerprint.update(len(raw).to_bytes(8, 'big') + raw); count += 1
            result['b2b_rows'][table] = {'count': count, 'sha256': fingerprint.hexdigest()}
        queries = {
            'database': "SELECT datdba::regrole::text AS owner,datacl::text,pg_encoding_to_char(encoding) AS encoding,datlocprovider,datcollate,datctype,datlocale,datcollversion FROM pg_catalog.pg_database WHERE datname=current_database()",
            'extensions': "SELECT e.extname,e.extversion,e.extowner::regrole::text AS owner,n.nspname FROM pg_catalog.pg_extension e JOIN pg_catalog.pg_namespace n ON n.oid=e.extnamespace ORDER BY e.extname",
            'columns': """SELECT c.relname,c.relowner::regrole::text AS owner,c.relrowsecurity,c.relforcerowsecurity,
                a.attname,format_type(a.atttypid,a.atttypmod) AS type,a.attnotnull,pg_get_expr(d.adbin,d.adrelid) AS default_value
                FROM pg_catalog.pg_class c JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
                LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
                WHERE c.relnamespace='public'::regnamespace AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum""",
            'constraints': "SELECT c.relname,k.conname,pg_get_constraintdef(k.oid,true) AS definition,k.convalidated FROM pg_catalog.pg_constraint k JOIN pg_catalog.pg_class c ON c.oid=k.conrelid WHERE c.relnamespace='public'::regnamespace ORDER BY c.relname,k.conname",
            'indexes': "SELECT p.tablename,p.indexname,p.indexdef,i.indisvalid,i.indisready FROM pg_catalog.pg_indexes p JOIN pg_catalog.pg_class c ON c.relname=p.indexname AND c.relnamespace='public'::regnamespace JOIN pg_catalog.pg_index i ON i.indexrelid=c.oid WHERE p.schemaname='public' ORDER BY p.tablename,p.indexname",
            'triggers': "SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid,true) AS definition FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid WHERE c.relnamespace='public'::regnamespace AND NOT t.tgisinternal ORDER BY c.relname,t.tgname",
            'roles': f"SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls,rolconnlimit,rolvaliduntil FROM pg_catalog.pg_roles WHERE rolname<>'{locks.OWNER}' ORDER BY rolname",
            'memberships': "SELECT roleid::regrole::text AS role,member::regrole::text AS member,grantor::regrole::text AS grantor,admin_option,inherit_option,set_option FROM pg_catalog.pg_auth_members ORDER BY role,member,grantor",
            'defaults': "SELECT defaclrole::regrole::text AS role,COALESCE(n.nspname,'') AS schema,defaclobjtype,defaclacl::text FROM pg_catalog.pg_default_acl d LEFT JOIN pg_catalog.pg_namespace n ON n.oid=d.defaclnamespace ORDER BY role,schema,defaclobjtype",
            'sequences': "SELECT s.sequencename,s.sequenceowner,s.data_type::text,s.start_value,s.min_value,s.max_value,s.increment_by,s.cycle,s.cache_size,c.relacl::text AS acl FROM pg_catalog.pg_sequences s JOIN pg_catalog.pg_class c ON c.relname=s.sequencename AND c.relnamespace='public'::regnamespace WHERE s.schemaname='public' ORDER BY s.sequencename",
            'other_routines': "SELECT n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) AS args,p.proowner::regrole::text AS owner,p.proacl::text,p.proconfig,p.prosecdef,p.provolatile,p.proparallel,encode(sha256(convert_to(p.prosrc,'UTF8')),'hex') AS body_sha256 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' ORDER BY p.proname,args",
        }
        for name, sql in queries.items():
            result[name] = list(connection.exec_driver_sql('SELECT row_to_json(q)::text FROM (' + sql + ') q').scalars())
        result['sequence_values'] = {name: list(connection.exec_driver_sql(f'SELECT last_value,is_called FROM public.{name}').one())
                                     for name in sorted(self.m.BUSINESS_SEQUENCES | self.m.B2B_SEQUENCES)}
        return result

    def acl(self, connection):
        # OIDs are deliberately excluded: a restored database has different OIDs.
        query = """SELECT * FROM (
            SELECT 'schema' AS kind,n.nspname AS name,'' AS col,x.grantee,x.grantor,x.privilege_type,x.is_grantable
              FROM pg_catalog.pg_namespace n CROSS JOIN LATERAL aclexplode(COALESCE(n.nspacl,acldefault('n',n.nspowner))) x
              WHERE n.nspname IN ('public','b2b_lock')
            UNION ALL SELECT CASE WHEN c.relkind='S' THEN 'sequence' ELSE 'table' END,n.nspname||'.'||c.relname,'',x.grantee,x.grantor,x.privilege_type,x.is_grantable
              FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
              CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault(CASE WHEN c.relkind='S' THEN 'S'::\"char\" ELSE 'r'::\"char\" END,c.relowner))) x
              WHERE n.nspname IN ('public','b2b_lock') AND c.relkind IN ('r','p','S')
            UNION ALL SELECT 'column',n.nspname||'.'||c.relname,a.attname,x.grantee,x.grantor,x.privilege_type,x.is_grantable
              FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
              CROSS JOIN LATERAL aclexplode(a.attacl) x WHERE n.nspname IN ('public','b2b_lock') AND a.attnum>0 AND NOT a.attisdropped
            UNION ALL SELECT 'function',n.nspname||'.'||p.proname||'('||oidvectortypes(p.proargtypes)||')','',x.grantee,x.grantor,x.privilege_type,x.is_grantable
              FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
              CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) x WHERE n.nspname IN ('public','b2b_lock')
            ) a"""
        rows = connection.exec_driver_sql("SELECT kind,name,col,CASE WHEN grantee=0 THEN 'PUBLIC' ELSE grantee::regrole::text END,grantor::regrole::text,privilege_type,is_grantable FROM (" + query + ') q').all()
        # oidvectortypes inserts comma-space, unlike regprocedure input spellings.
        return sorted(tuple(str(v).replace(', ', ',') if i == 1 else v for i, v in enumerate(row)) for row in rows)

    def confirm(self, action, directory, **binding):
        token_plan = {'plan': self.plan, 'bundle': str(directory), **binding}
        import json
        # Public inventory and hashes only; never serialize the private config.
        print(json.dumps(token_plan, sort_keys=True, indent=2))
        self.m.b2b_confirm(action, token_plan, archive_hash=binding.get('archive_sha256', 'none'))

    def backup(self, directory):
        directory = self.directory(directory, existing=False)
        require(not directory.exists(), 'Never overwrite a backup bundle')
        self.confirm('BACKUP-B2B-LOCKS', directory)
        directory.mkdir()
        engine = self.engine('migrator')
        try:
            with engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
                with c.begin():
                    c.exec_driver_sql('SET TRANSACTION READ ONLY')
                    self.identity(c, 'migrator')
                    require(self.state(c) == 'absent', 'Backup requires pre-install baseline')
                    snapshot, acl = self.snapshot(c), self.acl(c)
                    require(all(row[3] == row[4] == 'ui47_migrator' for row in acl
                                if row[0] in ('table', 'column') and row[1] in {'public.' + t for t in self.m.B2B_TABLES}),
                            'Unexpected pre-existing B2B grant')
                    exported = c.exec_driver_sql('SELECT pg_export_snapshot()').scalar_one()
                    archive = directory / ARCHIVE
                    self.m.b2b_pgtool(self.config, 'pg_dump', ['--dbname=industrial_predict_dev', '--format=custom', '--snapshot=' + exported, '--file=' + str(archive)])
                    require(archive.is_file() and archive.stat().st_size > 0, 'Empty backup archive')
                    toc = self.m.b2b_pgtool(self.config, 'pg_restore', ['--list', str(archive)])
                    (directory / 'archive-toc.txt').write_bytes(toc)
                    self.m.b2b_pgtool(self.config, 'pg_restore', ['--file=' + str(directory / 'archive-readback.sql'), str(archive)])
                    require(self.snapshot(c) == snapshot and self.acl(c) == acl, 'Backup snapshot/sequence drift')
            return write_receipt(directory, 'backup', self.plan, archive_sha256=policy.file_digest(archive), snapshot=snapshot, acl=acl)
        finally:
            engine.dispose()

    def backup_evidence(self, directory):
        backup, stamp = read_receipt(directory / 'backup.json')
        require(backup['stage'] == 'backup' and backup['plan_sha256'] == digest(self.plan), 'Backup belongs to another plan')
        archive = directory / ARCHIVE
        require(archive.is_file() and not archive.is_symlink() and archive.resolve().parent == directory.resolve(), 'Invalid archive path')
        require(archive.stat().st_size > 0 and policy.file_digest(archive) == backup['archive_sha256'], 'Archive fingerprint mismatch')
        return backup, stamp

    def rehearse(self, directory):
        directory = self.directory(directory)
        backup, stamp = self.backup_evidence(directory)
        require(not (directory / 'restore-intent.json').exists(), 'No automatic repeat of restoration')
        destination = self.restore_inventory()
        self.confirm('RESTORE-ISOLATED-B2B-LOCKS', directory, backup_sha256=stamp,
                     archive_sha256=backup['archive_sha256'], restore_destination={k: destination[k] for k in ('database', 'database_oid', 'instance_id', 'cluster_identifier')})
        engine = self.engine('migrator', destination)
        try:
            with engine.connect() as c, c.begin():
                c.exec_driver_sql('SET TRANSACTION READ ONLY')
                self.identity(c, 'migrator', destination, empty=True)
            current, current_stamp = self.backup_evidence(directory)
            require(current == backup and current_stamp == stamp, 'Approved backup changed before restore')
            write_receipt(directory, 'restore-intent', self.plan, backup_sha256=stamp)
            self.m.b2b_pgtool(self.config, 'pg_restore', ['--dbname=' + destination['database'], '--exit-on-error', '--single-transaction', str(directory / ARCHIVE)])
            with engine.connect() as c, c.begin():
                c.exec_driver_sql('SET TRANSACTION READ ONLY')
                self.identity(c, 'migrator', destination)
                require(self.snapshot(c) == backup['snapshot'] and self.acl(c) == [tuple(r) for r in backup['acl']], 'Restore verification mismatch')
            self.backup_evidence(directory)
            return write_receipt(directory, 'restore', self.plan, backup_sha256=stamp, archive_sha256=backup['archive_sha256'],
                                 destination={k: destination[k] for k in ('database', 'database_oid', 'instance_id', 'cluster_identifier')}, verified=True)
        finally:
            engine.dispose()

    def evidence(self, directory):
        backup, backup_stamp = self.backup_evidence(directory)
        restored, restore_stamp = read_receipt(directory / 'restore.json')
        require(restored['stage'] == 'restore' and restored['plan_sha256'] == digest(self.plan) and restored['verified'] is True,
                'Unverified restoration')
        require(restored['backup_sha256'] == backup_stamp and restored['archive_sha256'] == backup['archive_sha256'], 'Restore/backup mismatch')
        destination = self.restore_inventory()
        require(restored['destination'] == {k: destination[k] for k in ('database', 'database_oid', 'instance_id', 'cluster_identifier')}, 'Restore inventory changed')
        require(datetime.fromisoformat(restored['created_at']) >= datetime.fromisoformat(backup['created_at']), 'Restore predates backup')
        return backup, {'backup_sha256': backup_stamp, 'restore_sha256': restore_stamp, 'archive_sha256': backup['archive_sha256']}

    def verify_restore(self, backup):
        destination = self.restore_inventory()
        engine = self.engine('migrator', destination)
        try:
            with engine.connect() as c, c.begin():
                c.exec_driver_sql('SET TRANSACTION READ ONLY')
                self.identity(c, 'migrator', destination)
                require(self.snapshot(c) == backup['snapshot'] and self.acl(c) == [tuple(r) for r in backup['acl']], 'Restored data changed')
        finally:
            engine.dispose()

    def installed_receipt(self, directory, stage, binding):
        receipt, stamp = read_receipt(directory / (stage + '.json'))
        require(receipt['stage'] == stage and receipt['plan_sha256'] == digest(self.plan) and receipt['binding'] == binding
                and receipt['commit_confirmed'] is True and receipt['postcheck_verified'] is True, 'Installed delta not proven')
        return stamp

    def object_ids(self, c):
        identities = {'role': c.exec_driver_sql(f"SELECT oid FROM pg_catalog.pg_roles WHERE rolname='{locks.OWNER}'").scalar_one(),
                      'schema': c.exec_driver_sql("SELECT oid FROM pg_catalog.pg_namespace WHERE nspname='b2b_lock'").scalar_one()}
        for f in locks.FUNCTIONS:
            identities[f['signature']] = c.exec_driver_sql(f"SELECT to_regprocedure('{f['signature']}')::oid").scalar_one()
        require(all(type(oid) is int and oid > 0 for oid in identities.values()), 'Missing installed object identity')
        return identities

    def dependencies(self, c):
        # DROP ... RESTRICT remains authoritative, including dependencies raced
        # after this check. Never remove unrelated dependencies to make it pass.
        require(c.exec_driver_sql(f"SELECT count(*) FROM pg_catalog.pg_shdepend WHERE refclassid='pg_authid'::regclass AND refobjid='{locks.OWNER}'::regrole AND dbid NOT IN (0,(SELECT oid FROM pg_catalog.pg_database WHERE datname=current_database()))").scalar_one() == 0,
                'Lock owner has dependencies in another database')
        signatures = ','.join("to_regprocedure('" + f['signature'] + "')" for f in locks.FUNCTIONS)
        require(c.exec_driver_sql(f"SELECT count(*) FROM pg_catalog.pg_proc WHERE proowner='{locks.OWNER}'::regrole AND oid NOT IN ({signatures})").scalar_one() == 0,
                'Unexpected routine owned by technical role')
        require(c.exec_driver_sql(f"SELECT count(*) FROM pg_catalog.pg_depend WHERE refclassid='pg_proc'::regclass AND refobjid IN ({signatures}) AND deptype='n'").scalar_one() == 0,
                'External function dependency')

    def transact(self, engine, work, postcheck):
        committed = False
        commit_attempted = False
        try:
            with engine.connect() as c:
                tx = c.begin()
                try:
                    result = work(c)
                except BaseException:
                    tx.rollback()
                    raise
                try:
                    commit_attempted = True
                    tx.commit()
                    committed = True
                except BaseException:
                    raise policy.CommitUncertain('B2B_LOCKS_COMMIT_UNCERTAIN; no retry') from None
            with engine.connect() as c, c.begin():
                c.exec_driver_sql('SET TRANSACTION READ ONLY')
                postcheck(c)
            return result
        except BaseException:
            if committed:
                raise policy.PostcheckFailed('B2B_LOCKS_COMMIT_CONFIRMED_POSTCHECK_FAILED; keep runtime closed') from None
            raise
        finally:
            try:
                engine.dispose()
            except BaseException:
                if committed:
                    raise policy.PostcheckFailed('B2B_LOCKS_DISPOSE_FAILED_AFTER_COMMIT') from None
                if commit_attempted:
                    raise policy.CommitUncertain('B2B_LOCKS_COMMIT_UNCERTAIN; disposal failed; no retry') from None
                raise

    def _step(self, directory, action, backup, binding):
        role = ACTION_ROLES[action]
        before, after = {'install': ('absent', 'closed'), 'grant': ('closed', 'granted'),
                         'rollback-acl': ('granted', 'closed'), 'remove': ('closed', 'absent')}[action]
        objects = None
        if action != 'install':
            self.installed_receipt(directory, 'install', binding)
            receipt, _ = read_receipt(directory / 'install.json')
            objects = receipt['objects']
        require(not (directory / ('intent-' + action + '.json')).exists(), 'Operation already attempted; no retry')
        write_receipt(directory, 'intent-' + action, self.plan, binding=binding)
        def verify(c, state):
            self.identity(c, role)
            require(self.state(c) == state, 'Unexpected deployment state')
            require(self.snapshot(c) == backup['snapshot'], 'Protected data/schema/roles/sequence drift')
            require(self.acl(c) == expected_acl(backup['acl'], state), 'Unapproved ACL delta')
            if state != 'absent' and objects is not None:
                require(self.object_ids(c) == objects, 'Installed objects replaced since stage A')
        def work(c):
            nonlocal objects
            c.exec_driver_sql("SET LOCAL lock_timeout='5s'")
            c.exec_driver_sql("SET LOCAL statement_timeout='15s'")
            require(c.exec_driver_sql('SELECT pg_try_advisory_xact_lock(474702,2)').scalar_one() is True, 'Another B2B operation is running')
            require(c.exec_driver_sql("SELECT count(*) FROM pg_catalog.pg_stat_activity WHERE datname=current_database() AND backend_type='client backend' AND pid<>pg_backend_pid()").scalar_one() == 0,
                    'Close other DEV client connections before deployment')
            c.exec_driver_sql('LOCK TABLE ' + ','.join('public.' + t for t in self.tables) + ' IN SHARE MODE')
            verify(c, before)
            current_backup, current_binding = self.evidence(directory)
            require(current_backup == backup and current_binding == binding, 'Approved evidence changed before write')
            if action == 'remove':
                self.dependencies(c)
                body = inverse_sql()
            else:
                name = {'install': 'b2b-lock-install.review.sql', 'grant': 'b2b-auth-grants.review.sql',
                        'rollback-acl': 'b2b-auth-revoke.review.sql'}[action]
                body = self.bodies[name]
            c.exec_driver_sql(body, execution_options={'no_parameters': True})
            if action == 'install':
                objects = self.object_ids(c)
            verify(c, after)
            return {'pre_state': before, 'post_state': after, 'objects': objects}
        result = self.transact(self.engine(role), work, lambda c: verify(c, after))
        # Independently verify actual app identity/ACL via its own credential.
        app = None
        try:
            try:
                app = self.engine('app')
                with app.connect() as c, c.begin():
                    c.exec_driver_sql('SET TRANSACTION READ ONLY')
                    self.m.inspect_runtime_connection(c, self.config)
                    self.m.inspect_runtime_schema(c, profile=activation.CANDIDATE if after == 'granted' else activation.PREPARATION)
            finally:
                if app is not None:
                    app.dispose()
        except BaseException:
            raise policy.PostcheckFailed('B2B_LOCKS_APP_POSTCHECK_FAILED; keep runtime closed') from None
        try:
            return write_receipt(directory, action, self.plan, binding=binding, commit_confirmed=True,
                                 postcheck_verified=True, **result)
        except BaseException:
            raise policy.PostcheckFailed('B2B_LOCKS_RECEIPT_FAILED_AFTER_COMMIT; no retry') from None

    def operate(self, directory, action):
        require(action in ('install', 'grant', 'rollback'), 'Unknown deployment action')
        directory = self.directory(directory)
        backup, binding = self.evidence(directory)
        require(not (directory / ('intent-' + action + '.json')).exists(), 'Operation already attempted; no retry')
        confirmations = dict(binding)
        if action != 'install':
            confirmations['install_receipt_sha256'] = self.installed_receipt(directory, 'install', binding)
        if action == 'grant':
            require(not any((directory / name).exists() for name in ('intent-remove.json', 'intent-rollback.json')), 'Rollback already started')
        if action == 'rollback' and (directory / 'intent-grant.json').exists():
            confirmations['grant_receipt_sha256'] = self.installed_receipt(directory, 'grant', binding)
        self.confirm({'install': 'INSTALL-B2B-LOCKS-A', 'grant': 'GRANT-B2B-LOCKS-B', 'rollback': 'ROLLBACK-B2B-LOCKS'}[action],
                     directory, **confirmations)
        self.verify_restore(backup)
        if action != 'rollback':
            return self._step(directory, action, backup, binding)
        # A single operator approval binds the bounded two-actor inverse. Each
        # acknowledged subcommit is recorded; any failure stops before next step.
        write_receipt(directory, 'intent-rollback', self.plan, binding=binding)
        if 'grant_receipt_sha256' in confirmations:
            self._step(directory, 'rollback-acl', backup, binding)
        result = self._step(directory, 'remove', backup, binding)
        try:
            return write_receipt(directory, 'rollback', self.plan, binding=binding, removed=True,
                                 commit_confirmed=True, postcheck_verified=True, final_state=result['post_state'])
        except BaseException:
            raise policy.PostcheckFailed('B2B_LOCKS_INVERSE_RECEIPT_FAILED_AFTER_COMMIT; no retry') from None
