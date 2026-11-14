"""Offline B2B ACL contract and read-only qualification; no engine or executor.

This candidate profile cannot start an application. Grants are column-scoped;
PostgreSQL requires real UPDATE authority for SELECT row-lock clauses.
"""
from sqlalchemy import text


PREPARATION = 'b2b-preparation'
CANDIDATE = 'b2b-auth-candidate'
ROLE = 'ui47_app'
TABLE_PRIVILEGES = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER', 'MAINTAIN')
COLUMN_PRIVILEGES = ('SELECT', 'INSERT', 'UPDATE', 'REFERENCES')
SESSION_COLUMNS = tuple('secret_digest csrf_digest user_id external_identity_id authenticated_at created_at '
    'last_activity_at absolute_expires_at idle_timeout_seconds absolute_timeout_seconds revoked_at replaced_by '
    'contract_version'.split())
OIDC_COLUMNS = tuple('transaction_id state_digest browser_binding_digest policy_digest nonce code_verifier '
    'issuer client_id callback_url return_target created_at expires_at contract_version'.split())
COLUMNS = {
    'local_users': ('id', 'state'),
    'external_identities': ('id', 'user_id', 'issuer', 'subject'),
    'company_memberships': ('id', 'user_id', 'company_id', 'state', 'role'),
    'membership_permissions': ('membership_id', 'permission', 'role'),
    'application_sessions': SESSION_COLUMNS,
    'oidc_transactions': OIDC_COLUMNS,
}


def require_profile(profile):
    if type(profile) is not str or profile not in (PREPARATION, CANDIDATE):
        raise ValueError('Unknown runtime profile')
    return profile


def require_preparation(config, profile=PREPARATION):
    require_profile(profile)
    if profile != PREPARATION or config.get('runtime_profile', PREPARATION) != PREPARATION:
        raise ValueError('B2B candidate is qualification-only; runtime activation unavailable')


def matrix(profile):
    require_profile(profile)
    result = {}
    for table, columns in COLUMNS.items():
        update = {'application_sessions': ('last_activity_at', 'revoked_at', 'replaced_by'),
                  'oidc_transactions': ('transaction_id',),
                  'membership_permissions': ('membership_id',)}.get(table, ('id',))
        result[table] = {
            'table': ['DELETE'] if profile == CANDIDATE and table == 'oidc_transactions' else [],
            'columns': {p: list(values) for p, values in (
                ('SELECT', columns),
                ('INSERT', columns if table in ('application_sessions', 'oidc_transactions') else ()),
                ('UPDATE', update), ('REFERENCES', ()))
                if profile == CANDIDATE and values},
        }
    return result


def inspect_acl(connection, *, profile):
    """Independent qualification on an actual ui47_app connection, after commit."""
    if connection.exec_driver_sql('SELECT current_user').scalar_one() != ROLE:
        raise ValueError('Only ui47_app can qualify B2B ACL')
    return _inspect_target_acl(connection, profile=profile)


def inspect_named_acl(connection, *, profile):
    """Owner transaction: inspect ui47_app explicitly without changing identity.

    The caller retains the existing destination/TLS/revision checks. This helper
    creates no engine, changes no role, and does not commit or grant anything.
    """
    if connection.exec_driver_sql('SELECT current_user').scalar_one() != 'ui47_migrator':
        raise ValueError('Owner connection required for precommit ACL check')
    return _inspect_target_acl(connection, profile=profile)


