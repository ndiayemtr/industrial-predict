"""Closed, offline lock-function specification. Never connects or executes DDL."""
import hashlib

OWNER = 'ui47_b2b_lock_owner'
SCHEMA = 'b2b_lock'
OWNER_RIGHTS = {
    'local_users': (('id', 'state'), 'id'),
    'external_identities': (('id', 'user_id', 'issuer', 'subject'), 'id'),
    'company_memberships': (('id', 'user_id', 'company_id', 'state', 'role'), 'id'),
    'membership_permissions': (('membership_id', 'permission', 'role'), 'membership_id'),
    'oidc_transactions': (('transaction_id', 'state_digest', 'browser_binding_digest', 'policy_digest',
                           'contract_version', 'created_at', 'expires_at'), 'transaction_id'),
}


def _function(name, arguments, result, validation, query):
    body = "\nBEGIN\n  IF session_user <> 'ui47_app' THEN\n    RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='B2B_LOCK_CALLER_REJECTED';\n  END IF;\n"
    body += f"  IF {validation} THEN\n    RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='B2B_LOCK_ARGUMENT_REJECTED';\n  END IF;\n  RETURN QUERY {query};\nEND;\n"
    signature = SCHEMA + '.' + name + '(' + ','.join(t for _, t in arguments) + ')'
    return dict(name=name, arguments=arguments, result=result, body=body, signature=signature,
                sha256=hashlib.sha256(body.encode()).hexdigest())


FUNCTIONS = (
    _function('lock_user_v1', (('p_user_id','integer'),), 'TABLE(state text)',
        'p_user_id IS NULL OR p_user_id <= 0',
        'SELECT u.state::text FROM public.local_users AS u WHERE u.id=p_user_id FOR UPDATE OF u'),
    _function('lock_external_identity_v1', (('p_user_id','integer'), ('p_external_id','integer'),
        ('p_issuer','text'), ('p_subject','text')), 'TABLE(id integer, issuer text, subject text)',
        """p_user_id IS NULL OR p_user_id <= 0 OR NOT (
    (p_external_id IS NOT NULL AND p_external_id > 0 AND p_issuer IS NULL AND p_subject IS NULL)
    OR (p_external_id IS NULL AND p_issuer IS NOT NULL AND p_subject IS NOT NULL
      AND pg_catalog.length(p_issuer) BETWEEN 1 AND 2048 AND pg_catalog.length(p_subject) BETWEEN 1 AND 2048
      AND p_issuer=pg_catalog.btrim(p_issuer) AND p_subject=pg_catalog.btrim(p_subject)
      AND p_issuer !~ '[[:cntrl:]]' AND p_subject !~ '[[:cntrl:]]'))""",
        """SELECT e.id,e.issuer::text,e.subject::text FROM public.external_identities AS e
    WHERE e.user_id=p_user_id AND ((p_external_id IS NOT NULL AND e.id=p_external_id)
      OR (p_external_id IS NULL AND e.issuer=p_issuer AND e.subject=p_subject)) FOR SHARE OF e"""),
    _function('lock_memberships_v1', (('p_user_id','integer'),),
        'TABLE(id integer, user_id integer, company_id integer, state text, role text)',
        'p_user_id IS NULL OR p_user_id <= 0',
        """SELECT m.id,m.user_id,m.company_id,m.state::text,m.role::text FROM public.company_memberships AS m
    WHERE m.user_id=p_user_id ORDER BY m.id FOR SHARE OF m"""),
    _function('lock_membership_permissions_v1', (('p_user_id','integer'), ('p_membership_id','integer')),
        'TABLE(permission text, role text)',
        'p_user_id IS NULL OR p_user_id <= 0 OR p_membership_id IS NULL OR p_membership_id <= 0',
        """SELECT p.permission::text,p.role::text FROM public.membership_permissions AS p
    WHERE p.membership_id=p_membership_id AND EXISTS (SELECT 1 FROM public.company_memberships AS m
      WHERE m.id=p_membership_id AND m.user_id=p_user_id)
    ORDER BY p.permission FOR SHARE OF p"""),
    _function('lock_oidc_transaction_v1', (('p_state_digest','text'), ('p_browser_binding_digest','text'),
        ('p_policy_digest','text'), ('p_contract_version','text'), ('p_now','timestamp with time zone')),
        'TABLE(transaction_id text)',
        """p_state_digest IS NULL OR p_state_digest !~ '^[0-9a-f]{64}$'
    OR p_browser_binding_digest IS NULL OR p_browser_binding_digest !~ '^[0-9a-f]{64}$'
    OR p_policy_digest IS NULL OR p_policy_digest !~ '^[0-9a-f]{64}$'
    OR p_contract_version IS NULL OR pg_catalog.length(p_contract_version) NOT BETWEEN 1 AND 128
    OR p_now IS NULL OR NOT pg_catalog.isfinite(p_now)""",
        """SELECT t.transaction_id::text FROM public.oidc_transactions AS t
    WHERE t.state_digest=p_state_digest AND t.browser_binding_digest=p_browser_binding_digest
      AND t.policy_digest=p_policy_digest AND t.contract_version=p_contract_version
      AND t.created_at<=p_now AND t.expires_at>p_now FOR UPDATE OF t"""),
)


