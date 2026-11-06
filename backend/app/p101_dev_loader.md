# P101-DEV-2 — injected industrial snapshot SQL reader

`p101_dev_loader.py` lives outside the pure `p101_dev` package. It imports only
settings-independent ORM metadata, B2B policy types and immutable projections.
There is no engine factory, configuration lookup, connection acquisition, CLI,
endpoint, prediction writer or lifecycle operation. It performs parameterized
Core SELECTs on private public-qualified copies of the five existing model tables;
no shared ORM metadata, schema or connection options are changed.

## Caller contract and security

`load_snapshot(session, authorization=..., equipment_id=..., sensor_id=...,
target_measurement_id=..., event_cutoff=..., observed_at=..., provenance=...)`
returns `IndustrialSnapshot`, not a prediction or authorization result.

The caller must already have verified the live B2B session, active account,
company membership and explicit analysis grant using the existing policy. The
loader requires the current-policy ALLOW decision for predictions:analyze and
checks the resolved SQL company against that decision. This typed decision is
only a server assertion: manually constructing it, sending a company ID or using
a mock is not authentication. No provider/default grant is installed. Upstream
policy must also cover the business reads needed by the operation.

The connection destination, role, instance, revision, transport and privileges
must be independently verified before calling. This component does not discover
or attest DEV identity. The caller supplies aware native datetimes and explicit
provenance; their origin/freshness are not independently authenticated here.

## Transaction lifecycle

Require a caller-owned PostgreSQL Connection already in a non-nested active
transaction and a Session explicitly bound to it. The Session must have an active
explicit `begin()` (not AUTOBEGIN), autoflush disabled, no new/dirty/deleted ORM
objects, and join_transaction_mode="rollback_only". Mapper-specific bindings
must resolve to that same Connection. Engines, unstarted/inactive transactions,
savepoints, schema translation/redirection and non-PostgreSQL dialects refuse.

FIX1 restricts the transport to the synchronous SQLAlchemy `postgresql+psycopg`
dialect and a native `psycopg.Connection` (repository pin: Psycopg 3.3.4). The
existing pool proxy's public `driver_connection` and `dbapi_connection` must be
the identical native connection. Its `autocommit` must be the literal False,
closed/broken must be False, and info.transaction_status must be the native
TransactionStatus.INTRANS. Missing, unreadable, ambiguous or unsupported driver
signals refuse without SQL. Async adapters and other drivers are not admitted.
This reads actual driver state, including engine-inherited autocommit; a declared
isolation execution option or logical SQLAlchemy transaction cannot override it.

This check precedes get_isolation_level(): that API does not report AUTOCOMMIT,
and the installed psycopg dialect rolls back its isolation probe if it started
from IDLE. Requiring native INTRANS first avoids that path. Native ownership/mode
is checked again around the probe/server check and at exit, with the same native
connection required across the load. No property setter, driver transaction
method or reconnect is used. Unknown physical state is never treated as a valid
transaction. These source/API checks are not a real PostgreSQL qualification.

The caller sets REPEATABLE READ or SERIALIZABLE before beginning its physical
transaction, establishes READ ONLY before business reads and supplies bounded
statement/lock deadlines. This is a read-phase contract, not a write orchestration.
The loader checks driver isolation and server transaction_isolation/read_only
before and after its reads, and verifies the same Session transaction, Connection
and physical transaction objects remain active. No begin, SET, flush, savepoint,
commit, rollback, close or automatic retry is called by the loader. It does not
materialize a Session connection or use cached ORM entities/relationships.

In PostgreSQL READ COMMITTED, successive SELECTs can see different committed
states, even inside one transaction; that mode is refused. REPEATABLE READ keeps
the snapshot established by the first relevant statement for the transaction;
SERIALIZABLE also provides a stable snapshot and may fail with serialization
errors, which remain refusals with no retry. A transaction may already have an
older snapshot: the caller controls when it starts, freshness and authorization.
The Session and Connection must not be shared across threads/tasks or changed
concurrently. Entry/exit checks cannot make a malicious/incoherent driver safe.

