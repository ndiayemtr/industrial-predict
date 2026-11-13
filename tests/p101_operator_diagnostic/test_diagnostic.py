from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.p101_dev.adapter import IndustrialChain, IndustrialMeasurement, IndustrialSnapshot
from app.p101_dev.contracts import DeclaredProvenance, Computed, Abstained, Rejected, RejectionCode, AbstentionCode
from app.services import p101_operator_diagnostic as diagnostic
from psycopg.pq import TransactionStatus


NOW = datetime(2026, 4, 11, 13, 47, 2, 123456, tzinfo=timezone.utc)


class FakeTransaction:
    is_active = True
    def rollback(self): self.is_active = False


class FakeNative:
    closed = False
    broken = False
    autocommit = False
    def __init__(self, status=TransactionStatus.IDLE):
        self.info = SimpleNamespace(transaction_status=status)


class FakeConnection:
    closed = invalidated = False
    def __init__(self):
        self.tx = None; self.statements = []; self.fail = False; self.fail_timeout = False
        self.no_target = False; self.bad_timeout_readback = False; self.native = FakeNative()
        self.connection = SimpleNamespace(driver_connection=self.native, dbapi_connection=self.native)
        self.dialect = SimpleNamespace(driver='psycopg', is_async=False)
    def in_transaction(self): return self.tx is not None and self.tx.is_active
    def in_nested_transaction(self): return False
    def execution_options(self, **kwargs): self.statements.append(('OPTIONS', kwargs)); return self
    def begin(self): self.tx = FakeTransaction(); return self.tx
    def exec_driver_sql(self, sql): self.statements.append(('SQL', sql))
    def execute(self, statement, params=None):
        sql = str(statement); self.statements.append(('SQL', sql))
        if self.fail: raise RuntimeError('secret DSN must not escape')
        if 'set_config' in sql:
            if self.fail_timeout: raise RuntimeError('timeout setup failed')
            assert params == {'timeout': '5000ms' if 'lock_timeout' in sql else '15000ms'}
            return SimpleNamespace(scalar_one=lambda: 'configured')
        if 'current_setting' in sql:
            return SimpleNamespace(mappings=lambda: SimpleNamespace(one=lambda: {
                'isolation':'repeatable read','read_only':'on',
                'lock_timeout_ms':diagnostic.LOCK_TIMEOUT_MS if not self.bad_timeout_readback else 0,
                'statement_timeout_ms':diagnostic.STATEMENT_TIMEOUT_MS}))
        if 'FROM companies' in sql:
            return SimpleNamespace(all=lambda: [(101, 202, 303)])
        if 'FROM sensors' in sql:
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: [dict(id=404, sensor_type='temperature', unit='°C')]))
        if 'FROM measurements' in sql and 'DESC' in sql:
            target = None if self.no_target else dict(id=11, timestamp=NOW)
            return SimpleNamespace(mappings=lambda: SimpleNamespace(first=lambda: target))
        if 'FROM measurements' in sql:
            return SimpleNamespace(all=lambda: [SimpleNamespace(timestamp=NOW-timedelta(days=i), quality='good') for i in range(11)])
        raise AssertionError(sql)


class FakeSession:
    def __init__(self, *, bind, **kwargs): self.bind=bind; self.kwargs=kwargs
    def __enter__(self): return self
    def __exit__(self, *args): pass
    @contextmanager
    def begin(self): yield self


def snapshot():
    chain=IndustrialChain(101,202,101,303,202,404,303,'temperature','°C')
    refs=tuple(IndustrialMeasurement(i+1,404,NOW-timedelta(days=10-i),65.0,'good') for i in range(10))
    return IndustrialSnapshot(chain,IndustrialMeasurement(11,404,NOW,70.0,'good'),refs,NOW,NOW,
        DeclaredProvenance('operator-dev','approval-record',False))


