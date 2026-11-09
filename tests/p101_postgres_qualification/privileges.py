"""Distinct P101 writer profile. No GRANT execution or B2B profile modification."""

from b2b_postgres_qualification import validation as v


TABLES = ('companies', 'sites', 'equipments', 'sensors', 'measurements',
    'maintenance_records', 'maintenance_recommendations', 'prediction_records', 'p101_prediction_operations')
INSERT_TABLES = frozenset(TABLES[:5] + TABLES[-2:])

SQL = """SELECT
 (SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)) AS memberships,
 has_schema_privilege(current_user,'public','USAGE') AS schema_usage,
 has_schema_privilege(current_user,'public','CREATE') AS schema_create,
 has_database_privilege(current_user,current_database(),'CREATE') AS database_create,
 has_database_privilege(current_user,current_database(),'TEMP') AS database_temp,
 (SELECT rolsuper FROM pg_roles WHERE rolname=current_user) AS superuser,
 (SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user) AS bypassrls,
 has_parameter_privilege(current_user,'session_replication_role','SET') AS replication_control,
 current_setting('session_replication_role') AS replication_role,
 (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))
 + (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
  WHERE n.nspname='public' AND p.proowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))
 + (SELECT count(*) FROM pg_namespace WHERE nspname='public' AND nspowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))
 + (SELECT count(*) FROM pg_database WHERE datname=current_database() AND datdba=(SELECT oid FROM pg_roles WHERE rolname=current_user)) AS owned,
 COALESCE((SELECT json_agg(x ORDER BY x.name) FROM (SELECT c.relname AS name,
  has_any_column_privilege(current_user,c.oid,'SELECT') AS sel,
  has_any_column_privilege(current_user,c.oid,'INSERT') AS ins,
  has_any_column_privilege(current_user,c.oid,'UPDATE') AS upd,
  has_table_privilege(current_user,c.oid,'DELETE') AS del,
  has_table_privilege(current_user,c.oid,'TRUNCATE') AS trunc,
  has_any_column_privilege(current_user,c.oid,'REFERENCES') AS ref,
  has_table_privilege(current_user,c.oid,'TRIGGER') AS trg,
  has_table_privilege(current_user,c.oid,'MAINTAIN') AS maintain
  FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r') x),'[]'::json) AS tables,
 COALESCE((SELECT json_agg(x ORDER BY x.name) FROM (SELECT c.relname AS name,
  has_sequence_privilege(current_user,c.oid,'USAGE') AS usage,
  has_sequence_privilege(current_user,c.oid,'SELECT') AS sel,
  has_sequence_privilege(current_user,c.oid,'UPDATE') AS upd
  FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='S') x),'[]'::json) AS sequences"""


def review(row, *, kind):
    v.require(kind in ('migrator', 'writer', 'observer'))
    v.require(type(row) is dict and set(row) == {'memberships', 'schema_usage', 'schema_create',
        'database_create', 'database_temp', 'superuser', 'bypassrls', 'replication_control',
        'replication_role', 'owned', 'tables', 'sequences'})
    v.require(type(row['memberships']) is int and row['memberships'] == 0
        and row['schema_usage'] is True and row['schema_create'] is (kind == 'migrator')
        and row['database_create'] is False and row['database_temp'] is False
        and row['superuser'] is False and row['bypassrls'] is False
        and row['replication_control'] is False and row['replication_role'] == 'origin')
    if kind == 'migrator':
        return  # DDL rights are further bound to the independently approved catalogue.
    v.require(type(row['owned']) is int and row['owned'] == 0 and type(row['tables']) is list)
    seen = set()
    for table in row['tables']:
        v.require(type(table) is dict and set(table) == {'name', 'sel', 'ins', 'upd', 'del', 'trunc', 'ref', 'trg', 'maintain'})
        name = table['name']
        v.require(type(name) is str and name not in seen)
        seen.add(name)
        expected = dict(sel=name in TABLES or name == 'alembic_version',
            ins=kind == 'writer' and name in INSERT_TABLES,
            maintain=kind == 'writer' and name in TABLES, upd=False, **{'del': False, 'trunc': False, 'ref': False, 'trg': False})
        v.require(all(type(table[key]) is bool and table[key] == value for key, value in expected.items()))
    v.require(set(TABLES).issubset(seen) and 'alembic_version' in seen)
    v.require(type(row['sequences']) is list)
    seen_sequences = set()
    for sequence in row['sequences']:
        v.require(type(sequence) is dict and set(sequence) == {'name', 'usage', 'sel', 'upd'})
        name = sequence['name']
        v.require(type(name) is str and name not in seen_sequences)
        seen_sequences.add(name)
        allowed = kind == 'writer' and name in {table + '_id_seq' for table in INSERT_TABLES}
        v.require(sequence['usage'] is allowed and sequence['sel'] is False and sequence['upd'] is False)
    v.require({table + '_id_seq' for table in INSERT_TABLES}.issubset(seen_sequences))


def review_rls(rows):
    """Only ordinary, unfiltered tables can support the row-count emptiness proof."""
    v.require(type(rows) is list and rows)
    seen = set()
    for row in rows:
        v.require(type(row) is dict and set(row) == {
            'table_name', 'row_security', 'force_row_security', 'policies'})
        name = row['table_name']
        v.require(type(name) is str and name not in seen)
        seen.add(name)
        v.require(type(row['row_security']) is bool and row['row_security'] is False
            and type(row['force_row_security']) is bool and row['force_row_security'] is False
            and type(row['policies']) is list and not row['policies'])
    v.require(set(TABLES).issubset(seen))
    return True


def grant_plan(campaign):
    """Fixed SQL for separately approved owner provisioning; never executed here."""
    v.validate_campaign(campaign)
    writer, reader = campaign.database + '_p101_writer', campaign.roles[3]
    tables = ','.join('public.' + name for name in TABLES)
    insert = ','.join('public.' + name for name in TABLES if name in INSERT_TABLES)
    sequences = ','.join('public.' + name + '_id_seq' for name in sorted(INSERT_TABLES))
    return (f'GRANT USAGE ON SCHEMA public TO {writer},{reader};',
        f'GRANT SELECT ON {tables},public.alembic_version TO {writer},{reader};',
        f'GRANT INSERT ON {insert} TO {writer};', f'GRANT MAINTAIN ON {tables} TO {writer};',
        f'GRANT USAGE ON SEQUENCE {sequences} TO {writer};')
