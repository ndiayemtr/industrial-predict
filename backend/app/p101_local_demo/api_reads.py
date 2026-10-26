"""Bounded Core SELECTs for the frozen P101 display profile. Never evaluates ML."""

from dataclasses import asdict
import json
import re

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, MetaData, String, Table, select

from app.anomaly_detection.p101_canonical import bounded_details, finite_value
from app.p101_local_demo.api_reader import ApiQueryError, ApiReadError, ApiReferenceNotFound
from app.p101_local_demo.contracts import CUTOFFS, TARGETS, SqlRows
from app.p101_local_demo.reader import adapt_rows, instant, sql_id, validate_fixture
from app.p101_persistence.contracts import CALCULATION_REVISION


metadata = MetaData()


def parent(name, *extra):
    return Table(name, metadata, Column('id', Integer), Column('name', String), Column('code', String),
        Column('description', String), Column('created_at', DateTime()), Column('updated_at', DateTime()),
        *extra, schema='public')


companies = parent('companies')
sites = parent('sites', Column('company_id', Integer))
equipments = parent('equipments', Column('site_id', Integer), Column('equipment_type', String),
                   Column('status', String), Column('criticality', String))
sensors = parent('sensors', Column('equipment_id', Integer), Column('sensor_type', String),
                 Column('status', String), Column('unit', String))
measurements = Table('measurements', metadata, Column('id', Integer), Column('sensor_id', Integer),
    Column('timestamp', DateTime(timezone=True)), Column('value', Float), Column('quality', String), schema='public')
predictions = Table('prediction_records', metadata, Column('id', Integer), Column('equipment_id', Integer),
    Column('sensor_id', Integer), Column('measurement_id', Integer), Column('prediction_type', String),
    Column('score', Float), Column('level', String), Column('is_alert', Boolean), Column('model_name', String),
    Column('model_version', String), Column('horizon_hours', Float), Column('details', JSON),
    Column('predicted_at', DateTime(timezone=True)), Column('created_at', DateTime(timezone=True)), schema='public')