On any loader failure the caller still owns cleanup. In particular, a failed
SQL statement can leave PostgreSQL's transaction aborted: do not reuse it until
the caller has explicitly rolled it back. No rollback confirmation is fabricated.
Before a future write in a separate write transaction, verify current authorization
and resolve/check the equipment/sensor/measurement chain again; this old snapshot
does not protect against reassignment or revocation after it was taken.

## Resolution and temporal candidates

1. Resolve sensor -> equipment -> site -> company through SQL joins. Compare all
   effective IDs/FKs with the requested equipment/sensor and trusted company scope.
   Missing/orphan/ambiguous chains refuse before measurement queries.
2. Read the explicit target ID under that sensor; missing/ambiguous/mismatched
   targets refuse. The target must have an aware timestamp to define the window.
3. Normalize target, cutoff, observation time and every candidate to UTC before
   time arithmetic/comparison. Read every other measurement of that sensor from
   target minus exactly 10*86400 seconds through
   min(target timestamp, event cutoff), both ends inclusive. Exclude only the
   selected target ID. Keep other measurements at target time to expose duplicate
   timestamps. Both bounds and consistency comparisons use aware UTC instants,
   including across DST transitions or ambiguous local fold values. Conversion
   changes only the in-memory representation, preserves microseconds and never
   writes or repairs stored dates. Order timestamp/id ascending, with no quality/value filter,
   DISTINCT, resampling, nearest-neighbor selection or last-ten truncation.

Rows after the target/cutoff or older than the window are not temporal candidates.
This exclusion is explicit event-time policy, not quality filtering. A target
after cutoff remains in the snapshot so the engine returns TARGET_AFTER_CUTOFF;
its references still cannot leak events after cutoff. No available_at is invented:
the existing engine's historical-availability limitation remains unchanged.

Fetch at most 33 candidate rows. If more than the existing maximum of 32 are
observed, refuse the entire load with CANDIDATE_LIMIT, never return a truncated
snapshot. Otherwise every returned candidate is copied without changing quality,
values or timestamp instants (UTC representation only). Unexpected out-of-window/foreign-sensor SQL rows refuse
rather than disappearing. Duplicate candidates are preserved. The resolved
sensor supplies its unit; measurements has no independent unit column.

Insufficient history, bad quality/unit/value, cadence, duplicates and zero std
remain `Abstained`/`Rejected` outcomes of `adapt`/`evaluate_snapshot`, not loader
calculations. Malformed scope/session, absent target, inconsistent SQL shape or
SQL failure raises `SnapshotLoadError`: constant public diagnostic, closed
LoadCode and detached exception context; no raw driver errors, data or logs.

## Offline evidence and remaining qualification

`tests/p101_dev_sql/test_loader.py` uses synthetic Session/Connection doubles and
compiles actual statements with the installed PostgreSQL dialect. It checks SQL
predicates/bounds, stable transaction checks, ownership, scope and preservation of
invalid rows, then passes snapshots to the unchanged adapter/engine. Engine/socket
connection entry points are blocked. Mocks can lie: these tests do not prove
PostgreSQL snapshot isolation, driver behavior, live ACLs, RLS, provenance,
destination identity or concurrent authorization. No SQL statement was run on a
real PostgreSQL server in this lot.

FIX1 regressions cover native autocommit (including inherited/misleading options),
missing/ambiguous signals, non-INTRANS status, native replacement/mode changes and
refusal before SQL. They also cover offset equivalence, spring/fall DST changes,
both ambiguous fold orderings, cutoff leakage, exact inclusive bounds and one
microsecond outside each bound, preserving existing invalid-data outcomes. Zone
rules use local tzdata already installed; no network or PostgreSQL is consulted.

The installed SQLAlchemy Session/dialect sources were consulted for explicit
transaction origin, binding/join behavior and isolation introspection. Before a
future DEV connection, separately authorize a read-only qualification with the
real driver, verified destination/role, server isolation/read-only/deadlines,
concurrent reassignment cases and fresh B2B authority. No migration or public API
activation follows from these unit tests.
