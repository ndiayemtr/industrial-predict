"""Offline ACT-5 comparator regressions; no database, Docker or private inputs."""
import copy
import json
import unittest
from unittest.mock import MagicMock

import b2b_deployment as d


class RestoreConstraintTests(unittest.TestCase):
    def snapshots(self, cases=None):
        before, after, columns = [], [], {}
        for table, name, old, new in cases or CASES:
            attributes = dict(relname=table, conname=name, contype='c', convalidated=True,
                              condeferrable=False, condeferred=False, connoinherit=False,
                              conislocal=True, coninhcount=0)
            before.append(json.dumps(dict(attributes, definition=old)))
            after.append(json.dumps(dict(attributes, definition=new)))
            names = ('role', 'permission') if table == 'membership_permissions' else (
                'state' if name.endswith('_state') else 'role',)
            for column in names:
                columns[table, column] = json.dumps(dict(relname=table, attname=column,
                    type='character varying(16)' if column == 'state' else 'character varying(32)',
                    attnotnull=True, collation={'schema': 'pg_catalog', 'name': 'default',
                                              'provider': 'd', 'deterministic': True}))
        protected = {'columns': list(columns.values()), 'database': ['unchanged locale'],
                     'rows': ['synthetic unchanged digest'], 'acl': ['unchanged']}
        return dict(protected, constraints=before), dict(protected, constraints=after)

    def change(self, snapshot, field, key, value, index=0):
        result = copy.deepcopy(snapshot)
        row = json.loads(result[field][index])
        row[key] = value
        result[field][index] = json.dumps(row)
        return result

    def test_four_exact_observed_pairs_both_directions(self):
        for case in CASES:
            with self.subTest(constraint=case[1]):
                before, after = self.snapshots([case])
                self.assertTrue(d.restored_snapshot_matches(before, after))
                self.assertTrue(d.restored_snapshot_matches(after, before))

    def test_combined_restore_preserves_raw_evidence(self):
        before, after = self.snapshots()
        original = copy.deepcopy((before, after))
        self.assertNotEqual(before, after)
        self.assertTrue(d.restored_snapshot_matches(before, after))
        self.assertEqual((before, after), original)
        self.assertNotEqual(d.digest(before), d.digest(after))

    def test_semantic_changes_are_rejected(self):
        for case in CASES:
            before, after = self.snapshots([case])
            definition = case[3]
            changes = [definition.replace('= ANY', '<> ANY', 1),
                       definition.replace('= ANY', '= ALL', 1),
                       definition.replace('::character varying::text', '::character varying(2)::text', 1),
                       definition.replace('::character varying::text', '::character::text', 1),
                       definition.replace('ARRAY[', 'ARRAY[NULL::text, ', 1),
                       definition.replace('::text =', '::text COLLATE "C" =', 1),
                       definition.replace("'active'", "'suspended'", 1) if '_state' in case[1]
                       else definition.replace("'reader'", "'company_admin'", 1)]
            if 'role_cap' in case[1]:
                changes += [definition.replace(' AND ', ' OR ', 1),
                            definition.replace("'predictions:analyze'", "'maintenance:write'", 1),
                            definition.replace("role::text = 'company_admin'", "role::text = 'reader'", 1)]
            for changed in changes:
                with self.subTest(constraint=case[1], definition=changed):
                    self.assertNotEqual(definition, changed)
                    self.assertFalse(d.restored_snapshot_matches(before,
                        self.change(after, 'constraints', 'definition', changed)))

    def test_constraint_attributes_and_unknown_attributes_stay_strict(self):
        before, after = self.snapshots()
        for key, value in [('relname', 'other'), ('conname', 'other'), ('contype', 'f'),
                           ('convalidated', False), ('condeferrable', True), ('condeferred', True),
                           ('connoinherit', True), ('conislocal', False), ('coninhcount', 1),
                           ('convalidated', 1), ('coninhcount', False),
                           ('future_attribute', True)]:
            with self.subTest(attribute=key):
                self.assertFalse(d.restored_snapshot_matches(before,
                    self.change(after, 'constraints', key, value)))

    def test_column_types_nullability_collations_and_other_sections_stay_strict(self):
        before, after = self.snapshots()
        for key, value in [('type', 'text'), ('attnotnull', False), ('collation', None),
                           ('collation', {'name': 'different', 'deterministic': False})]:
            with self.subTest(attribute=key):
                self.assertFalse(d.restored_snapshot_matches(before,
                    self.change(after, 'columns', key, value)))
        for section in ('database', 'rows', 'acl'):
            changed = copy.deepcopy(after)
            changed[section] = ['changed']
            self.assertFalse(d.restored_snapshot_matches(before, changed))

    def test_old_evidence_without_context_cannot_gain_exception(self):
        before, after = self.snapshots()
        for snapshot in (before, after):
            snapshot['columns'] = [json.dumps({k: v for k, v in json.loads(row).items()
                                              if k != 'collation'}) for row in snapshot['columns']]
        self.assertFalse(d.restored_snapshot_matches(before, after))
        before, after = self.snapshots()
        for snapshot in (before, after):
            snapshot['constraints'] = [json.dumps({k: v for k, v in json.loads(row).items()
                                                  if k != 'contype'}) for row in snapshot['constraints']]
        self.assertFalse(d.restored_snapshot_matches(before, after))

    def test_missing_duplicate_reordered_or_malformed_constraints_rejected(self):
        before, after = self.snapshots()
        for rows in (after['constraints'][:-1], after['constraints'][::-1],
                     [after['constraints'][0]] * len(after['constraints']), ['not json'] * 4):
            self.assertFalse(d.restored_snapshot_matches(before, dict(after, constraints=rows)))

    def test_unknown_constraints_compare_strictly(self):
        before, after = self.snapshots()
        before['constraints'].append(json.dumps(dict(relname='industrial', conname='other', definition='CHECK (id > 0)')))
        after['constraints'].append(before['constraints'][-1])
        self.assertTrue(d.restored_snapshot_matches(before, after))
        self.assertFalse(d.restored_snapshot_matches(before,
            self.change(after, 'constraints', 'definition', 'CHECK (id >= 0)', index=4)))

    def test_verify_restore_uses_bounded_comparison_and_keeps_acl_gate(self):
        before, after = self.snapshots()
        deployment = object.__new__(d.Deployment)
        deployment.restore_inventory = MagicMock(return_value={})
        deployment.identity = MagicMock()
        deployment.engine = MagicMock()
        deployment.snapshot = MagicMock(return_value=after)
        deployment.acl = MagicMock(return_value=[])
        deployment.verify_restore({'snapshot': before, 'acl': []})
        deployment.acl.return_value = [('unexpected grant',)]
        with self.assertRaisesRegex(ValueError, 'Restored data changed'):
            deployment.verify_restore({'snapshot': before, 'acl': []})
        deployment.acl.return_value = []
        deployment.snapshot.return_value = self.change(after, 'constraints', 'convalidated', False)
        with self.assertRaisesRegex(ValueError, 'Restored data changed'):
            deployment.verify_restore({'snapshot': before, 'acl': []})

    def test_snapshot_captures_strict_catalog_metadata_without_normalizing(self):
        deployment = object.__new__(d.Deployment)
        deployment.m = MagicMock(BUSINESS_SEQUENCES=set(), B2B_SEQUENCES=set())
        connection = MagicMock()
        connection.exec_driver_sql.return_value.scalars.return_value = []
        deployment.snapshot(connection)
        sql = '\n'.join(call.args[0] for call in connection.exec_driver_sql.call_args_list)
        for field in ('k.contype', 'k.convalidated', 'k.condeferrable', 'k.condeferred',
                      'k.connoinherit', 'k.conislocal', 'k.coninhcount', 'col.collprovider',
                      'col.collisdeterministic', 'col.collversion', 'col.colllocale',
                      'col.collicurules', 'daticurules'):
            self.assertIn(field, sql)
        self.assertIn('pg_get_constraintdef(k.oid,true) AS definition', sql)

    def test_approved_sql_and_five_function_hashes_remain_unchanged(self):
        bodies = d.capture()  # All five approved source pins, no external I/O.
        self.assertEqual(len(d.locks.FUNCTIONS), 5)
        for function in d.locks.FUNCTIONS:
            self.assertEqual(d.policy.digest(function['body'].encode('utf-8')), function['sha256'])
        grants = bodies['b2b-auth-grants.review.sql']
        self.assertEqual(sum(line.startswith('GRANT ') for line in grants.splitlines()), 16)


