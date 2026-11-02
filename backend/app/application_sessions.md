# B2B application sessions — offline persistence foundation

No engine, schema, route, cookie or DEV binding is created by these modules.
Import the model explicitly. Existing model exports and migrations are unchanged.

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

The independent user and external-identity FKs do NOT prove that the identity
belongs to that user. The adapter verifies that exact pair at creation and every
read under user/external-link locks. Direct SQL can still create an inconsistent
pair; the adapter rejects it. A future database-level composite FK would require
a new UNIQUE(id,user_id) on external_identities, corresponding ORM changes and
explicitly reviewed migration scope; no existing model is changed here.

The future general revision must follow **4b7e2a91c6d0**, after the published OIDC
and professional-account revisions. Do not edit either published revision.
Prepare the new schema revision, source fingerprints/manifest, scope and approval
mechanism in a separate mission. Current general guards only recognize the old
scope and keep MigrationExecutionDisabled unconditional, including after
preflight. No create_all, manual SQL or alternate Alembic loader is a substitute.

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