@pytest.fixture
def doubles(monkeypatch):
    connection=FakeConnection()
    monkeypatch.setattr(diagnostic, 'Connection', FakeConnection)
    monkeypatch.setattr(diagnostic, 'PsycopgConnection', FakeNative)
    monkeypatch.setattr(diagnostic, 'Session', FakeSession)
    def load(session, **kwargs):
        assert session.bind is connection
        assert session.bind.connection.driver_connection is connection.native
        return snapshot()
    monkeypatch.setattr(diagnostic, 'load_snapshot', load)
    monkeypatch.setattr(diagnostic, 'evaluate_snapshot', lambda _: Computed.__new__(Computed))
    return connection


def run(connection, **overrides):
    args=dict(company_id=101,site_id=202,equipment_id=303,cutoff_utc=NOW,
        provenance=DeclaredProvenance('operator-dev','approval-record',False))
    args.update(overrides)
    return diagnostic.diagnose(connection,**args)


def test_exact_scope_read_only_transaction_and_real_evaluator_path(doubles):
    report=run(doubles)
    assert (report.company_id,report.site_id,report.equipment_id)==(101,202,303)
    assert len(report.sensors)==1 and report.sensors[0].sensor_id==404
    assert type(report.sensors[0].result) is Computed
    assert report.sensors[0].window_measurement_count==11
    assert report.sensors[0].quality_counts==(('good',11),)
    sqls = [statement for kind, statement in doubles.statements if kind == 'SQL']
    assert sqls.index('SET TRANSACTION READ ONLY') < next(i for i, sql in enumerate(sqls) if 'set_config' in sql)
    assert [sql for sql in sqls if 'set_config' in sql] == [
        "SELECT set_config('lock_timeout', :timeout, true)",
        "SELECT set_config('statement_timeout', :timeout, true)",
    ]
    assert sqls.index("SELECT set_config('statement_timeout', :timeout, true)") < next(
        i for i, sql in enumerate(sqls) if 'current_setting' in sql)
    assert doubles.tx.is_active is False
    assert all(not any(word in sql.upper() for word in ('INSERT ','UPDATE ','DELETE ','COMMIT'))
        for kind,sql in doubles.statements if kind=='SQL')


@pytest.mark.parametrize('field,value', [('company_id',True),('site_id',0),('equipment_id','303')])
def test_invalid_scope_refuses_before_database_use(doubles,field,value):
    with pytest.raises(diagnostic.DiagnosticRefused): run(doubles,**{field:value})
    assert doubles.statements==[]


def test_synthetic_provenance_is_refused(doubles):
    with pytest.raises(diagnostic.DiagnosticRefused):
        run(doubles,provenance=DeclaredProvenance('fixture','test',True))
    assert doubles.statements==[]


def test_missing_target_is_abstained_without_fabricated_measurement_id(doubles):
    doubles.no_target = True
    report = run(doubles)
    sensor = report.sensors[0]
    assert sensor.status == 'abstained'
    assert sensor.outcome_code == AbstentionCode.INSUFFICIENT_HISTORY.value
    assert sensor.result is None
    assert sensor.target_measurement_id is None
    assert doubles.tx.is_active is False


def test_database_error_rolls_back_and_sanitizes_secret(doubles):
    doubles.fail=True
    with pytest.raises(diagnostic.DiagnosticRefused) as error: run(doubles)
    assert error.value.code=='DIAGNOSTIC_UNAVAILABLE'
    assert 'secret' not in str(error.value)
    assert doubles.tx.is_active is False


@pytest.mark.parametrize('native_status', [
    TransactionStatus.INTRANS, TransactionStatus.INERROR, TransactionStatus.ACTIVE,
    TransactionStatus.UNKNOWN,
])
def test_native_non_idle_state_refused_before_sql_or_rollback(doubles, native_status):
    doubles.native.info.transaction_status = native_status
    with pytest.raises(diagnostic.DiagnosticRefused) as error:
        run(doubles)
    assert error.value.code == 'NATIVE_CONNECTION_NOT_IDLE'
    assert doubles.statements == []
    assert doubles.tx is None


def test_native_idle_state_accepted(doubles):
    assert run(doubles).sensors[0].status == 'computed'
    assert doubles.native.info.transaction_status is TransactionStatus.IDLE


def test_native_autocommit_or_incompatible_driver_refused_before_sql(doubles):
    doubles.native.autocommit = True
    with pytest.raises(diagnostic.DiagnosticRefused): run(doubles)
    assert doubles.statements == []
    doubles.native.autocommit = False
    doubles.dialect.driver = 'psycopg2'
    with pytest.raises(diagnostic.DiagnosticRefused): run(doubles)
    assert doubles.statements == []


