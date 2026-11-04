# INT-3C2B — offline B2B PostgreSQL qualification contracts

This directory is a standalone, standard-library-only foundation. It contains no
collector, SQL, Docker client, process launcher, operational signature, migration
loader or executor. No application module is imported. Existing execution guards,
DEV, P101 and OIDC are unchanged. Namespace-package imports use the existing
pytest `pythonpath = backend tests` setting; no package bootstrap is necessary.

## Files and boundary

- `contracts.py`: immutable, opaque declarations and one authority Protocol.
- `validation.py`: explicit validation, canonical fingerprints, comparisons,
  declared effect journal and scenario catalogue.
- `test_contracts.py`: synthetic positive/negative tests, plus read-only checks of
  the already-published source references. No migration module is imported.

Constructors do not validate authority, uniqueness, provenance or live state.
The protected validation/comparison entry points revalidate their inputs. Objects
inheriting from `Offline` expose `execution_authorized=False`, `authenticated=False`
and `real_attested=False`; their boolean conversion refuses and their repr is
opaque, including for malformed raw instances. `Scenario` is a static descriptive
record with the standard dataclass repr, not an `Offline` result. Entry points
wrapped by `guarded`, and the explicit refusals using `deny`, emit constant public
diagnostics with cause/context detached. Helpers called directly do not
automatically provide that error-sanitization guarantee. This does not erase
memory, frame locals, independently retained errors, or malicious server code.
Canonical envelopes contain metadata only: do not put
secrets into identifiers. No automatic logging or JSON serialization is supplied
for secrets or observation payloads.

## Campaign and exclusions

The profile declares PostgreSQL 17.10/linux-amd64, a private RFC1918 /24–/28,
one PostgreSQL container, one runner, an internal network and a named data volume.
No host port or extra mount is admitted by the observation profile. Certificate
delivery and a fuller inventory will require a separately reviewed profile;
this first contract is deliberately not a deployment recipe.

Resource names, database, host, cluster and four distinct roles are bound exactly
to a canonical nonzero campaign UUID. Container/runner/network IDs are distinct
full digests. The instance UUID is independent. The Docker engine can be shared;
its identity does not establish resource isolation. All resources are declarations,
not proof of creation, ownership, global uniqueness or route non-overlap.

Known exclusions are explicit: historical/DEV/P101 database and resource names;
ports 5433/5434/55432 and OIDC 56439 (also existing application ports); the DEV
instance UUID; the OIDC campaign UUID, old container ID, network ID and
172.30.91.0/28 subnet from `tests/oidc_postgres_bootstrap/validation.py`.
The DEV UUID is the identity supplied in REV-2B1. Unknown private IDs/subnets are
not discovered. A future independent exhaustive inventory must supplement these
static exclusions; campaign-looking names or caller-supplied IDs never prove a
resource is new. Loopback hosts, existing role names and alternate ports fail.

## Published migration references

`PUBLICATIONS` is a closed snapshot at
`3917027af6fabb482af1fa4a650e4f676025b8ad`. The nine historical source hashes
come from `backend/app/general_migrations.py`; the four general references come
from `backend/general_migrations/revision_manifest.json`. No hash is generated
or re-approved at validation time. The source-verification test checks all paths,
hashes and parent metadata by reading files/AST only.

Four disjoint plans are recognized: bootstrap (nine historical revisions),
prerequisites (OIDC then accounts), sessions, and analysis. `None` as bootstrap's
initial revision is a declaration of an empty initial state, not permission to
bootstrap or stamp a database. Reordering, additions, wrong parents, paths,
revisions or hashes fail. The application general resolver remains unchanged and
cannot execute/bootstrap these plans.

## Approval and observations

An approval envelope binds authority ID, campaign, exact operation, full campaign
inventory fingerprint, publication-plan fingerprint and an injected UTC window
of at most 15 minutes. Its canonical JSON is deterministic. Its SHA-256 is a
content fingerprint, not a signature or approval ID consumed durably.

`IndependentAuthority` has no operational implementation. `review_approval`
requires a typed favorable assertion bound to the exact envelope; booleans,
missing/unfavorable/unbound claims fail. Even a favorable double produces only
`unverified_authority_claim_only`, never authentication. `request_execution`
always refuses, before inspecting inputs or invoking any authority. There is no
key store, verifier, replay protection, issuance service or enable switch.

Nine observations are required: a Docker declaration, plus PostgreSQL and TLS
declarations for each of the four roles. Role sessions use distinct declared PIDs
and connection IDs. SQL/TLS observations are paired by connection ID, PID,
timestamps and provenance. Facts must match the closed identity/inventory profile.
Collection intervals are at most 10 seconds, and observations at most 30 seconds
old relative to the explicit UTC `now`; future observations fail. No clock is read.

Only `synthetic` and `unverified_external` provenance are accepted. Neither proves
actual collection. Literal `real`/`attested` claims fail; a caller falsely using
`unverified_external` still cannot obtain real attestation. Comparison returns
`injected_observations_only`; `require_real_attestation` always refuses. The TLS
fields are injected claims, not proof of a TLS handshake. Tamper-resistant
evidence collection, monotonic/live timing and the observe/use race remain future
work. The profile does not certify all privileges or catalogue/schema contents.

## Effects and scenarios

The immutable journal binds campaign and destination, orders UTC events and keeps
refusal, rollback-confirmed, commit-confirmed and uncertain declarations distinct.
Commit/rollback declarations require an evidence digest; that digest is not a
verification. After `uncertain`, *all* further append attempts fail, including a
success or rollback. Revalidating a constructed history with a later event also
fails. There is no reset, reconciliation, persistence, cleanup or retry API.
Callers can retain/discard objects: this is not durable tamper-proof storage.

The 26 immutable scenario descriptions cover migrations, sessions, concurrency,
authorization and privileges. Each records preconditions, future action, expected
result, evidence and stop condition. No action is callable; no runner exists.
Infinity gaps, row-lock UPDATE privileges, retained RESTRICT references and lost
commit acknowledgements remain real-PostgreSQL qualification topics.

## Targeted validation

From the repository root, one targeted offline campaign:

```powershell
& backend/.venv/Scripts/python.exe -B -m pytest tests/b2b_postgres_qualification/test_contracts.py -q -p no:cacheprovider
```

These tests do not validate Docker isolation, PostgreSQL installation/durability,
TLS, real approval or application authentication. The next step is review of the
contracts and a separate specification of independent authority/evidence sources;
no PostgreSQL qualification or deployment follows automatically.
