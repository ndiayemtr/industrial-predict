"""Closed DEV B2B policy and offline evidence checks, not a migration manager.

The sole operational entry point is manage.py. Receipts are local evidence,
never authenticated approvals. No imports of application settings or revisions.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

POLICY = Path(__file__).with_name('b2b-policy.json')
POLICY_SHA256 = 'ccfd21577a85e884db79d0284bef2fe61bd1589dbc39b2259088c1d1cd973e1b'
BACKEND = Path(__file__).resolve().parents[2] / 'backend'


class CommitUncertain(RuntimeError):
    """Commit acknowledgement lost; no automatic retry/restore."""


class PostcheckFailed(RuntimeError):
    """Commit acknowledged but subsequent verification/close failed."""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def parse_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def read_json(path):
    return parse_json(Path(path).read_text(encoding='utf-8'))


def policy():
    raw = POLICY.read_bytes()
    require(digest(raw) == POLICY_SHA256, 'DEV B2B policy fingerprint mismatch')
    return parse_json(raw)


def release(config, *, current, role, target):
    """Read/check all sources; capture only the four approved immutable bodies."""
    p = policy()
    require(Path(config['_path']).resolve() == Path(p['profile']).resolve(), 'Unapproved DEV profile')
    require(all(config.get(k) == v for k, v in p['destination'].items()), 'B2B destination mismatch')
    require(current == p['initial'], 'Unexpected initial revision')
    require(role == p['role'], 'B2B role mismatch')
    require(target == p['target'], 'B2B target not authorized')
    # Reuse the existing hash/AST/graph guards; generic execution stays closed.
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from app import general_migrations as guards
    snapshot = guards.inspect_sources()
    require({s.path: s.sha256 for s in snapshot.sources} == p['sources'], 'Unapproved release sources')
    sequence = guards.resolve_upgrade(snapshot.revisions, current, target)
    require(sequence == tuple(p['sequence']), 'Unexpected B2B sequence')
    bodies = []
    for revision in sequence:
        description = next(r for r in snapshot.revisions if r.revision == revision)
        source = (BACKEND / description.path).read_text(encoding='utf-8').replace('\r\n', '\n')
        require(digest(source.encode()) == p['sources'][description.path], 'Release changed during capture')
        bodies.append((revision, description.path, source))
    # All later execution uses these bytes, never reopens a revision path.
    plan = {'policy_sha256': POLICY_SHA256, 'destination': p['destination'],
            'role': role, 'initial': current, 'target': target,
            'sequence': list(sequence), 'scope': p['scope'], 'sources': p['sources']}
    return plan, tuple(bodies)


def report(config, *, current, role, target):
    plan, _ = release(config, current=current, role=role, target=target)
    return {'stage': 'offline_prevalidation', 'accepted': True,
            'live_verified': False, 'execution_enabled': False,
            'approval_verified': False, 'backup_verified': False,
            'plan_sha256': digest(canonical(plan)), 'plan': plan}


def private_directory(config, directory, *, existing=True):
    path = Path(directory).resolve(strict=existing)
    root = (Path(config['_directory']) / 'evidence').resolve()
    require(path != root and path.is_relative_to(root), 'Evidence must be a private evidence subdirectory')
    return path


def transport(config):
    """No fallback to libpq defaults, ambient PG variables, or plaintext."""
    t = config.get('b2b_transport')
    require(type(t) is dict and set(t) == {'sslmode', 'sslrootcert', 'ca_sha256'}, 'B2B transport not approved')
    require(t['sslmode'] == 'verify-full', 'B2B requires verify-full')
    ca = Path(t['sslrootcert']).resolve(strict=True)
    require(not ca.is_relative_to(BACKEND.parent), 'CA must be outside repository')
    require(digest(ca.read_bytes()) == t['ca_sha256'] and len(t['ca_sha256']) == 64,
            'B2B CA mismatch')
    return {'sslmode': 'verify-full', 'sslrootcert': str(ca)}


def evidence(config, directory, plan, *, now=None):
    """Check locally generated receipts; operator still must approve their meaning."""
    directory = private_directory(config, directory)
    backup = read_json(directory / 'backup.json')
    restored = read_json(directory / 'restore.json')
    plan_hash = digest(canonical(plan))
    now = now or datetime.now(timezone.utc)
    for receipt, stage in ((backup, 'backup'), (restored, 'restore')):
        require(receipt['format'] == 'dev-b2b-evidence-v1' and receipt['stage'] == stage, 'Invalid evidence stage')
        require(receipt['plan_sha256'] == plan_hash, 'Evidence belongs to another plan')
        instant = datetime.fromisoformat(receipt['created_at'])
        require(instant.tzinfo is not None and timedelta(0) <= now - instant <= timedelta(hours=24),
                'Evidence expired or future dated')
    require(datetime.fromisoformat(restored['created_at']) >= datetime.fromisoformat(backup['created_at']),
            'Restore evidence predates backup')
    archive = directory / 'before-b2b.dump'
    require(archive.is_file() and archive.stat().st_size > 0, 'Backup archive missing')
    archive_hash = file_digest(archive)
    require(backup['archive_sha256'] == restored['archive_sha256'] == archive_hash, 'Backup fingerprint mismatch')
    require(restored['restored_snapshot'] == backup['snapshot'], 'Restore differs from backup snapshot')
    require(restored['database'] == policy()['restore_database'], 'Restore target not isolated')
    require(restored['database_oid'] != config['database_oid'] and
            restored['instance_id'] != config['instance_id'], 'Restore identity overlaps DEV')
    require(restored['verified'] is True and backup.get('stage') == 'backup', 'Unverified evidence')
    require(restored['verified'] is True, 'Restore not validated')
    return backup, restored


def file_digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