def test_untracked_native_transaction_refused_even_when_sqlalchemy_is_idle(doubles):
    doubles.native.info.transaction_status = TransactionStatus.INTRANS
    assert not doubles.in_transaction()
    with pytest.raises(diagnostic.DiagnosticRefused) as error: run(doubles)
    assert error.value.code == 'NATIVE_CONNECTION_NOT_IDLE'
    assert doubles.tx is None and doubles.statements == []


@pytest.mark.parametrize('bad_timeout', [0, -1, True, '5000'])
def test_invalid_timeout_refused_before_checkout_or_sql(doubles, monkeypatch, bad_timeout):
    monkeypatch.setattr(diagnostic, 'LOCK_TIMEOUT_MS', bad_timeout)
    with pytest.raises(diagnostic.DiagnosticRefused) as error: run(doubles)
    assert error.value.code == 'INVALID_SQL_TIMEOUT'
    assert doubles.statements == []
    assert doubles.tx is None


def test_timeout_setup_failure_rolls_back_diagnostic_transaction(doubles):
    doubles.fail_timeout = True
    with pytest.raises(diagnostic.DiagnosticRefused): run(doubles)
    assert doubles.tx is not None and doubles.tx.is_active is False


def test_timeout_readback_mismatch_refuses_before_business_reads_and_rolls_back(doubles):
    doubles.bad_timeout_readback = True
    with pytest.raises(diagnostic.DiagnosticRefused) as error: run(doubles)
    assert error.value.code == 'TRANSACTION_GUARD_MISMATCH'
    assert not any('FROM companies' in sql for kind, sql in doubles.statements)
    assert doubles.tx.is_active is False


def test_timeout_values_are_checked_before_business_reads(doubles):
    run(doubles)
    sqls = [statement for kind, statement in doubles.statements if kind == 'SQL']
    first_business = next(i for i, sql in enumerate(sqls) if 'FROM companies' in sql)
    assert sqls.index("SELECT set_config('lock_timeout', :timeout, true)") < first_business
    assert sqls.index("SELECT set_config('statement_timeout', :timeout, true)") < first_business
    assert next(i for i, sql in enumerate(sqls) if 'current_setting' in sql) < first_business


def test_loader_physical_connection_replacement_is_refused_and_rolled_back(doubles, monkeypatch):
    def replace_native(session, **kwargs):
        assert session.bind is doubles
        doubles.connection.driver_connection = FakeNative(TransactionStatus.INTRANS)
        doubles.connection.dbapi_connection = doubles.connection.driver_connection
        return snapshot()
    monkeypatch.setattr(diagnostic, 'load_snapshot', replace_native)
    with pytest.raises(diagnostic.DiagnosticRefused) as error: run(doubles)
    assert error.value.code == 'NATIVE_CONNECTION_CHANGED'
    assert doubles.tx.is_active is False


def test_existing_sqlalchemy_transaction_is_not_rolled_back(doubles):
    doubles.tx = FakeTransaction()
    with pytest.raises(diagnostic.DiagnosticRefused) as error: run(doubles)
    assert error.value.code == 'CONNECTION_NOT_IDLE'
    assert doubles.tx.is_active is True
    assert doubles.statements == []


def test_rejected_evaluator_result_is_preserved(doubles, monkeypatch):
    expected = Rejected(RejectionCode.INVALID_INPUT, 'quality')
    monkeypatch.setattr(diagnostic, 'evaluate_snapshot', lambda _: expected)
    report = run(doubles)
    assert report.sensors[0].result is expected
    assert report.sensors[0].status == 'rejected'


def test_abstained_evaluator_result_is_preserved(doubles, monkeypatch):
    expected = Abstained(AbstentionCode.INVALID_QUALITY, 11, 10)
    monkeypatch.setattr(diagnostic, 'evaluate_snapshot', lambda _: expected)
    report = run(doubles)
    assert report.sensors[0].result is expected
    assert report.sensors[0].status == 'abstained'
