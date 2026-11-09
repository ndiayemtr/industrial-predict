"""P101-specific read-only Docker preflight. B2B's no-extra-mount profile unchanged.

The ONLY extension is one fresh, campaign-bound replay volume in the runner.
Reuse the existing bounded CLI transport/formats; never rewrite observed mounts.
"""

from datetime import datetime
from hashlib import sha256
from time import monotonic
from uuid import uuid4

from b2b_postgres_qualification import collectors as c, evidence, validation as v
from b2b_postgres_qualification.contracts import Offline, Observation
from p101_postgres_qualification.execution import resource_inventory

VOLUME_FORMAT = c._template((("name", ".Name"), ("driver", ".Driver"), ("scope", ".Scope"),
    ("created", ".CreatedAt"), ("options", ".Options"), ("mountpoint", ".Mountpoint")))


def facts(campaign, registry):
    result = v._expected_facts(campaign, 'docker', '', '', '')
    result['extra_mounts'] = 'runner-volume:' + registry['volume'] + ':' + registry['mount_target']
    return result


class P101ResourceCollector(Offline):
    @v.guarded
    def __init__(self, campaign, policy, resources, *, executable, clock):
        expected = resource_inventory(campaign, policy, runner_image_id=resources.get('runner_image_id'),
            registry=resources.get('registry'))
        v.require('registry' in resources and expected == resources)
        self.campaign, self.policy, self.resources, self.clock = campaign, policy, expected, clock
        self.limits = (c.ResourceLimits(expected['postgres_memory'], expected['nano_cpus'], 67108864),
            c.ResourceLimits(expected['runner_memory'], expected['nano_cpus'], 67108864))
        self.reader = c.DockerCollector(campaign, policy, executable=executable, postgres_limits=self.limits[0],
            runner_limits=self.limits[1], runner_image_id_sha256=expected['runner_image_id'], clock=clock)

    @v.guarded
    def collect(self):
        campaign, policy, expected = self.campaign, self.policy, self.resources
        start, deadline = self.clock(), monotonic()+10
        v.utc(start)
        query = lambda *args: self.reader._query(deadline, *args)
        endpoint = query('context', 'inspect', policy.context_name, '--format', '{{json .Endpoints.docker.Host}}')
        v.require(type(endpoint) is str and endpoint.startswith(('unix://', 'npipe://'))
            and sha256(endpoint.encode()).hexdigest() == policy.endpoint_sha256)
        engine = query('info', '--format', '{{json .ID}}')
        v.require(engine == campaign.engine_id)
        containers = []
        for identifier, limits in zip((campaign.container_id, campaign.runner_id), self.limits):
            data = query('inspect', '--type', 'container', '--format', c.CONTAINER_FORMAT, identifier)
            v.require(type(data) is dict and set(data) == {'id', 'name', 'image', 'image_ref', 'networks', 'mounts',
                'ports', 'status', 'privileged', 'restart', 'memory', 'cpus', 'shm', 'readonly_root'})
            v.require(data['id'] == identifier and identifier not in v.FORBIDDEN_IDS and data['status'] == 'running'
                and data['privileged'] is False and data['restart'] == 'no' and data['readonly_root'] is True)
            v.require(type(data['networks']) is dict and set(data['networks']) == {campaign.network_name}
                and data['networks'][campaign.network_name]['NetworkID'] == campaign.network_id)
            v.require(data['ports'] is None or type(data['ports']) is dict and all(value is None or value == [] for value in data['ports'].values()))
            v.require(all(type(data[name]) is int for name in ('memory', 'cpus', 'shm'))
                and (data['memory'], data['cpus'], data['shm']) == (limits.memory_bytes, limits.nano_cpus, limits.shm_bytes))
            containers.append(data)
        postgres, runner = containers
        registry = expected['registry']
        v.require(postgres['name'] == '/' + campaign.container_name
            and runner['name'] == '/' + campaign.container_name.removesuffix('-postgres') + '-runner')
        v.require(postgres['image'] == 'sha256:' + policy.image_id_sha256
            and postgres['image_ref'] == 'docker.io/library/postgres@sha256:' + campaign.image_sha256
            and runner['image'] == 'sha256:' + expected['runner_image_id'])
        v.require(postgres['networks'][campaign.network_name]['IPAddress'] == campaign.server_address)
        for container, name, target in ((postgres, campaign.volume_name, '/var/lib/postgresql/data'),
                                      (runner, registry['volume'], registry['mount_target'])):
            mounts = container['mounts']
            v.require(type(mounts) is list and len(mounts) == 1 and mounts[0]['Type'] == 'volume'
                and mounts[0]['Name'] == name and mounts[0]['Destination'] == target and mounts[0]['RW'] is True)
        network = query('network', 'inspect', campaign.network_id, '--format', c.NETWORK_FORMAT)
        v.require(network['id'] == campaign.network_id and network['name'] == campaign.network_name
            and network['driver'] == 'bridge' and network['internal'] is True
            and set(network['members']) == {campaign.container_id, campaign.runner_id}
            and type(network['ipam']) is list and len(network['ipam']) == 1
            and network['ipam'][0]['Subnet'] == campaign.subnet)
        for name, created_at in ((campaign.volume_name, policy.volume_created_at.isoformat()),
                                 (registry['volume'], registry['created_at'])):
            volume = query('volume', 'inspect', name, '--format', VOLUME_FORMAT)
            v.require(volume['name'] == name and volume['driver'] == 'local' and volume['scope'] == 'local'
                and datetime.fromisoformat(volume['created'].replace('Z', '+00:00')) == datetime.fromisoformat(created_at)
                and (volume['options'] is None or volume['options'] == {})
                and type(volume['mountpoint']) is str and volume['mountpoint'].startswith('/')
                and volume['mountpoint'].endswith('/volumes/' + name + '/_data'))
        for container in containers:
            image = query('image', 'inspect', container['image'], '--format', c.IMAGE_FORMAT)
            v.require(image['id'] == container['image'] and image['os'] == 'linux' and image['arch'] == 'amd64')
            if container is postgres:
                v.require(postgres['image_ref'] in image['digests'])
        end = self.clock()
        v.utc(end)
        v.require(0 <= (end-start).total_seconds() <= 10 and monotonic() < deadline)
        observation = Observation('docker', campaign.campaign_id, v.destination_fingerprint(campaign),
            'unverified_external', 'p101-docker-cli', start, end, str(uuid4()), tuple(sorted(facts(campaign, registry).items())))
        supplemental = dict(context_name=policy.context_name, endpoint_sha256=policy.endpoint_sha256,
            image_id_sha256=policy.image_id_sha256, container_networks=campaign.network_id,
            volume_engine_id=campaign.engine_id, volume_driver='local', volume_scope='local',
            volume_created_at=policy.volume_created_at.isoformat(timespec='microseconds'))
        packet = evidence.EvidencePacket(observation, tuple(sorted(supplemental.items())))
        return c.DockerCollection(packet, *self.limits, expected['runner_image_id'])