# Exact expressions copied from restore-constraint-diff.json; no receipt or data.
CASES = [('company_memberships', 'ck_company_memberships_role', "CHECK (role::text = ANY (ARRAY['reader'::character varying, 'technician'::character varying, 'company_admin'::character varying]::text[]))", "CHECK (role::text = ANY (ARRAY['reader'::character varying::text, 'technician'::character varying::text, 'company_admin'::character varying::text]))"), ('company_memberships', 'ck_company_memberships_state', "CHECK (state::text = ANY (ARRAY['active'::character varying, 'inactive'::character varying]::text[]))", "CHECK (state::text = ANY (ARRAY['active'::character varying::text, 'inactive'::character varying::text]))"), ('local_users', 'ck_local_users_state', "CHECK (state::text = ANY (ARRAY['active'::character varying, 'suspended'::character varying]::text[]))", "CHECK (state::text = ANY (ARRAY['active'::character varying::text, 'suspended'::character varying::text]))"), ('membership_permissions', 'ck_membership_permissions_role_cap', "CHECK ((role::text = ANY (ARRAY['reader'::character varying, 'technician'::character varying, 'company_admin'::character varying]::text[])) AND (permission::text = ANY (ARRAY['companies:read'::character varying, 'assets:read'::character varying, 'measurements:read'::character varying, 'predictions:read'::character varying]::text[])) OR (role::text = ANY (ARRAY['technician'::character varying, 'company_admin'::character varying]::text[])) AND permission::text = 'maintenance:write'::text OR role::text = 'company_admin'::text AND (permission::text = ANY (ARRAY['memberships:manage'::character varying, 'predictions:analyze'::character varying]::text[])))", "CHECK ((role::text = ANY (ARRAY['reader'::character varying::text, 'technician'::character varying::text, 'company_admin'::character varying::text])) AND (permission::text = ANY (ARRAY['companies:read'::character varying::text, 'assets:read'::character varying::text, 'measurements:read'::character varying::text, 'predictions:read'::character varying::text])) OR (role::text = ANY (ARRAY['technician'::character varying::text, 'company_admin'::character varying::text])) AND permission::text = 'maintenance:write'::text OR role::text = 'company_admin'::text AND (permission::text = ANY (ARRAY['memberships:manage'::character varying::text, 'predictions:analyze'::character varying::text])))")]
