# Copyright 2010-2011 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Registry's Client API
"""

import os

from oslo.serialization import jsonutils
from oslo_config import cfg
from oslo_log import log as logging

from daisy.common import exception
from daisy import i18n
from daisy.registry.client.v1 import client

LOG = logging.getLogger(__name__)
_ = i18n._

registry_client_ctx_opts = [
    cfg.BoolOpt('send_identity_headers', default=False,
                help=_("Whether to pass through headers containing user "
                       "and tenant information when making requests to "
                       "the registry. This allows the registry to use the "
                       "context middleware without keystonemiddleware's "
                       "auth_token middleware, removing calls to the keystone "
                       "auth service. It is recommended that when using this "
                       "option, secure communication between glance api and "
                       "glance registry is ensured by means other than "
                       "auth_token middleware.")),
]

CONF = cfg.CONF
CONF.register_opts(registry_client_ctx_opts)
_registry_client = 'daisy.registry.client'
CONF.import_opt('registry_client_protocol', _registry_client)
CONF.import_opt('registry_client_key_file', _registry_client)
CONF.import_opt('registry_client_cert_file', _registry_client)
CONF.import_opt('registry_client_ca_file', _registry_client)
CONF.import_opt('registry_client_insecure', _registry_client)
CONF.import_opt('registry_client_timeout', _registry_client)
CONF.import_opt('use_user_token', _registry_client)
CONF.import_opt('admin_user', _registry_client)
CONF.import_opt('admin_password', _registry_client)
CONF.import_opt('admin_tenant_name', _registry_client)
CONF.import_opt('auth_url', _registry_client)
CONF.import_opt('auth_strategy', _registry_client)
CONF.import_opt('auth_region', _registry_client)
CONF.import_opt('metadata_encryption_key', 'daisy.common.config')

_CLIENT_CREDS = None
_CLIENT_HOST = None
_CLIENT_PORT = None
_CLIENT_KWARGS = {}
# AES key used to encrypt 'location' metadata
_METADATA_ENCRYPTION_KEY = None


def configure_registry_client():
    """
    Sets up a registry client for use in registry lookups
    """
    global _CLIENT_KWARGS, _CLIENT_HOST, _CLIENT_PORT, _METADATA_ENCRYPTION_KEY
    try:
        host, port = CONF.registry_host, CONF.registry_port
    except cfg.ConfigFileValueError:
        msg = _("Configuration option was not valid")
        LOG.error(msg)
        raise exception.BadRegistryConnectionConfiguration(reason=msg)
    except IndexError:
        msg = _("Could not find required configuration option")
        LOG.error(msg)
        raise exception.BadRegistryConnectionConfiguration(reason=msg)

    _CLIENT_HOST = host
    _CLIENT_PORT = port
    _METADATA_ENCRYPTION_KEY = CONF.metadata_encryption_key
    _CLIENT_KWARGS = {
        'use_ssl': CONF.registry_client_protocol.lower() == 'https',
        'key_file': CONF.registry_client_key_file,
        'cert_file': CONF.registry_client_cert_file,
        'ca_file': CONF.registry_client_ca_file,
        'insecure': CONF.registry_client_insecure,
        'timeout': CONF.registry_client_timeout,
    }

    if not CONF.use_user_token:
        configure_registry_admin_creds()


def configure_registry_admin_creds():
    global _CLIENT_CREDS

    if CONF.auth_url or os.getenv('OS_AUTH_URL'):
        strategy = 'keystone'
    else:
        strategy = CONF.auth_strategy

    _CLIENT_CREDS = {
        'user': CONF.admin_user,
        'password': CONF.admin_password,
        'username': CONF.admin_user,
        'tenant': CONF.admin_tenant_name,
        'auth_url': os.getenv('OS_AUTH_URL') or CONF.auth_url,
        'strategy': strategy,
        'region': CONF.auth_region,
    }


def get_registry_client(cxt):
    global _CLIENT_CREDS, _CLIENT_KWARGS, _CLIENT_HOST, _CLIENT_PORT
    global _METADATA_ENCRYPTION_KEY
    kwargs = _CLIENT_KWARGS.copy()
    if CONF.use_user_token:
        kwargs['auth_token'] = cxt.auth_token
    if _CLIENT_CREDS:
        kwargs['creds'] = _CLIENT_CREDS

    if CONF.send_identity_headers:
        identity_headers = {
            'X-User-Id': cxt.user,
            'X-Tenant-Id': cxt.tenant,
            'X-Roles': ','.join(cxt.roles),
            'X-Identity-Status': 'Confirmed',
            'X-Service-Catalog': jsonutils.dumps(cxt.service_catalog),
        }
        kwargs['identity_headers'] = identity_headers
    return client.RegistryClient(_CLIENT_HOST, _CLIENT_PORT,
                                 _METADATA_ENCRYPTION_KEY, **kwargs)


def get_images_list(context, **kwargs):
    c = get_registry_client(context)
    return c.get_images(**kwargs)


def get_images_detail(context, **kwargs):
    c = get_registry_client(context)
    return c.get_images_detailed(**kwargs)


def get_image_metadata(context, image_id):
    c = get_registry_client(context)
    return c.get_image(image_id)


def add_image_metadata(context, image_meta):
    LOG.debug("Adding image metadata...")
    c = get_registry_client(context)
    return c.add_image(image_meta)


def update_image_metadata(context, image_id, image_meta,
                          purge_props=False, from_state=None):
    LOG.debug("Updating image metadata for image %s...", image_id)
    c = get_registry_client(context)
    return c.update_image(image_id, image_meta, purge_props=purge_props,
                          from_state=from_state)


def delete_image_metadata(context, image_id):
    LOG.debug("Deleting image metadata for image %s...", image_id)
    c = get_registry_client(context)
    return c.delete_image(image_id)


def get_image_members(context, image_id):
    c = get_registry_client(context)
    return c.get_image_members(image_id)


def get_member_images(context, member_id):
    c = get_registry_client(context)
    return c.get_member_images(member_id)


def replace_members(context, image_id, member_data):
    c = get_registry_client(context)
    return c.replace_members(image_id, member_data)


def add_member(context, image_id, member_id, can_share=None):
    c = get_registry_client(context)
    return c.add_member(image_id, member_id, can_share=can_share)


def delete_member(context, image_id, member_id):
    c = get_registry_client(context)
    return c.delete_member(image_id, member_id)

def add_host_metadata(context, host_meta):
    LOG.debug("Adding host...")
    c = get_registry_client(context)
    return c.add_host(host_meta)

def delete_host_metadata(context, host_id):
    LOG.debug("Deleting host metadata for host %s...", host_id)
    c = get_registry_client(context)
    return c.delete_host(host_id)

def update_host_metadata(context, host_id, host_meta):
    LOG.debug("Updating host metadata for host %s...", host_id)
    c = get_registry_client(context)
    return c.update_host(host_id, host_meta)

def get_host_metadata(context, host_id):
    c = get_registry_client(context)
    return c.get_host(host_id)

def get_host_interface(context, host_meta):
    c = get_registry_client(context)
    return c.get_host_interface(host_meta)

def get_all_host_interfaces(context, params):
    c = get_registry_client(context)
    return c.get_all_host_interfaces(params)

def get_assigned_network(context, host_interface_id, network_id):
    c = get_registry_client(context)
    return c.get_assigned_network(host_interface_id, network_id)

def add_discover_host_metadata(context, discover_host_meta):
    LOG.debug("Adding discover host...")
    c = get_registry_client(context)
    return c.add_discover_host(discover_host_meta)   

def delete_discover_host_metadata(context, discover_host_id):
    LOG.debug("Deleting host metadata for host %s...", discover_host_id)
    c = get_registry_client(context)
    return c.delete_discover_host(discover_host_id)
    
def get_discover_hosts_detail(context, **kwargs):
    c = get_registry_client(context)
    return c.get_discover_hosts_detailed(**kwargs)
    
def update_discover_host_metadata(context, host_id, host_meta):
    c = get_registry_client(context)
    return c.update_discover_host(host_id, host_meta)
    
def get_discover_host_metadata(context, host_id):
    c = get_registry_client(context)
    return c.get_discover_host_metadata(host_id)

def add_cluster_metadata(context, cluster_meta):
    LOG.debug("Adding cluster...")
    c = get_registry_client(context)
    return c.add_cluster(cluster_meta)

def update_cluster_metadata(context, cluster_id, cluster_meta):
    LOG.debug("Updating cluster metadata for cluster %s...", cluster_id)
    c = get_registry_client(context)
    print context
    print cluster_meta
    return c.update_cluster(cluster_id, cluster_meta)

def delete_cluster_metadata(context, cluster_id):
    LOG.debug("Deleting cluster metadata for cluster %s...", cluster_id)
    c = get_registry_client(context)
    return c.delete_cluster(cluster_id)

def get_cluster_metadata(context, cluster_id):
    c = get_registry_client(context)
    return c.get_cluster(cluster_id)

def add_cluster_host(context, cluster_id, host_id):
    c = get_registry_client(context)
    return c.add_cluster_host(cluster_id, host_id)

def delete_cluster_host(context, cluster_id, host_id):
    c = get_registry_client(context)
    return c.delete_cluster_host(cluster_id, host_id)

def get_hosts_detail(context, **kwargs):
    c = get_registry_client(context)
    return c.get_hosts_detailed(**kwargs)

def get_clusters_detail(context, **kwargs):
    c = get_registry_client(context)
    return c.get_clusters_detailed(**kwargs)

def get_cluster_hosts(context, cluster_id, host_id=None):
    c = get_registry_client(context)
    return c.get_cluster_hosts(cluster_id, host_id)


def get_host_clusters(context, host_id):
    c = get_registry_client(context)
    return c.get_host_clusters(host_id)

def add_component_metadata(context, component_meta):
    LOG.debug("Adding component...")
    c = get_registry_client(context)
    return c.add_component(component_meta)

def add_template_metadata(context, template):
    c = get_registry_client(context)
    return c.add_template(template)
    
def update_template_metadata(context, template_id, template):
    c = get_registry_client(context)
    return c.update_template(template_id, template)
    
def delete_template_metadata(context, template_id):
    c = get_registry_client(context)
    return c.delete_template(template_id)
    

def template_lists_metadata(context, **kwargs):
    c = get_registry_client(context)
    return c.list_template(**kwargs)

def template_detail_metadata(context, template_id):
    c = get_registry_client(context)
    return c.get_template_detail(template_id)

def add_host_template_metadata(context, template):
    c = get_registry_client(context)
    return c.add_host_template(template)
    
def update_host_template_metadata(context, template_id, template):
    c = get_registry_client(context)
    return c.update_host_template(template_id, template)
    
def delete_host_template_metadata(context, template_id):
    c = get_registry_client(context)
    return c.delete_host_template(template_id)
    

def host_template_lists_metadata(context, **kwargs):
    c = get_registry_client(context)
    return c.list_host_template(**kwargs)

def host_template_detail_metadata(context, template_id):
    c = get_registry_client(context)
    return c.get_host_template_detail(template_id)
    
def delete_component_metadata(context, component_id):
    LOG.debug("Deleting component metadata for component %s...", component_id)
    c = get_registry_client(context)
    return c.delete_component(component_id)

def get_components_detail(context, **kwargs):
    c = get_registry_client(context)
    return c.get_components_detailed(**kwargs)

def get_component_metadata(context, component_id):
    c = get_registry_client(context)
    return c.get_component(component_id)

def update_component_metadata(context, component_id, component_meta):
    LOG.debug("Updating component metadata for component %s...", component_id)
    c = get_registry_client(context)
    return c.update_component(component_id, component_meta)

def add_service_metadata(context, service_meta):
    LOG.debug("Adding service...")
    c = get_registry_client(context)
    return c.add_service(service_meta)

def delete_service_metadata(context, service_id):
    LOG.debug("Deleting service metadata for service %s...", service_id)
    c = get_registry_client(context)
    return c.delete_service(service_id)

def get_services_detail(context, **kwargs):
    c = get_registry_client(context)
    return c.get_services_detailed(**kwargs)

def get_service_metadata(context, service_id):
    c = get_registry_client(context)
    return c.get_service(service_id)

def update_service_metadata(context, service_id, service_meta):
    LOG.debug("Updating service metadata for service %s...", service_id)
    c = get_registry_client(context)
    return c.update_service(service_id, service_meta)

def add_role_metadata(context, role_meta):
    LOG.debug("Adding role...")
    c = get_registry_client(context)
    return c.add_role(role_meta)

def delete_role_metadata(context, role_id):
    LOG.debug("Deleting role metadata for role %s...", role_id)
    c = get_registry_client(context)
    return c.delete_role(role_id)

def get_roles_detail(context, **kwargs):
    c = get_registry_client(context)
    return c.get_roles_detailed(**kwargs)

def get_role_metadata(context, role_id):
    c = get_registry_client(context)
    return c.get_role(role_id)

def update_role_metadata(context, role_id, role_meta):
    LOG.debug("Updating role metadata for role %s...", role_id)
    c = get_registry_client(context)
    return c.update_role(role_id, role_meta)

def get_role_services(context, role_id):
    c = get_registry_client(context)
    return c.get_role_services(role_id)

def get_role_host_metadata(context, role_id):
    LOG.debug("get role_host metadata for role %s...", role_id)
    c = get_registry_client(context)
    return c.get_role_host(role_id)

def delete_role_host_metadata(context, role_id):
    LOG.debug("delete role_host metadata for role %s...", role_id)
    c = get_registry_client(context)
    return c.delete_role_host(role_id)

def update_role_host_metadata(context, role_host_id, role_meta):
    LOG.debug("update role_host metadata for role %s...", role_host_id)
    c = get_registry_client(context)
    return c.update_role_host(role_host_id, role_meta)

def add_config_file_metadata(context, config_file_meta):
    LOG.debug("Adding config_file...")
    c = get_registry_client(context)
    return c.add_config_file(config_file_meta)

def delete_config_file_metadata(context, config_file_id):
    LOG.debug("Deleting config_file metadata for config_file %s...", config_file_id)
    c = get_registry_client(context)
    return c.delete_config_file(config_file_id)

def update_config_file_metadata(context, config_file_id, config_file_meta):
    LOG.debug("Updating config_file metadata for config_file %s...", config_file_id)
    c = get_registry_client(context)
    return c.update_config_file(config_file_id, config_file_meta)

def get_config_file_metadata(context, config_file_id):
    c = get_registry_client(context)
    return c.get_config_file(config_file_id)

def get_config_files_detail(context, **kwargs):
    c = get_registry_client(context)
    return c.get_config_files_detailed(**kwargs)
def add_config_set_metadata(context, config_set_meta):
    LOG.debug("Adding config_set...")
    c = get_registry_client(context)
    return c.add_config_set(config_set_meta)

def delete_config_set_metadata(context, config_set_id):
    LOG.debug("Deleting config_set metadata for config_set %s...", config_set_id)
    c = get_registry_client(context)
    return c.delete_config_set(config_set_id)

def update_config_set_metadata(context, config_set_id, config_set_meta):
    LOG.debug("Updating config_set metadata for config_file %s...", config_set_id)
    c = get_registry_client(context)
    return c.update_config_set(config_set_id, config_set_meta)

def get_config_set_metadata(context, config_set_id):
    c = get_registry_client(context)
    return c.get_config_set(config_set_id)

def get_config_sets_detail(context, **kwargs):
    c = get_registry_client(context)
    return c.get_config_sets_detailed(**kwargs)

def add_config_metadata(context, config_meta):
    LOG.debug("Adding config...")
    c = get_registry_client(context)
    return c.add_config(config_meta)

def delete_config_metadata(context, config_id):
    LOG.debug("Deleting config metadata for config %s...", config_id)
    c = get_registry_client(context)
    return c.delete_config(config_id)

def update_config_metadata(context, config_id, config_meta):
    LOG.debug("Updating config metadata for config_file %s...", config_id)
    c = get_registry_client(context)
    return c.update_config(config_id, config_meta)

def update_configs_metadata_by_role_hosts(context, config_metas):
    c = get_registry_client(context)
    return c.update_config_by_role_hosts(config_metas)

def get_config_metadata(context, config_id):
    c = get_registry_client(context)
    return c.get_config(config_id)

def get_configs_detail(context, **kwargs):
    c = get_registry_client(context)
    return c.get_configs_detailed(**kwargs)

def add_network_metadata(context, network_meta):
    LOG.debug("Adding network...")
    c = get_registry_client(context)
    return c.add_network(network_meta)

def update_phyname_of_network(context, network_phyname_set):
    c = get_registry_client(context)
    return c.update_phyname_of_network(network_phyname_set)

def update_network_metadata(context, network_id, network_meta):
    LOG.debug("Updating cluster metadata for cluster %s...", network_id)
    c = get_registry_client(context)
    return c.update_network(network_id, network_meta)

def delete_network_metadata(context, network_id):
    LOG.debug("Deleting cluster metadata for cluster %s...", network_id)
    c = get_registry_client(context)
    return c.delete_network(network_id)

def get_network_metadata(context, network_id):
    c = get_registry_client(context)
    return c.get_networks(network_id)

def get_networks_detail(context, cluster_id, **kwargs):
    c = get_registry_client(context)
    return c.get_networks_detailed(cluster_id, **kwargs)

def get_all_networks(context, **kwargs):
    c = get_registry_client(context)
    return c.get_all_networks(**kwargs)

def config_interface_metadata(context, config_interface_meta):
    c = get_registry_client(context)
    return c.config_interface(config_interface_meta)

def add_service_disk_metadata(context, service_disk_meta):
    c = get_registry_client(context)
    return c.add_service_disk(service_disk_meta)

def delete_service_disk_metadata(context, service_disk_id):
    LOG.debug("Deleting service_disk metadata %s...", service_disk_id)
    c = get_registry_client(context)
    return c.delete_service_disk(service_disk_id)

def update_service_disk_metadata(context, service_disk_id, service_disk_meta):
    LOG.debug("Updating config metadata for config_file %s...", service_disk_id)
    c = get_registry_client(context)
    return c.update_service_disk(service_disk_id, service_disk_meta)
    
def get_service_disk_detail_metadata(context, service_disk_id):
    c = get_registry_client(context)
    return c.get_service_disk_detail(service_disk_id)
    
def list_service_disk_metadata(context, **kwargs):
    c = get_registry_client(context)
    return c.list_service_disk(**kwargs)
    
def add_cinder_volume_metadata(context, cinder_volume_meta):
    c = get_registry_client(context)
    return c.add_cinder_volume(cinder_volume_meta)
    
def delete_cinder_volume_metadata(context, cinder_volume_id):
    LOG.debug("Deleting cinder_volume metadata %s...", cinder_volume_id)
    c = get_registry_client(context)
    return c.delete_cinder_volume(cinder_volume_id)

def update_cinder_volume_metadata(context, cinder_volume_id, cinder_volume_meta):
    LOG.debug("Updating config metadata for cinder_volume %s...", cinder_volume_id)
    c = get_registry_client(context)
    return c.update_cinder_volume(cinder_volume_id, cinder_volume_meta)
    
def get_cinder_volume_detail_metadata(context, cinder_volume_id):
    c = get_registry_client(context)
    return c.get_cinder_volume_detail(cinder_volume_id)
    
def list_cinder_volume_metadata(context, **kwargs):
    c = get_registry_client(context)
    return c.list_cinder_volume(**kwargs)