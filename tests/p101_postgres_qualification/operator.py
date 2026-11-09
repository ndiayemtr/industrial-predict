"""Explicit REAL-1 operator entry. No execution on import or default action.

Administrator configuration/trusted keys must be independent of the submitted
request. No DSN/password CLI argument, environment lookup, signing or provisioning.
"""

import argparse
import base64
from dataclasses import asdict
from datetime import datetime, timezone
from getpass import getpass, GetPassWarning
import json
import os
from pathlib import Path
import stat
import warnings

from b2b_postgres_qualification.authority import TrustedKey
from b2b_postgres_qualification.contracts import Campaign, Rejected
from b2b_postgres_qualification.evidence import CollectorPolicy
from p101_postgres_qualification import execution as ex, privileges
from p101_postgres_qualification.execution_authority import Intent, ReplayReservations, verify_signature
from p101_postgres_qualification.live_authority import LiveGuard, read_json, safe_path, prepare_readiness


TRUST_STORE = Path('/etc/p101-qualification/trusted-keys.json')


def passwords(roles):
    # getpass's fallback may echo input. Turn its warning into a refusal BEFORE
    # fallback_input reads anything; never expose credentials in a non-TTY log.
    with warnings.catch_warnings():
        warnings.simplefilter('error', GetPassWarning)
        return {role: getpass('Qualification password for ' + role + ': ') for role in roles}


def load_keys(path):
    path = safe_path(path)
    if os.name == 'posix':
        for item in (path, *path.parents):
            metadata = item.stat()
            if metadata.st_uid != 0 or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise Rejected()
    keys = []
    data = read_json(path)
    if type(data) is not dict or set(data) != {'trusted_keys'}:
        raise Rejected()
    for item in data['trusted_keys']:
        item = dict(item)
        item['public_key'] = base64.b64decode(item['public_key'], validate=True)
        for field in ('valid_from', 'valid_until'):
            item[field] = datetime.fromisoformat(item[field])
        keys.append(TrustedKey(**item))
    return tuple(keys)


def load_admin(path, trust_store=TRUST_STORE):
    """Operator-supplied managed root of trust; never a field of request.json."""
    data = read_json(path)
    required = {'campaign', 'policy', 'resources', 'registry', 'catalogue_sha256', 'artifact_lock'}
    if type(data) is not dict or set(data) != required:
        raise Rejected()
    campaign = dict(data['campaign'])
    campaign['roles'] = tuple(campaign['roles'])
    campaign = Campaign(**campaign)
    policy = dict(data['policy'])
    policy['trusted_ca_der'] = base64.b64decode(policy['trusted_ca_der'], validate=True)
    policy['volume_created_at'] = datetime.fromisoformat(policy['volume_created_at'])
    if safe_path(path) == safe_path(trust_store):
        raise Rejected()
    keys = load_keys(trust_store)
    executor = ex.CampaignExecutor(campaign, CollectorPolicy(**policy), expected_campaign=campaign,
        resources=data['resources'], trusted_keys=tuple(keys), reservations=ReplayReservations(safe_path(data['registry'])),
        catalogue_sha256=data['catalogue_sha256'], clock=lambda: datetime.now(timezone.utc))
    return executor, safe_path(data['artifact_lock'])


def main(argv=None):
    parser = argparse.ArgumentParser(description='P101 explicit approved qualification; default is offline preparation')
    parser.add_argument('action', nargs='?', default='describe', choices=('describe', 'prepare', 'preflight', 'grant-plan', 'execute-approved'))
    parser.add_argument('--admin-config')
    parser.add_argument('--request')
    parser.add_argument('--operation', choices=('migrate', 'first-pair'))
    parser.add_argument('--trust-store', default=str(TRUST_STORE))
    parser.add_argument('--docker-executable')
    parser.add_argument('--artifact-sha256')
    args = parser.parse_args(argv)
    if args.action == 'describe':
        print(json.dumps(dict(default_execution=False, operations=['migrate', 'first-pair'],
            authorization='separate administrator trust + signed EXEC intent + signed fresh readiness',
            real_qualification_performed=False)))
        return 0
    try:
        admin = safe_path(Path(args.admin_config))
        if args.request and admin == safe_path(Path(args.request)):
            raise Rejected()
        if args.action == 'execute-approved' and Path(args.trust_store) != TRUST_STORE:
            raise Rejected()  # Only the root-owned image anchor may authorize execution.
        executor, artifact_lock = load_admin(admin, Path(args.trust_store))
        if args.action == 'prepare':
            if args.operation is None:
                raise Rejected()
            print(json.dumps(dict(bindings=executor.expected_bindings(args.operation),
                program_sha256=ex._program_digest()), sort_keys=True))
            return 0
        if args.action == 'grant-plan':
            print('\n'.join(privileges.grant_plan(executor.campaign)))
            return 0
        request = read_json(Path(args.request))
        if args.action == 'preflight':
            if type(request) is not dict or set(request) != {'intent', 'signature'}:
                raise Rejected()
            values = dict(request['intent'])
            for name in ('issued_at', 'expires_at'):
                values[name] = datetime.fromisoformat(values[name])
            intent = Intent(**values)
            verify_signature(intent, base64.b64decode(request['signature'], validate=True),
                trusted_keys=executor.keys, now=executor.clock(), expected=executor.expected_bindings(intent.operation))
            from p101_postgres_qualification.resources import P101ResourceCollector
            collection = P101ResourceCollector(executor.campaign, executor.policy, executor.resources,
                executable=str(safe_path(Path(args.docker_executable))), clock=executor.clock).collect()
            target = executor.resources['registry']['mount_target'] + '/p101q-exec-' + executor.campaign.campaign_id.replace('-', '')
            receipt = prepare_readiness(executor, intent, collection=collection,
                artifact_sha256=args.artifact_sha256, registry_root=executor.reservations._root, registry_target=target)
            print(json.dumps(dict(requires_human_review=True, unsigned_readiness=receipt), sort_keys=True))
            return 0
        if type(request) is not dict or set(request) != {'intent', 'signature', 'readiness', 'readiness_signature'}:
            raise Rejected()
        values = dict(request['intent'])
        for field in ('issued_at', 'expires_at'):
            values[field] = datetime.fromisoformat(values[field])
        intent = Intent(**values)
        signature = base64.b64decode(request['signature'], validate=True)
        guard = LiveGuard(executor, intent, signature, receipt=request['readiness'],
            receipt_signature=base64.b64decode(request['readiness_signature'], validate=True), artifact_lock=artifact_lock)
        role = executor.campaign.roles[1] if intent.operation == 'migrate' else executor.campaign.database + '_p101_writer'
        # Only after both envelopes, campaign, artifacts and registry have passed.
        credentials = passwords((role, executor.campaign.roles[3]))
        report = executor.execute_approved(guard, credentials=credentials)
        credentials.clear()
        print(json.dumps(asdict(report), sort_keys=True))
        return 0 if report.status == 'commit_confirmed' and not report.cleanup_failed and not report.recording_failed else 2
    except Exception:
        pass
    print('{"status":"refused","code":"P101_REAL1_REJECTED"}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
