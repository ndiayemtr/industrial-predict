"""Offline contracts only; actual PostgreSQL function execution needs approval."""
import hashlib
from pathlib import Path
import re
import unittest

import b2b_activation as activation
import b2b_locks as locks


class LockDefinitionTests(unittest.TestCase):
    def test_five_exact_signatures_results_and_parameter_guards(self):
        expected = {
            'lock_user_v1': ('integer', 'TABLE(state text)'),
            'lock_external_identity_v1': ('integer,integer,text,text', 'TABLE(id integer, issuer text, subject text)'),
            'lock_memberships_v1': ('integer', 'TABLE(id integer, user_id integer, company_id integer, state text, role text)'),
            'lock_membership_permissions_v1': ('integer,integer', 'TABLE(permission text, role text)'),
            'lock_oidc_transaction_v1': ('text,text,text,text,timestamp with time zone', 'TABLE(transaction_id text)'),
        }
        self.assertEqual({f['name'] for f in locks.FUNCTIONS}, set(expected))
        for f in locks.FUNCTIONS:
            arguments,result = expected[f['name']]
            self.assertEqual(f['signature'], f"b2b_lock.{f['name']}({arguments})")
            self.assertEqual(f['result'], result)
            self.assertIn("session_user <> 'ui47_app'", f['body'])
            self.assertIn("ERRCODE='22023'", f['body'])
            for argument,_ in f['arguments']:
                self.assertIn(argument+' IS NULL', f['body'])
            self.assertEqual(hashlib.sha256(f['body'].encode()).hexdigest(), f['sha256'])

    def test_lock_strength_scope_cardinality_and_order_are_preserved(self):
        bodies = {f['name']: f['body'] for f in locks.FUNCTIONS}
        self.assertIn('WHERE u.id=p_user_id FOR UPDATE OF u', bodies['lock_user_v1'])
        external = bodies['lock_external_identity_v1']
        for value in ('e.user_id=p_user_id', 'e.id=p_external_id', 'e.issuer=p_issuer AND e.subject=p_subject',
                      'FOR SHARE OF e', 'p_issuer IS NULL AND p_subject IS NULL', 'BETWEEN 1 AND 2048'):
            self.assertIn(value, external)
        self.assertIn('WHERE m.user_id=p_user_id ORDER BY m.id FOR SHARE OF m', bodies['lock_memberships_v1'])
        permissions = bodies['lock_membership_permissions_v1']
        for value in ('p.membership_id=p_membership_id', 'm.id=p_membership_id AND m.user_id=p_user_id',
                      'ORDER BY p.permission FOR SHARE OF p'):
            self.assertIn(value, permissions)
        oidc = bodies['lock_oidc_transaction_v1']
        for value in ('t.state_digest=p_state_digest', 't.browser_binding_digest=p_browser_binding_digest',
                      't.policy_digest=p_policy_digest', 't.contract_version=p_contract_version',
                      't.created_at<=p_now AND t.expires_at>p_now FOR UPDATE OF t', 'pg_catalog.isfinite(p_now)'):
            self.assertIn(value, oidc)
        for body in bodies.values():
            self.assertNotIn('LIMIT', body)
            self.assertNotIn('SKIP LOCKED', body)
            self.assertNotIn('clock_timestamp', body)  # Clock stays a separate post-lock command.
            for word in ('INSERT','DELETE','EXECUTE','COMMIT','ROLLBACK','EXCEPTION WHEN'):
                self.assertNotRegex(body, r'\b'+word+r'\b')
            self.assertNotRegex(body.replace('FOR UPDATE', ''), r'\bUPDATE\b')

    def test_installation_has_closed_public_acl_and_no_app_or_industrial_grant(self):
        sql = locks.install_sql()
        self.assertEqual((Path(__file__).parent/'b2b-lock-install.review.sql').read_text(encoding='utf-8'), sql+'\n')
        self.assertTrue(sql.endswith('ROLLBACK;'))
        self.assertIn('NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', sql)
        self.assertEqual(sql.count('SECURITY DEFINER VOLATILE PARALLEL UNSAFE'), 5)
        self.assertEqual(sql.count('SET search_path TO pg_catalog, pg_temp'), 5)
        self.assertEqual(sql.count('FROM PUBLIC;'), 5)
        for line in sql.splitlines():
            if line.startswith('GRANT '):
                self.assertNotIn('TO ui47_app', line)
                self.assertNotIn('companies ', line)
                self.assertNotIn('equipments ', line)
        self.assertNotIn('GRANT '+locks.OWNER+' TO', sql)
        self.assertNotIn('CREATE OR REPLACE', sql)

    def test_owner_and_application_have_different_narrow_capabilities(self):
        self.assertNotIn('application_sessions', locks.OWNER_RIGHTS)
        oidc_columns,_ = locks.OWNER_RIGHTS['oidc_transactions']
        self.assertNotIn('nonce', oidc_columns)
        self.assertNotIn('code_verifier', oidc_columns)
        matrix = activation.matrix(activation.CANDIDATE)
        self.assertEqual({t for t,r in matrix.items() if 'UPDATE' in r['columns']}, {'application_sessions'})
        sql = locks.assertion_sql(app_access=True, columns=activation.COLUMNS)
        for value in ('proowner=', 'prosecdef', "provolatile='v'", "proparallel='u'", 'proargnames=',
                      'prosrc', 'is_grantable', 'pg_auth_members', "'EXECUTE WITH GRANT OPTION'"):
            self.assertIn(value, sql)


if __name__ == '__main__':
    unittest.main()
