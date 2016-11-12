# Copyright 2013 OpenStack Foundation
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
/hosts endpoint for Daisy v1 API
"""
import os
import copy
import ast
import json
import re
import time
import commands
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden
from daisy.api import policy
import daisy.api.v1
from daisy.api.v1 import controller
from daisy.api.v1 import filters
from daisy.common import exception
from daisy.common import utils
from daisy.common import wsgi
from daisy.api import common
from daisy import i18n
from daisy import notifier
import daisy.registry.client.v1.api as registry
import daisy.api.common as api_cmn
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.tecs.common as tecs_cmn
from daisy.api.backends.tecs import config
import daisy.api.backends.tecs.install as tecs_install
import daisy.api.backends.tecs.disk_array as disk_array
from daisy.api.configset import manager as push_mngr

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE

UPDATE_NETWORK_PARAMS = ('id', 'cidr', 'gateway', 'ip_ranges',
                         'vlan_id', 'vlan_start', 'vlan_end',
                         'vxlan', 'vni_start', 'vni_end', 'description')

UPDATE_MGNT_VIP_PARAMS = ['vip', 'glance_vip', 'db_vip',
                          'mongodb_vip']
UPDATE_PUBLIC_VIP_PARAMS = ['public_vip']
UPDATE_VIP_PARAMS = UPDATE_MGNT_VIP_PARAMS + UPDATE_PUBLIC_VIP_PARAMS
UPDATE_ROLE_PARAMS = ['id', 'ntp_server'] + UPDATE_VIP_PARAMS

UPDATE_SERVICE_DISK_PARAMS = ('id', 'data_ips')
UPDATE_CINDER_VOLUME_PARAMS = ('id', 'data_ips', 'management_ips')
UPDATE_MODULES = ['networks', 'roles', 'service_disks', 'cinder_volumes']
AUTO_SCALE = ['auto_scale', 'tecs_version_id']
GEN_PARAMS = ['cluster_id'] + AUTO_SCALE + UPDATE_MODULES
SUPPORT_GET_PARAMS = UPDATE_MODULES + ['hosts']

daisy_tecs_path = tecs_cmn.daisy_tecs_path
UPDATE_DATA_FILE_NAME = 'origin_update_data.json'
HOSTS_NETWORK_IP_FILE_NAME = 'hosts_network_ip.json'
ALL_OS_JSON_FILE_NAME = 'all_os.json'
OS_JSON_FILE_NAME = 'os.json'
HA_CONF_FILE_NAME = 'HA_1.conf'
CONFIG_ITEMS_FILE_NAME = 'config_items.json'
POST_CONFIG_ITEMS_FILE_NAME = 'post_config_items.json'
CINDER_JSON_FILE_NAME = 'cinder.json'
CONTROL1_JSON_FILE_NAME = 'control_1.json'
CONTROL2_JSON_FILE_NAME = 'control_2.json'
CONTROL_JSON_FILE_NAME = 'control.json'
KEYSTONE_JSON_FILE_NAME = 'keystone.json'
PRIVATE_CTRL_JSON_FILE_NAME = 'private_ctrl.json'
CLUSTER_CONFIG_PATH = daisy_tecs_path + '%(cluster_id)s'
CONFIG_PATH = CLUSTER_CONFIG_PATH + '/update_config/'
LAST_CONFIG_PATH = CLUSTER_CONFIG_PATH + '/last_update_config/'
FAILED_CONFIG_PATH = CLUSTER_CONFIG_PATH + '/failed_update_config/'
FAILED_UPDATE_FILE_NAME = 'failed_update_data.json'
FAILED_UPDATE_FILE = FAILED_CONFIG_PATH + FAILED_UPDATE_FILE_NAME
CONFIG_FILE = (CONFIG_PATH + '%(file_name)s')
REMOTE_DIR = '/home/config_dir/' + 'config_update'

tecs_state = tecs_cmn.TECS_STATE
network_update_script_name = "network_update.sh"
network_update_script = daisy_tecs_path + "/" + network_update_script_name


class Controller(controller.BaseController):

    """
    WSGI controller for networks resource in Daisy v1 API

    The networks resource API is a RESTful web service for host data. The API
    is as follows::

        GET  /networks -- Returns a set of brief metadata about networks
        GET  /networks/detail -- Returns a set of detailed metadata about
                              networks
        HEAD /networks/<ID> -- Return metadata about an host with id <ID>
        GET  /networks/<ID> -- Return host data for host with id <ID>
        POST /networks -- Store host data and return metadata about the
                        newly-stored host
        PUT  /networks/<ID> -- Update host metadata and/or upload host
                            data for a previously-reserved host
        DELETE /networks/<ID> -- Delete the host with id <ID>
    """

    def __init__(self):
        self.notifier = notifier.Notifier()
        registry.configure_registry_client()
        self.policy = policy.Enforcer()

    def _enforce(self, req, action, target=None):
        """Authorize an action against our policies"""
        if target is None:
            target = {}
        try:
            self.policy.enforce(req.context, action, target)
        except exception.Forbidden:
            raise HTTPForbidden()

    def _get_filters(self, req):
        """
        Return a dictionary of query param filters from the request

        :param req: the Request object coming from the wsgi layer
        :retval a dict of key/value filters
        """
        query_filters = {}
        for param in req.params:
            if param in SUPPORTED_FILTERS:
                query_filters[param] = req.params.get(param)
                if not filters.validate(param, query_filters[param]):
                    raise HTTPBadRequest(_('Bad value passed to filter '
                                           '%(filter)s got %(val)s')
                                         % {'filter': param,
                                            'val': query_filters[param]})
        return query_filters

    def _get_query_params(self, req):
        """
        Extracts necessary query params from request.

        :param req: the WSGI Request object
        :retval dict of parameters that can be used by registry client
        """
        params = {'filters': self._get_filters(req)}

        for PARAM in SUPPORTED_PARAMS:
            if PARAM in req.params:
                params[PARAM] = req.params.get(PARAM)
        return params

    def _valid_tecs_backend(self, req, cluster_id):
        orig_roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
        deploy_backends = []
        for role in orig_roles:
            deploy_backends.append(role['deployment_backend'])
        if 'tecs' not in deploy_backends:
            msg = "update config isn't support because no 'tecs' in cluster"
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)

    def _update_config_by_failed_config(self, configs, old_configs):
        if not old_configs:
            return configs

        new_configs = copy.deepcopy(configs)
        for module in UPDATE_MODULES:
            if not old_configs.get(module):
                continue
            if not new_configs.get(module):
                new_configs[module] = old_configs.get(module)
                continue
            for item in old_configs[module]:
                has_exist = False
                for new_item in new_configs[module]:
                    if item['id'] == new_item['id']:
                        has_exist = True
                        for key in item.keys():
                            if key not in new_item:
                                new_item.update({key: item[key]})
                if not has_exist:
                    new_configs[module].append(item)

        return new_configs

    @utils.mutating
    def config_update_gen(self, req, cluster_id, config_update_meta):
        """
        Updates an existing host with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        new_update_config = {}
        self._enforce(req, 'config_update_gen')

        try:
            cluster_data = registry.get_cluster_metadata(
                req.context, cluster_id)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        if cluster_data['use_dns'] != 1:
            msg = "Cluster must use DNS."
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)
        update_auto_scale = False
        for key in config_update_meta.keys():
            if key in AUTO_SCALE:
                auto_scale_value = config_update_meta.pop(key)
                if (str(cluster_data[key]) != str(auto_scale_value)):
                    update_auto_scale = True
                    cluster_meta = {key: auto_scale_value}
                    registry.update_cluster_metadata(req.context,
                                                     cluster_id,
                                                     cluster_meta)

        self. _valid_tecs_backend(req, cluster_id)

        modules_handling_together = ['networks', 'roles']
        # roles need to check with networks
        check_config_dict = \
            {'networks': self._check_networks_config,
             'service_disks': self._check_service_disks_config,
             'cinder_volumes': self._check_cinder_volumes_config}
        get_config_dict = \
            {'networks': self._get_networks_update_config,
             'roles': self._get_roles_update_config,
             'service_disks': self._get_service_disks_update_config,
             'cinder_volumes': self._get_cinder_volume_update_configs}

        for update_key in config_update_meta.keys():
            if update_key not in GEN_PARAMS:
                msg = "'%s' is not supported to update" % update_key
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)
            else:
                if not isinstance(config_update_meta[update_key], list):
                    config_update_meta[update_key] = ast.literal_eval(
                        config_update_meta[update_key])

        check_config_dict['networks'](req, cluster_id,
                                      config_update_meta.get('networks', []),
                                      config_update_meta.get('roles', []))

        for update_key in config_update_meta.keys():
            if config_update_meta[update_key]:
                if update_key not in modules_handling_together:
                    check_config_dict[update_key](
                        req, config_update_meta[update_key])

                update_configs = get_config_dict[update_key](
                    req, config_update_meta[update_key])
                if update_configs[update_key]:
                    new_update_config.update(update_configs)

        # failed_update_config = self._read_from_failed_config(cluster_id)
        # it's a error to update old failed data, should get config from db
        # new_update_config = \
            # self._update_config_by_failed_config(need_update_config,
                    # failed_update_config)

        config_path = CONFIG_PATH % {'cluster_id': cluster_id}
        if os.path.exists(config_path):
            rm_cmd = "rm -rf %s/* " % config_path
            daisy_cmn.subprocess_call(rm_cmd)
        if not new_update_config:
            if update_auto_scale:
                msg = "Config has been updated to database"
                LOG.warn(msg)
                config_update_gen_result = msg
                update_config_result = {'config_update_gen_result':
                                        config_update_gen_result}
                return {'config_update_meta': update_config_result}
            msg = "No config data need to update"
            LOG.warn(msg)
            config_update_gen_result = msg
            update_config_result = {'config_update_gen_result':
                                    config_update_gen_result}
            return {'config_update_meta': update_config_result}
        else:
            self._write_json_file(cluster_id,
                                  UPDATE_DATA_FILE_NAME, new_update_config)

        self._land_networks_config(req, cluster_id,
                                   new_update_config)

        self._land_disk_array_config(req, cluster_id,
                                     new_update_config)

        role_nodes_info = self._get_role_nodes_info(req, cluster_id)

        # stop HA
        self._stop_ha_cluster(req, role_nodes_info['ha'])

        is_storage_changed = False
        for network in new_update_config.get('networks', []):
            if network['network_type'] == 'STORAGE':
                is_storage_changed = True

        is_disk_array_changed = False
        # should stop VMs manually when modify disk array
        if new_update_config.get('cinder_volumes') or is_storage_changed:
            self._pre_disk_array_config(req, role_nodes_info['computer'])
            is_disk_array_changed = True
        if new_update_config.get('service_disks'):
            self._pre_disk_array_config(req, role_nodes_info['ha'])
            is_disk_array_changed = True

        config_update_gen_result = "Config files generated successfully"
        if is_disk_array_changed:
            disk_array_hint = ", then you need to config disk array "\
                "device before apply modification."
            config_update_gen_result += disk_array_hint
        msg = "%s, config files path is %s" % (config_update_gen_result,
                                               config_path)
        LOG.info(msg)
        update_config_result = {'config_update_gen_result':
                                config_update_gen_result}

        return {'config_update_meta': update_config_result}

    # only 'CONTROLLER_HA' and 'CONTROLLER_LB' need to update configs
    def _check_roles_config(self, req, roles_meta,
                            cidr_dict, ip_ranges_dict):
        LOG.info("Check roles configs...")
        support_update_roles = ['CONTROLLER_HA', 'CONTROLLER_LB']
        for role in roles_meta:
            if role.get('id', None):
                orig_role_meta = self.get_role_meta_or_404(
                    req, role['id'])
            else:
                msg = "id must be given when update role config"
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)

            if orig_role_meta['deployment_backend'] != 'tecs':
                msg = "deployment backend %s is not supported to updated "\
                    "config" % orig_role_meta['deployment_backend']
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)

            if orig_role_meta['name'] not in support_update_roles:
                continue

            if (orig_role_meta['name'] == 'CONTROLLER_HA' and
                    'public_vip' not in role.keys()):
                msg = (_("public vip must be given"))
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)
            for key in role.keys():
                if key in UPDATE_VIP_PARAMS and role[key]:
                    if key == 'public_vip':
                        cidr = cidr_dict['PUBLICAPI']
                        ip_ranges = ip_ranges_dict['PUBLICAPI']
                    else:
                        cidr = cidr_dict['MANAGEMENT']
                        ip_ranges = ip_ranges_dict['MANAGEMENT']

                    if not utils.is_ip_in_cidr(role[key], cidr):
                        msg = (_("IP '%s' is not in the range "
                                 "of CIDR '%s'." % (role[key], cidr)))
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg, request=req)
                    is_ip_in_ranges = \
                        utils.is_ip_in_ranges(role[key], ip_ranges)
                    if (ip_ranges and not is_ip_in_ranges):
                        msg = (_("IP '%s' is not in the ip ranges "
                                 "of '%s'." % (role[key], ip_ranges)))
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg, request=req)

    def _valid_private_network(self, req,
                               segmentation_type,
                               update_network_config):
        update_keys = update_network_config.keys()
        if segmentation_type == 'vlan':
            if ('vni_start' in update_keys or
                    'vni_end' in update_keys):
                msg = (_("vni range is not allowed to update "
                         "when segmentation type is vlan"))
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)
        if segmentation_type == 'vxlan':
            if ('vlan_start' in update_keys or
                    'vlan_end' in update_keys):
                msg = (_("vni range is not allowed to update "
                         "when segmentation type is vlan"))
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)
    # if two or more networks cidr is same in orign networks,
    # and they must be same in new networks

    def _valid_networks_same_cidr(self, orig_cluster_networks,
                                  new_cluster_networks):
        same_cidr_networks_list = []
        for network1 in orig_cluster_networks:
            cidr = network1.get('cidr', None)
            same_cidr_networks = []
            for network2 in orig_cluster_networks:
                if (network2.get('cidr', None) == cidr and
                        network1['id'] != network2['id']):
                    same_cidr_networks.append(network1['id'])
                    same_cidr_networks.append(network2['id'])
            if same_cidr_networks:
                same_cidr_networks_list.append(same_cidr_networks)

        networks_id_cidr_dict = {}
        for network in new_cluster_networks:
            networks_id_cidr_dict.update({network['id']: network['cidr']})

        for same_cidr_networks in same_cidr_networks_list:
            cidr = None
            for network_id in set(same_cidr_networks):
                if not cidr:
                    cidr = networks_id_cidr_dict[network_id]
                else:
                    if networks_id_cidr_dict[network_id] != cidr:
                        msg = (_("New networks cidr must be same when "
                                 "orign cidr same among these networks"))
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg)

    def _remove_unused_networks(self, req, cluster_id, orig_networks):
        params = {'filters': {'cluster_id': cluster_id}}
        orig_cluster_hosts = registry.get_hosts_detail(req.context, **params)
        cluster_network_plane = list()
        for host in orig_cluster_hosts:
            host_detail = daisy_cmn.get_host_detail(req, host['id'])
            for host_interface in host_detail.get('interfaces', []):
                if host_interface.get('assigned_networks'):
                    for assigned_network in \
                            host_interface.get('assigned_networks'):
                        cluster_network_plane.append(assigned_network['type'])
        cluster_network_plane = set(cluster_network_plane)
        orig_cluster_networks = list()
        for orig_network in orig_networks:
            if orig_network['network_type'] in cluster_network_plane:
                orig_cluster_networks.append(orig_network)

        return orig_cluster_networks


    # return if has change for update_info
    def _check_networks_config(self, req, cluster_id,
                               networks_meta, roles_meta):
        LOG.info("Check networks configs...")
        network_planes_with_vip = ['MANAGEMENT', 'PUBLICAPI']
        cidr_dict = {}
        ip_ranges_dict = {}
        for network in networks_meta:
            if 'id' in network:
                orig_network_meta = self.get_network_meta_or_404(
                    req, network['id'])
            else:
                msg = "id must be given when update network configs"
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)

            if orig_network_meta['network_type'] == 'DATAPLANE':
                self._valid_private_network(
                    req, orig_network_meta['segmentation_type'], network)
            # check ranges for 'vlan_start','vlan_end'
            # and 'vni_start', 'vni_end'
            common.valid_network_range(req, network)

            if 'cidr' in network:
                if (not network['cidr'] and
                        orig_network_meta['network_type'] != 'DATAPLANE'):
                    msg = "cidr can't be empty for network %s"\
                        % orig_network_meta['name']
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg, request=req)
                utils.valid_cidr(network['cidr'])
                cidr = network.get('cidr')
            else:
                cidr = orig_network_meta.get('cidr')

            if 'ip_ranges' in network and network['ip_ranges']:
                common.valid_ip_ranges(network['ip_ranges'], cidr)
                ip_ranges = network.get('ip_ranges')
            else:
                ip_ranges = orig_network_meta.get('ip_ranges')

            if 'gateway' in network and network['gateway']:
                gateway = network['gateway']
                utils.validate_ip_format(gateway)
            else:
                gateway = orig_network_meta.get('gateway')
            if gateway:
                is_gateway_valid = True
                if ip_ranges:
                    if utils.is_ip_in_ranges(gateway, ip_ranges):
                        is_gateway_valid = False
                else:
                    if cidr and utils.is_ip_in_cidr(gateway, cidr):
                        is_gateway_valid = False
                if not is_gateway_valid:
                    msg = "gateway should be out of ip ranges for "\
                          "network %s" % orig_network_meta['name']
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg, request=req)
            # check vlan id in 1-4094
            if 'vlan_id' in network and network['vlan_id']:
                common.valid_vlan_id(network['vlan_id'])

        orig_networks = daisy_cmn.get_cluster_networks_detail(
            req, cluster_id)
        orig_cluster_networks = self._remove_unused_networks(req, cluster_id,
                                                             orig_networks)
        new_cluster_networks = self._get_new_cluster_networks(
            orig_cluster_networks, networks_meta)

        common.valid_cluster_networks(new_cluster_networks)
        self._valid_networks_same_cidr(orig_cluster_networks,
                                       new_cluster_networks)

        if roles_meta and network_planes_with_vip:
            for network_name in network_planes_with_vip:
                networks = [network for network in new_cluster_networks
                            if network['name'] == network_name]
                cidr_dict[network_name] = networks[0]['cidr']
                ip_ranges_dict[network_name] = networks[0]['ip_ranges']
            self._check_roles_config(req, roles_meta,
                                     cidr_dict, ip_ranges_dict)

    def _check_service_disks_config(self, req, service_disks_meta):
        LOG.info("Check service_disks configs...")
        for service_disk in service_disks_meta:
            if not service_disk.get('id', None):
                msg = "id must be given when update service backend configs"
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)
            else:
                self.get_service_disk_meta_or_404(req, service_disk['id'])

            if service_disk.get('data_ips', None):
                for ip_addr in service_disk['data_ips'].split(','):
                    utils.validate_ip_format(ip_addr)

    def _check_cinder_volumes_config(self, req, cinder_volumes_meta):
        LOG.info("Check cinder_volumes configs...")
        for cinder_volume in cinder_volumes_meta:
            if not cinder_volume.get('id', None):
                msg = "id must be given when update cinder backend configs"
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)
            else:
                self.get_cinder_volume_meta_or_404(
                    req, cinder_volume['id'])
            if cinder_volume.get('data_ips', None):
                for ip_addr in cinder_volume['data_ips'].split(','):
                    utils.validate_ip_format(ip_addr)

            if cinder_volume.get('management_ips', None):
                for ip_addr in cinder_volume['management_ips'].split(','):
                    utils.validate_ip_format(ip_addr)

    def _get_networks_update_config(self, req, networks_meta):
        LOG.info("Get network configs...")
        networks_config = []
        for network in networks_meta:
            new_network = {}
            orig_network_meta = self.get_network_meta_or_404(
                req, network['id'])
            for key in network.keys():
                if not network[key] and not orig_network_meta[key]:
                    continue
                if key in UPDATE_NETWORK_PARAMS:
                    if key == 'ip_ranges':
                        is_equal = utils.is_ip_ranges_equal(
                            network[key], orig_network_meta[key])
                        if not is_equal:
                            new_network[key] = network[key]
                        continue
                    if key == 'vlan_id':
                        # vlan id maybe null
                        if str(network[key]) != str(orig_network_meta[key]):
                            new_network[key] = network[key]
                    elif str(network[key]) != str(orig_network_meta[key]):
                        new_network[key] = network[key]

            if new_network:
                if ('vlan_start' in new_network and
                        'vlan_end' not in new_network):
                    orig_vlan_end = orig_network_meta['vlan_end']
                    new_network['vlan_end'] = network.get('vlan_end',
                                                          orig_vlan_end)
                if ('vlan_start' not in new_network and
                        'vlan_end' in new_network):
                    orig_vlan_end = orig_network_meta['vlan_start']
                    new_network['vlan_start'] = network.get('vlan_start',
                                                            orig_vlan_end)
                new_network['id'] = network['id']
                new_network['name'] = orig_network_meta['name']
                new_network['network_type'] = orig_network_meta['network_type']
                if orig_network_meta['network_type'] == 'DATAPLANE':
                    new_network['segmentation_type'] =\
                        orig_network_meta['segmentation_type']

                networks_config.append(new_network)

        return {'networks': networks_config}

    def _get_roles_update_config(self, req, roles_meta):
        LOG.info("Get role configs...")
        roles_config = []
        for role in roles_meta:
            role_config = {}
            orig_role_meta = self.get_role_meta_or_404(
                req, role['id'])
            for key in role.keys():
                if (key in UPDATE_ROLE_PARAMS and
                        role[key] != orig_role_meta[key]):
                    role_config[key] = role[key]
            if role_config:
                role_config['id'] = orig_role_meta['id']
                role_config['name'] = orig_role_meta['name']
                roles_config.append(role_config)

        return {'roles': roles_config}

    def _get_service_disks_update_config(self, req, service_disks_meta):
        LOG.info("Get service_disk configs...")
        service_disks_config = []
        for service_disk in service_disks_meta:
            service_disk_config = {}
            orig_service_disk_meta = self.get_service_disk_meta_or_404(
                req, service_disk['id'])
            for key in service_disk.keys():
                if (key in UPDATE_SERVICE_DISK_PARAMS and
                        set(service_disk[key].split(',')) !=
                        set(orig_service_disk_meta[key].split(','))):
                    service_disk_config[key] = service_disk[key]
            if service_disk_config:
                service_disk_config['id'] = service_disk['id']
                service_disks_config.append(service_disk_config)

        return {'service_disks': service_disks_config}

    def _get_cinder_volume_update_configs(self, req, cinder_volumes_meta):
        LOG.info("Get cinder_volume configs...")
        cinder_volumes_config = []
        for cinder_volume in cinder_volumes_meta:
            cinder_volume_config = {}
            orig_cinder_volume_meta = self.get_cinder_volume_meta_or_404(
                req, cinder_volume['id'])
            for key in cinder_volume.keys():
                if (key in UPDATE_CINDER_VOLUME_PARAMS and
                        set(cinder_volume[key].split(',')) !=
                        set(orig_cinder_volume_meta[key].split(','))):
                    cinder_volume_config[key] = cinder_volume[key]
            if cinder_volume_config:
                cinder_volume_config['id'] = cinder_volume['id']
                cinder_volumes_config.append(cinder_volume_config)

        return {'cinder_volumes': cinder_volumes_config}

    def _get_host_network_ip(self, host_detail, network_name):
        for interface in host_detail['interfaces']:
            for assigned_network in interface.get('assigned_networks', []):
                if (assigned_network.get('name') == network_name and
                        assigned_network.get('ip')):
                    return assigned_network['ip']
        if network_name == 'MANAGEMENT':
            msg = "Can't find management ip from host %s."\
                % host_detail['id']
            LOG.error(msg)
            raise exception.InvalidNetworkConfig(msg)
        else:
            return None

    def _sort_hosts_by_network_ip(self, network_name, hosts_detail):
        ip_hosts_dict = {}
        for host_detail in hosts_detail:
            ip = self._get_host_network_ip(host_detail, network_name)
            if ip is None:
                msg = "Can't find ip of network '%s' from host %s."\
                    % (network_name, host_detail['id'])
                LOG.error(msg)
                raise exception.InvalidNetworkConfig(msg)
            ip_hosts_dict.update({ip: host_detail})
        sort_hosts_detail = [ip_hosts_dict[key] for key in
                             sorted(ip_hosts_dict.keys())]
        return sort_hosts_detail

    def _cidr_convert_ip_ranges(self, cidr):
        str_ip_mask = cidr.split('/')[1]
        ip_addr = cidr.split('/')[0]
        ip_inst = utils.ip_into_int(ip_addr)
        mask = ~(2**(32 - int(str_ip_mask)) - 1)
        ip_addr_min = utils.int_into_ip(ip_inst & (mask & 0xffffffff))
        ip_addr_max = utils.int_into_ip(ip_inst | (~mask & 0xffffffff))
        if ip_addr_min.split('.')[3] == '0':
            ip_addr_min = ip_addr_min.split('.')[0] + '.' + \
                ip_addr_min.split(
                    '.')[1] + '.' + ip_addr_min.split('.')[2] + '.1'
        return [ip_addr_min, ip_addr_max]

    def _distribute_ip(self, network, used_ips=set()):
        not_support_networks = ['EXTERNAL']
        if network['network_type'] in not_support_networks:
            msg = "network of '%s' type is not support to distribute ip"\
                % network['network_type']
            LOG.error(msg)
            raise exception.Forbidden(msg)

        int_ip_ranges = []
        if network.get('ip_ranges'):
            ip_ranges_dict = {}
            for ip_range in network['ip_ranges']:
                start_ip_int = utils.ip_into_int(ip_range['start'])
                end_ip_int = utils.ip_into_int(ip_range['end'])
                ip_ranges_dict.update(
                    {ip_range['start']: [start_ip_int, end_ip_int]})
            sorted_start_ips = sorted(ip_ranges_dict.keys())
            for ip in sorted_start_ips:
                int_ip_ranges.append(ip_ranges_dict[ip])
        else:
            ip_ranges_cidr = self._cidr_convert_ip_ranges(network['cidr'])
            start_ip_int = utils.ip_into_int(ip_ranges_cidr[0])
            end_ip_int = utils.ip_into_int(ip_ranges_cidr[1])
            # skip the first ip xx.xx.xx.1, so start_ip_int add 1
            int_ip_ranges.append([start_ip_int + 1, end_ip_int])

        for int_range in int_ip_ranges:
            ip_int = int_range[0]
            while ip_int <= int_range[1]:
                ip = utils.int_into_ip(ip_int)
                if ip not in used_ips:
                    return ip
                ip_int += 1
        msg = "distribute ip failed for network '%s', because ip "\
            "ranges are not enough." % network['name']
        LOG.error(msg)
        raise exception.Forbidden(msg)

    def _get_new_cluster_networks(self,
                                  orig_cluster_networks,
                                  update_networks):
        new_cluster_networks = []
        for orig_network in orig_cluster_networks:
            changed_network = False
            for network in update_networks:
                if orig_network['id'] == network['id']:
                    changed_network = True
                    new_network = copy.deepcopy(orig_network)
                    new_network.update(network)
                    new_cluster_networks.append(new_network)
            if not changed_network:
                new_cluster_networks.append(orig_network)
        return new_cluster_networks

    def _get_new_cluster_roles(self, orig_cluster_roles, update_roles):
        new_cluster_roles = []
        for orig_role in orig_cluster_roles:
            changed_role = False
            for role in update_roles:
                if orig_role['id'] == role['id']:
                    changed_role = True
                    new_role = copy.deepcopy(orig_role)
                    new_role.update(role)
                    new_cluster_roles.append(new_role)
            if not changed_role:
                new_cluster_roles.append(orig_role)
        return new_cluster_roles

    # get networks name which cidr is same with given network,
    # don't include itself
    def _get_same_cidr_networks(self, network, cluster_networks):
        cidr = network.get('cidr')
        name = network.get('name')
        if not cidr:
            msg = (_("cidr not given"))
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg)
        return [net['name'] for net in cluster_networks
                if net['cidr'] == cidr and net['name'] != name]

    def _get_host_network_new_ip(self, hosts_network_ip,
                                 network_name, host_id):
        if hosts_network_ip.get(network_name):
            for host in hosts_network_ip.get(network_name):
                if host['id'] == host_id:
                    return host['ip']
        return None

    def _write_json_file(self, cluster_id, file_name, update_config):
        if not update_config:
            return

        config_path = CONFIG_PATH % {'cluster_id': cluster_id}
        if not os.path.exists(config_path):
            mkdir_cmd = "mkdir -p " + config_path
            daisy_cmn.subprocess_call(mkdir_cmd)

        json_file = CONFIG_FILE % {'cluster_id': cluster_id,
                                   'file_name': file_name}

        with open(json_file, "w+") as fp:
            fp.write(json.dumps(update_config, indent=2))

    def _read_json_file(self, cluster_id, file_name):
        LOG.info("Get config %s..." % file_name)
        json_file = CONFIG_FILE % {'cluster_id': cluster_id,
                                   'file_name': file_name}
        if not os.path.exists(json_file):
            msg = "No config file '%s'." % json_file
            LOG.info(msg)
            return {}

        with open(json_file, 'r') as fp:
            update_config = json.load(fp)
        return update_config

    def _get_cidr_used_ips(self, network_name, hosts_network_ip,
                           hosts_detail, same_cidr_networks_name,
                           cidr_changed_networks_name):
        used_ips = []
        for host_detail in hosts_detail:
            for interface in host_detail['interfaces']:
                for assigned_network in interface.get(
                        'assigned_networks', []):
                    # if new ips inlclude part of old ips, they will
                    # conflict when configing network, so old network ip
                    # also be considered to be has used,
                    # because we will used this ip when the old ip
                    # still in new cidr and ip_ranges
                    if assigned_network.get('name') == network_name:
                        if assigned_network.get('ip') not in used_ips:
                            used_ips.append(assigned_network.get('ip'))
                    # same cidr network
                    if (assigned_network.get('name') in
                            same_cidr_networks_name):
                        if (assigned_network.get('name') in
                                cidr_changed_networks_name):
                            # get ip assigned again for cidr changed networks
                            new_ip = self._get_host_network_new_ip(
                                hosts_network_ip,
                                assigned_network.get('name'),
                                host_detail['id'])
                            if new_ip and new_ip not in used_ips:
                                used_ips.append(new_ip)
                        else:
                            if assigned_network.get('ip') not in used_ips:
                                used_ips.append(assigned_network.get('ip'))
        return used_ips

    def _get_ip_from_same_cidr_networks(self, hosts_network_ip,
                                        host_detail, new_network,
                                        same_cidr_networks_name):
        for network_name in same_cidr_networks_name:
            new_ip = self._get_host_network_new_ip(hosts_network_ip,
                                                   network_name,
                                                   host_detail['id'])
            if new_ip:
                return new_ip

        for interface in host_detail['interfaces']:
            for assigned_network in interface.get('assigned_networks', []):
                if (assigned_network.get('name') in
                    same_cidr_networks_name and
                        assigned_network.get('ip')):
                    new_ip = assigned_network.get('ip')
                    if new_network.get('ip_ranges'):
                        if (utils.is_ip_in_ranges(
                                new_ip, new_network.get('ip_ranges'))):
                            return new_ip
                    else:
                        if utils.is_ip_in_cidr(new_ip,
                                               new_network.get('cidr')):
                            return new_ip
        return None

    def _get_management_vips(self, roles):
        mgnt_vips = []
        for role in roles:
            for key in role.keys():
                if key in UPDATE_MGNT_VIP_PARAMS:
                    mgnt_vips.append(role[key])
        return mgnt_vips

    def _filter_hosts_by_network(self, network_name, hosts_detail):
        hosts = []
        for host_detail in hosts_detail:
            for interface in host_detail['interfaces']:
                assigned_networks = \
                    interface.get('assigned_networks', [])
                for assigned_network in assigned_networks:
                    if assigned_network.get('name') == network_name:
                        hosts.append(host_detail)
        return hosts

    def _host_ip_in_network_ranges(self, host_detail,
                                   new_network, vip_used_ips):
        if new_network['name'] == 'DATAPLANE':
            msg = "network 'DATAPLANE' is not supported."
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg)
        for interface in host_detail['interfaces']:
            for assigned_network in interface.get('assigned_networks', []):
                if assigned_network.get('name') == new_network['name']:
                    if not assigned_network.get('ip'):
                        msg = "No ip assigned for network %s of host %s."\
                            % (new_network['name'], host_detail['id'])
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg)
                    if assigned_network['ip'] in vip_used_ips:
                        return None
                    if new_network.get('ip_ranges'):
                        if utils.is_ip_in_ranges(assigned_network['ip'],
                                                 new_network['ip_ranges']):
                            return assigned_network.get('ip')
                        else:
                            return None
                    else:
                        if utils.is_ip_in_cidr(assigned_network['ip'],
                                               new_network['cidr']):
                            return assigned_network.get('ip')
                        else:
                            return None

        msg = "Can't find network '%s' from host '%s'."\
            % (new_network['name'], host_detail['id'])
        LOG.error(msg)
        raise HTTPBadRequest(explanation=msg)

    def _is_host_network_ip_in_used(self, host_detail,
                                    network_name, used_ips):
        if network_name == 'DATAPLANE':
            msg = "network 'DATAPLANE' is not supported."
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg)
        for interface in host_detail['interfaces']:
            for assigned_network in interface.get('assigned_networks', []):
                if assigned_network.get('name') == network_name:
                    if not assigned_network.get('ip'):
                        msg = "No ip assigned for network %s of host %s."\
                            % (network_name, host_detail['id'])
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg)
                    if assigned_network['ip'] in used_ips:
                        return True
                    else:
                        return False
        msg = "Can't find network '%s' from host '%s'."\
            % (network_name, host_detail['id'])
        LOG.error(msg)
        raise HTTPBadRequest(explanation=msg)

    def _get_hosts_network_ip(self, req, cluster_id, update_config):
        networks_config = update_config.get('networks', [])
        roles_config = update_config.get('roles', [])
        orig_cluster_networks = \
            daisy_cmn.get_cluster_networks_detail(req, cluster_id)

        changed_networks = {}
        cidr_changed_networks_name = []
        if networks_config:
            new_cluster_networks = self._get_new_cluster_networks(
                orig_cluster_networks, networks_config)
            for network in networks_config:
                changed_networks.update({network['name']: network})
                cidr_changed_networks_name.append(network['name'])
        else:
            LOG.info('No networks need to update')
            new_cluster_networks = orig_cluster_networks

        params = {'filters': {'cluster_id': cluster_id}}
        orig_cluster_roles = registry.get_roles_detail(req.context,
                                                       **params)
        changed_roles = {}
        if roles_config:
            new_cluster_roles = self._get_new_cluster_roles(
                orig_cluster_roles, roles_config)
            for role in roles_config:
                changed_roles.update({role['name']: role})
        else:
            LOG.info('No roles need to update')
            new_cluster_roles = orig_cluster_roles

        new_ha_role = [role for role in new_cluster_roles
                       if role['name'] == 'CONTROLLER_HA'][0]

        # self._redistribute_hosts_network_ip(req, cluster_id, )
        hosts_network_ip = {}
        orig_hosts_detail = tecs_cmn.get_tecs_hosts_detail(req, cluster_id)
        for network_name in changed_networks.keys():
            new_network = [network for network in new_cluster_networks
                           if network['name'] == network_name][0]
            orig_network = [network for network in orig_cluster_networks
                            if network['name'] == network_name][0]
            not_supported_network_type = ['EXTERNAL']
            if new_network['network_type'] in not_supported_network_type:
                continue
            # for the first stage, only support to modify public and storage
            supported_network_type = ['DATAPLANE', 'PUBLICAPI', 'STORAGE']
            if new_network['network_type'] not in supported_network_type:
                continue
            hosts_detail = self._filter_hosts_by_network(
                network_name, orig_hosts_detail)

            if hosts_detail:
                if (new_network['network_type'] == 'DATAPLANE' and
                        new_network['segmentation_type'] != 'vxlan'):
                    continue

                same_cidr_networks = self._get_same_cidr_networks(
                    new_network, new_cluster_networks)

                used_ips = self._get_cidr_used_ips(network_name,
                                                   hosts_network_ip,
                                                   orig_hosts_detail,
                                                   same_cidr_networks,
                                                   cidr_changed_networks_name)
                vip_used_ips = []
                if network_name == 'PUBLICAPI':
                    used_ips.append(new_ha_role['public_vip'])
                    vip_used_ips.append(new_ha_role['public_vip'])
                if 'MANAGEMENT' in same_cidr_networks:
                    mgnt_vips = self._get_management_vips(new_cluster_roles)
                    used_ips += mgnt_vips
                    vip_used_ips += mgnt_vips
                if (new_network['gateway'] and
                    utils.is_ip_in_cidr(new_network['gateway'],
                                        new_network['cidr'])):
                    used_ips.append(new_network['gateway'])
                hosts_sorted = self._sort_hosts_by_network_ip(
                    network_name, hosts_detail)
                hosts_ip = []
                if 'cidr' in changed_networks[network_name]:
                    for host_detail in hosts_sorted:
                        host_ip = {}
                        old_ip = self._host_ip_in_network_ranges(
                            host_detail, new_network, vip_used_ips)
                        if old_ip:
                            new_cidr = changed_networks[network_name]['cidr']
                            orig_cidr = orig_network['cidr']
                            if (new_cidr.split('/')[1] !=
                                    orig_cidr.split('/')[1]):
                                host_ip = {'id': host_detail['id'],
                                           'name': host_detail['name'],
                                           'ip': old_ip}
                                if old_ip not in used_ips:
                                    used_ips.append(old_ip)
                                hosts_ip.append(host_ip)
                            continue

                        ip = None
                        if same_cidr_networks:
                            ip = self._get_ip_from_same_cidr_networks(
                                hosts_network_ip, host_detail,
                                new_network, same_cidr_networks)
                        if not ip:
                            ip = self._distribute_ip(
                                new_network, set(used_ips))
                        host_ip = {'id': host_detail['id'],
                                   'name': host_detail['name'],
                                   'ip': ip}
                        if ip not in used_ips:
                            used_ips.append(ip)
                        hosts_ip.append(host_ip)
                elif 'ip_ranges' in changed_networks[network_name]:
                    for host_detail in hosts_sorted:
                        host_ip = {}
                        old_ip = self._host_ip_in_network_ranges(
                            host_detail, new_network, vip_used_ips)
                        if old_ip:
                            # don't need to add used_ips,
                            # because it has add before
                            continue

                        ip = None
                        if same_cidr_networks:
                            ip = self._get_ip_from_same_cidr_networks(
                                hosts_network_ip, host_detail,
                                new_network, same_cidr_networks)
                        if not ip:
                            ip = self._distribute_ip(
                                new_network, set(used_ips))
                        host_ip = {'id': host_detail['id'],
                                   'name': host_detail['name'],
                                   'ip': ip}
                        if ip not in used_ips:
                            used_ips.append(ip)
                        hosts_ip.append(host_ip)
                if hosts_ip:
                    hosts_network_ip.update({network_name: hosts_ip})
        return hosts_network_ip

    def _land_networks_config(self, req, cluster_id, update_config):
        if (not update_config.get('networks') and
                not update_config.get('roles')):
            LOG.info('No networks and roles need to update')
            return

        hosts_network_ip = self._get_hosts_network_ip(
            req, cluster_id, update_config)
        if hosts_network_ip:
            self._write_json_file(cluster_id,
                                  HOSTS_NETWORK_IP_FILE_NAME,
                                  hosts_network_ip)

        self._get_os_json(req, cluster_id,
                          update_config, hosts_network_ip)
        self._get_ctrl_nodes_private_network_json(
            req, cluster_id, update_config.get('networks', []))

        self._get_ha_conf(req, cluster_id,
                          update_config, hosts_network_ip)
        self._get_keystone_conf(req, cluster_id, update_config)
        self._get_other_config_items(req,
                                     cluster_id,
                                     update_config,
                                     hosts_network_ip)

    def _land_disk_array_config(self, req, cluster_id, update_config):
        service_disks_meta = update_config.get('service_disks', [])
        cinder_volumes_meta = update_config.get('cinder_volumes', [])

        if cinder_volumes_meta:
            self._gen_cinder_json(req, cluster_id, cinder_volumes_meta)

        if service_disks_meta:
            self._gen_control_json(req, cluster_id, service_disks_meta)

    def _gen_cinder_json(self, req, cluster_id, cinder_volumes_meta):
        volume_disk_info = self._get_origin_volume_disk(req, cluster_id)
        for disk in volume_disk_info:
            disk['management_ips'] = disk['management_ips'].split(',')
            disk['data_ips'] = disk['data_ips'].split(',')
            new_management_ip = self._get_new_mgnt_ip_with_cinder_volume_id(
                disk['id'], cinder_volumes_meta)
            if new_management_ip:
                new_management_ip_list = new_management_ip.split(',')
                disk['management_ips'] = new_management_ip_list
            new_data_ip = self._get_new_data_ip_with_cinder_volume_id(
                disk['id'], cinder_volumes_meta)
            if new_data_ip:
                new_data_ip_list = new_data_ip.split(',')
                disk['data_ips'] = new_data_ip_list
        json_file = CONFIG_FILE % {
            'cluster_id': cluster_id,
            'file_name': 'cinder.json'
        }
        with open(json_file, "w") as fp:
            json.dump({'disk_array': volume_disk_info}, fp, indent=2)

    def _gen_control_json(self, req, cluster_id, service_disks_meta):
        all_share_disk_info = self._get_all_share_disk_info(
            req, cluster_id, service_disks_meta)
        origin_roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
        share_disk_json = dict()
        host_id_dict = dict()
        for role in origin_roles:
            if role['name'] == "CONTROLLER_HA":
                role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
                for role_host in role_hosts:
                    orig_host_detail = daisy_cmn.get_host_detail(
                        req, role_host['host_id'])
                    min_mac = utils.get_host_min_mac(
                        orig_host_detail['interfaces'])
                    host_id_dict[role_host['host_id']] = min_mac

        sorted_host_ids = sorted(host_id_dict, key=lambda d: d[1])
        config_path = CONFIG_PATH % {'cluster_id': cluster_id}
        for (index, host_id, share_disk) in zip(
                (1, 2), sorted_host_ids, all_share_disk_info):
            orig_host_detail = daisy_cmn.get_host_detail(req, host_id)
            hosts_network_ip = self._read_json_file(
                cluster_id, HOSTS_NETWORK_IP_FILE_NAME)
            host_detail = self._get_new_host_detail(orig_host_detail,
                                                    hosts_network_ip)
            host_mgnt_ip = self._get_new_host_mgnt_ip(host_detail)
            share_disk_json['json'] = share_disk
            share_disk_json['host_id'] = host_id
            share_disk_json['min_mac'] = host_id_dict[host_id]
            share_disk_json['new_mgnt_ip'] = host_mgnt_ip
            with open(config_path + "/control_%s.json" % index, "w") as fp:
                json.dump(share_disk_json, fp, indent=2)

    def _get_all_share_disk_info(self, req, cluster_id, service_disks_meta):
        (share_disk_info, volume_disk_info,
         share_cluster_disk_info) = \
            disk_array.get_disk_array_info(req, cluster_id)

        if share_disk_info:
            for share_disk in share_disk_info:
                share_disk_data_ip = \
                    self._get_new_data_ip_with_service_disk_id(
                        service_disks_meta, share_disk)
                if share_disk_data_ip:
                    share_disk['data_ips'] = share_disk_data_ip

        if share_cluster_disk_info:
            for share_cluster_disk in share_cluster_disk_info:
                share_cluster_disk_ip = \
                    self._get_new_data_ip_with_service_disk_id(
                        service_disks_meta, share_cluster_disk)
                if share_cluster_disk_ip:
                    share_cluster_disk['data_ips'] = share_cluster_disk_ip

        db_share_cluster_disk = [disk for disk in share_cluster_disk_info
                                 if disk['service'] == 'db']
        sorted_db_share_cluster = sorted(db_share_cluster_disk,
                                         key=lambda s: s['lun'])

        if sorted_db_share_cluster:
            all_share_disk_info = \
                [[disk] + share_disk_info for disk in sorted_db_share_cluster]
        else:
            all_share_disk_info = [share_disk_info, share_disk_info]
        return all_share_disk_info

    def _get_new_data_ip_with_service_disk_id(self, service_disks_meta,
                                              share_disk):
        for service_disk in service_disks_meta:
            if service_disk['id'] == share_disk['id']:
                return service_disk['data_ips'].split(',')

        return None

    def _get_new_host_mgnt_ip(self, host_detail):
        interfaces = host_detail.get('interfaces', [])
        for interface in interfaces:
            assigned_networks = interface.get('assigned_networks', [])
            for assigned_network in assigned_networks:
                if assigned_network.get('name') == 'MANAGEMENT':
                    return assigned_network.get('ip')

    def _get_new_mgnt_ip_with_cinder_volume_id(self, disk_id,
                                               cinder_volumes_meta):
        for cinder_volume in cinder_volumes_meta:
            if disk_id == cinder_volume.get('id'):
                return cinder_volume.get('management_ips')

        return None

    def _get_new_data_ip_with_cinder_volume_id(self, disk_id,
                                               cinder_volumes_meta):
        for cinder_volume in cinder_volumes_meta:
            if disk_id == cinder_volume.get('id'):
                return cinder_volume.get('data_ips')

        return None

    def _get_origin_volume_disk(self, req, cluster_id):
        roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
        cinder_volume_disk_list = list()
        for role in roles:
            if role['name'] == 'CONTROLLER_HA':
                cinder_volume_info = list()
                cinder_volumes = tecs_cmn.get_cinder_volume_list(
                    req, {'filters': {'role_id': role['id']}})
                for cinder_volume in cinder_volumes:
                    cv_info = dict()
                    cv_info['id'] = cinder_volume['id']
                    cv_info['management_ips'] = cinder_volume['management_ips']
                    cv_info['data_ips'] = cinder_volume['data_ips']
                    cv_info['user_name'] = cinder_volume['user_name']
                    cv_info['user_pwd'] = cinder_volume['user_pwd']
                    cv_info['volume_driver'] = cinder_volume['volume_driver']
                    index = cinder_volume['backend_index']
                    cv_info['backend'] = {index: {}}
                    cv_info['backend'][index][
                        'volume_driver'] = cinder_volume['volume_driver']
                    cv_info['backend'][index][
                        'volume_type'] = cinder_volume['volume_type']
                    cv_info['backend'][index][
                        'pools'] = cinder_volume['pools'].split(',')
                    cinder_volume_info.append(cv_info)

                cinder_volume_disk_list += cinder_volume_info

        return cinder_volume_disk_list

    def _get_network_plat(self, req, host_config, cluster_networks):
        if host_config['interfaces']:
            count = 0
            host_config_orig = copy.deepcopy(host_config)
            for interface in host_config['interfaces']:
                count += 1
                # if (interface.has_key('assigned_networks') and
                if ('assigned_networks' in interface and
                        interface['assigned_networks']):
                    assigned_networks = copy.deepcopy(
                        interface['assigned_networks'])
                    host_config['interfaces'][
                        count - 1]['assigned_networks'] = []
                    alias = []
                    for assigned_network in assigned_networks:
                        network_name = assigned_network['name']
                        cluster_network = [
                            network for network in cluster_networks
                            if network['name'] == network_name][0]
                        alias.append(cluster_network['alias'])
                        assigned_networks_ip = daisy_cmn.get_host_network_ip(
                            req, host_config_orig,
                            cluster_networks, network_name)
                        # convert cidr to netmask
                        cidr_to_ip = ""
                        if cluster_network.get('cidr'):
                            int_netmask = cluster_network['cidr'].split('/')[1]
                            cidr_to_ip = utils.cidr_netmask_to_ip(int_netmask)
                        if cluster_network['alias'] is None or len(alias) == 1:
                            network_plat = dict(network_name=network_name,
                                                ml2_type=cluster_network[
                                                    'ml2_type'],
                                                capability=cluster_network[
                                                    'capability'],
                                                physnet_name=cluster_network[
                                                    'physnet_name'],
                                                gateway=cluster_network.get(
                                                    'gateway', ""),
                                                ip=assigned_networks_ip,
                                                netmask=cidr_to_ip,
                                                vlan_id=cluster_network.get(
                                                    'vlan_id', ""))
                            host_config['interfaces'][count - 1][
                                'assigned_networks'].append(network_plat)
                interface['ip'] = ""
                interface['netmask'] = ""
                interface['gateway'] = ""

        return host_config

    def _get_hosts_config(self, req, cluster_id, host_detail):
        linux_bond_mode = {'balance-rr': '0', 'active-backup': '1',
                           'balance-xor': '2', 'broadcast': '3',
                           '802.3ad': '4', 'balance-tlb': '5',
                           'balance-alb': '6'}
        networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)
        host_config_detail = copy.deepcopy(host_detail)
        for interface in host_config_detail['interfaces']:
            if (interface['type'] == 'bond' and
                    interface['mode'] in linux_bond_mode.keys()):
                interface['mode'] = linux_bond_mode[interface['mode']]
        host_config = self._get_network_plat(req, host_config_detail,
                                             networks)
        sorted_host = daisy_cmn.sort_interfaces_by_pci(networks, host_config)
        return sorted_host

    def _pop_useless_fields(self, new_interface):
        useless_fields = ['updated_at', 'deleted_at', 'created_at',
                          'deleted', 'is_deployment', 'host_id']
        for key in new_interface.keys():
            if key in useless_fields:
                new_interface.pop(key)

    def _add_fields_for_private_network(self, new_interface, host_detail):
        # where to get mtu?
        new_interface['mtu'] = ''
        slave1 = new_interface.get('slave1', None)
        slave2 = new_interface.get('slave2', None)
        if not slave1 and not slave2:
            return
        for interface in host_detail['interfaces']:
            if slave1 and 0 == cmp(interface.get('name', None), slave1):
                new_interface['pci1'] = interface['pci']
            if slave2 and 0 == cmp(interface.get('name', None), slave2):
                new_interface['pci2'] = interface['pci']

    def _get_host_os_json_data(self, req, cluster_id,
                               update_networks, hosts_network_ip):
        orig_hosts_detail = tecs_cmn.get_tecs_hosts_detail(req, cluster_id)
        orig_networks = daisy_cmn.get_cluster_networks_detail(req,
                                                              cluster_id)
        all_os_json_data = {}
        mgnt_network_name = 'MANAGEMENT'
        for orig_host_detail in orig_hosts_detail:
            mgnt_interface = daisy_cmn.get_host_interface_by_network(
                orig_host_detail, mgnt_network_name)
            mgnt_ip = [assgin_network.get('ip') for assgin_network in
                       mgnt_interface.get('assigned_networks', [])
                       if assgin_network.get('name') == mgnt_network_name][0]
            if not mgnt_ip:
                msg = "Can't get 'MANAGEMENT' network ip for host '%s'"\
                    % orig_host_detail['id']
                raise exception.InvalidNetworkConfig(msg)
            network_change_factors = ['netmask', 'gateway', 'vlan_id']
            host_network_change_factors = ['ip'] + network_change_factors
            orig_host_config = self._get_hosts_config(req, cluster_id,
                                                      orig_host_detail)
            for interface in orig_host_config.get('interfaces', []):
                for assign_network in interface.get('assigned_networks', []):
                    network_changed = False
                    if assign_network.get('network_name'):
                        for key in assign_network.keys():
                            if key in host_network_change_factors:
                                old_key = 'old_' + key
                                assign_network[old_key] = assign_network[key]
                        orig_network = \
                            [network for network in orig_networks
                                if network['name'] ==
                                assign_network['network_name']][0]
                        assign_network['network_type'] = \
                            orig_network['network_type']
                        assign_network['segmentation_type'] = \
                            orig_network['segmentation_type']
                        network_name = assign_network['network_name']
                        for host in hosts_network_ip.get(network_name, []):
                            if orig_host_config['id'] == host['id']:
                                assign_network['ip'] = host['ip']
                                network_changed = True
                        for network in update_networks:
                            not_supported_networks = ['EXTERNAL']
                            if (network['network_type'] in
                                    not_supported_networks):
                                continue
                            if (network['network_type'] == 'DATAPLANE' and
                                    network.get('segmentation_type') and
                                    network['segmentation_type'] != 'vxlan'):
                                continue
                            if network_name == network['name']:
                                for key in network.keys():
                                    if key == 'cidr' and network[key]:
                                        int_netmask = network[
                                            key].split('/')[1]
                                        ip_netmask = utils.cidr_netmask_to_ip(
                                            int_netmask)
                                        assign_network['netmask'] = ip_netmask
                                        network_changed = True
                                    if key in network_change_factors:
                                        assign_network[key] = network[key]
                                        network_changed = True
                        if network_changed:
                            new_interface = copy.deepcopy(interface)
                            new_interface['assigned_networks'] = \
                                [assign_network]
                            self._pop_useless_fields(new_interface)
                            if orig_network['network_type'] == 'DATAPLANE':
                                self._add_fields_for_private_network(
                                    new_interface, orig_host_detail)
                            os_json = {'host_id': orig_host_config['id'],
                                       'hostname': orig_host_config['name'],
                                       'interfaces': [new_interface]}
                            new_host_config = {}
                            new_host_config = {'json': os_json,
                                               'old_mgnt_ip': mgnt_ip}
                            if network_name in all_os_json_data:
                                all_os_json_data[network_name].append(
                                    new_host_config)
                            else:
                                all_os_json_data.update(
                                    {network_name: [new_host_config]})
        return all_os_json_data

    def _get_os_json(self, req, cluster_id,
                     orig_update_config, hosts_network_ip):
        if (not orig_update_config.get('networks') and
                not orig_update_config.get('roles')):
            LOG.info('No network and roles data updated, '
                     'so no OS JSON file generated')
            return

        if not hosts_network_ip:
            if not orig_update_config.get('networks'):
                LOG.info('No networks data need to updated, '
                         'so no OS JSON file generated')
                return
            else:
                network_changed = False
                network_change_factors = ['vlan_id', 'gateway']
                for network in orig_update_config['networks']:
                    for key in network.keys():
                        if key in network_change_factors:
                            network_changed = True
                if not network_changed:
                    LOG.info('No host need to update network, '
                             'so no OS JSON file generated')
                    return

        all_os_json_data = \
            self._get_host_os_json_data(req, cluster_id,
                                        orig_update_config['networks'],
                                        hosts_network_ip)
        if all_os_json_data:
            self._write_json_file(
                cluster_id, ALL_OS_JSON_FILE_NAME, all_os_json_data)

    def _get_new_roles(self, orig_roles, update_roles):
        if not update_roles:
            return orig_roles
        new_roles = copy.deepcopy(orig_roles)
        for role in new_roles:
            for update_role in update_roles:
                if role['id'] == update_role['id']:
                    role.update(update_role)
        return new_roles

    def _get_new_networks(self, orig_networks, update_networks):
        if not update_networks:
            return orig_networks
        new_networks = copy.deepcopy(orig_networks)
        for network in new_networks:
            for update_network in update_networks:
                if network['id'] == update_network['id']:
                    network.update(update_network)
        return new_networks

    def _get_new_cluster(self, orig_cluster, update_roles):
        if not update_roles:
            return orig_cluster

        for update_role in update_roles:
            if (update_role['name'] == 'CONTROLLER_HA' and
                    'public_vip' in update_role):
                new_cluster = copy.deepcopy(orig_cluster)
                new_cluster['public_vip'] = update_role['public_vip']
                return new_cluster
        return orig_cluster

    def _get_new_host_detail(self, orig_host_detail, hosts_network_ip):
        if not hosts_network_ip:
            return orig_host_detail

        new_host = copy.deepcopy(orig_host_detail)
        for interface in new_host.get('interfaces', []):
            for assigned_network in interface.get('assigned_networks', []):
                new_ip = self._get_host_network_new_ip(
                    hosts_network_ip,
                    assigned_network.get('name'),
                    new_host['id'])
                if new_ip:
                    assigned_network['ip'] = new_ip
        return new_host

    def _get_cluster_ha_config(self, req, cluster_id,
                               orig_update_config, hosts_network_ip):
        LOG.info(_("Get cluster ha config..."))
        orig_roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
        roles = self._get_new_roles(orig_roles,
                                    orig_update_config.get('roles'))
        orig_networks = daisy_cmn.get_cluster_networks_detail(req,
                                                              cluster_id)
        cluster_networks = self._get_new_networks(
            orig_networks, orig_update_config.get('networks'))
        try:
            params = dict(limit=1000000)
            all_services = registry.get_services_detail(req.context, **params)
            all_components = registry.get_components_detail(
                req.context, **params)
            orig_cluster = registry.get_cluster_metadata(
                req.context, cluster_id)
            cluster_data = self._get_new_cluster(
                orig_cluster, orig_update_config.get('roles'))
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)

        tecs_config = {}
        tecs_config.update({'OTHER': {}})
        other_config = tecs_config['OTHER']
        other_config.update({'cluster_data': cluster_data})
        for role in roles:
            if role['deployment_backend'] != daisy_cmn.tecs_backend_name:
                continue
            try:
                role_service_ids = registry.get_role_services(
                    req.context, role['id'])
            except exception.Invalid as e:
                raise HTTPBadRequest(explanation=e.msg, request=req)

            role_services_detail = [asc for rsci in role_service_ids
                                    for asc in all_services if asc[
                                        'id'] == rsci['service_id']]
            component_id_to_name = dict(
                [(ac['id'], ac['name']) for ac in all_components])
            service_components = dict(
                [(scd['name'], component_id_to_name[scd['component_id']])
                 for scd in role_services_detail])

            role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
            ha_nic_name = ''
            host_interfaces = []
            hosts_id = []
            for role_host in role_hosts:
                orig_host_detail = daisy_cmn.get_host_detail(
                    req, role_host['host_id'])
                host_detail = self._get_new_host_detail(
                    orig_host_detail, hosts_network_ip)
                hosts_id.append(role_host['host_id'])
                sorted_host_detail = daisy_cmn.sort_interfaces_by_pci(
                    cluster_networks, host_detail)

                # get ha nic port name
                if role['name'] == "CONTROLLER_HA":
                    mgr_nic_name = tecs_install.get_host_nic_name(
                        cluster_networks, sorted_host_detail)
                    mgr_vlan_id = tecs_cmn.get_mngt_network_vlan_id(
                        cluster_networks)
                    if mgr_vlan_id:
                        mgr_nic_name = mgr_nic_name + '.' + str(mgr_vlan_id)
                    if ha_nic_name and mgr_nic_name != ha_nic_name:
                        msg = "management plane nic name is\
                                different on hosts with HA role"
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg, request=req)
                    else:
                        ha_nic_name = mgr_nic_name
                    # if not other_config.has_key('ha_nic_name'):
                    if 'ha_nic_name' not in other_config:
                        other_config.update({'ha_nic_name': mgr_nic_name})

                has_interfaces = tecs_install.get_interfaces_network(
                    req, host_detail, cluster_networks)
                has_interfaces.update({'name': host_detail['name']})
                host_interfaces.append(has_interfaces)

            share_disk_services = \
                tecs_install.get_share_disk_services(req, role['id'])
            share_cluster_disk_services = \
                tecs_install.get_share_cluster_disk_services(req, role['id'])

            if host_interfaces:
                # if role['public_vip'] and not
                # host_interfaces[0].has_key('public'):
                if (role['public_vip'] and
                        'publicapi' not in host_interfaces[0]):
                    msg = "no public networkplane "\
                        "found while role has public vip"
                    LOG.error(msg)
                    raise exception.NotFound(message=msg)

                tecs_config.update({role['name']: {
                    'services': service_components,
                    'vip': role['vip'],
                    'host_interfaces': host_interfaces,
                    'share_disk_services': share_disk_services,
                    'share_cluster_disk_services':
                        share_cluster_disk_services,
                    'hosts_id': hosts_id}})
            is_ha = re.match(".*_HA$", role['name']) is not None
            if is_ha:
                tecs_config[role['name']]['ntp_server'] = role['ntp_server']
                tecs_config[role['name']]['public_vip'] = role['public_vip']
                tecs_config[role['name']]['glance_vip'] = role['glance_vip']
                tecs_config[role['name']]['db_vip'] = role['db_vip']

        return tecs_config

    def _gen_ha_conf(self, cluster_id, config_data):
        ha_conf_file = CONFIG_FILE % {'cluster_id': cluster_id,
                                      'file_name': HA_CONF_FILE_NAME}
        ha_conf_template_file = os.path.join(
            config.ha_template_file_path, "HA.conf")
        ha = config.ConfigParser()
        ha.optionxform = str
        ha.read(ha_conf_template_file)

        config_handle = config.AnalsyConfig(config_data)
        if 'ha_nic_name'in config_data['OTHER']:
            ha_nic_name = config_data['OTHER']['ha_nic_name']
        else:
            ha_nic_name = ""

        for role_name, role_configs in config_handle.all_configs.items():
            if role_name == "OTHER":
                continue
            is_ha = re.match(".*_HA$", role_name) is not None
            is_lb = re.match(".*_LB$", role_name) is not None
            if is_lb:
                config_handle.lb_vip = role_configs['vip']
            if is_ha:
                if role_configs['db_vip']:
                    config_handle.db_vip = role_configs['db_vip']
                else:
                    config_handle.db_vip = role_configs['vip']

                if role_configs['glance_vip']:
                    config_handle.glance_vip = role_configs['glance_vip']
                else:
                    config_handle.glance_vip = role_configs['vip']

                if role_configs['public_vip']:
                    config_handle.public_vip = role_configs['public_vip']
                else:
                    config_handle.public_vip = role_configs['vip']

                config_handle.ha_vip = role_configs['vip']
                config_handle.share_disk_services += role_configs[
                    'share_disk_services']
                config_handle.share_cluster_disk_services += \
                    role_configs['share_cluster_disk_services']
                config_handle.get_heartbeats(role_configs['host_interfaces'])

            for service, component in role_configs['services'].items():
                s = service.strip().upper().replace('-', '_')
                config_handle.prepare_role_service(is_ha, s, role_configs)
                config_handle.prepare_mode(is_ha, is_lb, s)

                if is_ha:
                    if component == 'log':
                        continue
                    config_handle.prepare_services_in_component(component,
                                                                service,
                                                                role_configs)

        config_handle.update_ha_conf(ha, ha_nic_name)
        ha.write(open(ha_conf_file, "w+"))

    def _is_network_fields_updated(self, network, fields):
        for field in network.keys():
            if field in fields:
                return True
        return False

    def _get_ha_conf(self, req, cluster_id,
                     orig_update_config, hosts_network_ip):
        need_rebulid_ha = False
        for role in orig_update_config.get('roles', []):
            if (set(UPDATE_VIP_PARAMS) & set(role.keys())):
                need_rebulid_ha = True
        storage_fields_affect_ha = ('cidr', 'ip_ranges')
        public_fields_affect_ha = ('cidr', 'ip_ranges', 'vlan_id')
        mgnt_fields_affect_ha = ('cidr', 'ip_ranges', 'vlan_id')
        heartbeat_fields_affect_ha = ('cidr', 'ip_ranges')
        for network in orig_update_config.get('networks', []):
            if ((network['network_type'] == 'STORAGE' and
                 self._is_network_fields_updated(
                    network, storage_fields_affect_ha)) or
                (network['network_type'] == 'PUBLICAPI' and
                 self._is_network_fields_updated(
                    network, public_fields_affect_ha)) or
                    (network['network_type'] == 'MANAGEMENT' and
                     self._is_network_fields_updated(
                        network, mgnt_fields_affect_ha)) or
                    (network['network_type'] == 'HEARTBEAT' and
                     self._is_network_fields_updated(
                        network, heartbeat_fields_affect_ha))):
                need_rebulid_ha = True
        if need_rebulid_ha:
            config_data = self._get_cluster_ha_config(req,
                                                      cluster_id,
                                                      orig_update_config,
                                                      hosts_network_ip)
            self._gen_ha_conf(cluster_id, config_data)

    def _get_keystone_conf(self, req, cluster_id, orig_update_config):
        ha_role_list = [role for role in orig_update_config.get('roles', [])
                        if role['name'] == 'CONTROLLER_HA']

        if ha_role_list and 'public_vip' in ha_role_list[0]:
            ha_role = ha_role_list[0]
            config_data = {'id': ha_role['id'],
                           'public_vip': ha_role['public_vip']}
            self._write_json_file(cluster_id,
                                  KEYSTONE_JSON_FILE_NAME, config_data)

    def _get_ctrl_private_network_field(self, orig_network, new_network):
        private_network = {}
        private_network['id'] = new_network['id']
        private_network['network_name'] = new_network['name']
        private_network['network_type'] = new_network['network_type']
        private_network['segmentation_type'] = \
            new_network['segmentation_type']
        if new_network['segmentation_type'] == 'vlan':
            private_network['old_vlan_start'] = str(orig_network['vlan_start'])
            private_network['old_vlan_end'] = str(orig_network['vlan_end'])
            private_network['vlan_start'] = str(new_network['vlan_start'])
            private_network['vlan_end'] = str(new_network['vlan_end'])
        if new_network['segmentation_type'] == 'vxlan':
            private_network['old_vlan_start'] = str(orig_network['vni_start'])
            private_network['old_vlan_end'] = str(orig_network['vni_end'])
            private_network['vlan_start'] = str(new_network['vni_start'])
            private_network['vlan_end'] = str(new_network['vni_end'])
        return private_network

    def _get_ctrl_nodes_private_network_json(self,
                                             req, cluster_id, update_networks):
        if not update_networks:
            return
        orig_networks = daisy_cmn.get_cluster_networks_detail(req,
                                                              cluster_id)
        new_networks = self._get_new_cluster_networks(
            orig_networks, update_networks)

        private_networks = []
        for update_network in update_networks:
            if update_network['network_type'] == 'DATAPLANE':
                # when vlan and vni ranges changed,
                # then write them to private_ctrl.json
                if ('vlan_start' not in update_network and
                        'vlan_end' not in update_network and
                        'vni_start' not in update_network and
                        'vni_end' not in update_network):
                    continue
                orig_network = [network for network in orig_networks
                                if network['name'] ==
                                update_network['name']][0]
                new_network = [network for network in new_networks
                               if network['name'] ==
                               update_network['name']][0]
                private_network = self._get_ctrl_private_network_field(
                    orig_network, new_network)
                if private_network:
                    private_networks.append(private_network)
        if private_networks:
            self._write_json_file(
                cluster_id, PRIVATE_CTRL_JSON_FILE_NAME,
                {'private_networks': private_networks})

    def _get_cluster_mgnt_ip(self, req, cluster_id,
                             orig_update_config={}, hosts_network_ip={}):
        LOG.info(_("Get cluster hosts management ip..."))
        orig_roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
        roles = self._get_new_roles(orig_roles,
                                    orig_update_config.get('roles'))
        orig_networks = daisy_cmn.get_cluster_networks_detail(req,
                                                              cluster_id)
        cluster_networks = self._get_new_networks(
            orig_networks, orig_update_config.get('networks'))
        ip_list = {'ha': [], 'lb': [], 'computer': []}
        for role in roles:
            if role['deployment_backend'] != daisy_cmn.tecs_backend_name:
                continue
            role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
            for role_host in role_hosts:
                if role_host['status'] != tecs_state['ACTIVE']:
                    if role['name'] == 'CONTROLLER_HA':
                        msg = "tecs status of HA node %s is not active."\
                            % role_host['host_id']
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg, request=req)
                    else:
                        continue
                orig_host_detail = daisy_cmn.get_host_detail(
                    req, role_host['host_id'])
                host_detail = self._get_new_host_detail(
                    orig_host_detail, hosts_network_ip)
                has_interfaces = tecs_install.get_interfaces_network(
                    req, host_detail, cluster_networks)
                # mangement network must be configed
                host_mgnt_ip = has_interfaces['management']['ip']
                if (role['name'] == 'CONTROLLER_HA' and
                        host_mgnt_ip not in ip_list['ha']):
                    ip_list['ha'].append(host_mgnt_ip)
                if (role['name'] == 'CONTROLLER_LB' and
                        host_mgnt_ip not in ip_list['lb']):
                    ip_list['lb'].append(host_mgnt_ip)
                if (role['name'] == 'COMPUTER' and
                        host_mgnt_ip not in ip_list['computer']):
                    ip_list['computer'].append(host_mgnt_ip)

        if not ip_list['ha']:
            msg = "No HA node management ip got."
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)
        return ip_list

    def _get_role_nodes_info(self, req, cluster_id):
        LOG.info(_("Get cluster hosts management ip..."))
        roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)

        cluster_networks = daisy_cmn.get_cluster_networks_detail(
            req, cluster_id)
        ctrl_role = ['CONTROLLER_HA', 'CONTROLLER_LB', 'COMPUTER']
        role_nodes_info = {'ha': [], 'lb': [], 'computer': []}

        for role in roles:
            if role['deployment_backend'] != daisy_cmn.tecs_backend_name:
                continue
            role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
            for role_host in role_hosts:
                if role['name'] not in ctrl_role:
                    continue
                host_detail = daisy_cmn.get_host_detail(
                    req, role_host['host_id'])
                has_interfaces = tecs_install.get_interfaces_network(
                    req, host_detail, cluster_networks)
                # mangement network must be configed
                host_mgnt_ip = has_interfaces['management']['ip']
                if host_detail['root_pwd']:
                    root_pwd = host_detail['root_pwd']
                else:
                    root_pwd = "ossdbg1"
                if role['name'] == 'CONTROLLER_HA':
                    role_nodes_info['ha'].append({'ip': host_mgnt_ip,
                                                  'root_pwd': root_pwd})
                if role['name'] == 'CONTROLLER_LB':
                    role_nodes_info['lb'].append({'ip': host_mgnt_ip,
                                                  'root_pwd': root_pwd})
                if role['name'] == 'COMPUTER':
                    role_nodes_info['computer'].append(
                        {'ip': host_mgnt_ip, 'root_pwd': root_pwd})

        if not role_nodes_info['ha']:
            msg = "No HA node got."
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)
        return role_nodes_info

    def _get_ntp_config_items(self, orig_ha_role,
                              new_ha_role, ha_node_ips):
        config_items = []
        if orig_ha_role['ntp_server'] \
                and orig_ha_role['ntp_server'] != orig_ha_role['vip']:
            old_ntp_server = orig_ha_role['ntp_server']
        else:
            old_ntp_server = 'ha-vip'
        if new_ha_role['ntp_server'] \
                and new_ha_role['ntp_server'] != new_ha_role['vip']:
            new_ntp_server = new_ha_role['ntp_server']
        else:
            new_ntp_server = 'ha-vip'

        if old_ntp_server != new_ntp_server:
            chrony_file = '/etc/chrony.conf'
            for ip in ha_node_ips:
                config_item = {'ip': ip,
                               'config_set': [{
                                   'key': 'server',
                                   'value': new_ntp_server,
                                   'old_value': old_ntp_server,
                                   'config_file': chrony_file,
                                   'action': 'set',
                                   'services': ['chronyd'],
                                   'force_type':'service',
                                   'file_format':'others',
                                   'separator':' '
                               }]}
                config_items.append(config_item)
        return config_items

    def _get_horizon_config_items(self, orig_ha_role,
                                  new_ha_role, ha_node_ips):
        config_items = []
        if (orig_ha_role['public_vip'] != new_ha_role['public_vip']):
            dashboard_file = "/etc/httpd/conf.d/15-horizon_vhost.conf"
            for ip in ha_node_ips:
                config_item = {'ip': ip,
                               'config_set': [{
                                   'key': 'ServerAlias',
                                   'value': new_ha_role['public_vip'],
                                   'old_value':orig_ha_role['public_vip'],
                                   'config_file':dashboard_file,
                                   'action':'set',
                                   'services':['httpd'],
                                   'force_type':'service',
                                   'file_format':'others',
                                   'separator':' '
                               }]}
                config_items.append(config_item)
        return config_items

    def _get_dns_config_items(self, orig_ha_role,
                              new_ha_role, ha_node_ips):
        config_items = []
        if (orig_ha_role['public_vip'] != new_ha_role['public_vip']):
            dns_file = "/etc/dnsmasq.conf"
            new_value = '/public-vip/%s' % new_ha_role['public_vip']
            old_value = '/public-vip/%s' % orig_ha_role['public_vip']
            for ip in ha_node_ips:
                config_item = {'ip': ip,
                               'config_set': [{
                                   'key': 'address',
                                   'value': old_value,
                                   'config_file': dns_file,
                                   'action': 'delete',
                                   'services': ['dnsmasq'],
                                   'force_type':'service',
                                   'file_format':'others',
                                   'separator':'='
                               },
                                   {'key': 'address',
                                    'value': new_value,
                                    'config_file': dns_file,
                                    'action': 'add',
                                    'services': ['dnsmasq'],
                                    'force_type':'service',
                                    'file_format':'others',
                                    'separator':'='
                                    }]}
                config_items.append(config_item)
        return config_items

    def _get_nova_config_items(self, orig_ha_role,
                               new_ha_role, computer_node_ips):
        config_items = []
        if (orig_ha_role['public_vip'] != new_ha_role['public_vip']):
            nova_file = "/etc/nova/nova.conf"
            new_value = 'http://%s:6080/vnc_auto.html' % new_ha_role[
                'public_vip']
            for ip in computer_node_ips:
                config_item = {'ip': ip,
                               'config_set': [{
                                   'key': 'novncproxy_base_url',
                                   'value': new_value,
                                   'config_file': nova_file,
                                   'action': 'set',
                                   'services': ['openstack-nova-compute'],
                                   'force_type': 'service',
                                   'section': 'DEFAULT',
                                   'file_format': 'SKV'}]}
                config_items.append(config_item)
        return config_items

    def _get_hosts_config_items(self, orig_ha_role,
                                new_ha_role, all_ips):
        config_items = []
        if (orig_ha_role['public_vip'] != new_ha_role['public_vip']):
            hosts_file = "/etc/hosts"
            new_key = new_ha_role['public_vip']
            old_key = orig_ha_role['public_vip']
            value = 'public-vip'
            for ip in all_ips:
                config_item = {'ip': ip,
                               'config_set': [{
                                   'key': old_key,
                                   'value': value,
                                   'config_file': hosts_file,
                                   'action': 'delete',
                                   'force_type': 'none',
                                   'file_format': 'others',
                                   'separator': ' '
                               },
                                   {'key': new_key,
                                    'value': value,
                                    'config_file': hosts_file,
                                    'action': 'add',
                                    'force_type': 'none',
                                    'file_format': 'others',
                                    'separator': ' '
                                    }]}
                config_items.append(config_item)
        return config_items

    # all config items should be dispatch after dispatching hosts network ip
    def _get_other_config_items(self, req, cluster_id,
                                update_config, hosts_network_ip):
        # if support update 'MANAGEMENT', return condition
        # here should be modified
        if not update_config.get('roles'):
            LOG.info(_("No roles update, "
                       "so no config items file generate"))
            return

        LOG.info(_("Get config items..."))

        orig_roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
        new_roles = self._get_new_roles(orig_roles,
                                        update_config.get('roles'))
        # orig_networks = daisy_cmn.get_cluster_networks_detail(req,
        # cluster_id)
        # new_networks = self._get_new_networks(
        # orig_networks, update_config.get('networks'))

        orig_ha_role = [role for role in orig_roles
                        if role['name'] == 'CONTROLLER_HA'][0]
        new_ha_role = [role for role in new_roles
                       if role['name'] == 'CONTROLLER_HA'][0]
        mgnt_ips = self._get_cluster_mgnt_ip(req, cluster_id,
                                             update_config,
                                             hosts_network_ip)

        config_items = []
        ntp_config_items = self._get_ntp_config_items(
            orig_ha_role, new_ha_role, mgnt_ips['ha'])
        config_items += ntp_config_items
        horizon_config_items = self._get_horizon_config_items(
            orig_ha_role, new_ha_role, mgnt_ips['ha'])
        config_items += horizon_config_items
        dns_config_items = self._get_dns_config_items(
            orig_ha_role, new_ha_role, mgnt_ips['ha'])
        config_items += dns_config_items

        all_ips = set(mgnt_ips['ha'] + mgnt_ips['lb'] +
                      mgnt_ips['computer'])
        hosts_config_items = self._get_hosts_config_items(
            orig_ha_role, new_ha_role, all_ips)
        config_items += hosts_config_items
        if config_items:
            self._write_json_file(cluster_id,
                                  CONFIG_ITEMS_FILE_NAME, config_items)
        nova_config_items = self._get_nova_config_items(
            orig_ha_role, new_ha_role, mgnt_ips['computer'])
        if nova_config_items:
            self._write_json_file(cluster_id,
                                  POST_CONFIG_ITEMS_FILE_NAME,
                                  nova_config_items)

    def _get_networks_detail(self, req, cluster_id, update_configs):
        LOG.info("Get network configs...")
        update_networks = []
        if 'networks' in update_configs:
            update_networks = update_configs['networks']

        orig_cluster_networks = daisy_cmn.get_cluster_networks_detail(
            req, cluster_id)

        new_networks = []
        for orig_network in orig_cluster_networks:
            new_network = copy.deepcopy(orig_network)
            for network in update_networks:
                if orig_network['id'] == network['id']:
                    new_network.update(network)

            new_networks.append(new_network)

        return new_networks

    def _get_roles_detail(self, req, cluster_id, update_configs):
        LOG.info("Get role configs...")
        update_roles = []
        if 'roles' in update_configs:
            update_roles = update_configs['roles']

        params = {'filters': {'cluster_id': cluster_id}}
        orig_cluster_roles = registry.get_roles_detail(req.context, **params)

        new_roles = []
        for orig_role in orig_cluster_roles:
            new_role = copy.deepcopy(orig_role)
            for role in update_roles:
                if orig_role['id'] == role['id']:
                    new_role.update(role)

            new_roles.append(new_role)

        return new_roles

    def _get_service_disks_detail(self, req, cluster_id, update_configs):
        LOG.info("Get service_disk configs...")
        update_service_disks = []
        if 'service_disks' in update_configs:
            update_service_disks = update_configs['service_disks']

        params = {'filters': {'cluster_id': cluster_id}}
        orig_cluster_roles = registry.get_roles_detail(req.context, **params)
        ha_role_id = [role['id'] for role in orig_cluster_roles
                      if role['name'] == 'CONTROLLER_HA'][0]
        params = {'filters': {'role_id': ha_role_id}}
        orig_service_disks = registry.list_service_disk_metadata(
            req.context, **params)
        new_service_disks = []
        for orig_service_disk in orig_service_disks:
            new_service_disk = copy.deepcopy(orig_service_disk)
            for service_disk in update_service_disks:
                if orig_service_disk['id'] == service_disk['id']:
                    new_service_disk.update(service_disk)

            new_service_disks.append(new_service_disk)

        return new_service_disks

    def _get_cinder_volumes_detail(self, req, cluster_id, update_configs):
        LOG.info("Get cinder_volume configs...")
        update_cinder_volumes = []
        if 'cinder_volumes' in update_configs:
            update_cinder_volumes = update_configs['cinder_volumes']

        params = {'filters': {'cluster_id': cluster_id}}
        orig_cluster_roles = registry.get_roles_detail(req.context, **params)
        ha_role_id = [role['id'] for role in orig_cluster_roles
                      if role['name'] == 'CONTROLLER_HA'][0]
        params = {'filters': {'role_id': ha_role_id}}
        orig_cinder_volumes = registry.list_cinder_volume_metadata(
            req.context, **params)
        new_cinder_volumes = []
        for orig_cinder_volume in orig_cinder_volumes:
            new_cinder_volume = copy.deepcopy(orig_cinder_volume)
            for cinder_volume in update_cinder_volumes:
                if orig_cinder_volume['id'] == cinder_volume['id']:
                    new_cinder_volume.update(cinder_volume)

            new_cinder_volumes.append(new_cinder_volume)

        return new_cinder_volumes

    def _get_hosts_detail(self, req, cluster_id):
        LOG.info("Get host configs...")

        hosts_network_ip = self._read_json_file(
            cluster_id, HOSTS_NETWORK_IP_FILE_NAME)

        params = {'filters': {'cluster_id': cluster_id}}
        orig_cluster_hosts = registry.get_hosts_detail(req.context, **params)

        new_hosts = []
        for orig_host in orig_cluster_hosts:
            orig_host_detail = daisy_cmn.get_host_detail(
                req, orig_host['id'])
            new_host = self._get_new_host_detail(
                orig_host_detail, hosts_network_ip)
            new_hosts.append(new_host)

        return new_hosts

    @utils.mutating
    def config_update_get(self, req, cluster_id, config_update_meta):
        self._enforce(req, 'config_update_get')
        self._raise_404_if_cluster_deleted(req, cluster_id)
        modules = config_update_meta.get('modules')
        if not modules:
            msg = "No modules given."
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)
        else:
            if not isinstance(modules, list):
                modules = ast.literal_eval(modules)
            for module in modules:
                if module not in SUPPORT_GET_PARAMS:
                    msg = "'%s' is not supported." % module
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg, request=req)

        orig_update_config = self._read_json_file(
            cluster_id, UPDATE_DATA_FILE_NAME)

        modules_detail = {}
        get_modules_detail_dict = \
            {'networks': self._get_networks_detail,
             'roles': self._get_roles_detail,
             'service_disks': self._get_service_disks_detail,
             'cinder_volumes': self._get_cinder_volumes_detail}

        for module in modules:
            if module == 'hosts':
                details = self._get_hosts_detail(req, cluster_id)
            else:
                details = get_modules_detail_dict[module](req,
                                                          cluster_id,
                                                          orig_update_config)
            modules_detail.update({module: details})

        return {'config_update_meta': modules_detail}

    def _stop_ha_cluster(self, req, ssh_hosts_info):
        stop_ha_cmds = ['systemctl disable pacemaker', 'pcs cluster stop']
        for host_info in ssh_hosts_info:
            LOG.info("stop HA on host %s" % host_info['ip'])
            api_cmn.remote_execute_script(host_info,
                                          commands=stop_ha_cmds)

    def _start_ha_cluster(self, req, cluster_id):
        role_nodes_info = self._get_role_nodes_info(req, cluster_id)
        ssh_hosts_info = role_nodes_info['ha']

        start_ha_cmds = ['systemctl enable pacemaker', 'pcs cluster start']
        for host_info in ssh_hosts_info:
            LOG.info("start HA on host %s" % host_info['ip'])
            api_cmn.remote_execute_script(host_info,
                                          commands=start_ha_cmds)

    def _get_local_ips(self):
        (status, output) = commands.getstatusoutput('ifconfig')
        netcard_pattern = re.compile('\S*: ')
        ip_str = '([0-9]{1,3}\.){3}[0-9]{1,3}'
        pattern = re.compile(ip_str)
        ips = []
        for netcard in re.finditer(netcard_pattern, str(output)):
            nic_name = netcard.group().split(': ')[0]
            if nic_name == "lo":
                continue
            ifconfig_nic_cmd = "ifconfig %s" % nic_name
            (status, output) = commands.getstatusoutput(ifconfig_nic_cmd)
            if status:
                continue
            ip = pattern.search(str(output))
            if ip and ip.group() != "127.0.0.1":
                ips.append(ip.group())
        return ips

    def _get_ip_for_network(self, ips, network):
        network_ips = []
        if network.get('ip_ranges'):
            for ip in ips:
                if utils.is_ip_in_ranges(ip, network['ip_ranges']):
                    network_ips.append(ip)
        if network_ips:
            return network_ips
        # if daisy is not in docker.
        for ip in ips:
            if utils.is_ip_in_cidr(ip, network['cidr']):
                network_ips.append(ip)
        return network_ips

    def _dispatch_config_items(self, req, cluster_id,
                               allow_dispatch_hosts,
                               update_roles,
                               config_file_name):
        config_items = self._read_json_file(
            cluster_id, config_file_name)
        if not config_items:
            LOG.info("No config items need to dispatch")
            return
        LOG.info("Dispatch config items")
        config_backend = push_mngr.configBackend("clushshell", req)
        for item in config_items:
            if item['ip'] in allow_dispatch_hosts:
                config_backend.push_origin_config_to_host(item)

        for role in update_roles:
            if 'ntp_server' in role:
                daisy_cmn.update_role(req, role['id'],
                                      {'ntp_server': role['ntp_server']})
                self._delete_from_failed_config(cluster_id,
                                                'roles',
                                                role['id'],
                                                ['ntp_server'])

    def _get_networks_dispatch_order(self, req,
                                     orig_cluster_networks):
        mgnt_network = [network for network in orig_cluster_networks
                        if network['name'] == 'MANAGEMENT']
        if not mgnt_network or not mgnt_network[0]:
            msg = "Can't find MANAGEMENT network"
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)
        mgnt_cidr = mgnt_network[0].get('cidr')
        if not mgnt_cidr:
            msg = "Can't get CIDR of MANAGEMENT network"
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)

        update_networks_order = []
        networks_with_mgnt_cidr = []
        exclusive_networks = ['DATAPLANE', 'EXTERNAL', 'MANAGEMENT']
        for network in orig_cluster_networks:
            if network['network_type'] in exclusive_networks:
                continue
            if network.get('cidr') and network['cidr'] == mgnt_cidr:
                networks_with_mgnt_cidr.append(network['name'])
                continue
            update_networks_order.append(network['name'])

        if networks_with_mgnt_cidr:
            update_networks_order += networks_with_mgnt_cidr
        update_networks_order.append('MANAGEMENT')
        return update_networks_order

    def _get_host_root_pwd(self, req, host_id):
        root_pwd = 'ossdbg1'
        host_detail = daisy_cmn.get_host_detail(req, host_id)
        if host_detail['root_pwd']:
            root_pwd = host_detail['root_pwd']
        return root_pwd

    def _write_host_network_to_db(self, req, host_id, cluster_id,
                                  network_name):
        hosts_network_ip = self._read_json_file(cluster_id,
                                                HOSTS_NETWORK_IP_FILE_NAME)
        for host_network in hosts_network_ip.get(network_name, []):
            if host_network['id'] == host_id:
                host_detail = daisy_cmn.get_host_detail(req, host_id)
                interfaces = []
                for interface in host_detail['interfaces']:
                    for assigned_network in interface.get(
                            'assigned_networks', []):
                        if assigned_network.get('name') == network_name:
                            assigned_network['ip'] = host_network['ip']
                            interfaces = host_detail['interfaces']
                if interfaces:
                    LOG.info("Write network '%s' of host '%s' to db"
                             % (network_name, host_network['name']))
                    host_meta = {'cluster': cluster_id,
                                 'interfaces': interfaces}
                    registry.update_host_metadata(req.context,
                                                  host_network['id'],
                                                  host_meta)
                else:
                    msg = "Can't find network %s from host %s"\
                        % (network_name, host_network['name'])
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg, request=req)

    def _dispatch_network_for_host(self, req, cluster_id, os_network,
                                   network_name, is_local_host=False):
        os_json_data = os_network['json']
        self._write_json_file(cluster_id,
                              OS_JSON_FILE_NAME,
                              os_json_data)

        host_id = os_json_data['host_id']
        host_pwd = self._get_host_root_pwd(req, host_id)
        ssh_host_info = {'ip': os_network['old_mgnt_ip'],
                         'root_pwd': host_pwd}
        os_json_file = CONFIG_FILE % {'cluster_id': cluster_id,
                                      'file_name': OS_JSON_FILE_NAME}
        remote_dir = REMOTE_DIR + '/networks'

        LOG.info("Dispatch network %s on host %s"
                 % (network_name, os_network['old_mgnt_ip']))
        scp_files = [{'file': os_json_file, 'remote_dir': remote_dir}]
        api_cmn.remote_execute_script(ssh_host_info,
                                      files=scp_files)
        remote_json_file = remote_dir + '/' + OS_JSON_FILE_NAME
        try:
            api_cmn.config_network(ssh_host_info, json_file=remote_json_file)
        except Exception:
            LOG.exception(_LE("Dispatch network. %s") % Exception)
        if is_local_host:
            time.sleep(20)
        self._write_host_network_to_db(req,
                                       host_id,
                                       cluster_id,
                                       network_name)

    def _write_network_to_db(self, req, cluster_id,
                             orig_update_network):
        LOG.info("Write network '%s' to db" % orig_update_network['name'])
        new_network_meta = {}
        for key in orig_update_network.keys():
            if key != 'id' and key in UPDATE_NETWORK_PARAMS:
                new_network_meta[key] = orig_update_network[key]
        registry.update_network_metadata(req.context,
                                         orig_update_network['id'],
                                         new_network_meta)
        self._delete_from_failed_config(cluster_id,
                                        'networks',
                                        orig_update_network['id'])

    def _is_network_4_host_dispatched(self,
                                      dispatched_host_networks,
                                      will_dispatch_network):
        for dispatched_network in dispatched_host_networks:
            dispatched_interface = dispatched_network['interfaces'][0]
            will_dispatch_interface = will_dispatch_network['interfaces'][0]
            if (dispatched_network['host_id'] ==
                    will_dispatch_network['host_id'] and
                    dispatched_interface['name'] ==
                    will_dispatch_interface['name'] and
                    dispatched_interface['assigned_networks'][0]['ip'] ==
                    will_dispatch_interface['assigned_networks'][0]['ip']):
                return True
        return False

    def _dispatch_networks_config(self, req, cluster_id,
                                  allow_dispatch_hosts, update_networks):
        if not update_networks:
            LOG.info("No networks config need to dispatch")
            return

        LOG.info("Dispatch networks config")

        networks_need_put_db = copy.deepcopy(update_networks)
        os_networks_config = self._read_json_file(
            cluster_id, ALL_OS_JSON_FILE_NAME)

        local_mgnt_ips = []
        if os_networks_config:
            orig_cluster_networks = \
                daisy_cmn.get_cluster_networks_detail(req, cluster_id)
            update_networks_order = \
                self._get_networks_dispatch_order(req,
                                                  orig_cluster_networks)
            local_ips = self._get_local_ips()
            mgnt_network = [network for network in orig_cluster_networks
                            if network['name'] == 'MANAGEMENT']
            local_mgnt_ips = \
                self._get_ip_for_network(local_ips, mgnt_network[0])
            if not local_mgnt_ips:
                msg = "Can't get local host ip"
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)

            has_dispatch_host_network = []
            for network_name in update_networks_order:
                local_host_network = None
                for os_network in os_networks_config.get(
                        network_name, []):
                    if (os_network['old_mgnt_ip'] not in
                            allow_dispatch_hosts):
                        continue
                    # network of local host should be dispatch
                    # for the last time
                    if os_network['old_mgnt_ip'] in local_mgnt_ips:
                        local_host_network = os_network
                        continue
                    if self._is_network_4_host_dispatched(
                        has_dispatch_host_network,
                            os_network['json']):
                        host_id = os_network['json']['host_id']
                        LOG.info("Network '%s' of host %s has dispatched "
                                 "by other network" % (network_name,
                                                       host_id))
                        self._write_host_network_to_db(req,
                                                       host_id,
                                                       cluster_id,
                                                       network_name)
                        continue
                    self._dispatch_network_for_host(req,
                                                    cluster_id,
                                                    os_network,
                                                    network_name)
                    has_dispatch_host_network.append(
                        os_network['json'])
                if local_host_network:
                    if self._is_network_4_host_dispatched(
                        has_dispatch_host_network,
                            local_host_network['json']):
                        host_id = local_host_network['json']['host_id']
                        LOG.info("Network '%s' of host %s has dispatched "
                                 "by other network"
                                 % (network_name, host_id))
                        self._write_host_network_to_db(req,
                                                       host_id,
                                                       cluster_id,
                                                       network_name)
                        continue
                    self._dispatch_network_for_host(req,
                                                    cluster_id,
                                                    local_host_network,
                                                    network_name,
                                                    is_local_host=True)
                    has_dispatch_host_network.append(
                        local_host_network['json'])
                time.sleep(20)
                # write network to table after
                # all hosts of this network has pushed.
                orig_update_network = \
                    [network for network in networks_need_put_db
                     if network['name'] == network_name]
                if orig_update_network:
                    self._write_network_to_db(req,
                                              cluster_id,
                                              orig_update_network[0])
                    networks_need_put_db.remove(orig_update_network[0])

        for network in networks_need_put_db:
            # private network dispatch at behind
            if network['network_type'] == 'DATAPLANE':
                continue
            self._write_network_to_db(req,
                                      cluster_id,
                                      network)

    def _pre_disk_array_config(self, req, ssh_hosts_info):
        cmds = ['iscsiadm -m node -U all',
                'rm -rf /var/lib/iscsi/nodes/*']
        for host_info in ssh_hosts_info:
            LOG.info("Preparing for disk array config on host %s"
                     % host_info['ip'])
            api_cmn.remote_execute_script(host_info, commands=cmds)

    def _dispatch_cinder_volume_config(self, req, cluster_id,
                                       update_cinder_volumes):
        cinder_json_file = CONFIG_FILE % {'cluster_id': cluster_id,
                                          'file_name': CINDER_JSON_FILE_NAME}
        if not os.path.exists(cinder_json_file):
            LOG.info("No cinder volume disk array config need to dispatch")
            return

        role_nodes_info = self._get_role_nodes_info(req, cluster_id)

        remote_dir = REMOTE_DIR + '/cinder_volume'
        rm_cmd = 'rm -rf %s/storage_auto_config/base/*.json' \
            % daisy_tecs_path
        daisy_cmn.subprocess_call(rm_cmd)
        cp_cmd = 'cp %s %s/storage_auto_config/base/' \
            % (cinder_json_file, daisy_tecs_path)
        daisy_cmn.subprocess_call(cp_cmd)
        ssh_hosts_info = role_nodes_info['ha']

        script_files = '%s/storage_auto_config' % daisy_tecs_path
        scp_files = [{'file': script_files, 'remote_dir': remote_dir}]
        script_name = 'storage_auto_config.py'
        cmd1 = 'cd %s/storage_auto_config/; chmod +x %s' \
            % (remote_dir, script_name)
        cmd2 = 'cd %s/storage_auto_config/; python %s cinder_conf' \
            % (remote_dir, script_name)
        for host_info in ssh_hosts_info:
            LOG.info("Dispatch cinder volume disk array config "
                     "on host %s" % host_info['ip'])
            api_cmn.remote_execute_script(host_info,
                                          files=scp_files,
                                          commands=[cmd1, cmd2])

        for cinder_volume in update_cinder_volumes:
            id = cinder_volume.pop('id')
            registry.update_cinder_volume_metadata(
                req.context, id, cinder_volume)
            self._delete_from_failed_config(cluster_id,
                                            'cinder_volumes',
                                            id)

    def _dispatch_service_disk_config(self, req,
                                      cluster_id,
                                      update_service_disks):
        ctrl1_config = self._read_json_file(
            cluster_id, CONTROL1_JSON_FILE_NAME)
        ctrl2_config = self._read_json_file(
            cluster_id, CONTROL2_JSON_FILE_NAME)

        if not ctrl1_config and not ctrl2_config:
            LOG.info("No share disks config need to dispatch")
            return
        if not ctrl1_config:
            msg = "No expected control_1.json generated, but "\
                "share disk config is updated"
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)
        if not ctrl2_config:
            msg = "No expected control_2.json generated, but "\
                "share disk config is updated"
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)

        remote_dir = REMOTE_DIR + '/share_disk'

        ctrl_json_file = CONFIG_FILE % {'cluster_id': cluster_id,
                                        'file_name': CONTROL_JSON_FILE_NAME}
        for ctrl_config in [ctrl1_config, ctrl2_config]:
            self._write_json_file(cluster_id,
                                  CONTROL_JSON_FILE_NAME,
                                  ctrl_config['json'])
            rm_cmd = 'rm -rf %s/storage_auto_config/base/*.json' \
                % daisy_tecs_path
            daisy_cmn.subprocess_call(rm_cmd)
            cp_cmd = 'cp %s %s/storage_auto_config/base/' \
                % (ctrl_json_file, daisy_tecs_path)
            daisy_cmn.subprocess_call(cp_cmd)

            host_pwd = self._get_host_root_pwd(req,
                                               ctrl_config['host_id'])
            ssh_host_info = {'ip': ctrl_config['new_mgnt_ip'],
                             'root_pwd': host_pwd}
            script_files = '%s/storage_auto_config' % daisy_tecs_path
            scp_files = [{'file': script_files, 'remote_dir': remote_dir}]

            script_name = 'storage_auto_config.py'
            cmd1 = 'cd %s/storage_auto_config/; chmod +x %s' \
                % (remote_dir, script_name)
            cmd2 = 'cd %s/storage_auto_config/; python %s share_disk %s' \
                % (remote_dir, script_name, ctrl_config['min_mac'])
            LOG.info("Dispatch share disks disk array config "
                     "on host %s" % ssh_host_info['ip'])
            api_cmn.remote_execute_script(ssh_host_info,
                                          files=scp_files,
                                          commands=[cmd1, cmd2])

        for service_disk in update_service_disks:
            id = service_disk.pop('id')
            registry.update_service_disk_metadata(
                req.context, id, service_disk)

            self._delete_from_failed_config(cluster_id,
                                            'service_disks',
                                            id)

    def _dispatch_ha_config(self, req, cluster_id, update_roles):
        ha_conf_file = CONFIG_FILE % {'cluster_id': cluster_id,
                                      'file_name': HA_CONF_FILE_NAME}
        if not os.path.exists(ha_conf_file):
            msg = "No HA_1.conf generated, so "\
                "don't need to dispatch HA"
            LOG.info(msg)
            return

        LOG.info("Dispatch ha cluster config")

        pre_ha_script_name = 'pre_ha_auto.sh'
        ha_script_name = 'ha_auto.sh'
        role_nodes_info = self._get_role_nodes_info(req, cluster_id)
        pre_ha_script = '%s/HA/%s' % (daisy_tecs_path, pre_ha_script_name)
        ha_script = '%s/HA/ha_auto.sh' % daisy_tecs_path
        ssh_host_info = {'ip': role_nodes_info['ha'][0]['ip'],
                         'root_pwd': role_nodes_info['ha'][0]['root_pwd']}
        remote_dir = REMOTE_DIR + '/HA'

        scp_files = [{'file': pre_ha_script, 'remote_dir': remote_dir},
                     {'file': ha_script, 'remote_dir': remote_dir},
                     {'file': ha_conf_file, 'remote_dir': remote_dir}]
        cmd1 = 'cd %s; chmod +x %s' % (remote_dir, pre_ha_script_name)
        cmd2 = 'cd %s; chmod +x %s' % (remote_dir, ha_script_name)
        cmd3 = 'cd %s; ./%s' % (remote_dir, pre_ha_script_name)
        cmd4 = 'cd %s; ./%s' % (remote_dir, ha_script_name)
        api_cmn.remote_execute_script(ssh_host_info,
                                      files=scp_files,
                                      commands=[cmd1, cmd2, cmd3, cmd4])

        # pulic_vip will be writed to db after configing keystone publicurl
        for role in update_roles:
            role_meta = {}
            for key in role.keys():
                if key in UPDATE_MGNT_VIP_PARAMS:
                    role_meta.update({key: role[key]})
            if role_meta:
                daisy_cmn.update_role(req, role['id'], role_meta)
            self._delete_from_failed_config(cluster_id,
                                            'roles',
                                            role['id'],
                                            UPDATE_MGNT_VIP_PARAMS)

    def _dispatch_keystone_publicurl_config(self, req,
                                            cluster_id):
        keystone_data = self._read_json_file(
            cluster_id, KEYSTONE_JSON_FILE_NAME)
        if not keystone_data:
            msg = "No data to dispatch for keystone public url"
            LOG.info(msg)
            return

        LOG.info("Dispatch keystone public url config")

        public_vip = keystone_data['public_vip']
        role_id = keystone_data['id']
        role_nodes_info = self._get_role_nodes_info(req, cluster_id)
        if role_nodes_info['lb']:
            host_ip = role_nodes_info['lb'][0]['ip']
            host_pwd = role_nodes_info['lb'][0]['root_pwd']
        else:
            host_ip = role_nodes_info['ha'][0]['ip']
            host_pwd = role_nodes_info['ha'][0]['root_pwd']
        script_name = 'update_endpoint_url.sh'
        script = '%s/%s' % (daisy_tecs_path, script_name)
        remote_dir = REMOTE_DIR + '/keyston_url'
        ssh_host_info = {'ip': host_ip, 'root_pwd': host_pwd}
        scp_files = [{'file': script, 'remote_dir': remote_dir}]
        remote_script = remote_dir + '/' + script_name
        cmd1 = 'chmod +x %s' % remote_script
        # the third param is region, default is RegionOne
        cmd2 = '%s %s public' % (remote_script, public_vip)

        api_cmn.remote_execute_script(ssh_host_info,
                                      files=scp_files,
                                      commands=[cmd1, cmd2])
        public_meta = {'public_vip': public_vip}
        daisy_cmn.update_role(req, role_id,
                              public_meta)
        # public_vip also must be updated to cluster
        # but when no public plane, here use management vip
        # so code here need to be modified
        registry.update_cluster_metadata(req.context,
                                         cluster_id,
                                         public_meta)

        self._delete_from_failed_config(cluster_id,
                                        'roles',
                                        role_id,
                                        ['public_vip'])

    def _dispatch_private_network_config(self, req,
                                         cluster_id, update_networks):
        orig_update_config = self._read_json_file(cluster_id,
                                                  UPDATE_DATA_FILE_NAME)
        private_networks_name = []
        for network in orig_update_config.get('networks', []):
            if network['network_type'] == 'DATAPLANE':
                private_networks_name.append(network['name'])
        if not private_networks_name:
            msg = "No data to dispatch for control nodes private network"
            LOG.info(msg)
            return

        os_networks_data = self._read_json_file(
            cluster_id, ALL_OS_JSON_FILE_NAME)
        for network_name in private_networks_name:
            # only vxlan maybe dispatch private config to compute host
            os_networks_info = \
                os_networks_data.get(network_name, [])
            for os_network_info in os_networks_info:
                LOG.info("Dispatch private networks for computer nodes")
                # private network config script
                # is same with non-private networks???
                self._dispatch_network_for_host(req,
                                                cluster_id,
                                                os_network_info,
                                                network_name)
            time.sleep(20)
        private_ctrl_data = self._read_json_file(
            cluster_id, PRIVATE_CTRL_JSON_FILE_NAME)
        if private_ctrl_data:
            LOG.info("Dispatch private networks for controller nodes")
            role_nodes_info = self._get_role_nodes_info(req, cluster_id)
            if role_nodes_info['lb']:
                need_dispatch_hosts = role_nodes_info['lb']
            else:
                need_dispatch_hosts = role_nodes_info['ha']

            private_ctrl_json_file = \
                CONFIG_FILE % {'cluster_id': cluster_id,
                               'file_name': PRIVATE_CTRL_JSON_FILE_NAME}

            remote_dir = REMOTE_DIR + '/private_network'
            remote_json_file = remote_dir + '/' + PRIVATE_CTRL_JSON_FILE_NAME
            scp_files = [{'file': private_ctrl_json_file,
                          'remote_dir': remote_dir}]
            for host_info in need_dispatch_hosts:
                ssh_host_info = {'ip': host_info['ip'],
                                 'root_pwd': host_info['root_pwd']}
                api_cmn.remote_execute_script(ssh_host_info,
                                              files=scp_files)
                api_cmn.execute_remote_network_script(
                    ssh_host_info, json_file=remote_json_file)

        for network_name in private_networks_name:
            orig_update_network = \
                [network for network in orig_update_config.get('networks', [])
                 if network['name'] == network_name]
            if not orig_update_network or not orig_update_network[0]:
                msg = "Can't get network % in orgin network" \
                    " update json file" % network_name
                LOG.error(msg)
            self._write_network_to_db(req,
                                      cluster_id,
                                      orig_update_network[0])

    def _backup_last_config(self, cluster_id):
        last_config_path = LAST_CONFIG_PATH % {'cluster_id': cluster_id}
        config_path = CONFIG_PATH % {'cluster_id': cluster_id}
        if os.path.exists(config_path):
            if os.path.exists(last_config_path):
                rm_old_config_cmd = "rm -rf %s/*" % last_config_path
                daisy_cmn.subprocess_call(rm_old_config_cmd)
            backup_last_config_cmd = "mv %s %s" % (
                config_path, last_config_path)
            daisy_cmn.subprocess_call(backup_last_config_cmd)

    def _copy_to_failed_config(self, cluster_id):
        failed_config_path = FAILED_CONFIG_PATH % {'cluster_id': cluster_id}
        if not os.path.exists(failed_config_path):
            mkdir_cmd = "mkdir -p " + failed_config_path
            daisy_cmn.subprocess_call(mkdir_cmd)

        failed_config_file = \
            FAILED_UPDATE_FILE % {'cluster_id': cluster_id}
        if os.path.exists(failed_config_file):
            rm_cmd = "rm -rf %s" % failed_config_file
            daisy_cmn.subprocess_call(rm_cmd)

        config_path = CONFIG_PATH % {'cluster_id': cluster_id}
        cp_cmd = "cp %s/%s %s/%s" % (config_path,
                                     UPDATE_DATA_FILE_NAME,
                                     failed_config_path,
                                     FAILED_UPDATE_FILE_NAME)
        daisy_cmn.subprocess_call(cp_cmd)

    def _read_from_failed_config(self, cluster_id):
        failed_config_file = \
            FAILED_UPDATE_FILE % {'cluster_id': cluster_id}
        if not os.path.exists(failed_config_file):
            return {}

        with open(failed_config_file, 'r') as fp:
            failed_update_config = json.load(fp)
            return failed_update_config

    def _delete_from_failed_config(self, cluster_id,
                                   module_name, id, key_list=[]):
        failed_update_config = \
            self._read_from_failed_config(cluster_id)

        if not failed_update_config.get(module_name):
            return

        reserved_module_data = []
        for meta in failed_update_config.get(module_name, []):
            if meta['id'] == id:
                if key_list:
                    for key in meta.keys():
                        if key != 'id' and key in key_list:
                            meta.pop(key)
                    if meta:
                        reserved_module_data.append(meta)
                else:
                    continue
            else:
                reserved_module_data.append(meta)
        failed_update_config.update({module_name: reserved_module_data})

        failed_config_file = \
            FAILED_UPDATE_FILE % {'cluster_id': cluster_id}
        with open(failed_config_file, "w+") as fp:
            fp.write(json.dumps(failed_update_config, indent=2))

    @utils.mutating
    def config_update_dispatch(self, req, cluster_id):
        orig_update_config = self._read_json_file(cluster_id,
                                                  UPDATE_DATA_FILE_NAME)
        dispatch_result = 'No config data can be dispatched'
        if not orig_update_config:
            msg = "No update config to dispatch."
            LOG.error(msg)
            return {'config_update_meta':
                    {'config_dispatch_result': dispatch_result}}

        self._copy_to_failed_config(cluster_id)

        orig_mgnt_ips = self._get_cluster_mgnt_ip(req, cluster_id)
        active_hosts_mgnt_ips = set(orig_mgnt_ips['ha'] +
                                    orig_mgnt_ips['lb'] +
                                    orig_mgnt_ips['computer'])
        # ping new_mgnt_ips for max 30s
        max_ping_times = 6
        unreachable_ips = daisy_cmn.check_ping_hosts(
            active_hosts_mgnt_ips, max_ping_times)
        if unreachable_ips:
            msg = "Ping test failed for ip '%s'"\
                % ','.join(unreachable_ips)
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)

        # dispatch config_items.json
        self._dispatch_config_items(req, cluster_id,
                                    active_hosts_mgnt_ips,
                                    orig_update_config.get('roles', []),
                                    CONFIG_ITEMS_FILE_NAME)

        # dispatch network and update db
        self._dispatch_networks_config(req, cluster_id,
                                       active_hosts_mgnt_ips,
                                       orig_update_config.get('networks', []))

        # when networks config dispatch to hosts completely, host new network
        # was updated into daisy db, so need to get new management ip.
        new_mgnt_ips = self._get_cluster_mgnt_ip(req, cluster_id)
        active_hosts_mgnt_ips = set(new_mgnt_ips['ha'] +
                                    new_mgnt_ips['lb'] +
                                    new_mgnt_ips['computer'])
        # ping new_mgnt_ips for max 30s
        max_ping_times = 6
        unreachable_ips = daisy_cmn.check_ping_hosts(
            active_hosts_mgnt_ips, max_ping_times)
        if unreachable_ips:
            msg = "Ping test failed for ip '%s'"\
                % ','.join(unreachable_ips)
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)

        # dispatch disk array config
        self._dispatch_cinder_volume_config(
            req, cluster_id, orig_update_config.get('cinder_volumes', []))

        self._dispatch_service_disk_config(
            req, cluster_id, orig_update_config.get('service_disks', []))

        # dispatch HA conf
        self._dispatch_ha_config(req, cluster_id,
                                 orig_update_config.get('roles', []))

        # some config must be start HA
        self._start_ha_cluster(req, cluster_id)

        # dispatch config_items.json
        self._dispatch_config_items(req, cluster_id,
                                    active_hosts_mgnt_ips,
                                    orig_update_config.get('roles', []),
                                    POST_CONFIG_ITEMS_FILE_NAME)
        # dispatch keystone url
        self._dispatch_keystone_publicurl_config(
            req, cluster_id)

        # dispatch private networks and update db
        self._dispatch_private_network_config(
            req, cluster_id, orig_update_config.get('networks', []))

        self._backup_last_config(cluster_id)

        failed_config_file = \
            FAILED_UPDATE_FILE % {'cluster_id': cluster_id}
        rm_config_cmd = "rm -rf %s" % failed_config_file
        daisy_cmn.subprocess_call(rm_config_cmd)

        dispatch_result = 'Config data dispatched successfully'
        LOG.info("===============================")
        LOG.info(dispatch_result)
        LOG.info("===============================")
        return {'config_update_meta':
                {'config_dispatch_result': dispatch_result}}


class ConfigUpdateDeserializer(wsgi.JSONRequestDeserializer):

    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["config_update_meta"] = utils.get_dict_meta(request)
        return result

    def config_update_gen(self, request):
        return self._deserialize(request)

    def config_update_get(self, request):
        return self._deserialize(request)

    def config_update_dispatch(self, request):
        return {}


class ConfigUpdateSerializer(wsgi.JSONResponseSerializer):

    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def config_update_gen(self, response, result):
        config_update_meta = result['config_update_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config_update=config_update_meta))
        return response

    def config_update_get(self, response, result):
        config_update_meta = result['config_update_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config_update=config_update_meta))
        return response

    def config_update_dispatch(self, response, result):
        config_update_meta = result['config_update_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config_update=config_update_meta))
        return response


def create_resource():
    """Hosts resource factory method"""
    deserializer = ConfigUpdateDeserializer()
    serializer = ConfigUpdateSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
