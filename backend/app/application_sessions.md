# B2B application sessions — offline persistence foundation

No engine, schema, route, cookie or DEV binding is created by these modules.
Import the model explicitly. Existing model exports and all previously published revisions are unchanged.
Two new general revisions are published offline; their execution remains disabled.

## Schema to migrate later

`public.application_sessions` uses secret_digest (64 lowercase hex) as its PK,
csrf_digest (64 hex), user_id and external_identity_id (positive FK, RESTRICT),
authenticated_at, created_at, last_activity_at, absolute_expires_at, revoked_at
(timestamptz), idle_timeout_seconds, absolute_timeout_seconds (positive integers),
replaced_by (nullable self-FK, RESTRICT) and contract_version=b2b-session-v1.
The model has no schema qualifier, like professional accounts: enforce
search_path=public on the approved runtime. No permissions, roles, company_id,
raw bearer/CSRF secret or provider token is stored.

CHECKs pin the version, hex formats, temporal ordering, exact absolute lifetime,
revocation ordering and non-self replacement only after revocation. Indexes cover
user enumeration and absolute expiry. No cleanup/purge executor is included.

The final ORM and offline revision b2b_0001_sessions enforce the pair
(external_identity_id, user_id) with a composite FK to external_identities(id,
user_id), backed by the new uq_external_identities_id_user constraint. The direct
user FK and replacement self-FK remain RESTRICT. The old single identity FK is
replaced, not duplicated. The adapter still checks exact issuer/subject and active
account state under locks: the FK does not authenticate or prove an active account.
These are declared constraints, not installed/qualified PostgreSQL guarantees.

The general chain extends 4b7e2a91c6d0 with b2b_0001_sessions, then
b2b_0002_analyze. The latter changes only the permission CHECK: explicit
predictions:analyze grants are admitted only for company_admin. It creates no
grants, memberships, accounts or sessions. Published OIDC/account revisions stay
byte-for-byte unchanged. Manifests recognize four fixed publications; independent
AST pins reject changed operations even with a recomputed source hash.

Both new downgrade bodies refuse unconditionally. A later reviewed retention and
approval procedure must precede any destructive session removal or CHECK rollback
with analysis grants. A work failure before commit and an approved post-deployment
downgrade are distinct operations. No automatic deletion or privilege removal.

On an empty-data database already at 4b7e2a91c6d0, the session table is created
empty; existing accounts/identities need no backfill. A database without the
prerequisite schema is not a valid starting point. Unexpected existing objects
must fail rather than be hidden by IF NOT EXISTS. PostgreSQL DDL locking, data
preservation and transactional behavior still need isolated qualification.

The current general guards keep MigrationExecutionDisabled unconditional,
including after preflight. No create_all, manual SQL or alternate Alembic loader
is a substitute. No timestamp-isfinite hardening is added in this minimal lot;
PostgreSQL infinity handling remains an explicit qualification/hardening topic.

## Authority and operations

PostgresApplicationSessionStore requires an explicit SqlRuntime, trusted admission
provider and UTC clock. create() takes no client identity/company argument. It
accepts only a READY/VALID AdmissionDecision, then rechecks the active local user
and exact external link in SQL. The provider must really perform the approved
verification/admission; constructing a typed decision cannot prove this.

read(reference) verifies both current local account state and session lifetime;
touch, revoke and rotate re-use the pure contracts. Individual revoke follows the
pure live-session transition and therefore rejects expired/revoked/suspended
sessions. Administrative revoke_for_user also handles expired sessions and
suspended accounts. Enumeration and bulk revocation are denied by default: an
injected server authority callback must approve the exact user and return None.
A client user_id or a returned bool never supplies authority.

create/rotate generate independent 32-byte CSPRNG bearer and CSRF secrets, encoded
as canonical unpadded base64url. SHA-256 fingerprints are domain-separated with
b2b-session-v1 and b2b-csrf-v1. Only fingerprints enter SQL. IssuedSession exposes
the two raw values solely to trusted delivery code AFTER commit confirmation;
repr is opaque. It is not a public JSON DTO. No memory-erasure guarantee exists.
CSRF comparison/HTTP enforcement is deferred, not implemented by storing a hash.

