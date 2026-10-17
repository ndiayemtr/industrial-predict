"""Insert-only, atomic demo seed for the explicitly verified development target."""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
from urllib.request import HTTPRedirectHandler, build_opener

from sqlalchemy import MetaData, String, Table, create_engine, func, insert, select, text

import manage

# Schemas import no application engine. Never import settings or backend sessions.
sys.path.insert(0, str(manage.REPO/'backend'))
from app.schemas.company import CompanyCreate
from app.schemas.site import SiteCreate
from app.schemas.equipment import EquipmentCreate
from app.schemas.sensor import SensorCreate
from app.schemas.measurement import MeasurementCreate
from app.schemas.maintenance import MaintenanceCreate

FIXTURE = Path(__file__).with_name('demo-data.json')
VERSION = 'industrial-predict-demo-v1'
SCHEMAS = {'companies':CompanyCreate, 'sites':SiteCreate, 'equipments':EquipmentCreate,
           'sensors':SensorCreate, 'measurements':MeasurementCreate, 'maintenance_records':MaintenanceCreate}
PARENTS = {'sites':('companies','company_code','company_id'),
           'equipments':('sites','site_code','site_id'),
           'sensors':('equipments','equipment_code','equipment_id'),
           'measurements':('sensors','sensor_code','sensor_id'),
           'maintenance_records':('equipments','equipment_code','equipment_id')}


class SeedConflict(ValueError):
    pass


@dataclass
class Record:
    table: str
    key: tuple
    values: dict
    parent: tuple | None = None
    foreign_key: str | None = None


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def compile_fixture(data):
    if data.get('version') != VERSION or set(data) != {'version','timestamps',*SCHEMAS}:
        raise ValueError('Unknown demo fixture contract')
    dates = {key:datetime.fromisoformat(value) for key,value in data['timestamps'].items()}
    for key in ('administrative_created_at','administrative_updated_at'):
        if dates[key].tzinfo is not None:
            raise ValueError('Administrative fixture dates must stay timezone-free')
    for key in ('audit_created_at','audit_updated_at'):
        if dates[key].tzinfo is None:
            raise ValueError('Audit fixture dates require a timezone')
    records, known, keys = [], set(), set()
    for table,schema in SCHEMAS.items():
        for source in data[table]:
            values = dict(source)
            parent, foreign_key = None, None
            if table in PARENTS:
                parent_table,code_field,foreign_key = PARENTS[table]
                if foreign_key in values:
                    raise ValueError('Fixture relations must use business codes, never numeric identifiers')
                parent = (parent_table,values.pop(code_field))
                if parent not in known:
                    raise ValueError('Unknown parent business code')
                # Validation placeholder only, removed before generating any row.
                values[foreign_key] = 1
            if set(values) - schema.model_fields.keys():
                raise ValueError('Unexpected fixture field')
            values = schema.model_validate(values).model_dump()
            if foreign_key:
                values.pop(foreign_key)
            for field,value in values.items():
                if isinstance(value, datetime) and value.tzinfo is not None:
                    values[field] = value.astimezone(timezone.utc)
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError('Non-finite demo measurement or cost')
            if table in ('companies','sites','equipments','sensors'):
                if not values['code'].startswith('UI47-'):
                    raise ValueError('Demo business code namespace required')
                key = (values['code'],)
                known.add((table,values['code']))
                values.update(created_at=dates['administrative_created_at'],updated_at=dates['administrative_updated_at'])
            elif table == 'measurements':
                key = (parent[1],values['timestamp'])
            else:
                if not values['title'].startswith('UI47-MAINT-'):
                    raise ValueError('Demo maintenance marker required')
                key = (parent[1],values['title'],values['planned_at'])
                values.update(created_at=dates['audit_created_at'],updated_at=dates['audit_updated_at'])
            if (table,key) in keys:
                raise ValueError('Duplicate demo natural key')
            keys.add((table,key))
            records.append(Record(table,key,values,parent,foreign_key))
    return records


def validate_columns(records, tables):
    for record in records:
        for field,value in record.values.items():
            column = tables[record.table].c[field]
            if value is None and not column.nullable:
                raise ValueError('Null in required fixture column')
            if isinstance(column.type, String) and column.type.length and value is not None and len(value) > column.type.length:
                raise ValueError('Fixture exceeds actual SQL column length')


def payload(record, identifiers):
    values = dict(record.values)
    if record.parent:
        values[record.foreign_key] = identifiers[record.parent]
    return values


