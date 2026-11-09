"""Compile the fourteen pinned declarations, never Python revision modules.

Alembic is used ONLY as an offline PostgreSQL DDL renderer, not via env.py or
an existing disabled execution path. No eval/exec/importlib, connection or engine.
"""

import ast
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
from io import StringIO

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app import general_migrations as general
from b2b_postgres_qualification import validation as v
from b2b_postgres_qualification.contracts import Offline
from p101_postgres_qualification import plans


@dataclass(frozen=True, slots=True, repr=False)
class RevisionSQL(Offline):
    revision: str
    parent: str | None
    source_sha256: str
    statements: tuple[str, ...]


@dataclass(frozen=True, slots=True, repr=False)
class Release(Offline):
    revisions: tuple[RevisionSQL, ...]
    version_create: str
    version_steps: tuple[str, ...]
    sha256: str


TYPES = {
    'Integer': sa.Integer, 'String': sa.String, 'Text': sa.Text, 'DateTime': sa.DateTime,
    'Float': sa.Float, 'Boolean': sa.Boolean, 'JSON': sa.JSON, 'Column': sa.Column,
    'PrimaryKeyConstraint': sa.PrimaryKeyConstraint, 'ForeignKeyConstraint': sa.ForeignKeyConstraint,
    'UniqueConstraint': sa.UniqueConstraint, 'CheckConstraint': sa.CheckConstraint,
}
OPERATIONS = ('create_table', 'create_index', 'add_column', 'create_unique_constraint',
    'create_foreign_key', 'drop_constraint', 'create_check_constraint', 'execute')


def _value(node):
    # This is a literal declaration decoder, not an interpreter of Python.
    if type(node) is ast.Constant:
        v.require(type(node.value) in (str, int, bool, type(None)))
        if type(node.value) is int:
            v.require(0 <= node.value <= 4096)
        return node.value
    if type(node) is ast.List:
        return [_value(child) for child in node.elts]
    v.require(type(node) is ast.Call and type(node.func) is ast.Attribute
        and type(node.func.value) is ast.Name)
    v.require(all(type(kw.arg) is str for kw in node.keywords)
        and len({kw.arg for kw in node.keywords}) == len(node.keywords))
    args = [_value(child) for child in node.args]
    kwargs = {kw.arg: _value(kw.value) for kw in node.keywords}
    if node.func.value.id == 'op' and node.func.attr == 'f':
        v.require(len(args) == 1 and type(args[0]) is str and not kwargs)
        return sa.sql.elements.conv(args[0])
    v.require(node.func.value.id == 'sa' and node.func.attr in TYPES)
    return TYPES[node.func.attr](*args, **kwargs)


def _decode_upgrade(source):
    tree = ast.parse(source)
    upgrades = [node for node in tree.body if type(node) is ast.FunctionDef and node.name == 'upgrade']
    v.require(len(upgrades) == 1 and not upgrades[0].decorator_list)
    operations = []
    for node in upgrades[0].body:
        v.require(type(node) is ast.Expr and type(node.value) is ast.Call)
        call = node.value
        v.require(type(call.func) is ast.Attribute and type(call.func.value) is ast.Name
            and call.func.value.id == 'op' and call.func.attr in OPERATIONS)
        v.require(all(type(kw.arg) is str for kw in call.keywords)
            and len({kw.arg for kw in call.keywords}) == len(call.keywords))
        args = [_value(child) for child in call.args]
        kwargs = {kw.arg: _value(kw.value) for kw in call.keywords}
        if call.func.attr == 'execute':
            v.require(len(args) == 1 and type(args[0]) is str and not kwargs)
        operations.append((call.func.attr, args, kwargs))
    return operations


@v.guarded
def compile_release():
    v.require(version('SQLAlchemy') == '2.0.52' and version('alembic') == '1.19.1')
    snapshot = general.inspect_sources()  # Published guards remain unchanged.
    graph = {item.revision: item for item in snapshot.revisions}
    captured = []
    previous = None
    for publication in plans.PUBLICATIONS:
        descriptor = graph[publication.revision]
        v.require(descriptor.parent == publication.parent == previous and descriptor.path == publication.path)
        path = general.BACKEND / publication.path
        v.require(path.resolve() == path and not path.is_symlink())
        source = path.read_text(encoding='utf-8').replace('\r\n', '\n')
        v.require(sha256(source.encode('utf-8')).hexdigest() == publication.sha256)
        captured.append((publication, source))
        previous = publication.revision
    v.require(len(captured) == len(graph) == 14)
    # Render only the immutable source strings captured and rehashed above.
    revisions = []
    for publication, source in captured:
        buffer = StringIO()
        # Render server-native SQL, not DB-API pyformat text (which doubles '%' and
        # would corrupt PL/pgSQL %ROWTYPE when sent without driver interpolation).
        context = MigrationContext.configure(dialect_name='postgresql', dialect_opts={'paramstyle': 'named'}, opts={
            'as_sql': True, 'output_buffer': buffer, 'literal_binds': True,
            'transactional_ddl': True, 'target_metadata': None})
        op = Operations(context)
        methods = {name: getattr(op, name) for name in OPERATIONS}
        statements = []
        for name, args, kwargs in _decode_upgrade(source):
            methods[name](*args, **kwargs)
            text = buffer.getvalue().strip()
            v.require(text and len(text.encode()) <= 131072)
            statements.append(text)  # Keep PL/pgSQL bodies intact; never split on ';'.
            buffer.seek(0)
            buffer.truncate()
        revisions.append(RevisionSQL(publication.revision, publication.parent, publication.sha256, tuple(statements)))
    # Standard Alembic bookkeeping, rendered without stamp/run_migrations/env.py.
    # A version marker is advanced only AFTER its corresponding DDL in the same TX.
    table = context.impl.version_table_impl(version_table='alembic_version',
        version_table_schema='public', version_table_pk=True)
    dialect = context.dialect
    version_create = str(sa.schema.CreateTable(table).compile(dialect=dialect)).strip() + ';'
    version_steps = []
    for revision in revisions:
        if revision.parent is None:
            statement = table.insert().values(version_num=revision.revision)
        else:
            statement = table.update().where(table.c.version_num == revision.parent).values(version_num=revision.revision)
        version_steps.append(str(statement.compile(dialect=dialect, compile_kwargs={'literal_binds': True})) + ';')
    digest = plans.fingerprint(dict(revisions=[(r.revision, r.parent, r.source_sha256, r.statements) for r in revisions],
        version_create=version_create, version_steps=version_steps))
    return Release(tuple(revisions), version_create, tuple(version_steps), digest)
