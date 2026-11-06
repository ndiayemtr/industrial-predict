# P101-DEV-3A — offline orchestration and persistence preparation

`P101DevOrchestrator` requires an explicit `OrchestrationPort` and UTC clock.
No port implementation, authenticated provider, SQL writer, engine, HTTP route
or runtime installation is supplied. The default reader is DEV-2 load_snapshot;
evaluation is DEV-1 evaluate_snapshot. Existing B2B policy/session contracts,
repositories and migrations are unchanged. All port outputs are injected
assertions, not cryptographic evidence; reports keep real_attested=False.

## Prepare, then explicitly attempt persistence

`prepare` takes an internal SessionReference and requested company/equipment/
sensor/target IDs, event cutoff and explicit provenance. IDs select resources;
they are never evidence of access. The port must supply CurrentCaller only after
actual upstream session verification, fresh account/link/membership reads and
expiry/revocation checks IN the supplied transaction. The service revalidates the
structure, exact session reference and refreshed_at, then recomputes the existing
predictions:analyze decision. A role ceiling is not a grant. No browser identity,
boolean, free favorable decision or stale membership snapshot is accepted as
authentication. A malicious injected port can still lie: do not wire one publicly.

The read port supplies a caller-owned DEV-2 compliant READ ONLY snapshot. The
service checks the loader result against the requested IDs and evaluates it once.
The read transaction must actually become inactive on context exit before an
outcome/plan is returned. No service commit/rollback/close is called.

Abstained and Rejected remain distinct and produce no persistence plan. Computed
produces an immutable PredictionDraft and PreparedPrediction. The draft maps
existing prediction_records fields: anomaly, binary score/alert, model/version,
target timestamp, and all original canonical details/provenance/references.
values(created_at=...) returns a fresh dict with explicit creation time; no SQL
row, DB identifier or stored success is fabricated during preparation.

The prepared key identifies company/equipment/sensor/target/model/version. It is
an INSERT uniqueness key, not an authority token or a source-content fingerprint.
The full engine input/details fingerprints separately bind content. Registering
the exact immutable plan in its creating service prevents substituting a copied
plan. An instance-local Lock consumes a plan before its single write attempt.
This is only in-memory anti-retry, not durable or distributed idempotence.

## Write boundary: mandatory future port obligations

`persist(plan)` is an explicit second operation. The write context must supply a
NEW, verified RW transaction, no implicit commit or retry, in the correct database
with bounded deadlines. The service refuses the read Session and its transaction,
requires an active new transaction, reobtains CurrentCaller within it and checks
the same user/issuer/subject/session plus current analysis permission again.
The service's structural transaction checks do not themselves attest RW mode,
destination or driver state; the concrete write port remains to be implemented
and qualified. Nothing in this lot can write SQL without an externally supplied
port implementation.

lock_and_reload must read current parents, target and COMPLETE candidate window,
holding protection against reassignment, source updates/deletes and insert
phantoms until transaction finish. It must retain the applicable account/link/
membership locks too, or refuse if this protection cannot be established. Merely
locking already existing measurement rows is not sufficient to prevent phantoms.
A future adapter needs a reviewed serialization/cooperative locking policy and
real concurrency tests; this interface is not proof that locks were acquired.

The service checks the fresh write observation time against the trusted clock,
then reevaluates the locked snapshot for comparison using the ORIGINAL read
observation time. Only that observation-context field is aligned; all identities,
measurements, policy, cutoff and provenance must preserve the original engine
input/details hashes. A mismatch/abstention/rejection refuses before staging.
The original result/provenance is persisted, not replaced with a fresh historical
availability claim. Availability before the historic target is still unattested.

reserve_and_stage must atomically enforce the prepared logical key and stage one
INSERT without commit. DuplicatePrediction is a no-insert assertion at ONLY that
boundary. The current schema has no dedicated DEV engine idempotency constraint:
a concrete adapter must define and qualify durable uniqueness and retain unresolved
attempts across restart; a Python set is not a production substitute. The service
does not use PredictionService.create (internal commit), nor call the existing
PredictionRepository.create without a separate reviewed transactional adapter.

finish explicitly returns COMMIT_CONFIRMED, ROLLBACK_CONFIRMED or UNCERTAIN; bools,
invalid acknowledgements and exceptions after staging yield UNCERTAIN. No ID is
reported except after confirmed commit. The context owner must rollback on body
errors and may only release resources after finish, never suppress or auto-commit.
A known commit/rollback survives a later resource-cleanup error, with cleanup_failed
set. Uncertainty is never promoted to success or rollback, and every plan is
single-attempt even after refusal. No automatic retry or reconciliation exists.
Unknown/foreign/replaced/already attempted plans refuse before opening a writer.

## Offline tests and remaining blockers

Tests combine the actual DEV-2 reader and DEV-1 evaluator with mocked SQLAlchemy/
Psycopg state and a port double. They exercise live-state assertions, permission
revocation, source changes, immutable payload mapping, transactional failures,
duplicate reservation, lost commit acknowledgements both before/after simulated
commit, terminal local anti-retry and distinct read/write phases. None is real
authentication, actual INSERT, proof of PostgreSQL locks or durability.

Before a secure endpoint: qualify/install the B2B schema and trusted session
provider, implement/qualify the write adapter (RW identity, freshness, locking,
unique reservation and uncertainty recovery), provide durable request tracking,
and authorize a bounded DEV campaign. No existing execution guard is changed;
no migration, environment, frontend or public route is activated by these files.
Keep service instances/plans within a bounded request workflow; their process-local
pending/attempted state is not an authenticated serialized job or persistent ledger.
