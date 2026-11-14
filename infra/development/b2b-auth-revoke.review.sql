-- REVIEW ONLY: qualify destination, grantor and exact ACL baseline first.
-- Approval required before replacing the final ROLLBACK with COMMIT.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '15s';
DO $guard$ BEGIN
  IF current_user <> 'ui47_migrator'
     OR current_database() <> 'industrial_predict_dev'
     OR (SELECT oid FROM pg_database WHERE datname=current_database()) <> 16384
     OR current_setting('server_version_num') <> '170010'
     OR current_setting('cluster_name') <> 'industrial-predict-development'
     OR current_setting('app.development_instance_id',true) IS DISTINCT FROM 'fb3284bd-fb7b-4c22-b620-96a1564b1d0c'
     OR (SELECT system_identifier::text FROM pg_control_system()) <> '7697614558579179559'
     OR (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) IS DISTINCT FROM true
     OR (SELECT version_num FROM public.alembic_version) IS DISTINCT FROM 'b2b_0002_analyze'
  THEN RAISE EXCEPTION 'B2B ACL destination/role check failed'; END IF;
END; $guard$;
-- Named-role ACL assertion: b2b-auth-candidate; session identity remains ui47_migrator.
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
    ('local_users',ARRAY['id','state']::text[],ARRAY[]::text[],ARRAY['id','state']::text[],ARRAY[]::text[],ARRAY['id']::text[],ARRAY[]::text[]),
    ('external_identities',ARRAY['id','user_id','issuer','subject']::text[],ARRAY[]::text[],ARRAY['id','user_id','issuer','subject']::text[],ARRAY[]::text[],ARRAY['id']::text[],ARRAY[]::text[]),
    ('company_memberships',ARRAY['id','user_id','company_id','state','role']::text[],ARRAY[]::text[],ARRAY['id','user_id','company_id','state','role']::text[],ARRAY[]::text[],ARRAY['id']::text[],ARRAY[]::text[]),
    ('membership_permissions',ARRAY['membership_id','permission','role']::text[],ARRAY[]::text[],ARRAY['membership_id','permission','role']::text[],ARRAY[]::text[],ARRAY['membership_id']::text[],ARRAY[]::text[]),
    ('application_sessions',ARRAY['secret_digest','csrf_digest','user_id','external_identity_id','authenticated_at','created_at','last_activity_at','absolute_expires_at','idle_timeout_seconds','absolute_timeout_seconds','revoked_at','replaced_by','contract_version']::text[],ARRAY[]::text[],ARRAY['secret_digest','csrf_digest','user_id','external_identity_id','authenticated_at','created_at','last_activity_at','absolute_expires_at','idle_timeout_seconds','absolute_timeout_seconds','revoked_at','replaced_by','contract_version']::text[],ARRAY['secret_digest','csrf_digest','user_id','external_identity_id','authenticated_at','created_at','last_activity_at','absolute_expires_at','idle_timeout_seconds','absolute_timeout_seconds','revoked_at','replaced_by','contract_version']::text[],ARRAY['last_activity_at','revoked_at','replaced_by']::text[],ARRAY[]::text[]),
    ('oidc_transactions',ARRAY['transaction_id','state_digest','browser_binding_digest','policy_digest','nonce','code_verifier','issuer','client_id','callback_url','return_target','created_at','expires_at','contract_version']::text[],ARRAY['DELETE']::text[],ARRAY['transaction_id','state_digest','browser_binding_digest','policy_digest','nonce','code_verifier','issuer','client_id','callback_url','return_target','created_at','expires_at','contract_version']::text[],ARRAY['transaction_id','state_digest','browser_binding_digest','policy_digest','nonce','code_verifier','issuer','client_id','callback_url','return_target','created_at','expires_at','contract_version']::text[],ARRAY['transaction_id']::text[],ARRAY[]::text[])
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
    FOREACH privilege_name IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN']::text[] LOOP
      IF has_table_privilege(target_role,relation_name,privilege_name)
          IS DISTINCT FROM (privilege_name=ANY(item.table_rights))
        THEN RAISE EXCEPTION 'B2B table ACL mismatch: % %', relation_name,privilege_name; END IF;
    END LOOP;
    FOREACH column_name IN ARRAY item.all_columns LOOP
      FOREACH privilege_name IN ARRAY ARRAY['SELECT','INSERT','UPDATE','REFERENCES']::text[] LOOP
        expected_columns := CASE privilege_name
          WHEN 'SELECT' THEN item.select_columns WHEN 'INSERT' THEN item.insert_columns
          WHEN 'UPDATE' THEN item.update_columns WHEN 'REFERENCES' THEN item.reference_columns END;
        IF has_column_privilege(target_role,relation_name,column_name,privilege_name)
            IS DISTINCT FROM (column_name=ANY(expected_columns))
          THEN RAISE EXCEPTION 'B2B column ACL mismatch: % % %', relation_name,column_name,privilege_name; END IF;
      END LOOP;
    END LOOP;
  END LOOP;
