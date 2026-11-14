-- REVIEW ONLY. Never run as a runtime/migration side effect. Separate approval required.
-- Qualify the exact DEV destination and verify-full transport before opening this transaction.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '15s';
DO $guard$ BEGIN IF current_user <> 'ui47_admin' OR NOT (SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname=current_user) THEN RAISE EXCEPTION 'Approved admin required'; END IF; END; $guard$;
DO $target$ BEGIN IF current_database()<>'industrial_predict_dev' OR (SELECT oid FROM pg_catalog.pg_database WHERE datname=current_database())<>16384 OR current_setting('server_version_num')<>'170010' OR current_setting('cluster_name')<>'industrial-predict-development' OR current_setting('app.development_instance_id',true) IS DISTINCT FROM 'fb3284bd-fb7b-4c22-b620-96a1564b1d0c' OR (SELECT system_identifier::text FROM pg_catalog.pg_control_system())<>'7697614558579179559' OR (SELECT ssl FROM pg_catalog.pg_stat_ssl WHERE pid=pg_catalog.pg_backend_pid()) IS DISTINCT FROM true OR (SELECT version_num FROM public.alembic_version) IS DISTINCT FROM 'b2b_0002_analyze' THEN RAISE EXCEPTION 'Approved DEV destination required'; END IF; END; $target$;
CREATE ROLE ui47_b2b_lock_owner NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE SCHEMA b2b_lock AUTHORIZATION ui47_migrator;
GRANT USAGE ON SCHEMA public,b2b_lock TO ui47_b2b_lock_owner;
GRANT SELECT (id, state) ON TABLE public.local_users TO ui47_b2b_lock_owner;
GRANT UPDATE (id) ON TABLE public.local_users TO ui47_b2b_lock_owner;
GRANT SELECT (id, user_id, issuer, subject) ON TABLE public.external_identities TO ui47_b2b_lock_owner;
GRANT UPDATE (id) ON TABLE public.external_identities TO ui47_b2b_lock_owner;
GRANT SELECT (id, user_id, company_id, state, role) ON TABLE public.company_memberships TO ui47_b2b_lock_owner;
GRANT UPDATE (id) ON TABLE public.company_memberships TO ui47_b2b_lock_owner;
GRANT SELECT (membership_id, permission, role) ON TABLE public.membership_permissions TO ui47_b2b_lock_owner;
GRANT UPDATE (membership_id) ON TABLE public.membership_permissions TO ui47_b2b_lock_owner;
GRANT SELECT (transaction_id, state_digest, browser_binding_digest, policy_digest, contract_version, created_at, expires_at) ON TABLE public.oidc_transactions TO ui47_b2b_lock_owner;
GRANT UPDATE (transaction_id) ON TABLE public.oidc_transactions TO ui47_b2b_lock_owner;
CREATE FUNCTION b2b_lock.lock_user_v1(p_user_id integer) RETURNS TABLE(state text)
LANGUAGE plpgsql SECURITY DEFINER VOLATILE PARALLEL UNSAFE
SET search_path TO pg_catalog, pg_temp
AS $body$
BEGIN
  IF session_user <> 'ui47_app' THEN
    RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='B2B_LOCK_CALLER_REJECTED';
  END IF;
  IF p_user_id IS NULL OR p_user_id <= 0 THEN
    RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='B2B_LOCK_ARGUMENT_REJECTED';
  END IF;
  RETURN QUERY SELECT u.state::text FROM public.local_users AS u WHERE u.id=p_user_id FOR UPDATE OF u;