class ApiReads:
    def __init__(self, connection, destination, reference):
        self.connection, self.destination, self.reference = connection, destination, reference
        self._rows = None
        self._identities = None

    def scope(self):
        if self._rows is None:
            validate_fixture(self.reference)
            groups = [tuple(dict(r) for r in self.connection.execute(select(table).order_by(table.c.id).limit(
                13 if table is measurements else 2)).mappings())
                for table in (companies, sites, equipments, sensors, measurements)]
            rows = SqlRows(*groups)
            self._identities = adapt_rows(rows, self.reference).identities
            self._rows = rows
        return self._rows

    def reference_by_id(self, kind, identity):
        sql_id(identity)
        row = getattr(self.scope(), kind)[0]
        if row['id'] != identity:
            raise ApiReferenceNotFound('P101_REFERENCE_NOT_FOUND')
        return dict(row)

    def references(self, kind, *, page, page_size, search=None, company_id=None, site_id=None,
                   status=None, criticality=None):
        row = dict(getattr(self.scope(), kind)[0])
        matches = (company_id is None or row.get('company_id') == company_id)
        matches = matches and (site_id is None or row.get('site_id') == site_id)
        matches = matches and (status is None or row.get('status') == status)
        matches = matches and (criticality is None or row.get('criticality') == criticality)
        matches = matches and (search is None or search.casefold() in row['name'].casefold()
                               or search.casefold() in row['code'].casefold())
        return self.page([row] if matches else [], page, page_size)

    @staticmethod
    def page(items, page, page_size):
        from app.core.pagination import build_page  # Pure existing response helper, no settings/engine.
        if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
            raise ApiQueryError('INVALID_PAGINATION')
        offset = (page - 1) * page_size
        return build_page(items=items[offset:offset+page_size], total=len(items), page=page, page_size=page_size)

    def prediction_history(self, equipment_id, *, page, page_size, prediction_type=None,
                           level=None, is_alert=None, start_time=None, end_time=None):
        self.reference_by_id('equipments', equipment_id)
        try:
            for value in (start_time, end_time):
                if value is not None:
                    instant(value)  # Reject naive dates; inclusive instants, as required by Angular.
            if start_time is not None and end_time is not None and start_time > end_time:
                raise ValueError('Reversed period')
        except (ValueError, TypeError):
            raise ApiQueryError('INVALID_PERIOD') from None
        rows = [dict(r) for r in self.connection.execute(select(predictions).order_by(
            predictions.c.predicted_at.desc(), predictions.c.id.desc()).limit(3)).mappings()]
        if len(rows) != 2 or len({sql_id(r['id']) for r in rows}) != 2:
            raise ApiReadError('TWO_PERSISTED_PREDICTIONS_REQUIRED')
        identities = self._identities
        mapping = asdict(identities)
        mapping['measurements'] = dict(identities.measurements)
        seen = set()
        for r in rows:
            if set(r) != set(predictions.c.keys()):
                raise ApiReadError('FOURTEEN_PREDICTION_FIELDS_REQUIRED')
            d = r['details']
            if type(d) is not dict or set(d) != {'schema_version','synthetic','reason','calculation','local_demo'}:
                raise ApiReadError('PREDICTION_DETAILS_REJECTED')
            bounded_details(d)
            calc, local = d['calculation'], d['local_demo']
            target = calc['target']['fixture_id']
            if target not in TARGETS or target in seen:
                raise ApiReadError('PREDICTION_TARGET_REJECTED')
            i = TARGETS.index(target)
            observation = next(o for o in self.reference['observations'] if o['fixture_id'] == target)
            expected_time = observation['timestamp']
            if (r['equipment_id'] != identities.equipment_id or r['sensor_id'] != identities.sensor_id
                    or r['measurement_id'] != dict(identities.measurements)[target]
                    or r['prediction_type'] != 'anomaly' or r['model_name'] != 'statistical_deviation'
                    or r['model_version'] != 'p101-stat-v1' or not finite_value(r['score']) or r['score'] != i
                    or type(r['is_alert']) is not bool or r['is_alert'] != bool(i)
                    or r['level'] is not None or r['horizon_hours'] is not None
                    or instant(r['predicted_at']) != instant(expected_time)
                    or instant(r['created_at']) < calc['prepared_at']
                    or d['schema_version'] != 'p101-local-demo-details-v1' or d['synthetic'] is not True
                    or type(d['reason']) is not str or not d['reason'] or d['reason'] != calc['reason']
                    or calc['synthetic'] is not True
                    or calc['statistics']['score_semantics'] != 'binary_indicator_non_probabilistic'
                    or any(calc['target'][k] != observation[k] for k in ('value','quality','unit'))
                    or instant(calc['target']['timestamp']) != instant(expected_time)
                    or calc['producer']['code_revision'] != CALCULATION_REVISION or calc['cutoff_utc'] != CUTOFFS[i]
                    or set(local) != {'instance_uuid','adapter_version','idempotency_key','content_sha256','sql_mapping'}
                    or local['instance_uuid'] != self.destination.instance_uuid
                    or local['adapter_version'] != 'p101-local-persistence-v1'
                    or json.dumps(local['sql_mapping'], sort_keys=True) != json.dumps(mapping, sort_keys=True)
                    or any(type(local[k]) is not str or re.fullmatch('[0-9a-f]{64}',local[k]) is None
                           for k in ('idempotency_key','content_sha256'))):
                raise ApiReadError('PREDICTION_PROFILE_REJECTED')
            seen.add(target)
        filtered = [r for r in rows if (prediction_type is None or r['prediction_type'] == prediction_type)
            and (level is None or r['level'] == level) and (is_alert is None or r['is_alert'] == is_alert)
            and (start_time is None or r['predicted_at'] >= start_time)
            and (end_time is None or r['predicted_at'] <= end_time)]
        return self.page(filtered, page, page_size)
