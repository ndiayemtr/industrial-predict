"""Pinned synthetic source plan and future atomic bootstrap. Never computes predictions."""

from dataclasses import dataclass
from datetime import timezone
from hashlib import sha256
import json

from sqlalchemy import text

from app.anomaly_detection.p101_canonical import instant_datetime
from app.anomaly_detection.p101_contracts import ASSET
from app.p101_local_demo.contracts import SqlRows
from app.p101_local_demo.provisioning import (
    BUSINESS, lock, marker, runtime_grants, validate_connection,
)
from app.p101_local_demo.reader import adapt_rows, validate_fixture
from app.p101_local_demo.setup_config import REVISION, ROLES, SetupError
from app.p101_persistence.contracts import FIXTURE_SHA256


@dataclass(frozen=True)
class BootstrapPlan:
    content_json: str
    sha256: str


def plan(settings, reference):
    """Pure plan: no SQL industrial identifiers, no allocated ids, no evaluate()."""
    settings.validate()
    validate_fixture(reference)
    parents = (
        dict(name='Entreprise synthétique P101', code=ASSET['company_code']),
        dict(name='Site synthétique P101', code=ASSET['site_code']),
        dict(name='Pompe P101 synthétique', code=ASSET['equipment_code'], status='operational',
             equipment_type='pump', criticality='medium'),
        dict(name='Température synthétique P101', code=ASSET['sensor_code'], status='active',
             sensor_type='temperature', unit='°C'),
    )
    for parent in parents:
        parent.update(description=None, created_at=settings.bootstrap_at, updated_at=settings.bootstrap_at)
    measurements = [dict(timestamp=o['timestamp'], value=float(o['value']), quality=o['quality'])
                    for o in sorted(reference['observations'], key=lambda r: r['timestamp'])]
    payload = dict(format='p101-local-bootstrap-v1', instance_uuid=settings.instance_uuid,
        revision=REVISION, fixture_sha256=FIXTURE_SHA256, parents=parents, measurements=measurements)
    content = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return BootstrapPlan(content, sha256(content.encode('utf-8')).hexdigest())


def insert_payloads(prepared):
    """Pure SQL values: explicit legacy UTC-naive parent dates, aware measurement dates."""
    data = json.loads(prepared.content_json)
    for parent in data['parents']:
        for key in ('created_at', 'updated_at'):
            parent[key] = instant_datetime(parent[key]).astimezone(timezone.utc).replace(tzinfo=None)
    for measurement in data['measurements']:
        measurement['timestamp'] = instant_datetime(measurement['timestamp'])
    return data


def validate_snapshot(prepared, rows, reference, instance_marker):
    """Pure exact retry/integrity comparison; never adopts partial or divergent data."""
    expected = insert_payloads(prepared)
    if (instance_marker.get('fixture_sha256') != FIXTURE_SHA256
            or instance_marker.get('bootstrap_closed') is not True
            or instance_marker.get('bootstrap_sha256') != prepared.sha256):
        raise SetupError('Closed bootstrap fingerprint mismatch')
    for group, wanted in zip((rows.companies, rows.sites, rows.equipments, rows.sensors), expected['parents']):
        if len(group) != 1 or any(group[0].get(k) != v for k, v in wanted.items()):
            raise SetupError('Synthetic parents differ; no overwrite permitted')
    return adapt_rows(rows, reference)


def snapshot(connection):
    # Whole source tables, bounded at one excess row: no hidden extra industrial entities.
    groups = [tuple(dict(r) for r in connection.execute(text(
        f'SELECT * FROM public.{table} ORDER BY id LIMIT {13 if table == "measurements" else 2}')).mappings())
        for table in BUSINESS[:5]]
    return SqlRows(*groups)


def bootstrap(connection, settings, reference):
    """Future one-owner transaction supplied by CLI; atomic 4 parents + 12 measures + closure."""
    validate_connection(connection, settings, ROLES[1])
    lock(connection)
    state = marker(connection, settings)
    prepared = plan(settings, reference)
    if state['bootstrap_closed']:
        return validate_snapshot(prepared, snapshot(connection), reference, state)
    if state['fixture_sha256'] != FIXTURE_SHA256 or state['bootstrap_sha256'] is not None:
        raise SetupError('Unexpected open bootstrap marker')
    for table in BUSINESS:
        if connection.execute(text(f'SELECT EXISTS(SELECT 1 FROM public.{table})')).scalar_one():
            raise SetupError('Empty business tables required; no adoption or cleanup')
    data = insert_payloads(prepared)
    parent_id = None
    for i, (table, payload) in enumerate(zip(BUSINESS[:4], data['parents'])):
        if i:
            payload[('company_id', 'site_id', 'equipment_id')[i - 1]] = parent_id
        columns = ','.join(payload)
        bindings = ','.join(':' + k for k in payload)
        parent_id = connection.execute(text(f'INSERT INTO public.{table} ({columns}) '
            f'VALUES ({bindings}) RETURNING id'), payload).scalar_one()
    for payload in data['measurements']:
        connection.execute(text('INSERT INTO public.measurements (sensor_id,timestamp,value,quality) '
            'VALUES (:sensor_id,:timestamp,:value,:quality)'), dict(sensor_id=parent_id, **payload))
    closed = dict(state, bootstrap_closed=True, bootstrap_sha256=prepared.sha256)
    result = validate_snapshot(prepared, snapshot(connection), reference, closed)
    runtime_grants(connection)
    changed = connection.execute(text('UPDATE local_demo.environment SET bootstrap_closed=true, '
        'bootstrap_sha256=:hash WHERE singleton AND NOT bootstrap_closed AND instance_uuid=CAST(:uuid AS uuid)'),
        dict(hash=prepared.sha256, uuid=settings.instance_uuid)).rowcount
    if changed != 1:
        raise SetupError('Bootstrap closure conflict')
    return result
