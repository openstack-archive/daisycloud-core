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
/install endpoint for zenic API
"""
import copy
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from daisy import i18n
from daisy.common import exception
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

daisy_kolla_path = '/var/lib/daisy/kolla/'
KOLLA_STATE = {
    'INIT': 'init',
    'INSTALLING': 'installing',
    'ACTIVE': 'active',
    'INSTALL_FAILED': 'install-failed',
    'UNINSTALLING': 'uninstalling',
    'UNINSTALL_FAILED': 'uninstall-failed',
    'UPDATING': 'updating',
    'UPDATE_FAILED': 'update-failed',
}


def get_cluster_hosts(req, cluster_id):
    try:
        cluster_hosts = registry.get_cluster_hosts(req.context, cluster_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return cluster_hosts


def get_host_detail(req, host_id):
    try:
        host_detail = registry.get_host_metadata(req.context, host_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return host_detail


def get_roles_detail(req):
    try:
        roles = registry.get_roles_detail(req.context)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return roles


def get_hosts_of_role(req, role_id):
    try:
        hosts = registry.get_role_host_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return hosts


def get_role_detail(req, role_id):
    try:
        role = registry.get_role_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return role

def update_role(req, role_id,role_meta):
    try:
        registry.update_role_metadata(req.context, role_id, role_meta)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


def update_role_host(req, role_id, role_host):
    try:
        registry.update_role_host_metadata(req.context, role_id, role_host)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


def delete_role_hosts(req, role_id):
    try:
        registry.delete_role_host_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


def _get_cluster_network(cluster_networks, network_type):
    network = [cn for cn in cluster_networks
                        if  cn['name'] in network_type]
    if not network or not network[0]:
        msg = "network %s is not exist" % (network_type)
        raise exception.InvalidNetworkConfig(msg)
    else:
        return network[0]


def get_host_interface_by_network(host_detail, network_type):
    host_detail_info = copy.deepcopy(host_detail)
    interface_list = [hi for hi in host_detail_info['interfaces']
                        for assigned_network in hi['assigned_networks']
                        if assigned_network and network_type == assigned_network['name']]
    interface = {}
    if interface_list:
        interface = interface_list[0]
    if not interface:
        msg = "network %s of host %s is not exist" % (network_type, host_detail_info['id'])
        raise exception.InvalidNetworkConfig(msg)
    return interface


def get_host_network_ip(req, host_detail, cluster_networks, network_type):
    interface_network_ip = ''
    host_interface = get_host_interface_by_network(host_detail, network_type)
    if host_interface:
        network = _get_cluster_network(cluster_networks, network_type)
        assigned_network = daisy_cmn.get_assigned_network(req,
                                                host_interface['id'],
                                                network['id'])
        interface_network_ip = assigned_network['ip']

    if not interface_network_ip:
        msg = "%s network ip of host %s can't be empty" % (network_type, host_detail['id'])
        raise exception.InvalidNetworkConfig(msg)
    return interface_network_ip


def get_deploy_node_cfg(req, host_detail, cluster_networks):
    #host_mgt_ip = get_host_network_ip(req, host_detail, cluster_networks, 'MANAGEMENT')
    host_mgt_network = get_host_interface_by_network(host_detail, 'MANAGEMENT')
    host_mgt_macname = host_mgt_network['name']
    host_mgt_ip =host_mgt_network['ip']
    host_pub_network = get_host_interface_by_network(host_detail, 'PUBLICAPI')
    host_pub_macname = host_pub_network['name']
    if not host_mgt_ip:
        msg = "management ip of host %s can't be empty" % host_detail['id']
        raise exception.InvalidNetworkConfig(msg)
    deploy_node_cfg = {}
    deploy_node_cfg.update({'mgtip':host_mgt_ip})
    deploy_node_cfg.update({'mgt_macname':host_mgt_macname})
    deploy_node_cfg.update({'pub_macname':host_pub_macname})
    return deploy_node_cfg


def get_roles_and_hosts_list(req, cluster_id):
    roles_id_list = set()
    hosts_id_list = set()
    hosts_list = []
    cluster_networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    roles = daisy_cmn.get_cluster_roles_detail(req,cluster_id)
    for role in roles:
        if role['deployment_backend'] != daisy_cmn.kolla_backend_name:
            continue
        role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
        if role_hosts:
            for role_host in role_hosts:
                if role_host['host_id'] not in hosts_id_list:
                    host = daisy_cmn.get_host_detail(req, role_host['host_id'])
                    host_ip = get_host_network_ip(req, host, cluster_networks, 'MANAGEMENT')
                    hosts_id_list.add(host['id'])
                    host_cfg = {}
                    host_cfg['mgtip'] = host_ip
                    host_cfg['rootpwd'] = host['root_pwd']
                    hosts_list.append(host_cfg)
            roles_id_list.add(role['id'])
    return (roles_id_list, hosts_list)

