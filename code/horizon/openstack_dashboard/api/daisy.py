from __future__ import absolute_import

from django.conf import settings

from horizon.utils.memoized import memoized  # noqa
from openstack_dashboard.api import base

from daisyclient.v1 import client as daisy_client

import logging
LOG = logging.getLogger(__name__)


class Host(base.APIResourceWrapper):
    """Simple wrapper around novaclient.server.Server.

    Preserves the request info so image name can later be retrieved.
    """
    _attrs = ['id', 'name', 'description', 'resource_type', 'status',
              'os_version_id', 'os_version_file', 'tecs_version_id','tecs_version_file',
              'ipmi_user', 'ipmi_passwd',
              'ipmi_addr', 'os_version', 'role', 'cluster', 'mac',
              'interfaces', 'os_progress', 'messages', 'role_status',
              'os_status', 'role_progress', 'role_messages', 'discover_state']

    def __init__(self, apiresource, request):
        super(Host, self).__init__(apiresource)
        self.request = request


@memoized
def daisyclient(request):
    endpoint = getattr(settings,
                       'DAISY_ENDPOINT_URL',
                       "http://127.0.0.1:19292")
    return daisy_client.Client(version=1, endpoint=endpoint)


def cluster_list(request):
    return daisyclient(request).clusters.list()


def cluster_add(request, **kwargs):
    return daisyclient(request).clusters.add(**kwargs)


def role_list(request):
    roles = daisyclient(request).roles.list()
    return [r for r in roles]


def role_get(request, role, **kwargs):
    return daisyclient(request).roles.get(role, **kwargs)


def role_update(request, role, **kwargs):
    return daisyclient(request).roles.update(role, **kwargs)


def host_list(request, **kwargs):
    hosts = daisyclient(request).hosts.list(**kwargs)
    hosts_handled = [Host(h, request) for h in hosts]
    return hosts_handled


def host_add(request, **kwargs):
    return daisyclient(request).hosts.add(**kwargs)


def host_update(request, host, **kwargs):
    return daisyclient(request).hosts.update(host, **kwargs)


def host_get(request, host_id):
    return daisyclient(request).hosts.get(host_id)


def cluster_host_list(request, cluster_id):
    qp = {"cluster_id": cluster_id}
    hosts = daisyclient(request).hosts.list(filters=qp)
    return [h for h in hosts]


def add_host_to_cluster(request, cluster_id, host_id):
    daisyclient(request).cluster_hosts.add(cluster_id, host_id)


def delete_host_from_cluster(request, cluster_id, host_id):
    daisyclient(request).cluster_hosts.delete(cluster_id, host_id)


def cluster_get(request, cluster_id):
    return daisyclient(request).clusters.get(cluster_id)


def cluster_update(request, cluster_id, **kwargs):
    return daisyclient(request).clusters.update(cluster_id, **kwargs)


def network_update(request, network_id, **kwargs):
    return daisyclient(request).networks.update(network_id, **kwargs)


def net_plane_add(request, **kwargs):
    return daisyclient(request).networks.add(**kwargs)


def cluster_delete(request, cluster_id, **kwargs):
    return daisyclient(request).clusters.delete(cluster_id, **kwargs)


def network_list(request, cluster_id):
    qp = {'cluster_id': cluster_id}
    networks = daisyclient(request).networks.list(filters=qp)
    return [n for n in networks]


def netplane_delete(request, network_id):
    return daisyclient(request).networks.delete(network_id)


def install_cluster(request, cluster_id):
    return daisyclient(request).install.install(cluster_id=cluster_id)


def uninstall_cluster(request, cluster_id):
    return daisyclient(request).uninstall.uninstall(cluster_id=cluster_id)


def upgrade_cluster(request, cluster_id, **kwargs):
    return daisyclient(request).update.update(cluster_id=cluster_id, **kwargs)


def config_add(request, **kwargs):
    return daisyclient(request).configs.add(**kwargs)


def config_delete(request, **kwargs):
    return daisyclient(request).configs.delete(**kwargs)


def config_list(request, **kwargs):
    configs = daisyclient(request).configs.list(**kwargs)
    return [c for c in configs]


def service_disk_add(request, **kwargs):
    return daisyclient(request).disk_array.service_disk_add(**kwargs)


def service_disk_delete(request, id, **kwargs):
    return daisyclient(request).disk_array.service_disk_delete(id, **kwargs)


