"""AST/schema inspection only: never import or execute a migration module."""

import ast
import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app import general_migrations as guards
from app.models.professional_account import LocalUserRecord, ExternalIdentityRecord, MembershipRecord, MembershipPermissionRecord


PATH=guards.GENERAL_DIRECTORY/'versions/4b7e2a91c6d0_create_professional_accounts.py'
TABLES={c.__tablename__:c.__table__ for c in (LocalUserRecord,ExternalIdentityRecord,MembershipRecord,MembershipPermissionRecord)}


def value(node):
    if isinstance(node,ast.Constant): return node.value
    if isinstance(node,ast.List): return tuple(value(x) for x in node.elts)
    assert isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
    return (node.func.attr,tuple(value(x) for x in node.args),{k.arg:value(k.value) for k in node.keywords})


def functions():
    tree=ast.parse(PATH.read_text(encoding='utf-8'))
    return {n.name:[value(s.value) for s in n.body] for n in tree.body if isinstance(n,ast.FunctionDef)}


def test_publication_extends_only_oidc_head_and_all_hashes_are_verified():
    published=guards.read_manifest()
    assert len(published)==2
    assert published[1].revision=='4b7e2a91c6d0' and published[1].parent=='12e2fc65f372'
    assert published[1].schema_scope==tuple('public.'+n for n in TABLES)
    assert hashlib.sha256(PATH.read_bytes()).hexdigest()==published[1].sha256
    snapshot=guards.inspect_sources()
    assert guards.resolve_upgrade(snapshot.revisions,guards.HISTORICAL_HEAD,published[1].revision)==('12e2fc65f372','4b7e2a91c6d0')


def test_literal_migration_exactly_matches_independent_orm_metadata():
    ops=functions()['upgrade']
    creates={args[0]:(args[1:],kw) for name,args,kw in ops if name=='create_table'}
    assert set(creates)==set(TABLES)
    for name,table in TABLES.items():
        items,kw=creates[name]
        assert kw=={'schema':'public'}
        columns=[(args[0],args[1],options) for kind,args,options in items if kind=='Column']
        expected=[(c.name,('String',(c.type.length,),{}) if hasattr(c.type,'length') else ('Integer',(),{}),{'nullable':False}) for c in table.columns]
        assert columns==expected
        constraints=[(kind,args,options) for kind,args,options in items if kind!='Column']
        expected=[]
        for c in table.constraints:
            if isinstance(c,CheckConstraint): expected.append(('CheckConstraint',(str(c.sqltext),),{'name':c.name}))
            elif isinstance(c,ForeignKeyConstraint):
                expected.append(('ForeignKeyConstraint',(tuple(c.column_keys),tuple('public.'+e.target_fullname for e in c.elements)),{'name':c.name,'ondelete':'RESTRICT'}))
            elif isinstance(c,PrimaryKeyConstraint): expected.append(('PrimaryKeyConstraint',tuple(x.name for x in c.columns),{}))
            elif isinstance(c,UniqueConstraint): expected.append(('UniqueConstraint',tuple(x.name for x in c.columns),{'name':c.name}))
            else: pytest.fail('Unexpected ORM constraint')
        assert sorted(map(repr,constraints))==sorted(map(repr,expected))
        assert 'CREATE TABLE' in str(CreateTable(table).compile(dialect=postgresql.dialect()))
    indexes={(args[0],args[1],args[2],tuple(sorted(kw.items()))) for kind,args,kw in ops if kind=='create_index'}
    expected_indexes={(i.name,t.name,tuple(c.name for c in i.columns),(('schema','public'),('unique',False))) for t in TABLES.values() for i in t.indexes}
    assert indexes==expected_indexes


def test_downgrade_is_bounded_and_does_not_cascade():
    ops=functions()['downgrade']
    assert [args[0] for kind,args,kw in ops if kind=='drop_table']==list(reversed(TABLES))
    assert all(kind in ('drop_table','drop_index') and kw.get('schema')=='public' for kind,args,kw in ops)
    assert 'CASCADE' not in PATH.read_text(encoding='utf-8').upper()


@pytest.mark.parametrize('mutation', [
    lambda s:s+'\nraise RuntimeError("unapproved")\n',
    lambda s:s.replace('"local_users",','"companies",',1),
    lambda s:s.replace('"RESTRICT"','"CASCADE"'),
    lambda s:s.replace('    op.create_table(','    dynamic(op.create_table,',1),
    lambda s:s.replace('sa.String(16)','sa.String(32)',1),
    lambda s:s.replace('"12e2fc65f372"','"09ac8101e9fe"',1),
])
def test_changed_source_cannot_be_approved_by_recomputing_manifest(monkeypatch,mutation):
    original=guards._read
    altered=mutation(original(PATH))
    manifest=json.loads(original(guards.MANIFEST_PATH))
    manifest['revisions'][1]['sha256']=hashlib.sha256(altered.encode()).hexdigest()
    def read(path):
        if path==PATH:return altered
        if path==guards.MANIFEST_PATH:return json.dumps(manifest)
        return original(path)
    monkeypatch.setattr(guards,'_read',read)
    with pytest.raises(guards.MigrationGuardError):guards.inspect_sources()


def test_execution_boundary_and_ini_remain_inert_by_static_inspection():
    tree=ast.parse((guards.GENERAL_DIRECTORY/'env.py').read_text(encoding='utf-8'))
    assert isinstance(tree.body[-1],ast.Raise)
    assert tree.body[-1].exc.func.id=='MigrationExecutionDisabled'
    ini=(guards.GENERAL_DIRECTORY/'alembic.ini').read_text(encoding='utf-8')
    active='\n'.join(line for line in ini.splitlines() if not line.lstrip().startswith('#'))
    for forbidden in ('script_location','version_locations','sqlalchemy.url'):assert forbidden not in active