END;
$body$;
ALTER FUNCTION b2b_lock.lock_user_v1(integer) OWNER TO ui47_b2b_lock_owner;
REVOKE ALL ON FUNCTION b2b_lock.lock_user_v1(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION b2b_lock.lock_user_v1(integer) TO ui47_migrator WITH GRANT OPTION;
CREATE FUNCTION b2b_lock.lock_external_identity_v1(p_user_id integer, p_external_id integer, p_issuer text, p_subject text) RETURNS TABLE(id integer, issuer text, subject text)
LANGUAGE plpgsql SECURITY DEFINER VOLATILE PARALLEL UNSAFE
SET search_path TO pg_catalog, pg_temp
AS $body$
BEGIN
  IF session_user <> 'ui47_app' THEN
    RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='B2B_LOCK_CALLER_REJECTED';
  END IF;
  IF p_user_id IS NULL OR p_user_id <= 0 OR NOT (
    (p_external_id IS NOT NULL AND p_external_id > 0 AND p_issuer IS NULL AND p_subject IS NULL)
    OR (p_external_id IS NULL AND p_issuer IS NOT NULL AND p_subject IS NOT NULL
      AND pg_catalog.length(p_issuer) BETWEEN 1 AND 2048 AND pg_catalog.length(p_subject) BETWEEN 1 AND 2048
      AND p_issuer=pg_catalog.btrim(p_issuer) AND p_subject=pg_catalog.btrim(p_subject)
      AND p_issuer !~ '[[:cntrl:]]' AND p_subject !~ '[[:cntrl:]]')) THEN
    RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='B2B_LOCK_ARGUMENT_REJECTED';
  END IF;
  RETURN QUERY SELECT e.id,e.issuer::text,e.subject::text FROM public.external_identities AS e
    WHERE e.user_id=p_user_id AND ((p_external_id IS NOT NULL AND e.id=p_external_id)
      OR (p_external_id IS NULL AND e.issuer=p_issuer AND e.subject=p_subject)) FOR SHARE OF e;
END;
$body$;
ALTER FUNCTION b2b_lock.lock_external_identity_v1(integer,integer,text,text) OWNER TO ui47_b2b_lock_owner;
REVOKE ALL ON FUNCTION b2b_lock.lock_external_identity_v1(integer,integer,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION b2b_lock.lock_external_identity_v1(integer,integer,text,text) TO ui47_migrator WITH GRANT OPTION;
CREATE FUNCTION b2b_lock.lock_memberships_v1(p_user_id integer) RETURNS TABLE(id integer, user_id integer, company_id integer, state text, role text)
LANGUAGE plpgsql SECURITY DEFINER VOLATILE PARALLEL UNSAFE
SET search_path TO pg_catalog, pg_temp
AS $body$
BEGIN
  IF session_user <> 'ui47_app' THEN
    RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='B2B_LOCK_CALLER_REJECTED';
  END IF;
  IF p_user_id IS NULL OR p_user_id <= 0 THEN
    RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='B2B_LOCK_ARGUMENT_REJECTED';
  END IF;
  RETURN QUERY SELECT m.id,m.user_id,m.company_id,m.state::text,m.role::text FROM public.company_memberships AS m
    WHERE m.user_id=p_user_id ORDER BY m.id FOR SHARE OF m;
END;
$body$;
ALTER FUNCTION b2b_lock.lock_memberships_v1(integer) OWNER TO ui47_b2b_lock_owner;
REVOKE ALL ON FUNCTION b2b_lock.lock_memberships_v1(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION b2b_lock.lock_memberships_v1(integer) TO ui47_migrator WITH GRANT OPTION;
CREATE FUNCTION b2b_lock.lock_membership_permissions_v1(p_user_id integer, p_membership_id integer) RETURNS TABLE(permission text, role text)
LANGUAGE plpgsql SECURITY DEFINER VOLATILE PARALLEL UNSAFE
SET search_path TO pg_catalog, pg_temp
AS $body$
BEGIN
  IF session_user <> 'ui47_app' THEN
    RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='B2B_LOCK_CALLER_REJECTED';
  END IF;
  IF p_user_id IS NULL OR p_user_id <= 0 OR p_membership_id IS NULL OR p_membership_id <= 0 THEN
    RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='B2B_LOCK_ARGUMENT_REJECTED';
  END IF;
  RETURN QUERY SELECT p.permission::text,p.role::text FROM public.membership_permissions AS p
    WHERE p.membership_id=p_membership_id AND EXISTS (SELECT 1 FROM public.company_memberships AS m
      WHERE m.id=p_membership_id AND m.user_id=p_user_id)
    ORDER BY p.permission FOR SHARE OF p;
END;
$body$;
ALTER FUNCTION b2b_lock.lock_membership_permissions_v1(integer,integer) OWNER TO ui47_b2b_lock_owner;
REVOKE ALL ON FUNCTION b2b_lock.lock_membership_permissions_v1(integer,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION b2b_lock.lock_membership_permissions_v1(integer,integer) TO ui47_migrator WITH GRANT OPTION;
CREATE FUNCTION b2b_lock.lock_oidc_transaction_v1(p_state_digest text, p_browser_binding_digest text, p_policy_digest text, p_contract_version text, p_now timestamp with time zone) RETURNS TABLE(transaction_id text)
LANGUAGE plpgsql SECURITY DEFINER VOLATILE PARALLEL UNSAFE
SET search_path TO pg_catalog, pg_temp
AS $body$
BEGIN
  IF session_user <> 'ui47_app' THEN
    RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='B2B_LOCK_CALLER_REJECTED';
  END IF;
  IF p_state_digest IS NULL OR p_state_digest !~ '^[0-9a-f]{64}$'
    OR p_browser_binding_digest IS NULL OR p_browser_binding_digest !~ '^[0-9a-f]{64}$'
    OR p_policy_digest IS NULL OR p_policy_digest !~ '^[0-9a-f]{64}$'
    OR p_contract_version IS NULL OR pg_catalog.length(p_contract_version) NOT BETWEEN 1 AND 128
    OR p_now IS NULL OR NOT pg_catalog.isfinite(p_now) THEN
    RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='B2B_LOCK_ARGUMENT_REJECTED';
  END IF;
  RETURN QUERY SELECT t.transaction_id::text FROM public.oidc_transactions AS t
    WHERE t.state_digest=p_state_digest AND t.browser_binding_digest=p_browser_binding_digest
      AND t.policy_digest=p_policy_digest AND t.contract_version=p_contract_version
      AND t.created_at<=p_now AND t.expires_at>p_now FOR UPDATE OF t;
END;
$body$;
ALTER FUNCTION b2b_lock.lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone) OWNER TO ui47_b2b_lock_owner;
REVOKE ALL ON FUNCTION b2b_lock.lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION b2b_lock.lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone) TO ui47_migrator WITH GRANT OPTION;
DO $locks$ BEGIN
  IF (SELECT count(*) FROM pg_catalog.pg_roles WHERE rolname='ui47_b2b_lock_owner' AND NOT (rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) IS DISTINCT FROM 1 THEN RAISE EXCEPTION 'B2B lock contract mismatch: lock owner'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_auth_members WHERE member='ui47_b2b_lock_owner'::regrole OR roleid='ui47_b2b_lock_owner'::regrole) IS DISTINCT FROM 0 THEN RAISE EXCEPTION 'B2B lock contract mismatch: lock owner memberships'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_namespace WHERE nspname='b2b_lock' AND nspowner='ui47_migrator'::regrole) IS DISTINCT FROM 1 THEN RAISE EXCEPTION 'B2B lock contract mismatch: lock schema owner'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_namespace n CROSS JOIN LATERAL aclexplode(n.nspacl) x WHERE n.nspname='b2b_lock' AND (x.grantee=0 OR (x.grantee='ui47_app'::regrole AND x.is_grantable))) IS DISTINCT FROM 0 THEN RAISE EXCEPTION 'B2B lock contract mismatch: lock schema public/delegation'; END IF;
  IF (SELECT has_schema_privilege('ui47_app','b2b_lock','USAGE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: lock schema usage'; END IF;
  IF (SELECT has_schema_privilege('ui47_app','b2b_lock','CREATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: lock schema create'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_proc WHERE pronamespace='b2b_lock'::regnamespace) IS DISTINCT FROM 5 THEN RAISE EXCEPTION 'B2B lock contract mismatch: lock function count'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_language l ON l.oid=p.prolang
            WHERE p.oid=to_regprocedure('b2b_lock.lock_user_v1(integer)') AND p.proowner='ui47_b2b_lock_owner'::regrole AND p.prosecdef
            AND p.provolatile='v' AND p.proparallel='u' AND p.prokind='f' AND p.proretset AND NOT p.proisstrict
            AND NOT p.proleakproof AND l.lanname='plpgsql'
            AND p.pronargdefaults=0 AND p.provariadic=0 AND p.proargnames=ARRAY['p_user_id','state']::text[]
            AND p.proconfig=ARRAY['search_path=pg_catalog, pg_temp']::text[]
            AND pg_catalog.pg_get_function_result(p.oid)='TABLE(state text)'
            AND pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(p.prosrc,'UTF8')),'hex')='5089ed5b36aa11c87cd77551fa2700e9717e475bb80810fdebf6a03a80103b58') IS DISTINCT FROM 1 THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_user_v1(integer)'; END IF;
  IF (SELECT has_function_privilege('ui47_app','b2b_lock.lock_user_v1(integer)','EXECUTE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_user_v1(integer) execute'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_proc p CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) x
            WHERE p.oid=to_regprocedure('b2b_lock.lock_user_v1(integer)') AND NOT (
              (x.grantee='ui47_b2b_lock_owner'::regrole AND x.privilege_type='EXECUTE') OR
              (x.grantee='ui47_migrator'::regrole AND x.grantor='ui47_b2b_lock_owner'::regrole AND x.privilege_type='EXECUTE' AND x.is_grantable) OR
              (x.grantee='ui47_app'::regrole AND x.grantor='ui47_migrator'::regrole AND x.privilege_type='EXECUTE' AND NOT x.is_grantable))) IS DISTINCT FROM 0 THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_user_v1(integer) ACL'; END IF;
  IF (SELECT has_function_privilege('ui47_migrator','b2b_lock.lock_user_v1(integer)','EXECUTE WITH GRANT OPTION')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_user_v1(integer) migrator delegation'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_language l ON l.oid=p.prolang
            WHERE p.oid=to_regprocedure('b2b_lock.lock_external_identity_v1(integer,integer,text,text)') AND p.proowner='ui47_b2b_lock_owner'::regrole AND p.prosecdef
            AND p.provolatile='v' AND p.proparallel='u' AND p.prokind='f' AND p.proretset AND NOT p.proisstrict
            AND NOT p.proleakproof AND l.lanname='plpgsql'
            AND p.pronargdefaults=0 AND p.provariadic=0 AND p.proargnames=ARRAY['p_user_id','p_external_id','p_issuer','p_subject','id','issuer','subject']::text[]
            AND p.proconfig=ARRAY['search_path=pg_catalog, pg_temp']::text[]
            AND pg_catalog.pg_get_function_result(p.oid)='TABLE(id integer, issuer text, subject text)'
            AND pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(p.prosrc,'UTF8')),'hex')='9479d7977325e15ef91e5496cd8d9b8a3729cb6afce4677887372935486b91a5') IS DISTINCT FROM 1 THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_external_identity_v1(integer,integer,text,text)'; END IF;
  IF (SELECT has_function_privilege('ui47_app','b2b_lock.lock_external_identity_v1(integer,integer,text,text)','EXECUTE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_external_identity_v1(integer,integer,text,text) execute'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_proc p CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) x
            WHERE p.oid=to_regprocedure('b2b_lock.lock_external_identity_v1(integer,integer,text,text)') AND NOT (
              (x.grantee='ui47_b2b_lock_owner'::regrole AND x.privilege_type='EXECUTE') OR
              (x.grantee='ui47_migrator'::regrole AND x.grantor='ui47_b2b_lock_owner'::regrole AND x.privilege_type='EXECUTE' AND x.is_grantable) OR
              (x.grantee='ui47_app'::regrole AND x.grantor='ui47_migrator'::regrole AND x.privilege_type='EXECUTE' AND NOT x.is_grantable))) IS DISTINCT FROM 0 THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_external_identity_v1(integer,integer,text,text) ACL'; END IF;
  IF (SELECT has_function_privilege('ui47_migrator','b2b_lock.lock_external_identity_v1(integer,integer,text,text)','EXECUTE WITH GRANT OPTION')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_external_identity_v1(integer,integer,text,text) migrator delegation'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_language l ON l.oid=p.prolang
            WHERE p.oid=to_regprocedure('b2b_lock.lock_memberships_v1(integer)') AND p.proowner='ui47_b2b_lock_owner'::regrole AND p.prosecdef
            AND p.provolatile='v' AND p.proparallel='u' AND p.prokind='f' AND p.proretset AND NOT p.proisstrict
            AND NOT p.proleakproof AND l.lanname='plpgsql'
            AND p.pronargdefaults=0 AND p.provariadic=0 AND p.proargnames=ARRAY['p_user_id','id','user_id','company_id','state','role']::text[]
            AND p.proconfig=ARRAY['search_path=pg_catalog, pg_temp']::text[]
            AND pg_catalog.pg_get_function_result(p.oid)='TABLE(id integer, user_id integer, company_id integer, state text, role text)'
            AND pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(p.prosrc,'UTF8')),'hex')='167455a168274e4bfa3b0d8250560db0ce11067f3b1af33c7e24979c9aac87bd') IS DISTINCT FROM 1 THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_memberships_v1(integer)'; END IF;
  IF (SELECT has_function_privilege('ui47_app','b2b_lock.lock_memberships_v1(integer)','EXECUTE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_memberships_v1(integer) execute'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_proc p CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) x
            WHERE p.oid=to_regprocedure('b2b_lock.lock_memberships_v1(integer)') AND NOT (
              (x.grantee='ui47_b2b_lock_owner'::regrole AND x.privilege_type='EXECUTE') OR
              (x.grantee='ui47_migrator'::regrole AND x.grantor='ui47_b2b_lock_owner'::regrole AND x.privilege_type='EXECUTE' AND x.is_grantable) OR
              (x.grantee='ui47_app'::regrole AND x.grantor='ui47_migrator'::regrole AND x.privilege_type='EXECUTE' AND NOT x.is_grantable))) IS DISTINCT FROM 0 THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_memberships_v1(integer) ACL'; END IF;
  IF (SELECT has_function_privilege('ui47_migrator','b2b_lock.lock_memberships_v1(integer)','EXECUTE WITH GRANT OPTION')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_memberships_v1(integer) migrator delegation'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_language l ON l.oid=p.prolang
            WHERE p.oid=to_regprocedure('b2b_lock.lock_membership_permissions_v1(integer,integer)') AND p.proowner='ui47_b2b_lock_owner'::regrole AND p.prosecdef
            AND p.provolatile='v' AND p.proparallel='u' AND p.prokind='f' AND p.proretset AND NOT p.proisstrict
            AND NOT p.proleakproof AND l.lanname='plpgsql'
            AND p.pronargdefaults=0 AND p.provariadic=0 AND p.proargnames=ARRAY['p_user_id','p_membership_id','permission','role']::text[]
            AND p.proconfig=ARRAY['search_path=pg_catalog, pg_temp']::text[]
            AND pg_catalog.pg_get_function_result(p.oid)='TABLE(permission text, role text)'
            AND pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(p.prosrc,'UTF8')),'hex')='9e2227b3a60787373ae3ffcb1ee2b15b02aa21f10758446d08e4b04da4454059') IS DISTINCT FROM 1 THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_membership_permissions_v1(integer,integer)'; END IF;
  IF (SELECT has_function_privilege('ui47_app','b2b_lock.lock_membership_permissions_v1(integer,integer)','EXECUTE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_membership_permissions_v1(integer,integer) execute'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_proc p CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) x
            WHERE p.oid=to_regprocedure('b2b_lock.lock_membership_permissions_v1(integer,integer)') AND NOT (
              (x.grantee='ui47_b2b_lock_owner'::regrole AND x.privilege_type='EXECUTE') OR
              (x.grantee='ui47_migrator'::regrole AND x.grantor='ui47_b2b_lock_owner'::regrole AND x.privilege_type='EXECUTE' AND x.is_grantable) OR
              (x.grantee='ui47_app'::regrole AND x.grantor='ui47_migrator'::regrole AND x.privilege_type='EXECUTE' AND NOT x.is_grantable))) IS DISTINCT FROM 0 THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_membership_permissions_v1(integer,integer) ACL'; END IF;
  IF (SELECT has_function_privilege('ui47_migrator','b2b_lock.lock_membership_permissions_v1(integer,integer)','EXECUTE WITH GRANT OPTION')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_membership_permissions_v1(integer,integer) migrator delegation'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_language l ON l.oid=p.prolang
            WHERE p.oid=to_regprocedure('b2b_lock.lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone)') AND p.proowner='ui47_b2b_lock_owner'::regrole AND p.prosecdef
            AND p.provolatile='v' AND p.proparallel='u' AND p.prokind='f' AND p.proretset AND NOT p.proisstrict
            AND NOT p.proleakproof AND l.lanname='plpgsql'
            AND p.pronargdefaults=0 AND p.provariadic=0 AND p.proargnames=ARRAY['p_state_digest','p_browser_binding_digest','p_policy_digest','p_contract_version','p_now','transaction_id']::text[]
            AND p.proconfig=ARRAY['search_path=pg_catalog, pg_temp']::text[]
            AND pg_catalog.pg_get_function_result(p.oid)='TABLE(transaction_id text)'
            AND pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(p.prosrc,'UTF8')),'hex')='ba755fbf2f7c0a6a2412ef38415d2be316d9d18fbcd60150f1311154dd4069af') IS DISTINCT FROM 1 THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone)'; END IF;
  IF (SELECT has_function_privilege('ui47_app','b2b_lock.lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone)','EXECUTE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone) execute'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_proc p CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) x
            WHERE p.oid=to_regprocedure('b2b_lock.lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone)') AND NOT (
              (x.grantee='ui47_b2b_lock_owner'::regrole AND x.privilege_type='EXECUTE') OR
              (x.grantee='ui47_migrator'::regrole AND x.grantor='ui47_b2b_lock_owner'::regrole AND x.privilege_type='EXECUTE' AND x.is_grantable) OR
              (x.grantee='ui47_app'::regrole AND x.grantor='ui47_migrator'::regrole AND x.privilege_type='EXECUTE' AND NOT x.is_grantable))) IS DISTINCT FROM 0 THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone) ACL'; END IF;
  IF (SELECT has_function_privilege('ui47_migrator','b2b_lock.lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone)','EXECUTE WITH GRANT OPTION')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock.lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone) migrator delegation'; END IF;
  IF (SELECT has_schema_privilege('ui47_b2b_lock_owner','public','USAGE')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: public owner usage'; END IF;
  IF (SELECT has_schema_privilege('ui47_b2b_lock_owner','public','CREATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: public owner create'; END IF;
  IF (SELECT has_schema_privilege('ui47_b2b_lock_owner','b2b_lock','USAGE')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock owner usage'; END IF;
  IF (SELECT has_schema_privilege('ui47_b2b_lock_owner','b2b_lock','CREATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: b2b_lock owner create'; END IF;
  IF (SELECT has_database_privilege('ui47_b2b_lock_owner',current_database(),'CREATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: owner database CREATE'; END IF;
  IF (SELECT has_database_privilege('ui47_b2b_lock_owner',current_database(),'TEMP')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: owner database TEMP'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.local_users','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner table SELECT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.local_users','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner table INSERT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.local_users','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner table UPDATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.local_users','DELETE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner table DELETE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.local_users','TRUNCATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner table TRUNCATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.local_users','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner table REFERENCES'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.local_users','TRIGGER')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner table TRIGGER'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.local_users','MAINTAIN')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner table MAINTAIN'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','id','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner column id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','id','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner delegation id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','id','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner column id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','id','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner delegation id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','id','UPDATE')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner column id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','id','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner delegation id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','id','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner column id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','id','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner delegation id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','state','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner column state SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','state','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner delegation state SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','state','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner column state INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','state','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner delegation state INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','state','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner column state UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','state','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner delegation state UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','state','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner column state REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.local_users','state','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: local_users owner delegation state REFERENCES'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.external_identities','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner table SELECT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.external_identities','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner table INSERT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.external_identities','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner table UPDATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.external_identities','DELETE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner table DELETE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.external_identities','TRUNCATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner table TRUNCATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.external_identities','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner table REFERENCES'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.external_identities','TRIGGER')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner table TRIGGER'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.external_identities','MAINTAIN')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner table MAINTAIN'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','id','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','id','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','id','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','id','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','id','UPDATE')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','id','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','id','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','id','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','user_id','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column user_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','user_id','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation user_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','user_id','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column user_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','user_id','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation user_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','user_id','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column user_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','user_id','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation user_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','user_id','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column user_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','user_id','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation user_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','issuer','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column issuer SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','issuer','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation issuer SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','issuer','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column issuer INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','issuer','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation issuer INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','issuer','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column issuer UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','issuer','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation issuer UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','issuer','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column issuer REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','issuer','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation issuer REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','subject','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column subject SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','subject','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation subject SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','subject','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column subject INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','subject','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation subject INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','subject','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column subject UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','subject','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation subject UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','subject','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner column subject REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.external_identities','subject','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: external_identities owner delegation subject REFERENCES'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.company_memberships','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner table SELECT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.company_memberships','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner table INSERT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.company_memberships','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner table UPDATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.company_memberships','DELETE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner table DELETE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.company_memberships','TRUNCATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner table TRUNCATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.company_memberships','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner table REFERENCES'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.company_memberships','TRIGGER')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner table TRIGGER'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.company_memberships','MAINTAIN')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner table MAINTAIN'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','id','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','id','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','id','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','id','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','id','UPDATE')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','id','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','id','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','id','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','user_id','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column user_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','user_id','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation user_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','user_id','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column user_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','user_id','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation user_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','user_id','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column user_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','user_id','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation user_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','user_id','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column user_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','user_id','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation user_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','company_id','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column company_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','company_id','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation company_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','company_id','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column company_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','company_id','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation company_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','company_id','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column company_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','company_id','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation company_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','company_id','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column company_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','company_id','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation company_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','state','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column state SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','state','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation state SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','state','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column state INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','state','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation state INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','state','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column state UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','state','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation state UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','state','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column state REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','state','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation state REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','role','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column role SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','role','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation role SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','role','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column role INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','role','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation role INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','role','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column role UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','role','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation role UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','role','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner column role REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.company_memberships','role','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: company_memberships owner delegation role REFERENCES'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.membership_permissions','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner table SELECT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.membership_permissions','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner table INSERT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.membership_permissions','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner table UPDATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.membership_permissions','DELETE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner table DELETE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.membership_permissions','TRUNCATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner table TRUNCATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.membership_permissions','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner table REFERENCES'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.membership_permissions','TRIGGER')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner table TRIGGER'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.membership_permissions','MAINTAIN')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner table MAINTAIN'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','membership_id','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column membership_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','membership_id','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation membership_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','membership_id','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column membership_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','membership_id','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation membership_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','membership_id','UPDATE')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column membership_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','membership_id','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation membership_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','membership_id','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column membership_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','membership_id','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation membership_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','permission','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column permission SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','permission','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation permission SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','permission','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column permission INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','permission','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation permission INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','permission','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column permission UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','permission','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation permission UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','permission','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column permission REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','permission','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation permission REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','role','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column role SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','role','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation role SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','role','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column role INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','role','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation role INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','role','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column role UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','role','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation role UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','role','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner column role REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.membership_permissions','role','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: membership_permissions owner delegation role REFERENCES'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.application_sessions','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner table SELECT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.application_sessions','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner table INSERT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.application_sessions','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner table UPDATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.application_sessions','DELETE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner table DELETE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.application_sessions','TRUNCATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner table TRUNCATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.application_sessions','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner table REFERENCES'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.application_sessions','TRIGGER')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner table TRIGGER'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.application_sessions','MAINTAIN')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner table MAINTAIN'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','secret_digest','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column secret_digest SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','secret_digest','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation secret_digest SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','secret_digest','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column secret_digest INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','secret_digest','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation secret_digest INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','secret_digest','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column secret_digest UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','secret_digest','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation secret_digest UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','secret_digest','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column secret_digest REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','secret_digest','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation secret_digest REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','csrf_digest','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column csrf_digest SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','csrf_digest','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation csrf_digest SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','csrf_digest','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column csrf_digest INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','csrf_digest','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation csrf_digest INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','csrf_digest','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column csrf_digest UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','csrf_digest','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation csrf_digest UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','csrf_digest','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column csrf_digest REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','csrf_digest','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation csrf_digest REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','user_id','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column user_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','user_id','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation user_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','user_id','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column user_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','user_id','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation user_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','user_id','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column user_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','user_id','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation user_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','user_id','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column user_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','user_id','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation user_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','external_identity_id','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column external_identity_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','external_identity_id','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation external_identity_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','external_identity_id','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column external_identity_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','external_identity_id','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation external_identity_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','external_identity_id','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column external_identity_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','external_identity_id','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation external_identity_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','external_identity_id','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column external_identity_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','external_identity_id','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation external_identity_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','authenticated_at','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column authenticated_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','authenticated_at','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation authenticated_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','authenticated_at','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column authenticated_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','authenticated_at','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation authenticated_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','authenticated_at','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column authenticated_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','authenticated_at','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation authenticated_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','authenticated_at','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column authenticated_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','authenticated_at','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation authenticated_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','created_at','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column created_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','created_at','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation created_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','created_at','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column created_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','created_at','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation created_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','created_at','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column created_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','created_at','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation created_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','created_at','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column created_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','created_at','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation created_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','last_activity_at','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column last_activity_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','last_activity_at','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation last_activity_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','last_activity_at','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column last_activity_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','last_activity_at','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation last_activity_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','last_activity_at','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column last_activity_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','last_activity_at','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation last_activity_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','last_activity_at','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column last_activity_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','last_activity_at','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation last_activity_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_expires_at','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column absolute_expires_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_expires_at','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation absolute_expires_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_expires_at','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column absolute_expires_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_expires_at','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation absolute_expires_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_expires_at','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column absolute_expires_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_expires_at','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation absolute_expires_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_expires_at','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column absolute_expires_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_expires_at','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation absolute_expires_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','idle_timeout_seconds','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column idle_timeout_seconds SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','idle_timeout_seconds','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation idle_timeout_seconds SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','idle_timeout_seconds','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column idle_timeout_seconds INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','idle_timeout_seconds','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation idle_timeout_seconds INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','idle_timeout_seconds','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column idle_timeout_seconds UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','idle_timeout_seconds','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation idle_timeout_seconds UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','idle_timeout_seconds','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column idle_timeout_seconds REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','idle_timeout_seconds','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation idle_timeout_seconds REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_timeout_seconds','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column absolute_timeout_seconds SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_timeout_seconds','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation absolute_timeout_seconds SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_timeout_seconds','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column absolute_timeout_seconds INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_timeout_seconds','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation absolute_timeout_seconds INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_timeout_seconds','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column absolute_timeout_seconds UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_timeout_seconds','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation absolute_timeout_seconds UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_timeout_seconds','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column absolute_timeout_seconds REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','absolute_timeout_seconds','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation absolute_timeout_seconds REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','revoked_at','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column revoked_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','revoked_at','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation revoked_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','revoked_at','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column revoked_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','revoked_at','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation revoked_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','revoked_at','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column revoked_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','revoked_at','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation revoked_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','revoked_at','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column revoked_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','revoked_at','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation revoked_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','replaced_by','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column replaced_by SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','replaced_by','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation replaced_by SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','replaced_by','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column replaced_by INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','replaced_by','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation replaced_by INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','replaced_by','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column replaced_by UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','replaced_by','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation replaced_by UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','replaced_by','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column replaced_by REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','replaced_by','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation replaced_by REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','contract_version','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column contract_version SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','contract_version','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation contract_version SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','contract_version','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column contract_version INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','contract_version','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation contract_version INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','contract_version','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column contract_version UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','contract_version','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation contract_version UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','contract_version','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner column contract_version REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.application_sessions','contract_version','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: application_sessions owner delegation contract_version REFERENCES'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.oidc_transactions','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner table SELECT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.oidc_transactions','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner table INSERT'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.oidc_transactions','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner table UPDATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.oidc_transactions','DELETE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner table DELETE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.oidc_transactions','TRUNCATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner table TRUNCATE'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.oidc_transactions','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner table REFERENCES'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.oidc_transactions','TRIGGER')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner table TRIGGER'; END IF;
  IF (SELECT has_table_privilege('ui47_b2b_lock_owner','public.oidc_transactions','MAINTAIN')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner table MAINTAIN'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','transaction_id','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column transaction_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','transaction_id','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation transaction_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','transaction_id','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column transaction_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','transaction_id','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation transaction_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','transaction_id','UPDATE')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column transaction_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','transaction_id','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation transaction_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','transaction_id','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column transaction_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','transaction_id','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation transaction_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','state_digest','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column state_digest SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','state_digest','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation state_digest SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','state_digest','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column state_digest INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','state_digest','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation state_digest INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','state_digest','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column state_digest UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','state_digest','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation state_digest UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','state_digest','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column state_digest REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','state_digest','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation state_digest REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','browser_binding_digest','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column browser_binding_digest SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','browser_binding_digest','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation browser_binding_digest SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','browser_binding_digest','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column browser_binding_digest INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','browser_binding_digest','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation browser_binding_digest INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','browser_binding_digest','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column browser_binding_digest UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','browser_binding_digest','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation browser_binding_digest UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','browser_binding_digest','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column browser_binding_digest REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','browser_binding_digest','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation browser_binding_digest REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','policy_digest','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column policy_digest SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','policy_digest','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation policy_digest SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','policy_digest','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column policy_digest INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','policy_digest','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation policy_digest INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','policy_digest','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column policy_digest UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','policy_digest','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation policy_digest UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','policy_digest','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column policy_digest REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','policy_digest','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation policy_digest REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','nonce','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column nonce SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','nonce','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation nonce SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','nonce','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column nonce INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','nonce','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation nonce INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','nonce','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column nonce UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','nonce','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation nonce UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','nonce','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column nonce REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','nonce','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation nonce REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','code_verifier','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column code_verifier SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','code_verifier','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation code_verifier SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','code_verifier','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column code_verifier INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','code_verifier','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation code_verifier INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','code_verifier','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column code_verifier UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','code_verifier','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation code_verifier UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','code_verifier','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column code_verifier REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','code_verifier','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation code_verifier REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','issuer','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column issuer SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','issuer','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation issuer SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','issuer','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column issuer INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','issuer','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation issuer INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','issuer','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column issuer UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','issuer','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation issuer UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','issuer','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column issuer REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','issuer','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation issuer REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','client_id','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column client_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','client_id','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation client_id SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','client_id','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column client_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','client_id','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation client_id INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','client_id','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column client_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','client_id','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation client_id UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','client_id','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column client_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','client_id','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation client_id REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','callback_url','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column callback_url SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','callback_url','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation callback_url SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','callback_url','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column callback_url INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','callback_url','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation callback_url INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','callback_url','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column callback_url UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','callback_url','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation callback_url UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','callback_url','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column callback_url REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','callback_url','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation callback_url REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','return_target','SELECT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column return_target SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','return_target','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation return_target SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','return_target','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column return_target INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','return_target','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation return_target INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','return_target','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column return_target UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','return_target','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation return_target UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','return_target','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column return_target REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','return_target','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation return_target REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','created_at','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column created_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','created_at','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation created_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','created_at','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column created_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','created_at','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation created_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','created_at','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column created_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','created_at','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation created_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','created_at','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column created_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','created_at','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation created_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','expires_at','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column expires_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','expires_at','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation expires_at SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','expires_at','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column expires_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','expires_at','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation expires_at INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','expires_at','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column expires_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','expires_at','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation expires_at UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','expires_at','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column expires_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','expires_at','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation expires_at REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','contract_version','SELECT')) IS DISTINCT FROM true THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column contract_version SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','contract_version','SELECT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation contract_version SELECT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','contract_version','INSERT')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column contract_version INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','contract_version','INSERT WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation contract_version INSERT'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','contract_version','UPDATE')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column contract_version UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','contract_version','UPDATE WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation contract_version UPDATE'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','contract_version','REFERENCES')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner column contract_version REFERENCES'; END IF;
  IF (SELECT has_column_privilege('ui47_b2b_lock_owner','public.oidc_transactions','contract_version','REFERENCES WITH GRANT OPTION')) IS DISTINCT FROM false THEN RAISE EXCEPTION 'B2B lock contract mismatch: oidc_transactions owner delegation contract_version REFERENCES'; END IF;
  IF (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind IN ('r','p','S') AND c.relname NOT IN ('local_users','external_identities','company_memberships','membership_permissions','application_sessions','oidc_transactions')
        AND CASE WHEN c.relkind='S' THEN has_sequence_privilege('ui47_b2b_lock_owner',c.oid,'USAGE,SELECT,UPDATE')
          ELSE has_table_privilege('ui47_b2b_lock_owner',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER,MAINTAIN')
            OR has_any_column_privilege('ui47_b2b_lock_owner',c.oid,'SELECT,INSERT,UPDATE,REFERENCES') END) IS DISTINCT FROM 0 THEN RAISE EXCEPTION 'B2B lock contract mismatch: owner other tables'; END IF;
END; $locks$;
-- No USAGE/EXECUTE is granted to ui47_app by installation.
ROLLBACK;