def _inspect_target_acl(connection, *, profile):
    expected = matrix(profile)
    if connection.execute(text("""SELECT count(*) FROM pg_catalog.pg_roles
        WHERE oid=to_regrole(:role) AND NOT (rolsuper OR rolcreatedb OR rolcreaterole
            OR rolreplication OR rolbypassrls)"""), {'role': ROLE}).scalar_one() != 1:
        raise ValueError('Missing or excessive application role')
    if connection.execute(text('SELECT count(*) FROM pg_catalog.pg_auth_members WHERE member=to_regrole(:role)'),
                          {'role': ROLE}).scalar_one() != 0:
        raise ValueError('Inherited or switchable roles forbidden')
    for table, columns in COLUMNS.items():
        params = {'name': 'public.' + table, 'role': ROLE}
        if connection.execute(text("""SELECT count(*) FROM pg_catalog.pg_class
            WHERE oid=to_regclass(:name) AND relowner='ui47_migrator'::regrole
            AND relkind='r' AND NOT relrowsecurity AND NOT relforcerowsecurity"""), params).scalar_one() != 1:
            raise ValueError('Unexpected B2B owner or relation policy')
        shape = connection.execute(text("""SELECT a.attname FROM pg_catalog.pg_attribute a
            WHERE a.attrelid=to_regclass(:name) AND a.attnum>0 AND NOT a.attisdropped
            ORDER BY a.attnum"""), params).scalars().all()
        if tuple(shape) != columns:
            raise ValueError('B2B column shape mismatch')
        # Null ACL means no explicit grants on a table/column. Owners are checked
        # by manage.inspect_runtime_schema; their implicit authority is separate.
        unsafe = connection.execute(text("""SELECT count(*) FROM (
            SELECT x.grantee,x.grantor,x.is_grantable FROM pg_catalog.pg_class c
              CROSS JOIN LATERAL aclexplode(c.relacl) x WHERE c.oid=to_regclass(:name)
            UNION ALL
            SELECT x.grantee,x.grantor,x.is_grantable FROM pg_catalog.pg_attribute a
              CROSS JOIN LATERAL aclexplode(a.attacl) x
              WHERE a.attrelid=to_regclass(:name) AND a.attnum>0
            ) grants WHERE grantee=0 OR (grantee=to_regrole(:role)
                AND (is_grantable OR grantor<>'ui47_migrator'::regrole))"""), params).scalar_one()
        if unsafe != 0:
            raise ValueError('PUBLIC or delegable/unapproved-grantor B2B ACL forbidden')
        for privilege in TABLE_PRIVILEGES:
            p = {**params, 'privilege': privilege}
            actual = connection.execute(text('SELECT has_table_privilege(:role,:name,:privilege)'), p).scalar_one()
            if actual is not (privilege in expected[table]['table']):
                raise ValueError('B2B table ACL mismatch')
        for column in columns:
            for privilege in COLUMN_PRIVILEGES:
                p = {**params, 'column': column, 'privilege': privilege}
                actual = connection.execute(text('SELECT has_column_privilege(:role,:name,:column,:privilege)'), p).scalar_one()
                if actual is not (column in expected[table]['columns'].get(privilege, ())):
                    raise ValueError('B2B column ACL mismatch')
    return {'acl_profile': profile, 'checked_role': ROLE, 'acl_exact': True, 'activation_available': False}


def _sql_text(value):
    return "'" + value.replace("'", "''") + "'"


def _sql_array(values):
    return 'ARRAY[' + ','.join(_sql_text(value) for value in values) + ']::text[]'


def acl_assertion_sql(profile):
    """Inline owner-side assertions, not a persistent function or role switch.

    Compare effective named-role rights and raw ACL provenance before AND after
    the delta. The immutable matrix is rendered as data, never request input.
    """
    expected = matrix(profile)
    records = []
    for table, columns in COLUMNS.items():
        rights = expected[table]
        records.append('    (' + ','.join([_sql_text(table), _sql_array(columns),
            _sql_array(rights['table']), *(_sql_array(rights['columns'].get(p, ()))
                                         for p in COLUMN_PRIVILEGES)]) + ')')
    records_sql = ',\n'.join(records)
    return f"""-- Named-role ACL assertion: {profile}; session identity remains ui47_migrator.
DO $acl$
DECLARE
  target_role constant text := 'ui47_app';
  item record;
  relation_name text;
  column_name text;
  privilege_name text;
  expected_columns text[];
BEGIN
  IF current_user <> 'ui47_migrator' THEN RAISE EXCEPTION 'Owner connection required'; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE oid=to_regrole(target_role)
      AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
    THEN RAISE EXCEPTION 'Missing or excessive application role'; END IF;
  IF EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members WHERE member=to_regrole(target_role))
    THEN RAISE EXCEPTION 'Inherited or switchable roles forbidden'; END IF;
  FOR item IN SELECT * FROM (VALUES
{records_sql}
  ) AS expected(table_name,all_columns,table_rights,select_columns,insert_columns,update_columns,reference_columns)
  LOOP
    relation_name := 'public.' || item.table_name;
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_class WHERE oid=to_regclass(relation_name)
        AND relowner='ui47_migrator'::regrole AND relkind='r' AND NOT relrowsecurity AND NOT relforcerowsecurity)
      THEN RAISE EXCEPTION 'Unexpected B2B owner or relation policy: %', relation_name; END IF;
    IF (SELECT array_agg(attname::text ORDER BY attnum) FROM pg_catalog.pg_attribute
        WHERE attrelid=to_regclass(relation_name) AND attnum>0 AND NOT attisdropped)
        IS DISTINCT FROM item.all_columns
      THEN RAISE EXCEPTION 'B2B column shape mismatch: %', relation_name; END IF;
    IF EXISTS (SELECT 1 FROM (
        SELECT x.grantee,x.grantor,x.is_grantable FROM pg_catalog.pg_class c
          CROSS JOIN LATERAL aclexplode(c.relacl) x WHERE c.oid=to_regclass(relation_name)
        UNION ALL
        SELECT x.grantee,x.grantor,x.is_grantable FROM pg_catalog.pg_attribute a
          CROSS JOIN LATERAL aclexplode(a.attacl) x WHERE a.attrelid=to_regclass(relation_name) AND a.attnum>0
      ) grants WHERE grantee=0 OR (grantee=to_regrole(target_role)
        AND (is_grantable OR grantor<>'ui47_migrator'::regrole)))
      THEN RAISE EXCEPTION 'Unsafe B2B ACL provenance: %', relation_name; END IF;
    FOREACH privilege_name IN ARRAY {_sql_array(TABLE_PRIVILEGES)} LOOP
      IF has_table_privilege(target_role,relation_name,privilege_name)
          IS DISTINCT FROM (privilege_name=ANY(item.table_rights))
        THEN RAISE EXCEPTION 'B2B table ACL mismatch: % %', relation_name,privilege_name; END IF;
    END LOOP;
    FOREACH column_name IN ARRAY item.all_columns LOOP
      FOREACH privilege_name IN ARRAY {_sql_array(COLUMN_PRIVILEGES)} LOOP
        expected_columns := CASE privilege_name
          WHEN 'SELECT' THEN item.select_columns WHEN 'INSERT' THEN item.insert_columns
          WHEN 'UPDATE' THEN item.update_columns WHEN 'REFERENCES' THEN item.reference_columns END;
        IF has_column_privilege(target_role,relation_name,column_name,privilege_name)
            IS DISTINCT FROM (column_name=ANY(expected_columns))
          THEN RAISE EXCEPTION 'B2B column ACL mismatch: % % %', relation_name,column_name,privilege_name; END IF;
      END LOOP;
    END LOOP;
  END LOOP;
END; $acl$;"""


