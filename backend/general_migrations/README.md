# General migrations: offline foundations only

Execution is unconditionally disabled. `env.py` always refuses, including when
a connection is injected. There is no CLI executor, signature scheme, issuer,
default key, enable flag, or trusted approval authority in this component.
P101's verifiers are a different trust domain and are not imported or reused.

`MigrationIntent` is an intent; `ApprovalDeclaration` is an **untrusted claim**.
`preflight()` checks the exact destination declaration, transport expectations,
expiry, schema scope, revision sequence and current source fingerprints. Its
report always says `authenticated=False` and `execution_enabled=False`.
The allowlisted `oidc-migration-test` label is synthetic, not permission to
connect to an existing database. No production or DEV/P101 destination is enabled.
No connection identity has been inspected or proved by these offline checks.

The INI has no `script_location`, `version_locations`, import path or URL.
Direct Alembic graph commands fail before discovering/importing revisions.
`make_alembic_config()` calls `inspect_sources()` first, checks the INI options,
and returns a configuration that is STILL INERT. It never hands physical revision
locations to Alembic. This also avoids check-then-import races after API return;
rechecking once before returning a conventional loader would be insufficient.
Explicitly reconfiguring Alembic elsewhere is outside this component's boundary.

The nine historical sources remain in their original directory, with pinned
SHA-256 fingerprints over UTF-8/LF source (checkout CRLF is normalized). Safe graph
inspection uses AST metadata, never revision imports. `revision_manifest.json`
is the closed positive list of recognized publications: revision, parent, exact
backend-relative path, SHA-256 and scope. It contains exactly two revisions:
`12e2fc65f372` descends from `09ac8101e9fe`, and `4b7e2a91c6d0` extends it
with public.local_users, public.external_identities, public.company_memberships
and public.membership_permissions. Unknown keys, duplicate keys/entries,
external paths, altered hashes, redirects and extra files/directories in
`versions/` are rejected. `.gitkeep` is the only non-revision file allowed there.
No expected hash is derived automatically from directory discovery.

Order: validate manifest, compare exact file set, check paths, read all sources,
verify all expected hashes, parse AST, validate graph, check OIDC operations,
validate the independently pinned account AST, then include the manifest and
sources in the snapshot. A matching manifest is
recognition of a versioned publication, NOT proof of administrative approval.
Changing both the manifest and source cannot enable execution or Python loading.
The two-location loading strategy is reserved for a later reviewed activation
lot; it is not an operational configuration today. P101/local-demo paths stay intact.
An empty reference-to-reference plan is useful for offline contract checks only;
it cannot execute or bootstrap business tables.
Only a linear graph extending the historical chain is supported. Dynamic targets,
unknown revisions, branches, merges, downgrade, stamp and autogeneration are denied.

The published OIDC module is never imported, including by tests. Its closed AST profile
permits only the exact two imports, four literal metadata assignments and two
undecorated, parameterless functions. Literal calls must describe exactly the
13 required columns, nine named constraints and one expiration index. Unknown
calls, raw SQL execution, helpers, module-level execution, dynamic expressions,
decorators, defaults and operations outside OIDC are rejected. This is not a
Python sandbox or an authorization to import arbitrary future scripts.

The ORM and published revision both require exact length 43 for nonce/verifier.
The upgrade creates only `public.oidc_transactions` and its index. The downgrade
describes only their removal, without CASCADE. Neither function has been run;
having downgrade code never authorizes operational downgrade.

Destination hosts accept ASCII DNS labels (1–63 characters, alphanumeric ends,
hyphens inside, total at most 253), IPv4 literals or unbracketed IPv6 literals.
Trailing DNS root dots, empty labels, malformed numeric IP spellings, scoped IPv6,
URLs and Unicode/IDN spellings are rejected. No DNS lookup is performed.

Before enabling execution, a separate reviewed lot must establish a recognized
approval authority, an independently maintained destination inventory, immutable
approved release bytes and live transport/identity/state verification. Hashes
alone neither authenticate an approval nor eliminate filesystem TOCTOU races.
Schema scope is a declaration check, not a sandbox for arbitrary Python scripts.

The future administrative launcher must own the supplied connection and a single
outer transaction, confirm commit itself and classify lost acknowledgements as
uncertain, without automatic retry. The environment must use that transaction
with `target_metadata=None`, transactional DDL and no per-migration commit.
For an existing external transaction, Alembic's `begin_transaction()` is a no-op;
this behavior is checked with a simulated connection against installed Alembic.
It does **not** make scripts commit-free: `autocommit_block()` unconditionally
commits preceding work. Such blocks, direct commits and connection creation must
be excluded from future approved scripts. No executable transaction runner or
script-safety enforcement is supplied in this lot.

References: [connection sharing](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands),
[runtime transaction behavior](https://alembic.sqlalchemy.org/en/latest/api/runtime.html#alembic.runtime.migration.MigrationContext.begin_transaction).

## Professional accounts — Mission 2A

The account revision is also never imported/executed by these checks or tests.
Its complete reviewed AST has an independent fixed SHA-256 anchor in the guard.
Changing the source and its manifest hash together does not approve altered
operations: the AST anchor must also be changed in a separately reviewed policy.
This is closed recognition of one concrete revision, not a generic SQL/Python
validator or a signature. AST pinning permits formatting changes only when the
manifest source hash is also reviewed; runtime never calculates an approval pin.

Upgrade describes four new account tables and two indexes. Foreign keys may
reference public.companies; that business table is not modified. Downgrade
removes only these account objects in reverse dependency order, without CASCADE.
ORM names follow existing unqualified business conventions; deployment must fix
search_path to public, while revision references explicitly name public.
The independent schema test compares columns, PK/UK/FK/CHECK/index declarations
with ORM metadata without importing the revision or invoking Alembic.

No execution guard has been enabled: env.py and INI remain unchanged. This lot
adds no migrations runner, administrative authority or database provisioning.
