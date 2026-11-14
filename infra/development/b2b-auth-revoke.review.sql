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
-- Same transaction: SET LOCAL ROLE ui47_app, then run the reviewed read-only ACL checks.
-- A separate connection cannot see uncommitted grants. Do not commit without that check.
ROLLBACK;