def sql_delta(*, reverse=False):
    """Review template only: ROLLBACK is intentional; no executor is provided.

    Applicable solely to an independently captured, zero-B2B-ACL baseline, or
    its exact candidate successor. No REVOKE ALL/CASCADE/default ACL changes.
    """
    # Reuse the immutable approved DEV inventory, never a private config/secret.
    from b2b_policy import policy
    destination = policy()['destination']
    statements = ['-- REVIEW ONLY: qualify destination, grantor and exact ACL baseline first.',
                  '-- Approval required before replacing the final ROLLBACK with COMMIT.',
                  'BEGIN;', "SET LOCAL lock_timeout = '5s';", "SET LOCAL statement_timeout = '15s';",
                  "DO $guard$ BEGIN\n"
                  "  IF current_user <> 'ui47_migrator'\n"
                  "     OR current_database() <> 'industrial_predict_dev'\n"
                  "     OR (SELECT oid FROM pg_database WHERE datname=current_database()) <> 16384\n"
                  "     OR current_setting('server_version_num') <> '170010'\n"
                  "     OR current_setting('cluster_name') <> 'industrial-predict-development'\n"
                  f"     OR current_setting('app.development_instance_id',true) IS DISTINCT FROM '{destination['instance_id']}'\n"
                  f"     OR (SELECT system_identifier::text FROM pg_control_system()) <> '{destination['cluster_identifier']}'\n"
                  "     OR (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) IS DISTINCT FROM true\n"
                  "     OR (SELECT version_num FROM public.alembic_version) IS DISTINCT FROM 'b2b_0002_analyze'\n"
                  "  THEN RAISE EXCEPTION 'B2B ACL destination/role check failed'; END IF;\n"
                  "END; $guard$;",
                  acl_assertion_sql(CANDIDATE if reverse else PREPARATION)]
    for table, rights in matrix(CANDIDATE).items():
        for privilege in rights['table']:
            statements.append(f'{"REVOKE" if reverse else "GRANT"} {privilege} ON TABLE public.{table} '
                              f'{"FROM" if reverse else "TO"} {ROLE};')
        for privilege, columns in rights['columns'].items():
            statements.append(f'{"REVOKE" if reverse else "GRANT"} {privilege} ({", ".join(columns)}) '
                              f'ON TABLE public.{table} {"FROM" if reverse else "TO"} {ROLE};')
    statements.extend([acl_assertion_sql(PREPARATION if reverse else CANDIDATE),
                       '-- After an approved future COMMIT: independently qualify with a new official ui47_app connection.',
                       '-- A separate connection cannot see uncommitted grants. No runtime activation is provided.', 'ROLLBACK;'])
    return '\n'.join(statements)


def plan(*, profile):
    if require_profile(profile) != CANDIDATE:
        raise ValueError('Explicit candidate profile required for activation plan')
    return {'profile': profile, 'role': ROLE, 'revision': 'b2b_0002_analyze',
            'offline_only': True, 'activation_available': False,
            'google_routes_enabled': False, 'business_routes_enabled': False,
            'future_assembly': 'app.b2b_runtime.install_google_b2b (not imported or mounted)',
            'sequence_grants': [], 'matrix': matrix(profile),
            'grant_review_sql': sql_delta(), 'revoke_review_sql': sql_delta(reverse=True)}