def canonical(value):
    # SQLite test fixtures drop offsets; PostgreSQL timestamptz returns aware values.
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def existing_rows(connection, tables, records):
    identifiers, missing = {}, []
    for record in records:
        if record.parent and record.parent not in identifiers:
            missing.append(record)
            continue
        table = tables[record.table]
        expected = payload(record,identifiers)
        if 'code' in expected:
            predicate = table.c.code == expected['code']
        elif record.table == 'measurements':
            predicate = (table.c.sensor_id == expected['sensor_id']) & (table.c.timestamp == expected['timestamp'])
        else:
            predicate = ((table.c.equipment_id == expected['equipment_id']) &
                         (table.c.title == expected['title']) & (table.c.planned_at == expected['planned_at']))
        found = connection.execute(select(table).where(predicate)).mappings().all()
        if not found:
            missing.append(record)
            continue
        if len(found) != 1 or any(canonical(found[0][field]) != canonical(value) for field,value in expected.items()):
            raise SeedConflict('Existing demo row differs or natural key is ambiguous')
        if 'code' in expected:
            identifiers[(record.table,expected['code'])] = found[0]['id']
    return identifiers, missing


def counts(connection, tables):
    return {name:connection.execute(select(func.count()).select_from(table)).scalar_one() for name,table in tables.items()}


def apply_seed(connection, tables, records, *, write):
    validate_columns(records,tables)
    before = counts(connection,tables)
    identifiers, missing = existing_rows(connection,tables,records)
    expected_counts = {name:sum(r.table == name for r in records) for name in tables}
    if not missing:
        return {'action':'unchanged','inserted':0,'dataset_counts':expected_counts,'total_counts':before}
    if any(before.values()):
        raise SeedConflict('Initial load requires eight empty tables; partial seed or unrelated data found')
    if not write:
        return {'action':'ready','inserted':0,'dataset_counts':expected_counts,'total_counts':before}
    for record in records:
        table = tables[record.table]
        values = payload(record,identifiers)
        identifier = connection.execute(insert(table).values(**values).returning(table.c.id)).scalar_one()
        if 'code' in values:
            identifiers[(record.table,values['code'])] = identifier
    _, remaining = existing_rows(connection,tables,records)
    if remaining:
        raise SeedConflict('Seed verification failed; transaction must roll back')
    return {'action':'created','inserted':len(records),'dataset_counts':expected_counts,'total_counts':counts(connection,tables)}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verify_http(config, port):
    with build_opener(NoRedirect()).open(f'http://127.0.0.1:{port}/__dev/identity',timeout=5) as response:
        proof = json.load(response)
        if response.headers.get('X-Industrial-Predict-Environment') != 'local-development':
            raise ValueError('Development HTTP marker missing')
    expected = {'mode':config['mode'],'database':config['database'],'role':'ui47_app',
                'instance_id':config['instance_id'],'revision':manage.REVISION,'superuser':False,
                'database_oid':config['database_oid'],'cluster_name':'industrial-predict-development'}
    if any(proof.get(key) != value for key,value in expected.items()):
        raise ValueError('Development HTTP identity mismatch')


def preflight(config):
    manage.verify_container(config)
    manage.verify_volume(config)
    # Existing admin identity is used only for a read-only cluster identity check.
    admin = create_engine(manage.db_url(config,'admin'),echo=False,connect_args={'connect_timeout':3})
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql('SET TRANSACTION READ ONLY')
            manage.inspect_connection(connection,config,'admin')
            if connection.execute(text('SELECT system_identifier::text FROM pg_control_system()')).scalar_one() != config['cluster_identifier']:
                raise ValueError('Actual PostgreSQL cluster mismatch')
    finally:
        admin.dispose()
    manage.inspect_db(config)
    verify_http(config,config['api_port'])
    verify_http(config,config['frontend_port'])


def run(action, config):
    records = compile_fixture(load_fixture())
    preflight(config)
    engine = create_engine(manage.db_url(config,'app'),echo=False,connect_args={'connect_timeout':3})
    try:
        with engine.begin() as connection:
            if action != 'apply':
                connection.exec_driver_sql('SET TRANSACTION READ ONLY')
            manage.inspect_connection(connection,config)
            connection.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")
            connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
            connection.exec_driver_sql("SET LOCAL statement_timeout = '30s'")
            if action == 'apply':
                # Table locks also block concurrent API writes during initialisation.
                connection.exec_driver_sql('LOCK TABLE '+','.join('public.'+name for name in sorted(manage.TABLES))+' IN SHARE ROW EXCLUSIVE MODE')
            metadata = MetaData()
            tables = {name:Table(name,metadata,schema='public',autoload_with=connection) for name in manage.TABLES}
            result = apply_seed(connection,tables,records,write=action == 'apply')
        return {'version':VERSION,'fixture_sha256':hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
                'database':config['database'],'revision':manage.REVISION,**result}
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description='Insert-only development seed; no reset or deletion command')
    parser.add_argument('action',choices=('check','apply'))
    parser.add_argument('--config',required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.action,manage.load_config(args.config)),ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Seed STOP: '+type(error).__name__+'; no retry, overwrite or cleanup. Uncommitted rows rolled back.',file=sys.stderr)
        raise SystemExit(2)