def install_sql():
    """Future admin review only. Requires separately approved destination guard."""
    from b2b_policy import policy
    destination = policy()['destination']
    lines = ["-- REVIEW ONLY. Never run as a runtime/migration side effect. Separate approval required.",
        '-- Qualify the exact DEV destination and verify-full transport before opening this transaction.',
        'BEGIN;', "SET LOCAL lock_timeout = '5s';", "SET LOCAL statement_timeout = '15s';",
        "DO $guard$ BEGIN IF current_user <> 'ui47_admin' OR NOT (SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname=current_user) THEN RAISE EXCEPTION 'Approved admin required'; END IF; END; $guard$;",
        "DO $target$ BEGIN IF current_database()<>'industrial_predict_dev' OR "
        "(SELECT oid FROM pg_catalog.pg_database WHERE datname=current_database())<>16384 OR "
        "current_setting('server_version_num')<>'170010' OR "
        "current_setting('cluster_name')<>'industrial-predict-development' OR "
        f"current_setting('app.development_instance_id',true) IS DISTINCT FROM '{destination['instance_id']}' OR "
        f"(SELECT system_identifier::text FROM pg_catalog.pg_control_system())<>'{destination['cluster_identifier']}' OR "
        "(SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid=pg_catalog.pg_backend_pid()) IS DISTINCT FROM true OR "
        "(SELECT version_num FROM public.alembic_version) IS DISTINCT FROM 'b2b_0002_analyze' "
        "THEN RAISE EXCEPTION 'Approved DEV destination required'; END IF; END; $target$;",
        f'CREATE ROLE {OWNER} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;',
        'CREATE SCHEMA b2b_lock AUTHORIZATION ui47_migrator;',
        f'GRANT USAGE ON SCHEMA public,b2b_lock TO {OWNER};']
    for table, (columns, key) in OWNER_RIGHTS.items():
        lines.extend([f'GRANT SELECT ({", ".join(columns)}) ON TABLE public.{table} TO {OWNER};',
                      f'GRANT UPDATE ({key}) ON TABLE public.{table} TO {OWNER};'])
    for f in FUNCTIONS:
        args = ', '.join(n+' '+t for n,t in f['arguments'])
        lines.extend([f"CREATE FUNCTION {SCHEMA}.{f['name']}({args}) RETURNS {f['result']}\n"
            'LANGUAGE plpgsql SECURITY DEFINER VOLATILE PARALLEL UNSAFE\n'
            f"SET search_path TO pg_catalog, pg_temp\nAS $body${f['body']}$body$;",
            f"ALTER FUNCTION {f['signature']} OWNER TO {OWNER};",
            f"REVOKE ALL ON FUNCTION {f['signature']} FROM PUBLIC;",
            # The table/schema migrator must be able to grant these exact EXECUTEs
            # later, without membership in the NOLOGIN function-owner role.
            f"GRANT EXECUTE ON FUNCTION {f['signature']} TO ui47_migrator WITH GRANT OPTION;"])
    from b2b_activation import COLUMNS
    lines.extend([assertion_sql(app_access=False, columns=COLUMNS),
                  '-- No USAGE/EXECUTE is granted to ui47_app by installation.', 'ROLLBACK;'])
    return '\n'.join(lines)


