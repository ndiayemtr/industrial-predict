# INT-3C2B — offline B2B PostgreSQL qualification contracts

The INT-3C2B contracts/validation base uses only the standard library. The INT-3C2C
extension below adds offline cryptographic verification. This directory contains no
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

## INT-3C2C — offline authority and evidence foundations

`authority.py` uses Ed25519 verification from `cryptography`; `evidence.py` uses
its X.509 server-certificate policy verifier. `test_authority_evidence.py` generates
ephemeral signing keys and a synthetic EC CA/leaf chain in memory only. There are
no private key bytes, PEM credentials, signing API or production keys in the repo.
No transport or acquisition implementation is supplied. The original INT-3C2B
contracts, unconditional execution/attestation refusals and Alembic guards remain
unchanged.

Dependency availability was checked without installation: the main backend venv
has no cryptography/PyJWT; the existing
`D:/projets/industrial-predict-oidc-m1b-venv` has cryptography 50.0.2 and pytest 9.1.1.
The extension imports crypto lazily and rejects verification if unavailable. Its
crypto tests require that dependency and do not silently substitute or skip real
signature checks. No dependency declaration or shared environment is changed.

### Trust and signed intentions

`ApprovalVerifier` receives a nonempty immutable tuple of `TrustedKey` records and
a separate `MemoryReplayRegistry`. No submitted `Campaign`, `Approval` or
`SignedApproval` can supply a public key, key source, algorithm or trust callback.
Authority/key pairs and public keys are unique in the injected trust snapshot.
The fixed path verifies raw 64-byte Ed25519 signatures with the independently
configured public key. Unknown, revoked, duplicate, out-of-window and malformed
keys/approvals fail with the existing constant public diagnostic.

`signing_bytes` produces the versioned Ed25519 intention bytes, not a signature.
It reuses the INT-3C2B canonical approval and adds an approval UUID, key ID,
initial/final revisions, exact publication references and initial-state digest.
The approval already binds campaign/destination inventory, operation, plan and UTC
validity window. Verification checks a separately supplied expected initial-state
digest. `evidence_fingerprint` can reference the complete injected evidence/policy
snapshot, but cannot make those observations real. A valid signature proves the
key signed these exact bytes, not human consent, current server identity or that
the declared initial state actually exists.

The replay registry consumes (authority ID, approval UUID) only after successful
verification. A lock provides atomic single use in this registry within one
process. There is no persistence, reset, release or retry API. Another registry or
process cannot know the old consumption; no durable anti-replay guarantee is made.
Trust-root origin, live revocation, durable replay and lost process-state recovery
remain unmet operational prerequisites. Keys are logically separate arguments;
their physical delivery/storage independence is a deployment responsibility,
not something an injected Python object proves.

`SignatureReview.signature_verified` describes the offline verification path.
Its `authenticated`, `real_attested` and `execution_authorized` properties all
remain false. A manually constructed result is not a proof. Even a valid signature
cannot enable `request_execution`, which still refuses without inspecting inputs.

### Three injected adapters, no collectors

`ObservationSource` is an unwired protocol. `collect_real_evidence` refuses before
calling any source. The sole protected comparison entry point `review_evidence`
revalidates all nine INT-3C2B observations, then uses separate Docker, PostgreSQL
and TLS comparison adapters. Supplemental tuples are closed, bounded and revalidated.

- Docker compares engine/context endpoint fingerprint, container/image, the exact
  network, named-volume creation identity and inventory. Context/image/creation
  expectations come from the separately supplied `CollectorPolicy`. Existing
  exclusions, internal-only network and no published port profile remain intact.
- PostgreSQL compares the base destination, role, cluster, instance, version and
  revision, plus role-specific privilege claims. Runtime claims admit only the
  session writes and row-lock column rights required by the store, no sequence
  grant, DDL, membership or business write capability. Admin/migrator/observer
  profiles are explicit. These are not observations of effective PostgreSQL ACLs.
- TLS checks the injected DER leaf/intermediates with cryptography's server policy
  at explicit `now`, against the independently supplied trusted CA and campaign
  hostname. The CA DER hash must match the approved campaign. Merely asserting
  `chain_verified=true` cannot bypass parsing, signature, hostname or expiry
  checks. Certificate sizes and chain depth are bounded; extra/trailing DER is
  rejected. No certificate or CA is read from disk.

An offline valid certificate chain does not prove a handshake took place or bind
that certificate to an actual PostgreSQL connection. PID/connection/provenance
matching remains declarative. No network revocation lookup, CRL/OCSP policy,
tamper-resistant evidence source or observe/use race protection is provided.
Changing a field to `real` is refused; hand-built objects never obtain a real
attestation. The profile still excludes actual certificate-delivery mounts and is
not deployable as-is. Opaque repr and guarded diagnostics cover the new protected
entry points; frame locals, external diagnostics and caller-retained data remain
outside that guarantee.

One grouped offline campaign, including the existing local contract tests:

```powershell
& D:/projets/industrial-predict-oidc-m1b-venv/Scripts/python.exe -B -m pytest tests/b2b_postgres_qualification -q -p no:cacheprovider
```

Next minimum step: review the trust/canonical-intention and evidence profiles,
then specify a durable authority/replay boundary and independent collectors in a
separately authorized mission. No bootstrap or migration execution follows from
this foundation.