## Transactions and concurrency assumptions

Each operation owns a fresh session/transaction, READ COMMITTED, lock_timeout=5s,
statement_timeout=15s. No implicit retry. Engine echo/DEBUG logging and exposed
parameters are refused; operator SQL logs, diagnostics and backups also require
protection. Public errors are constant and discard driver exception chains;
debuggers that collect locals remain outside this protection.

Lock order is user FOR UPDATE, session FOR UPDATE when present, external identity
FOR SHARE. Creation has user then external identity then insert. All mutating
administrative account/link code must use the same user lock ordering.
Identity issuer/subject keys are treated as immutable: a future administrative
change must revoke affected sessions under that user lock before changing a key.
The existing repository offers no update/reassignment operation; raw SQL by a
privileged administrator remains a separate trust boundary.
Per-user serialization prevents a concurrent rotation/create from slipping through a bulk
revocation while its user lock is held; it does not prohibit a later new login.
Deadlock/timeouts fail closed with no retry. Database clocks must be synchronized.

The database clock is sampled in a separate command AFTER locks return. Caller
and database instants must both accept a live session. Activity and rotation use
the later instant, preserve authenticated_at and absolute_expires_at. Expiration
after the decision while committing remains possible; no promise of unlimited
freshness is made. Reads do not load memberships or constitute CurrentCaller.

Rotation inserts the successor and conditionally invalidates the locked old row
in ONE transaction. The self-FK explains insert-before-update order. Any failed
conditional update rolls back both changes. No new credential is returned before
commit. All commit exceptions are **SESSION_STORE_COMMIT_UNCERTAIN**, even if a
subsequent rollback succeeds. Do not retry, announce success, or restore the old
session automatically. A close failure after an acknowledged commit does not
cancel that confirmation. A lost HTTP delivery can leave an undisclosed session.

## Deployment privileges and qualification still required

Owner/migration authority is separate from runtime. Runtime needs SELECT/INSERT
on application_sessions and UPDATE only on last_activity_at, revoked_at and
replaced_by (also sufficient for row locks); no DELETE, DDL or sequence grant.
It needs SELECT on local_users/external_identities plus a minimal column UPDATE
grant on each for PostgreSQL row-lock statements (e.g. id); adapter never updates
those tables. Reassess whether separate administrative credentials are preferable
before deployment. Grant no membership or business-table write privileges.

Before activation: verify isolated destination, TLS, roles, public search_path,
FK/CHECK/index deployment and prior revision; test actual two-connection locks,
rotation/revocation/create races, expiry while waiting, suspension/relinking,
uniqueness conflicts, rollback and uncertain/lost commit outcomes. Compare data
before/after; exercise new connections. Offline doubles and DDL compilation prove
none of PostgreSQL durability, lock behavior or successful schema installation.

No OIDC transaction storage, caller-session pure contract, permission policy,
Angular, main assembly or session endpoint is modified or installed by this lot.

## INT-3C1K offline publication boundary

The session PK makes secret_digest unique; csrf_digest is independently generated,
not globally UNIQUE. No sequence is needed by this adapter. touch/revoke update
only allowed columns. rotate inserts the successor before updating the predecessor,
so the replacement FK need not be deferred. The replacement FK alone does not
prove matching user, identity, or absolute expiry; application checks remain required.

Qualification must use separate real connections for expiry after lock waits,
rotation/revocation/create races, account suspension and relinking; fresh reads
after commit; rollback/uncertain commit; FK/CHECK/UNIQUE failures and minimal
privileges. UPDATE(id) used to permit row locking is a real write capability,
not a lock-only privilege. Verify business equipment/measurement fingerprints
are unchanged, and grants for company A never authorize company B. Offline DDL,
AST, SQLite account tests and simulated session tests are not PostgreSQL evidence.