def checks(*, app_access, columns):
    """Scalar read-only checks, shared by Python inspection and inline SQL."""
    yield ("lock owner", f"SELECT count(*) FROM pg_catalog.pg_roles WHERE rolname='{OWNER}' AND NOT (rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)", 1)
    yield ("lock owner memberships", f"SELECT count(*) FROM pg_catalog.pg_auth_members WHERE member='{OWNER}'::regrole OR roleid='{OWNER}'::regrole", 0)
    yield ("lock schema owner", "SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname='b2b_lock' AND nspowner='ui47_migrator'::regrole", 1)
    yield ("lock schema public/delegation", "SELECT count(*) FROM pg_catalog.pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) x WHERE n.nspname='b2b_lock' AND (x.grantee=0 OR (x.grantee='ui47_app'::regrole AND x.is_grantable))", 0)
    yield ("lock schema usage", "SELECT has_schema_privilege('ui47_app','b2b_lock','USAGE')", app_access)
    yield ("lock schema create", "SELECT has_schema_privilege('ui47_app','b2b_lock','CREATE')", False)
    yield ("lock function count", "SELECT count(*) FROM pg_catalog.pg_proc WHERE pronamespace='b2b_lock'::regnamespace", 5)
    for f in FUNCTIONS:
        sig = f['signature']
        result_names = [part.strip().split()[0] for part in f['result'][6:-1].split(',')]
        argnames = ','.join(repr(name) for name,_ in f['arguments']) + ',' + ','.join(repr(name) for name in result_names)
        yield (sig, f"""SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_language l ON l.oid=p.prolang
            WHERE p.oid=to_regprocedure('{sig}') AND p.proowner='{OWNER}'::regrole AND p.prosecdef
            AND p.provolatile='v' AND p.proparallel='u' AND p.prokind='f' AND p.proretset AND NOT p.proisstrict
            AND NOT p.proleakproof AND l.lanname='plpgsql'
            AND p.pronargdefaults=0 AND p.provariadic=0 AND p.proargnames=ARRAY[{argnames}]::text[]
            AND p.proconfig=ARRAY['search_path=pg_catalog, pg_temp']::text[]
            AND pg_catalog.pg_get_function_result(p.oid)='{f['result']}'
            AND pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(p.prosrc,'UTF8')),'hex')='{f['sha256']}'""", 1)
        yield (sig+' execute', f"SELECT has_function_privilege('ui47_app','{sig}','EXECUTE')", app_access)
        yield (sig+' ACL', f"""SELECT count(*) FROM pg_catalog.pg_proc p CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) x
            WHERE p.oid=to_regprocedure('{sig}') AND NOT (
              (x.grantee='{OWNER}'::regrole AND x.privilege_type='EXECUTE') OR
              (x.grantee='ui47_migrator'::regrole AND x.grantor='{OWNER}'::regrole AND x.privilege_type='EXECUTE' AND x.is_grantable) OR
              (x.grantee='ui47_app'::regrole AND x.grantor='ui47_migrator'::regrole AND x.privilege_type='EXECUTE' AND NOT x.is_grantable))""", 0)
        yield (sig+' migrator delegation', f"SELECT has_function_privilege('ui47_migrator','{sig}','EXECUTE WITH GRANT OPTION')", True)
    for schema in ('public','b2b_lock'):
        yield (schema+' owner usage', f"SELECT has_schema_privilege('{OWNER}','{schema}','USAGE')", True)
        yield (schema+' owner create', f"SELECT has_schema_privilege('{OWNER}','{schema}','CREATE')", False)
    for privilege in ('CREATE','TEMP'):
        yield ('owner database '+privilege, f"SELECT has_database_privilege('{OWNER}',current_database(),'{privilege}')", False)
    for table, names in columns.items():
        reads, key = OWNER_RIGHTS.get(table, ((), None))
        for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN'):
            yield (table+' owner table '+privilege, f"SELECT has_table_privilege('{OWNER}','public.{table}','{privilege}')", False)
        for column in names:
            for privilege in ('SELECT','INSERT','UPDATE','REFERENCES'):
                wanted = (privilege=='SELECT' and column in reads) or (privilege=='UPDATE' and column==key)
                yield (table+' owner column '+column+' '+privilege,
                    f"SELECT has_column_privilege('{OWNER}','public.{table}','{column}','{privilege}')", wanted)
                yield (table+' owner delegation '+column+' '+privilege,
                    f"SELECT has_column_privilege('{OWNER}','public.{table}','{column}','{privilege} WITH GRANT OPTION')", False)
    yield ('owner other tables', f"""SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p','S') AND c.relname NOT IN ({','.join(repr(t) for t in columns)})
        AND CASE WHEN c.relkind='S' THEN has_sequence_privilege('{OWNER}',c.oid,'USAGE,SELECT,UPDATE')
          ELSE has_table_privilege('{OWNER}',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
            OR has_any_column_privilege('{OWNER}',c.oid,'SELECT,INSERT,UPDATE,REFERENCES') END""", 0)


def assertion_sql(*, app_access, columns):
    lines = ['DO $locks$ BEGIN']
    for label, query, wanted in checks(app_access=app_access, columns=columns):
        literal = ('true' if wanted else 'false') if type(wanted) is bool else str(wanted)
        lines.append(f"  IF ({query}) IS DISTINCT FROM {literal} THEN RAISE EXCEPTION 'B2B lock contract mismatch: {label}'; END IF;")
    lines.append('END; $locks$;')
    return '\n'.join(lines)