END; $acl$;
REVOKE SELECT (id, state) ON TABLE public.local_users FROM ui47_app;
REVOKE UPDATE (id) ON TABLE public.local_users FROM ui47_app;
REVOKE SELECT (id, user_id, issuer, subject) ON TABLE public.external_identities FROM ui47_app;
REVOKE UPDATE (id) ON TABLE public.external_identities FROM ui47_app;
REVOKE SELECT (id, user_id, company_id, state, role) ON TABLE public.company_memberships FROM ui47_app;
REVOKE UPDATE (id) ON TABLE public.company_memberships FROM ui47_app;
REVOKE SELECT (membership_id, permission, role) ON TABLE public.membership_permissions FROM ui47_app;
REVOKE UPDATE (membership_id) ON TABLE public.membership_permissions FROM ui47_app;
REVOKE SELECT (secret_digest, csrf_digest, user_id, external_identity_id, authenticated_at, created_at, last_activity_at, absolute_expires_at, idle_timeout_seconds, absolute_timeout_seconds, revoked_at, replaced_by, contract_version) ON TABLE public.application_sessions FROM ui47_app;
REVOKE INSERT (secret_digest, csrf_digest, user_id, external_identity_id, authenticated_at, created_at, last_activity_at, absolute_expires_at, idle_timeout_seconds, absolute_timeout_seconds, revoked_at, replaced_by, contract_version) ON TABLE public.application_sessions FROM ui47_app;
REVOKE UPDATE (last_activity_at, revoked_at, replaced_by) ON TABLE public.application_sessions FROM ui47_app;
REVOKE DELETE ON TABLE public.oidc_transactions FROM ui47_app;
REVOKE SELECT (transaction_id, state_digest, browser_binding_digest, policy_digest, nonce, code_verifier, issuer, client_id, callback_url, return_target, created_at, expires_at, contract_version) ON TABLE public.oidc_transactions FROM ui47_app;
REVOKE INSERT (transaction_id, state_digest, browser_binding_digest, policy_digest, nonce, code_verifier, issuer, client_id, callback_url, return_target, created_at, expires_at, contract_version) ON TABLE public.oidc_transactions FROM ui47_app;
REVOKE UPDATE (transaction_id) ON TABLE public.oidc_transactions FROM ui47_app;
-- Named-role ACL assertion: b2b-preparation; session identity remains ui47_migrator.
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
    ('local_users',ARRAY['id','state']::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[]),
    ('external_identities',ARRAY['id','user_id','issuer','subject']::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[]),
    ('company_memberships',ARRAY['id','user_id','company_id','state','role']::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[]),
    ('membership_permissions',ARRAY['membership_id','permission','role']::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[]),
    ('application_sessions',ARRAY['secret_digest','csrf_digest','user_id','external_identity_id','authenticated_at','created_at','last_activity_at','absolute_expires_at','idle_timeout_seconds','absolute_timeout_seconds','revoked_at','replaced_by','contract_version']::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[]),
    ('oidc_transactions',ARRAY['transaction_id','state_digest','browser_binding_digest','policy_digest','nonce','code_verifier','issuer','client_id','callback_url','return_target','created_at','expires_at','contract_version']::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[],ARRAY[]::text[])
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
    FOREACH privilege_name IN ARRAY ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN']::text[] LOOP
      IF has_table_privilege(target_role,relation_name,privilege_name)
          IS DISTINCT FROM (privilege_name=ANY(item.table_rights))
        THEN RAISE EXCEPTION 'B2B table ACL mismatch: % %', relation_name,privilege_name; END IF;
    END LOOP;
    FOREACH column_name IN ARRAY item.all_columns LOOP
      FOREACH privilege_name IN ARRAY ARRAY['SELECT','INSERT','UPDATE','REFERENCES']::text[] LOOP
        expected_columns := CASE privilege_name
          WHEN 'SELECT' THEN item.select_columns WHEN 'INSERT' THEN item.insert_columns
          WHEN 'UPDATE' THEN item.update_columns WHEN 'REFERENCES' THEN item.reference_columns END;
        IF has_column_privilege(target_role,relation_name,column_name,privilege_name)
            IS DISTINCT FROM (column_name=ANY(expected_columns))
          THEN RAISE EXCEPTION 'B2B column ACL mismatch: % % %', relation_name,column_name,privilege_name; END IF;
      END LOOP;
    END LOOP;
  END LOOP;
END; $acl$;
-- After an approved future COMMIT: independently qualify with a new official ui47_app connection.
-- A separate connection cannot see uncommitted grants. No runtime activation is provided.
ROLLBACK;
