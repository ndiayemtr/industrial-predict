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
inspection uses AST metadata, never revision imports. Any Python file in the new
`versions/` directory is refused before reading it: no authority can authenticate
it yet. A future cross-directory dependency on `09ac8101e9fe` is demonstrated
using Alembic metadata in memory only, without creating a revision file. The
two-location loading strategy is reserved for a later reviewed activation lot;
it is not an operational configuration today. P101/local-demo paths stay intact.
An empty reference-to-reference plan is useful for offline contract checks only;
it cannot execute or bootstrap business tables.
Only a linear graph extending the historical chain is supported. Dynamic targets,
unknown revisions, branches, merges, downgrade, stamp and autogeneration are denied.

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