def service_disk_update(request, id, **kwargs):
    return daisyclient(request).disk_array.service_disk_update(id, **kwargs)


def service_disk_detail(request, id, **kwargs):
    return daisyclient(request).disk_array.service_disk_detail(id, **kwargs)


def service_disk_list(request, **kwargs):
    return daisyclient(request).disk_array.service_disk_list(**kwargs)


def cinder_volume_add(request, **kwargs):
    return daisyclient(request).disk_array.cinder_volume_add(**kwargs)


def cinder_volume_delete(request, id, **kwargs):
    return daisyclient(request).disk_array.cinder_volume_delete(id, **kwargs)


def cinder_volume_update(request, id, **kwargs):
    return daisyclient(request).disk_array.cinder_volume_update(id, **kwargs)


def cinder_volume_detail(request, id, **kwargs):
    return daisyclient(request).disk_array.cinder_volume_detail(id, **kwargs)


def cinder_volume_list(request, **kwargs):
    return daisyclient(request).disk_array.cinder_volume_list(**kwargs)


def add_discover_host(request, **kwargs):
    return daisyclient(request).hosts.add_discover_host(**kwargs)


def discover_host(request, **kwargs):
    return daisyclient(request).hosts.discover_host(**kwargs)


def list_discover_host(request, **kwargs):
    return daisyclient(request).hosts.list_discover_host(**kwargs)


def export_db_to_json(request, **kwargs):
    return daisyclient(request).template.export_db_to_json(**kwargs)


def import_json_to_template(request, **kwargs):
    return daisyclient(request).template.import_json_to_template(**kwargs)


def import_template_to_db(request, **kwargs):
    return daisyclient(request).template.import_template_to_db(**kwargs)


def host_to_template(request, **kwargs):
    return daisyclient(request).template.host_to_template(**kwargs)


def template_to_host(request, **kwargs):
    return daisyclient(request).template.template_to_host(**kwargs)


def host_template_list(request, **kwargs):
    return daisyclient(request).template.host_template_list(**kwargs)


def template_list(request):
    return daisyclient(request).template.list()


def template_detail(request, template_id):
    return daisyclient(request).template.get(template_id)


def template_delete(request, template_id):
    return daisyclient(request).template.delete(template_id)


def node_update(request, **kwargs):
    return daisyclient(request).node.update(**kwargs)


def backup_system(request, **kwargs):
    return daisyclient(request).backup_restore.backup(**kwargs)


def restore_system(request, **kwargs):
    return daisyclient(request).backup_restore.restore(**kwargs)


def get_backup_file_version(request, **kwargs):
    return daisyclient(request).backup_restore.backup_file_version(**kwargs)


def get_daisy_internal_version(request):
    return daisyclient(request).backup_restore.version(**{'type': 'internal'})


def pxe_host_discover(request, **kwargs):
    return daisyclient(request).node.pxe_host_discover(**kwargs)


def get_pxeserver(request):
    qp = {'type': "system"}
    networks = daisyclient(request).networks.list(filters=qp)
    return [n for n in networks]


def set_pxeserver(request, network_id, interface, **kwargs):
    daisyclient(request).networks.update(network_id, **kwargs)
    daisyclient(request).install.install(deployment_interface=interface)


def version_get(request, version_id, **kwargs):
    return daisyclient(request).versions.get(version_id, **kwargs)


def version_list(request, **kwargs):
    return daisyclient(request).versions.list(**kwargs)


def version_add(request, **kwargs):
    return daisyclient(request).versions.add(**kwargs)


def version_delete(request, version_id, **kwargs):
    return daisyclient(request).versions.delete(version_id, **kwargs)


def version_update(request, version_id, **kwargs):
    return daisyclient(request).versions.update(version_id, **kwargs)


def version_patch_get(request, patch_id, **kwargs):
    return daisyclient(request).version_patchs.get(patch_id, **kwargs)


def version_patch_list(request, **kwargs):
    return daisyclient(request).version_patchs.list(**kwargs)


def version_patch_add(request, **kwargs):
    return daisyclient(request).version_patchs.add(**kwargs)


def version_patch_delete(request, patch_id, **kwargs):
    return daisyclient(request).version_patchs.delete(patch_id, **kwargs)


def version_patch_update(request, patch_id, **kwargs):
    return daisyclient(request).version_patchs.update(patch_id, **kwargs)


def backend_types_get(request):
    return daisyclient(request).backend_types.get()
