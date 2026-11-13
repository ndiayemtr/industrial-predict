# P101 operator diagnostic (read only)

`p101_operator_diagnostic.py` exposes `diagnose(connection, *, company_id,
site_id, equipment_id, cutoff_utc, provenance)`. It is a private Python entry
point, not imported by HTTP routes. It accepts an already-created synchronous
SQLAlchemy PostgreSQL `Connection`; it does not look up settings, create an
engine, acquire credentials, or close the caller's connection.

Before changing isolation or issuing SQL, the call rejects a closed or
invalidated SQLAlchemy connection, any SQLAlchemy transaction/savepoint, and
anything other than the actual synchronous `postgresql+psycopg` connection with
`autocommit=False` and native `TransactionStatus.IDLE`. An inaccessible or
replaced DBAPI connection fails closed. A pre-existing SQLAlchemy or native
transaction is never rolled back by the diagnostic.

The call also rejects malformed IDs, non-UTC/naive cutoffs, and synthetic
provenance. It sets REPEATABLE READ, begins its own transaction, sets READ ONLY,
then applies transaction-local `lock_timeout=5000ms` and
`statement_timeout=15000ms` before business queries. PostgreSQL settings are
read back and compared with the required values before the first business read.
These limit each lock wait and each SQL instruction respectively; they are not
a wall-clock limit for the full diagnostic across multiple sensors. Failure to
apply or verify any guard aborts and rolls back only the transaction created by
the diagnostic. No permanent PostgreSQL setting is changed.

Company/site/equipment are joined and checked;
the selected equipment's sensors and existing target measurements at or before
the cutoff are read in that same transaction. Per-sensor summaries contain
counts, quality distribution, and time bounds, but no raw measurement values.
The existing `load_snapshot` and `evaluate_snapshot` are used unchanged on the
same SQLAlchemy connection/session and the native psycopg connection identity
is checked around the loader/evaluator path. No missing measurement or identifier is
invented. A sensor without a target is reported as `status="abstained"`, with
`outcome_code="INSUFFICIENT_HISTORY"`, `result=None`, and no target ID.

On success or failure the owned transaction is rolled back; the supplied
connection remains open. SQL/driver exceptions become a constant sanitized
`DiagnosticRefused` code. The function issues no INSERT, UPDATE, DELETE, DDL,
or COMMIT and does not call the application prediction writer. The constructed
`predictions:analyze` decision is only a local operator assertion required by
the existing loader contract. It does not authenticate a user or authorize an
application request. Provenance is still caller-declared, not cryptographically
verified. Do not expose this function through HTTP or treat it as a B2B flow.

## Later operator procedure

Execution against DEV has not been authorized or performed. After separate
human authorization, an operator must use the approved DEV access procedure
and secret store; do not print a DSN/password. On the same supplied connection,
independently compare `current_database()`, `session_user`, `current_user`,
`inet_server_addr()` and `inet_server_port()` with the approved destination.
Check the role is not superuser, database/role creator, replication or
BYPASSRLS; inspect inherited memberships and source-table ownership. Confirm
SELECT on `public.companies`, `sites`, `equipments`, `sensors` and `measurements`,
and no table/column INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES or TRIGGER
rights. Review RLS flags/policies and stop on any unknown visibility behavior.
Confirm finite `statement_timeout` and `lock_timeout`. The operator should
perform these checks on the connection that will run the diagnostic, then
rollback the preflight read transaction so SQLAlchemy reports it idle. The
diagnostic independently requires the native psycopg connection to be IDLE.

Select and record the approved company, site, equipment and UTC cutoff before
execution. Create a synchronous SQLAlchemy `Connection` explicitly, then call
the function with confirmed IDs. Example call shape:

```python
from datetime import datetime
from app.p101_dev.contracts import DeclaredProvenance
from app.services.p101_operator_diagnostic import diagnose

# `approved_engine` is supplied by the separately approved, identity-verified
# operator setup. Confirm the three IDs and cutoff before running this block.
with approved_engine.connect() as connection:
    report = diagnose(
        connection,
        company_id=CONFIRMED_COMPANY_ID,
        site_id=CONFIRMED_SITE_ID,
        equipment_id=CONFIRMED_EQUIPMENT_ID,
        cutoff_utc=datetime.fromisoformat("2026-01-31T12:00:00+00:00"),
        provenance=DeclaredProvenance(
            source_id="operator-dev",
            declaration_ref="APPROVAL_RECORD_ID",
            synthetic=False,
        ),
    )
```

The operator must compare the server/database/role with independently approved
values; this function does not attest them. Stop if the identity, privileges,
timeouts, scope, sensor
selection, transaction mode, quality distribution, or temporal coverage differs
from the approved request. Record only sanitized status/reason/count/time-bound
evidence. Do not include credentials, user secrets, or measured values.

`Computed` means the existing evaluator computed its binary score from the
loaded target and references. It is not a failure probability. `Abstained`
means the evaluator declined to compute under its existing rules; a sensor with
no target has the explicit missing-target representation described above.
`Rejected` means the evaluator found invalid/inconsistent input. A request or
database guard failure raises `DiagnosticRefused` and is not a prediction
outcome.

## Evidence boundary

The targeted tests use doubles and exercise the transaction contract, scope,
loader/evaluator call path, abstention, refusal, rollback, and secret
sanitization. They are offline evidence only. They do not qualify PostgreSQL
DEV, actual role grants/RLS, live data, destination identity, TLS, or source
provenance. Angular continues to show its existing simulation; there is no real
analysis API or persistence integration.
