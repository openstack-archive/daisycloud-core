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
import subprocess
import re
import os
from oslo_log import log as logging
from oslo_utils import importutils
from webob.exc import HTTPBadRequest
from webob.exc import HTTPConflict
from webob.exc import HTTPForbidden
from webob.exc import HTTPNotFound
from webob import Response
from daisy.api import policy
import daisy.api.v1
from daisy.api.v1 import controller
from daisy.api.v1 import filters
from daisy.common import exception
from daisy.common import utils
from daisy.common import wsgi
from daisy.common import vcpu_pin
from daisy import i18n
from daisy import notifier
import daisy.registry.client.v1.api as registry
import threading
import daisy.api.backends.common as daisy_cmn
from daisy.api.backends import driver
from daisy.api.backends.osinstall import osdriver
import ConfigParser

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE


DISCOVER_DEFAULTS = {
    'listen_port': '5050',
}

ML2_TYPE = [
    'ovs',
    'dvs',
    'ovs,sriov(macvtap)',
    'ovs,sriov(direct)',
    'sriov(macvtap)',
    'sriov(direct)',
    'dvs,sriov(direct)']
NEED_VF_TYPE = ['dvs,sriov(direct)']
SUPPORT_HOST_PAGE_SIZE = ['2M', '1G']
config = ConfigParser.ConfigParser()
config.read(daisy_cmn.daisy_conf_file)
try:
    OS_INSTALL_TYPE = config.get("OS", "os_install_type")
except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
    OS_INSTALL_TYPE = 'pxe'

_OS_HANDLE = None


def get_os_handle():
    global _OS_HANDLE
    if _OS_HANDLE is not None:
        return _OS_HANDLE

    _OS_HANDLE = osdriver.load_install_os_driver(OS_INSTALL_TYPE)
    return _OS_HANDLE


def get_backend():
    config = ConfigParser.ConfigParser()
    config.read(daisy_cmn.daisy_conf_file)
    backend = config.get("BACKEND", "default_backend_types")
    backends = []
    backends.append(backend)
    return backends


class Controller(controller.BaseController):
    """
    WSGI controller for hosts resource in Daisy v1 API

    The hosts resource API is a RESTful web service for host data. The API
    is as follows::

        GET  /nodes -- Returns a set of brief metadata about hosts
        GET  /nodes -- Returns a set of detailed metadata about
                              hosts
        HEAD /nodes/<ID> -- Return metadata about an host with id <ID>
        GET  /nodes/<ID> -- Return host data for host with id <ID>
        POST /nodes -- Store host data and return metadata about the
                        newly-stored host
        PUT  /nodes/<ID> -- Update host metadata and/or upload host
                            data for a previously-reserved host
        DELETE /nodes/<ID> -- Delete the host with id <ID>
    """
    support_resource_type = ['baremetal', 'server', 'docker']
    support_discover_mode = ['PXE', 'SSH']

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

    def _raise_404_if_network_deleted(self, req, network_id):
        network = self.get_network_meta_or_404(req, network_id)
        if network is None or network['deleted']:
            msg = _("Network with identifier %s has been deleted.") % \
                network_id
            LOG.error(msg)
            raise HTTPNotFound(msg)

    def _raise_404_if_cluster_deleted(self, req, cluster_id):
        cluster = self.get_cluster_meta_or_404(req, cluster_id)
        if cluster is None or cluster['deleted']:
            msg = _("Cluster with identifier %s has been deleted.") % \
                cluster_id
            LOG.error(msg)
            raise HTTPNotFound(msg)

    def _raise_404_if_role_deleted(self, req, role_id):
        role = self.get_role_meta_or_404(req, role_id)
        if role is None or role['deleted']:
            msg = _("Cluster with identifier %s has been deleted.") % role_id
            LOG.error(msg)
            raise HTTPNotFound(msg)

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

    def check_bond_slaves_validity(
            self,
            bond_slaves_lists,
            ether_nic_names_list):
        '''
        members in bond slaves must be in ether_nic_names_list
        len(set(bond_slaves)) == 2, and can not be overlap
        between slaves members
        bond_slaves_lists: [[name1,name2], [name1,name2], ...]
        ether_nic_names_list: [name1, name2, ...]
        '''
        for bond_slaves in bond_slaves_lists:
            LOG.warning('bond_slaves: %s' % bond_slaves)
            if len(set(bond_slaves)) != 2:
                LOG.error('set(bond_slaves: %s' % set(bond_slaves))
                msg = (
                    _(
                        "Bond slaves(%s) must be different nic and existed "
                        "in ether nics in pairs." %
                        bond_slaves))
                LOG.error(msg)
                raise HTTPForbidden(msg)
            if not set(bond_slaves).issubset(set(ether_nic_names_list)):
                msg = (
                    _("Pay attention: illegal ether nic existed "
                      "in bond slaves(%s)." % bond_slaves))
                LOG.error(msg)
                raise HTTPForbidden(msg)

    def validate_ip_format(self, ip_str):
        '''
        valid ip_str format = '10.43.178.9'
        invalid ip_str format : '123. 233.42.12', spaces existed in field
                                '3234.23.453.353', out of range
                                '-2.23.24.234', negative number in field
                                '1.2.3.4d', letter in field
                                '10.43.1789', invalid format
        '''
        valid_fromat = False
        if ip_str.count('.') == 3 and all(num.isdigit() and 0 <= int(
                num) < 256 for num in ip_str.rstrip().split('.')):
            valid_fromat = True
        if not valid_fromat:
            msg = (_("%s invalid ip format!") % ip_str)
            LOG.error(msg)
            raise HTTPForbidden(msg)

    def validate_mac_format(self, mac_str):
        '''Validates a mac address'''
        if re.match("[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$",
                    mac_str.lower()):
            return
        else:
            msg = (_("%s invalid mac format!") % mac_str)
            LOG.error(msg)
            raise HTTPForbidden(msg)

    def get_cluster_networks_info(self, req, cluster_id=None, type=None):
        '''
        get_cluster_networks_info by cluster id
        '''

        if not type and not cluster_id:
            msg = "error, the type and cluster_id "\
                  "can not be empty at the same time"
            LOG.error(msg)
            raise HTTPForbidden(msg)
        params = {}
        if type and cluster_id:
            params['filters'] = {'type': type, 'cluster_id': cluster_id}
        elif type:
            params['filters'] = {'type': type}
        elif cluster_id:
            params['filters'] = {'cluster_id': cluster_id}

        all_networks = registry.get_all_networks(req.context, **params)

        return all_networks

    def _check_asged_net(self, req, cluster_id, assigned_networks,
                         bond_type=None):
        LOG.info("assigned_networks %s " % assigned_networks)
        cluster_networks = self.get_cluster_networks_info(req, cluster_id)
        list_of_assigned_networks = []
        for assigned_network in assigned_networks:
            LOG.info("assigned_network %s " % assigned_network)
            if 'name' not in assigned_network or not assigned_network['name']:
                msg = "assigned networks '%s' are invalid" % (
                    assigned_networks)
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")
            network_info = [network for network in cluster_networks if network[
                'name'] == assigned_network['name']]
            if network_info and network_info[0]:
                network_cidr = network_info[0]['cidr']
                LOG.info("network_info %s " % network_info)
                if network_info[0]['network_type'] != 'DATAPLANE':
                    if network_cidr:
                        if 'ip' in assigned_network and assigned_network['ip']:
                            self.validate_ip_format(assigned_network['ip'])
                            ip_in_cidr = utils.is_ip_in_cidr(
                                assigned_network['ip'], network_cidr)
                            if not ip_in_cidr:
                                msg = (_("The ip '%s' for network '%s'"
                                         " is not in cidr range." %
                                         (assigned_network['ip'],
                                          assigned_network['name'])))
                                LOG.error(msg)
                                raise HTTPBadRequest(explanation=msg)
                    else:
                        msg = "error, cidr of network '%s' is empty" % (
                            assigned_network['name'])
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg,
                                             request=req,
                                             content_type="text/plain")
                else:
                    if bond_type:
                        cluster_roles = daisy_cmn. \
                            get_cluster_roles_detail(req, cluster_id)
                        cluster_backends = set([role['deployment_backend']
                                                for role in cluster_roles if
                                                daisy_cmn.get_hosts_of_role(
                                                    req, role['id'])])
                        for backend in cluster_backends:
                            try:
                                backend_common = importutils.import_module(
                                    'daisy.api.backends.%s.common' % backend)
                            except Exception:
                                pass
                            else:
                                if hasattr(backend_common,
                                           'check_dataplane_bond_type'):
                                    backend_common.check_dataplane_bond_type(
                                        req, bond_type)
            else:
                msg = "can't find network named '%s' in cluster '%s'" % (
                    assigned_network['name'], cluster_id)
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")
            list_of_assigned_networks.append(network_info[0])
        return list_of_assigned_networks

    def _compare_assigned_networks_of_interface(self, interface1, interface2):
        for network in interface1:
            if network.get('segmentation_type') in ['vlan']:
                continue
            for network_compare in interface2:
                if network_compare.get('segmentation_type') in ['vlan']:
                    continue
                if network.get('cidr', None) \
                        and network_compare.get('cidr', None) \
                        and network['cidr'] == network_compare['cidr']:
                    return network['name'], network_compare['name']
        return False, False

    def _compare_assigned_networks_between_interfaces(
            self, interface_num, assigned_networks_of_interfaces):
        for interface_id in range(interface_num):
            for interface_id_compare in range(interface_id + 1, interface_num):
                network1_name, network2_name = self.\
                    _compare_assigned_networks_of_interface(
                        assigned_networks_of_interfaces[interface_id],
                        assigned_networks_of_interfaces[interface_id_compare])
                if network1_name and network2_name:
                    msg = (_('Network %s and network %s with same '
                             'cidr can not be assigned to different '
                             'interfaces.')) % (network1_name, network2_name)
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg)

    def _check_add_host_interfaces(self, req, host_meta):
        host_meta_interfaces = []
        if host_meta.get('interfaces') and host_meta['interfaces']:
            host_meta_interfaces = list(host_meta['interfaces'])
        else:
            msg = "No Interface in host, host_meta is: %s" % host_meta
            LOG.error(msg)
            raise HTTPBadRequest(msg)

        cluster_id = host_meta.get('cluster', None)

        exist_id, os_status = self._verify_interface_among_hosts(
            req, host_meta)
        if exist_id:
            if os_status == "active":
                msg = _(
                    'The host %s os_status is active,'
                    'forbidden daisy-discoverd to add host.') % exist_id
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg)
            host_meta['id'] = exist_id
            self.update_host(req, exist_id, host_meta)
            LOG.info(
                "<<<FUN:verify_interface, host:%s is already update.>>>" %
                exist_id)
            return {'host_meta': host_meta}

        ether_nic_names_list = list()
        bond_nic_names_list = list()
        bond_slaves_lists = list()
        have_assigned_network = False
        have_ip_netmask = False
        assigned_networks_of_intefaces = []
        interface_num = 0
        for interface in host_meta_interfaces:
            assigned_networks_of_one_interface = []
            if interface.get(
                    'type',
                    None) != 'bond' and not interface.get(
                    'mac',
                    None):
                msg = _('The ether interface need a non-null mac ')
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")
            if interface.get(
                    'type',
                    None) == 'ether' and not interface.get(
                    'pci',
                    None):
                msg = "The Interface need a non-null pci"
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")

            if interface.get('name', None):
                if 'type' in interface and interface['type'] == 'bond':
                    bond_nic_names_list.append(interface['name'])
                    if interface.get('slaves', None):
                        bond_slaves_lists.append(interface['slaves'])
                    else:
                        msg = (
                            _("Slaves parameter can not be None "
                              "when nic type was bond."))
                        LOG.error(msg)
                        raise HTTPForbidden(msg)
                else:  # type == ether or interface without type field
                    ether_nic_names_list.append(interface['name'])
            else:
                msg = (_("Nic name can not be None."))
                LOG.error(msg)
                raise HTTPForbidden(msg)

            if 'is_deployment' in interface:
                if interface['is_deployment'] == "True" or interface[
                        'is_deployment']:
                    interface['is_deployment'] = 1
                else:
                    interface['is_deployment'] = 0

            if ('assigned_networks' in interface and
                    interface['assigned_networks'] != [''] and
                    interface['assigned_networks']):
                have_assigned_network = True
                if cluster_id:
                    if interface.get('type', None) == "bond":
                        bond_type = interface.get("bond_type", None)
                        if bond_type:
                            assigned_networks_of_one_interface = self. \
                                _check_asged_net(req,
                                                 cluster_id,
                                                 interface[
                                                     'assigned_networks'],
                                                 bond_type)
                        else:
                            msg = "bond type must be given when interface " \
                                  "type is bond"
                            LOG.error(msg)
                            raise HTTPBadRequest(explanation=msg,
                                                 request=req,
                                                 content_type="text/plain")
                    else:
                        assigned_networks_of_one_interface = self. \
                            _check_asged_net(req,
                                             cluster_id,
                                             interface[
                                                 'assigned_networks'])
                else:
                    msg = "cluster must be given first when network " \
                          "plane is allocated"
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg,
                                         request=req,
                                         content_type="text/plain")

            if ('ip' in interface and interface['ip'] and
                    'netmask' in interface and interface['netmask']):
                have_ip_netmask = True

            if 'mac' in interface and 'ip' in interface:
                host_infos = registry.get_host_interface(
                    req.context, host_meta)
                for host_info in host_infos:
                    if 'host_id' in host_info:
                        host_meta["id"] = host_info['host_id']

            if 'vswitch_type' in interface and interface[
                    'vswitch_type'] != '' and \
                    interface['vswitch_type'] not in \
                    ML2_TYPE:
                msg = "vswitch_type %s is not supported" % interface[
                    'vswitch_type']
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req,
                                     content_type="text/plain")
            interface_num += 1
            assigned_networks_of_intefaces.\
                append(assigned_networks_of_one_interface)

        for interface_id in range(interface_num):
            for interface_id_compare in range(interface_id + 1, interface_num):
                network1_name, network2_name = self.\
                    _compare_assigned_networks_of_interface(
                        assigned_networks_of_intefaces[interface_id],
                        assigned_networks_of_intefaces[interface_id_compare])
                if network1_name and network2_name:
                    msg = (_('Network %s and network %s with same '
                             'cidr can not be assigned to different '
                             'interfaces.')) % (network1_name, network2_name)
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg)

        # when assigned_network is empty, ip must be config
        if not have_assigned_network:
            if not have_ip_netmask:
                msg = "ip and netmask must be given when network " \
                      "plane is not allocated"
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")

        # check bond slaves validity
        self.check_bond_slaves_validity(
            bond_slaves_lists, ether_nic_names_list)
        nic_name_list = ether_nic_names_list + bond_nic_names_list
        if len(set(nic_name_list)) != len(nic_name_list):
            msg = (_("Nic name must be unique."))
            LOG.error(msg)
            raise HTTPForbidden(msg)

    def _check_dvs_huge(self, host_meta, orig_host_meta={}):
        host_interfaces = (host_meta.get('interfaces') or
                           orig_host_meta.get('interfaces'))
        if host_interfaces:
            has_dvs = utils.get_dvs_interfaces(host_interfaces)
            if has_dvs:
                if (('hugepages' in host_meta and
                     int(host_meta['hugepages']) < 10) or
                    ('hugepagesize' in host_meta and
                     host_meta['hugepagesize'] != '1G')):
                    host_name = (host_meta.get('name') or
                                 orig_host_meta.get('name'))
                    msg = _("hugepages should be larger than 10G "
                            " when dvs installed on host %s") % host_name
                    LOG.error(msg)
                    raise HTTPForbidden(explanation=msg)

    @utils.mutating
    def add_host(self, req, host_meta):
        """
        Adds a new host to Daisy

        :param req: The WSGI/Webob Request object
        :param host_meta: Mapping of metadata about host

        :raises HTTPBadRequest if x-host-name is missing
        """
        self._enforce(req, 'add_host')
        # if host is update in '_verify_interface_among_hosts', no need add
        # host continue.
        cluster_id = host_meta.get('cluster', None)
        if cluster_id:
            self.get_cluster_meta_or_404(req, cluster_id)

        if 'role' in host_meta and host_meta['role']:
            role_id_list = []
            host_roles = []
            if 'cluster' in host_meta:
                params = self._get_query_params(req)
                role_list = registry.get_roles_detail(req.context, **params)
                for role_name in role_list:
                    if role_name['cluster_id'] == host_meta['cluster']:
                        host_roles = list(host_meta['role'])
                        for host_role in host_roles:
                            if role_name['name'] == host_role:
                                role_id_list.append(role_name['id'])
                                continue
                if len(role_id_list) != len(host_roles):
                    msg = "The role of params %s is not exist, " \
                          "please use the right name" % host_roles
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg,
                                         request=req,
                                         content_type="text/plain")
                host_meta['role'] = role_id_list
            else:
                msg = "cluster params is none"
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")
        # if host is found from ssh, don't set pxe interface
        if host_meta.get('os_status', None) == 'init':
            self._set_pxe_interface_for_host(req, host_meta)

        result = self._check_add_host_interfaces(req, host_meta)
        if result:
            return result

        if 'resource_type' in host_meta:
            if host_meta['resource_type'] not in self.support_resource_type:
                msg = "resource type is not supported, please use it in %s" % \
                      self.support_resource_type
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")
        else:
            host_meta['resource_type'] = 'baremetal'

        if 'os_status' in host_meta:
            if host_meta['os_status'] not in ['init', 'installing',
                                              'active', 'failed', 'none']:
                msg = "os_status is not valid."
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")

        self._check_dvs_huge(host_meta)

        if host_meta.get('config_set_id'):
            self.get_config_set_meta_or_404(req,
                                            host_meta['config_set_id'])
        if host_meta.get("discover_mode") and \
                (host_meta["discover_mode"] not in self.support_discover_mode):
            msg = "discover mode is not supported, please use it in %s" % \
                  self.support_discover_mode
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

        host_meta = registry.add_host_metadata(req.context, host_meta)

        return {'host_meta': host_meta}

    @utils.mutating
    def delete_host(self, req, id):
        """
        Deletes a host from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about host

        :raises HTTPBadRequest if x-host-name is missing
        """
        self._enforce(req, 'delete_host')
        try:
            orig_host_meta = self.get_host_meta_or_404(req, id)
            if orig_host_meta.get('interfaces', None):
                macs = [interface['mac'] for interface
                        in orig_host_meta['interfaces'] if interface['mac']]
                for mac in macs:
                    delete_host_discovery_info = 'pxe_os_install_clean ' + mac
                    subprocess.call(delete_host_discovery_info,
                                    shell=True,
                                    stdout=open('/dev/null', 'w'),
                                    stderr=subprocess.STDOUT)
            registry.delete_host_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find host to delete: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete host: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("Host %(id)s could not be deleted because it is in use: "
                     "%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.error(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            return Response(body='', status=200)

    def _host_additional_info(self, req, host_meta):
        path = os.path.join(os.path.abspath(os.path.dirname(
            os.path.realpath(__file__))), 'ext')
        for root, dirs, names in os.walk(path):
            filename = 'router.py'
            if filename in names:
                ext_name = root.split(path)[1].strip('/')
                ext_func = "%s.api.hosts" % ext_name
                extension = importutils.import_module(
                    'daisy.api.v1.ext.%s' % ext_func)
                if 'complement_host_extra_info' in dir(extension):
                    extension.complement_host_extra_info(req, host_meta)

        os_handle = get_os_handle()
        os_handle.check_discover_state(req,
                                       host_meta,
                                       is_detail=True)
        host_vcpu_pin = vcpu_pin.allocate_cpus(host_meta)
        host_meta.update(host_vcpu_pin)
        if 'role' in host_meta and 'CONTROLLER_HA' in host_meta['role']:
            host_cluster_name = host_meta['cluster']
            params = {'filters': {u'name': host_cluster_name}}
            cluster_info = registry.get_clusters_detail(req.context, **params)
            cluster_id = cluster_info[0]['id']

            ctl_ha_nodes_min_mac =\
                daisy_cmn.get_ctl_ha_nodes_min_mac(req, cluster_id)
            sorted_ha_nodes = \
                sorted(ctl_ha_nodes_min_mac.iteritems(), key=lambda d: d[1])
            sorted_ha_nodes_min_mac = \
                [min_mac[1] for min_mac in sorted_ha_nodes]

            host_min_mac = utils.get_host_min_mac(host_meta['interfaces'])
            host_iqn = daisy_cmn.calc_host_iqn(host_min_mac)
            host_meta['iqn'] = host_iqn

            cluster_roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
            role_id = ''
            for role in cluster_roles:
                if role['name'] == 'CONTROLLER_HA':
                    role_id = role['id']
                    break
            service_disks = \
                daisy_cmn.get_service_disk_list(req,
                                                {'filters': {
                                                    'role_id': role_id}})
            db_share_cluster_disk = []
            service_lun_info = []
            for disk in service_disks:
                if disk['service'] == 'db' and \
                        disk['disk_location'] == 'share_cluster':
                    db_share_cluster_disk.append(disk)
                if disk['disk_location'] == 'share':
                    tmp_disk = {}
                    tmp_disk[disk['service']] = disk['lun']
                    service_lun_info.append(tmp_disk)

            sorted_db_share_cluster = \
                sorted(db_share_cluster_disk, key=lambda s: s['lun'])

            db_service_lun_info = {}
            for (min_mac, share_disk) in \
                    zip(sorted_ha_nodes_min_mac, sorted_db_share_cluster):
                if host_min_mac == min_mac:
                    db_service_lun_info['db'] = share_disk['lun']
                    break
            if db_service_lun_info:
                service_lun_info.append(db_service_lun_info)
            if service_lun_info:
                host_meta['lun'] = service_lun_info

        return {'host_meta': host_meta}

    @utils.mutating
    def get_host(self, req, id):
        """
        Returns metadata about an host in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque host identifier

        :raises HTTPNotFound if host metadata is not available to user
        """
        self._enforce(req, 'get_host')
        host_meta = self.get_host_meta_or_404(req, id)
        self._host_additional_info(req, host_meta)

        return {'host_meta': host_meta}

    def detail(self, req):
        """
        Returns detailed information for all available nodes

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'nodes': [
                {'id': <ID>,
                 'name': <NAME>,
                 'description': <DESCRIPTION>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._enforce(req, 'get_hosts')
        params = self._get_query_params(req)
        os_handle = get_os_handle()
        try:
            nodes = registry.get_hosts_detail(req.context, **params)
            for node in nodes:
                self._host_additional_info(req, node)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(nodes=nodes)

    def _compute_hugepage_memory(self, hugepages, memory, hugepagesize='1G'):
        hugepage_memory = 0
        if hugepagesize == '2M':
            hugepage_memory = 2 * 1024 * int(hugepages)
        if hugepagesize == '1G':
            hugepage_memory = 1 * 1024 * 1024 * int(hugepages)
        if hugepage_memory > memory:
            msg = "The memory hugepages used is bigger " \
                  "than total memory."
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg)

    def _count_host_pxe_info(self, interfaces):
        input_host_pxe_info = [
            interface for interface in interfaces if interface.get(
                'is_deployment',
                None) == "True" or interface.get(
                'is_deployment',
                None) == "true" or interface.get(
                'is_deployment',
                None) == 1]
        return input_host_pxe_info

    def _update_networks_phyname(self, req, interface, cluster_id):
        phyname_networks = {}
        cluster_networks = registry.get_networks_detail(
            req.context, cluster_id)
        for assigned_network in list(interface['assigned_networks']):
            network_info_list = [network for network in cluster_networks
                                 if assigned_network['name'] ==
                                 network['name']]
            if network_info_list and network_info_list[0]:
                network_info = network_info_list[0]
                phyname_networks[network_info['id']] = \
                    [network_info['name'], interface['name']]
            else:
                msg = "can't find network named '%s' in cluster '%s'" % (
                    assigned_network['name'], cluster_id)
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")

        # by cluster id and network_name search interface table
        registry.update_phyname_of_network(req.context, phyname_networks)

    def _verify_interface_in_same_host(self, interfaces, id=None):
        """
        Verify interface in the input host.
        :param interface: host interface info
        :return:
        """
        # verify interface among the input host
        same_mac_list = [interface1['name']
                         for interface1 in interfaces for interface2 in
                         interfaces
                         if interface1.get('name', None) and
                         interface1.get('mac', None) and
                         interface2.get('name', None) and
                         interface2.get('mac', None) and
                         interface1.get('type', None) and
                         interface2.get('type', None) and
                         interface1['name'] != interface2['name'] and
                         interface1['mac'] == interface2['mac'] and
                         interface1['type'] != "bond" and
                         interface2['type'] != "bond"]
        # Notice:If interface with same 'mac' is illegal,
        # we need delete code #1,and raise exception in 'if' block.
        # This code block is just verify for early warning.
        if same_mac_list:
            msg = "%s%s" % ("" if not id else "Host id:%s." % id,
                            "The nic name of interface [%s] with same mac,"
                            "please check!" %
                            ",".join(same_mac_list))
            LOG.warning(msg)

        # 1-----------------------------------------------------------------
        # if interface with same 'pci', raise exception
        same_pci_list = [interface1['name']
                         for interface1 in interfaces for interface2 in
                         interfaces
                         if interface1.get('name', None) and
                         interface1.get('pci', None) and
                         interface2.get('name', None) and
                         interface2.get('pci', None) and
                         interface1.get('type', None) and
                         interface2.get('type', None) and
                         interface1['name'] != interface2['name'] and
                         interface1['pci'] == interface2['pci'] and
                         interface1['type'] == "ether" and
                         interface2['type'] == "ether"]

        if same_pci_list:
            msg = "The nic name of interface [%s] " \
                  "with same pci,please check!" % ",".join(
                      same_pci_list)
            LOG.error(msg)
            raise HTTPForbidden(msg)
        # 1-----------------------------------------------------------------

    def _verify_interface_among_hosts(self, req, host_meta):
        """
        Verify interface among the hosts in cluster
        :param req:
        :param cluster_id:
        :param host_meta:
        :return:True,host already update False,host need add
        """
        # If true, the host need update, not add and update is successful.
        self._verify_interface_in_same_host(host_meta['interfaces'])
        # verify interface between exist host and input host in cluster
        list_params = {
            'sort_key': u'name',
            'sort_dir': u'asc'}
        all_hosts = registry.get_hosts_detail(req.context, **list_params)
        exist_nodes = []
        for id in [host['id'] for host in all_hosts]:
            host_meta_list = registry.get_host_metadata(req.context, id)
            exist_nodes.append(host_meta_list)
        interfaces = list(host_meta['interfaces'])
        for host_interface in interfaces:
            host_mac = host_interface.get('mac', None)
            if not host_mac:
                continue
            for exist_node in exist_nodes:
                id = exist_node.get('id', None)
                os_status = exist_node.get('os_status', None)
                exist_node_info = self.get_host(req, id).get('host_meta',
                                                             None)
                if not exist_node_info.get('interfaces', None):
                    continue
                for interface in exist_node_info['interfaces']:
                    if interface.get('type', None) == "bond":
                        continue
                    if interface.get('mac', None) == host_mac:
                        if exist_node.get('dmi_uuid') \
                                and exist_node.get('dmi_uuid') != \
                                host_meta.get('dmi_uuid'):
                            msg = "The 'mac' of host interface is exist " \
                                  "in db, but 'dmi_uuid' is different.We" \
                                  " think you want update the host, but " \
                                  "the host can't find."
                            LOG.error(msg)
                            raise HTTPForbidden(explanation=msg)
                        return (id, os_status)
        return (None, None)

    def _get_swap_lv_size_m(self, memory_size_m):
        if memory_size_m <= 4096:
            swap_lv_size_m = 4096
        elif memory_size_m <= 16384:
            swap_lv_size_m = 8192
        elif memory_size_m <= 65536:
            swap_lv_size_m = 32768
        else:
            swap_lv_size_m = 65536
        return swap_lv_size_m

    def _ready_to_discover_host(self, req, host_meta, orig_host_meta):
        if orig_host_meta.get('interfaces', None):
            macs = [interface['mac'] for interface
                    in orig_host_meta['interfaces'] if interface['mac']]
            for mac in macs:
                delete_host_discovery_info = 'pxe_os_install_clean ' + mac
                subprocess.call(delete_host_discovery_info,
                                shell=True,
                                stdout=open('/dev/null', 'w'),
                                stderr=subprocess.STDOUT)
        if ('role' not in host_meta and
                'status' in orig_host_meta and
                orig_host_meta['status'] == 'with-role' and
                orig_host_meta['os_status'] != 'init'):
            role_info = {'messages': '', 'progress': '0', 'status': 'init'}
            host_roles = daisy_cmn.get_roles_of_host(req, orig_host_meta['id'])
            for host_role in host_roles:
                daisy_cmn.update_role_host(req, host_role['id'], role_info)
        if orig_host_meta.get('tecs_version_id'):
            host_meta['tecs_version_id'] = ''
        if orig_host_meta.get('tecs_patch_id'):
            host_meta['tecs_patch_id'] = ''
        if 'os_progress' not in host_meta:
            host_meta['os_progress'] = 0
        if 'messages' not in host_meta:
            host_meta['messages'] = ''

    def _set_pxe_interface_for_host(self, req, host_meta):
        all_networks = self.get_cluster_networks_info(req, type='system')
        template_deploy_network = [network for network in all_networks
                                   if network['type'] == 'system' and
                                   network['name'] == 'DEPLOYMENT']
        if not template_deploy_network:
            msg = "error, can't find deployment network of system"
            LOG.error(msg)
            raise HTTPNotFound(msg)

        dhcp_cidr = template_deploy_network[0]['cidr']
        dhcp_ip_ranges = template_deploy_network[0]['ip_ranges']

        deployment_interface_count = 0
        for interface in host_meta['interfaces']:
            if 'ip' in interface and interface['ip']:
                ip_in_cidr = utils.is_ip_in_cidr(interface['ip'],
                                                 dhcp_cidr)
                if dhcp_ip_ranges:
                    ip_in_ranges = utils.is_ip_in_ranges(interface['ip'],
                                                         dhcp_ip_ranges)
                else:
                    ip_in_ranges = True
                if ip_in_cidr and ip_in_ranges:
                    interface['is_deployment'] = 1
                    deployment_interface_count += 1

        if deployment_interface_count != 1:
            if deployment_interface_count == 0:
                msg = "error, can't find dhcp ip"
            if deployment_interface_count > 1:
                msg = "error, find more than one dhcp ip"
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg)

    def _get_os_version(self, host_meta, orig_host_meta):
        # os_version_file and os_version_id only exist one at same time
        os_version = None
        if host_meta.get('os_version', None) and not utils.is_uuid_like(
                host_meta['os_version']):
            os_version = host_meta['os_version']
        if host_meta.get('os_version', None) and utils.is_uuid_like(
                host_meta['os_version']):
            os_version = host_meta['os_version']
        if not host_meta.get('os_version', None) and \
                orig_host_meta['os_version_file']:
            os_version = orig_host_meta['os_version_file']
        if not host_meta.get('os_version', None) and \
                orig_host_meta['os_version_id']:
            os_version = orig_host_meta['os_version_id']
        return os_version

    def _get_group_list(self, host_meta, orig_host_meta, os_version_type):
        group_list = None
        if host_meta.get('group_list', None):
            group_list = host_meta['group_list']
        if not host_meta.get('group_list', None) and orig_host_meta.get(
                'group_list', None):
            group_list = orig_host_meta['group_list']
        if not host_meta.get('group_list', None) and not orig_host_meta.get(
                'group_list', None) and os_version_type == "redhat 7.0":
            host_meta['group_list'] = "core,base"
            group_list = host_meta['group_list']
        if not host_meta.get('group_list', None) and not orig_host_meta.get(
                'group_list', None) and os_version_type == "centos 7.0":
            host_meta['group_list'] = "core,base"
            group_list = host_meta['group_list']
        return host_meta, group_list

    def _get_os_version_type(self, req, os_version):
        os_version_type = None
        if utils.is_uuid_like(os_version):
            version_metadata = registry.get_version_metadata(req.context,
                                                             os_version)
            os_version_type = version_metadata['type']
            return os_version_type
        return os_version_type
        # else:
        #     params = {}
        #     version_list = registry.list_version_metadata(req.context,
        #                                                   **params)
        #     for version in version_list:
        #         if version['name'] == os_version.split("/")[-1]:
        #             return version['type']

    def _check_group_list(self, os_version_type, group_list):
        if os_version_type == "redhat 7.0":
            if "core" not in group_list.split(","):
                msg = "No group named 'core' found in redhat 7.0"
                raise HTTPBadRequest(explanation=msg)
            if "base" not in group_list.split(","):
                msg = "No group named 'base' found in redhat 7.0"
                raise HTTPBadRequest(explanation=msg)
        if os_version_type == "centos 7.0":
            if "core" not in group_list.split(","):
                msg = "No group named 'core' found in centos 7.0"
                raise HTTPBadRequest(explanation=msg)
            if "base" not in group_list.split(","):
                msg = "No group named 'base' found in centos 7.0"
                raise HTTPBadRequest(explanation=msg)

    def _check_os_version(self, req, os_version):
        params = {}
        version_list = registry.list_version_metadata(req.context, **params)
        if utils.is_uuid_like(os_version):
            version_id_list = [version['id'] for version in version_list]
            if os_version not in version_id_list:
                msg = _("os version %s does not exist") % os_version
                raise HTTPForbidden(explanation=msg)
        # else:
        #     version_file_list = [version['name'] for version in version_list]
        #     if not os_version.split("/")[-1] in version_file_list:
        #         msg = _("os version %s does not exist") % \
        #               os_version.split("/")[-1]
        #         raise HTTPForbidden(explanation=msg)

    def _verify_host_name(self, req, host_id, orig_host_meta, host_meta):
        if (host_meta.get('os_status', "") != 'init') and \
                (orig_host_meta.get('os_status', "") == 'active'):
            if (host_meta.get("name")) and \
                    (host_meta["name"] != orig_host_meta["name"]):
                msg = _(
                    "Forbidden to update name of %s "
                    "when os_status is active if "
                    "you don't want to install os") % host_meta['name']
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)
        else:
            if not host_meta.get("name"):
                return
            _name_regex = '^[a-zA-Z][a-zA-Z0-9-]{3,31}$'
            if not re.match(_name_regex, host_meta["name"]):
                msg = _(
                    "Forbidden to update name of %s "
                    "Name must begin with letters,and consist of numbers,"
                    "letters or strikethrough. "
                    "The length of name is 4 to 32.") % host_meta['name']
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)
            # host name is already existed?
            hosts = registry.get_hosts_detail(req.context)
            for host in hosts:
                if (host.get("name", "") == host_meta["name"]) and \
                        (host.get("id", "") != host_id):
                    msg = _("host name %s already exists.") % host_meta["name"]
                    LOG.error(msg)
                    raise HTTPForbidden(explanation=msg)

    def _verify_host_cluster(self, req, host_id, orig_host_meta, host_meta):
        if 'cluster' in host_meta:
            self.get_cluster_meta_or_404(req, host_meta['cluster'])
            if orig_host_meta['status'] == 'in-cluster':
                host_cluster = registry.get_host_clusters(
                    req.context, host_id)
                if host_meta['cluster'] != host_cluster[0]['cluster_id']:
                    msg = _("Forbidden to add host %s with status "
                            "'in-cluster' in another cluster") % host_id
                    LOG.error(msg)
                    raise HTTPForbidden(explanation=msg)
            if orig_host_meta.get("hwm_id"):
                daisy_cmn.check_discover_state_with_hwm(req, orig_host_meta)
            else:
                daisy_cmn.check_discover_state_with_no_hwm(req,
                                                           orig_host_meta)
            discover_success = (orig_host_meta.get("discover_state")) and \
                               ('DISCOVERY_SUCCESSFUL' in
                                orig_host_meta["discover_state"])
            if not discover_success:
                msg = _("Forbidden to update host %s with discover status "
                        "not successful") % host_id
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)

    def _interface_has_vf(self, interface):
        if interface and isinstance(interface, dict):
            if interface.get('is_support_vf'):
                return True
        return False

    def _get_interface_by_name(self, name, interfaces):
        if not interfaces:
            return None

        for interface in interfaces:
            if name == interface.get('name'):
                return interface

        return None

    def _check_vswitch_type(self, req, interface, interfaces):
        vswitch_type = interface.get('vswitch_type')
        if vswitch_type:
            if vswitch_type not in ML2_TYPE:
                msg = "vswitch_type (%s) is not supported" \
                      % vswitch_type
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req,
                                     content_type="text/plain")

            if vswitch_type in NEED_VF_TYPE:
                if "bond" == interface.get('type'):
                    slave_names = interface.get('slaves')
                    if slave_names:
                        for slave_name in slave_names:
                            interface_slave = \
                                self._get_interface_by_name(slave_name,
                                                            interfaces)
                            if not self._interface_has_vf(interface_slave):
                                msg = "vswitch_type (%s) is "\
                                      "not supported because slave %s"\
                                      " of %s does not support VF" % \
                                    (vswitch_type,
                                     slave_name,
                                     interface['name'])
                                LOG.error(msg)
                                raise HTTPBadRequest(
                                    explanation=msg,
                                    request=req,
                                    content_type="text/plain")
                else:
                    if not self._interface_has_vf(interface):
                        msg = "vswitch_type (%s) is not supported "\
                              "because interface %s does not support VF" %\
                            (vswitch_type, interface['name'])
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg, request=req,
                                             content_type="text/plain")

    def _check_interface_on_update_host(self, req, host_meta, orig_host_meta):
        orig_mac_list = []
        # get cluster id
        cluster_id = host_meta.get('cluster')
        if not cluster_id:
            clusters = registry.get_clusters_detail(req.context)
            orig_cluster_name = orig_host_meta.get('cluster', None)
            orig_cluster_id = None
            for cluster in clusters:
                if cluster['name'] == orig_cluster_name:
                    orig_cluster_id = cluster['id']
                    break
            cluster_id = orig_cluster_id

        if 'interfaces' in host_meta:
            host_meta_interfaces = list(host_meta['interfaces'])
            ether_nic_names_list = list()
            bond_nic_names_list = list()
            bond_slaves_lists = list()
            interface_num = 0
            assigned_networks_of_interfaces = []
            for interface_param in host_meta_interfaces:
                if not interface_param.get('pci', None) and \
                        interface_param.get('type', None) == 'ether':
                    msg = "The Interface need a non-null pci"
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg,
                                         request=req,
                                         content_type="text/plain")
                self._check_vswitch_type(req,
                                         interface_param,
                                         host_meta_interfaces)
                # check bond in pairs
                if interface_param.get('name', None):
                    if 'type' in interface_param and \
                            interface_param['type'] == 'bond':
                        bond_nic_names_list.append(interface_param['name'])
                        slave_list = []
                        if interface_param.get('slaves', None):
                            bond_slaves_lists.append(interface_param['slaves'])
                        elif interface_param.get('slave1', None) and \
                                interface_param.get('slave2', None):
                            slave_list.append(interface_param['slave1'])
                            slave_list.append(interface_param['slave2'])
                            bond_slaves_lists.append(slave_list)
                        else:
                            msg = (
                                _("Slaves parameter can not be "
                                  "None when nic type was bond."))
                            LOG.error(msg)
                            raise HTTPForbidden(msg)
                    else:  # type == ether or interface without type field
                        ether_nic_names_list.append(interface_param['name'])
                else:
                    msg = (_("Nic name can not be None."))
                    LOG.error(msg)
                    raise HTTPForbidden(msg)

                # set is_deployment status
                if 'is_deployment' in interface_param:
                    if interface_param['is_deployment'] == "True" or \
                            interface_param[
                            'is_deployment']:
                        interface_param['is_deployment'] = 1
                    else:
                        interface_param['is_deployment'] = 0

                # check assigned networks
                if ('assigned_networks' in interface_param and
                        interface_param['assigned_networks'] != [''] and
                        interface_param['assigned_networks']):
                    if cluster_id:
                        LOG.info(
                            "interface['assigned_networks']: %s" %
                            interface_param['assigned_networks'])
                        if interface_param.get('type', None) == "bond":
                            bond_type = interface_param.get("bond_type", None)
                            assigned_networks_of_one_interface = \
                                self._check_asged_net(
                                    req, cluster_id,
                                    interface_param['assigned_networks'],
                                    bond_type)
                        else:
                            assigned_networks_of_one_interface = self. \
                                _check_asged_net(
                                    req, cluster_id,
                                    interface_param['assigned_networks'])

                        self._update_networks_phyname(
                            req, interface_param, cluster_id)
                        host_meta['cluster'] = cluster_id
                    else:
                        msg = "cluster must be given first " \
                              "when network plane is allocated"
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg,
                                             request=req,
                                             content_type="text/plain")
                    assigned_networks_of_interfaces.\
                        append(assigned_networks_of_one_interface)
                else:
                    assigned_networks_of_interfaces.append([])
                interface_num += 1

            interfaces_db = orig_host_meta.get('interfaces', None)
            orig_mac_list = [interface_db['mac'] for interface_db in
                             interfaces_db if interface_db['mac']]

            self._compare_assigned_networks_between_interfaces(
                interface_num, assigned_networks_of_interfaces)

            # check bond slaves validity
            self.check_bond_slaves_validity(
                bond_slaves_lists, ether_nic_names_list)
            nic_name_list = ether_nic_names_list + bond_nic_names_list
            if len(set(nic_name_list)) != len(nic_name_list):
                msg = (_("Nic name must be unique."))
                LOG.error(msg)
                raise HTTPForbidden(msg)

        return orig_mac_list

    def _get_orig_host_meta(self, req, id):
        orig_host_meta = self.get_host_meta_or_404(req, id)
        # Do not allow any updates on a deleted host.
        if orig_host_meta['deleted']:
            msg = _("Forbidden to update deleted host.")
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        return orig_host_meta

    def _check_supported_resource_type(self, host_meta):
        if ('resource_type' in host_meta and
                host_meta['resource_type'] not in self.support_resource_type):
            msg = "resource type is not supported, please use it in %s" % \
                  self.support_resource_type
            LOG.error(msg)
            raise HTTPNotFound(msg)

    def _check_and_update_root_disk(self, req, id, host_meta, orig_host_meta):
        if host_meta.get(
                'os_status',
                None) != 'init' and orig_host_meta.get(
                'os_status',
                None) == 'active':
            if host_meta.get('root_disk', None) and host_meta[
                    'root_disk'] != orig_host_meta['root_disk']:
                msg = _(
                    "Forbidden to update root_disk of %s "
                    "when os_status is active if "
                    "you don't want to install os") % id
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)
            else:
                host_meta['root_disk'] = orig_host_meta['root_disk']
        elif orig_host_meta.get('discover_mode'):
            if host_meta.get('root_disk', None):
                root_disk = host_meta['root_disk']
            elif orig_host_meta.get('root_disk', None):
                root_disk = orig_host_meta['root_disk']
            else:
                host_meta['root_disk'] = 'sda'
                root_disk = host_meta['root_disk']
            if not orig_host_meta.get('disks', None):
                msg = "there is no disks in %s" % orig_host_meta['id']
                LOG.error(msg)
                raise HTTPNotFound(msg)
            if root_disk not in orig_host_meta['disks'].keys():
                msg = "There is no disk named %s" % root_disk
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")

    def _check_and_update_root_lv_size(self, req, id, host_meta, orig_host_meta):
        if host_meta.get(
                'os_status',
                None) != 'init' and orig_host_meta.get(
                'os_status',
                None) == 'active':
            if host_meta.get(
                    'root_lv_size', None) and int(
                    host_meta['root_lv_size']) != orig_host_meta[
                    'root_lv_size']:
                msg = _(
                    "Forbidden to update root_lv_size of %s "
                    "when os_status is active if "
                    "you don't want to install os") % host_meta['name']
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)
            else:
                host_meta['root_lv_size'] = orig_host_meta['root_lv_size']
        elif orig_host_meta.get('discover_mode'):
            if host_meta.get('root_lv_size', None):
                root_lv_size = host_meta['root_lv_size']
            elif orig_host_meta.get('root_lv_size', None):
                root_lv_size = orig_host_meta['root_lv_size']
            else:
                host_meta['root_lv_size'] = 102400
                root_lv_size = host_meta['root_lv_size']

            if not orig_host_meta.get('disks', None):
                msg = "there is no disks in %s" % orig_host_meta['id']
                LOG.error(msg)
                raise HTTPNotFound(msg)

            if isinstance(root_lv_size, int):
                root_disk_storage_size_b_str = str(
                    orig_host_meta['disks'][
                        '%s' %
                        root_disk]['size'])
                root_disk_storage_size_b_int = int(
                    root_disk_storage_size_b_str.strip().split()[0])
                root_disk_storage_size_m = root_disk_storage_size_b_int // (
                    1024 * 1024)
                boot_partition_m = 400
                redundant_partiton_m = 600
                if host_meta.get('role', None):
                    host_role_names = host_meta['role']
                elif orig_host_meta.get('role', None):
                    host_role_names = orig_host_meta['role']
                else:
                    host_role_names = []
                if 'CONTROLLER_HA' in host_role_names:
                    params = self._get_query_params(req)

                    role_list = registry.get_roles_detail(
                        req.context, **params)
                    ctrle_ha_role_info = [role for role in role_list if
                                          role['name'] == 'CONTROLLER_HA' and
                                          role['type'] == 'default']
                    docker_vg_size_m = ctrle_ha_role_info[0].get(
                        ctrle_ha_role_info[0]['docker_vg_size'], 104448)
                    free_root_disk_storage_size_m = \
                        root_disk_storage_size_m - \
                        boot_partition_m - redundant_partiton_m - \
                        docker_vg_size_m
                else:
                    free_root_disk_storage_size_m = \
                        root_disk_storage_size_m - boot_partition_m - \
                        redundant_partiton_m
                if (root_lv_size / 4) * 4 > free_root_disk_storage_size_m:
                    msg = (_("root_lv_size of %s is larger than the  free "
                             "root disk storage_size.the free"
                             " stroage is %s M " %
                             (orig_host_meta['id'],
                              free_root_disk_storage_size_m)))
                    LOG.error(msg)
                    raise HTTPForbidden(explanation=msg,
                                        request=req,
                                        content_type="text/plain")
                if (root_lv_size / 4) * 4 < 102400:
                    msg = "root_lv_size of %s is too small, " \
                          "it must be larger than 102400M." % orig_host_meta[
                              'id']
                    LOG.error(msg)
                    raise HTTPForbidden(explanation=msg,
                                        request=req,
                                        content_type="text/plain")
            else:
                msg = (
                    _("root_lv_size of %s is wrong,"
                      "please input a number and it must be positive number") %
                    orig_host_meta['id'])
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg,
                                    request=req,
                                    content_type="text/plain")

    def _check_and_update_swap_lv_size(self, req, id, host_meta, orig_host_meta):
        if host_meta.get(
                'os_status',
                None) != 'init' and orig_host_meta.get(
                'os_status',
                None) == 'active':
            if host_meta.get(
                    'swap_lv_size', None) and int(
                    host_meta['swap_lv_size']) != \
                    orig_host_meta['swap_lv_size']:
                msg = _(
                    "Forbidden to update swap_lv_size of %s "
                    "when os_status is active if "
                    "you don't want to install os") % host_meta['name']
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)
            else:
                host_meta['swap_lv_size'] = orig_host_meta['swap_lv_size']
        elif orig_host_meta.get('discover_mode'):
            if host_meta.get('swap_lv_size', None):
                swap_lv_size = host_meta['swap_lv_size']
            elif orig_host_meta.get('swap_lv_size', None):
                swap_lv_size = orig_host_meta['swap_lv_size']
            else:
                if not orig_host_meta.get('memory', None):
                    msg = "there is no memory in %s" % orig_host_meta['id']
                    LOG.error(msg)
                    raise HTTPNotFound(msg)
                memory_size_b_str = str(orig_host_meta['memory']['total'])
                memory_size_b_int = int(memory_size_b_str.strip().split()[0])
                memory_size_m = memory_size_b_int // 1024
                swap_lv_size_m = self._get_swap_lv_size_m(memory_size_m)
                host_meta['swap_lv_size'] = swap_lv_size_m
                swap_lv_size = host_meta['swap_lv_size']

            if isinstance(swap_lv_size, int):
                disk_storage_size_b = 0
                for key in orig_host_meta['disks']:
                    if orig_host_meta['disks'][key]['disk'].find("-fc-") \
                            != -1 or orig_host_meta['disks'][key]['disk'].\
                            find("-iscsi-") != -1 \
                            or orig_host_meta['disks'][key]['name'].\
                            find("mpath") != -1 \
                            or orig_host_meta['disks'][key]['name'].\
                            find("spath") != -1 \
                            or orig_host_meta['disks'][key]['removable'] == \
                            'removable':
                        continue
                    stroage_size_str = orig_host_meta['disks'][key]['size']
                    stroage_size_b_int = int(
                        stroage_size_str.strip().split()[0])
                    disk_storage_size_b = \
                        disk_storage_size_b + stroage_size_b_int
                disk_storage_size_m = disk_storage_size_b / (1024 * 1024)
                boot_partition_m = 400
                redundant_partiton_m = 600
                if host_meta.get('role', None):
                    host_role_names = host_meta['role']
                elif orig_host_meta.get('role', None):
                    host_role_names = orig_host_meta['role']
                else:
                    host_role_names = None
                if host_role_names:
                    roles_of_host = []
                    params = self._get_query_params(req)
                    role_lists = registry.get_roles_detail(
                        req.context, **params)
                    for host_role_name in host_role_names:
                        for role in role_lists:
                            if host_role_name == role[
                                    'name'] and role['type'] == 'default':
                                roles_of_host.append(role)
                    db_lv_size = 0
                    nova_lv_size = 0
                    glance_lv_size = 0
                    docker_vg_size = 0
                    for role_of_host in roles_of_host:
                        if role_of_host['name'] == 'CONTROLLER_HA':
                            if role_of_host.get('glance_lv_size', None):
                                glance_lv_size = role_of_host['glance_lv_size']
                            if role_of_host.get('db_lv_size', None):
                                db_lv_size = role_of_host['db_lv_size']
                            if role_of_host.get('docker_vg_size', None):
                                docker_vg_size = role_of_host['docker_vg_size']
                        if role_of_host['name'] == 'COMPUTER':
                            nova_lv_size = role_of_host['nova_lv_size']
                    free_disk_storage_size_m = disk_storage_size_m - \
                        boot_partition_m - \
                        redundant_partiton_m - \
                        (root_lv_size / 4) * 4 - (glance_lv_size / 4) * 4 - \
                        (nova_lv_size / 4) * 4 - \
                        (db_lv_size / 4) * 4 - (docker_vg_size / 4) * 4
                else:
                    free_disk_storage_size_m = disk_storage_size_m - \
                        boot_partition_m - redundant_partiton_m - \
                        (root_lv_size / 4) * 4
                if (swap_lv_size / 4) * 4 > free_disk_storage_size_m:
                    msg = "the sum of swap_lv_size and " \
                          "glance_lv_size and nova_lv_size and " \
                          "db_lv_size of %s is larger " \
                          "than the free_disk_storage_size." % \
                          orig_host_meta['id']
                    LOG.error(msg)
                    raise HTTPForbidden(explanation=msg,
                                        request=req,
                                        content_type="text/plain")
                if (swap_lv_size / 4) * 4 < 2000:
                    msg = "swap_lv_size of %s is too small, " \
                          "it must be larger than 2000M." % orig_host_meta[
                              'id']
                    LOG.error(msg)
                    raise HTTPForbidden(explanation=msg,
                                        request=req,
                                        content_type="text/plain")
            else:
                msg = (
                    _("swap_lv_size of %s is wrong,"
                      "please input a number and it must be positive number") %
                    orig_host_meta['id'])
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg,
                                    request=req,
                                    content_type="text/plain")

    def _check_and_update_root_passwd(self, req, id, host_meta, orig_host_meta):
        if host_meta.get(
                'os_status',
                None) != 'init' and orig_host_meta.get(
                'os_status',
                None) == 'active':
            if host_meta.get('root_pwd', None) and host_meta[
                    'root_pwd'] != orig_host_meta['root_pwd']:
                msg = _(
                    "Forbidden to update root_pwd of %s "
                    "when os_status is active if "
                    "you don't want to install os") % host_meta['name']
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)
            else:
                host_meta['root_pwd'] = orig_host_meta['root_pwd']
        else:
            if not host_meta.get(
                    'root_pwd',
                    None) and not orig_host_meta.get(
                    'root_pwd',
                    None):
                host_meta['root_pwd'] = 'ossdbg1'

    def _check_and_update_isolcpus(self, req, id, host_meta, orig_host_meta):
        if host_meta.get(
                'os_status',
                None) != 'init' and orig_host_meta.get(
                'os_status',
                None) == 'active':
            if host_meta.get('isolcpus', None) and host_meta[
                    'isolcpus'] != orig_host_meta['isolcpus']:
                msg = _(
                    "Forbidden to update isolcpus of %s "
                    "when os_status is active if "
                    "you don't want to install os") % host_meta['name']
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)
            else:
                host_meta['isolcpus'] = orig_host_meta['isolcpus']
        elif orig_host_meta.get('discover_mode'):
            if host_meta.get('isolcpus', None):
                isolcpus = host_meta['isolcpus']
            elif orig_host_meta.get('isolcpus', None):
                isolcpus = orig_host_meta['isolcpus']
            else:
                host_meta['isolcpus'] = None
                isolcpus = host_meta['isolcpus']
            if not orig_host_meta.get('cpu', None):
                msg = "there is no cpu in %s" % orig_host_meta['id']
                LOG.error(msg)
                raise HTTPNotFound(msg)
            cpu_num = orig_host_meta['cpu']['total']
            if isolcpus:
                isolcpus_lists = [value.split('-')
                                  for value in isolcpus.split(',')]
                isolcpus_list = []
                for value in isolcpus_lists:
                    isolcpus_list = isolcpus_list + value
                for value in isolcpus_list:
                    if int(value) < 0 or int(value) > cpu_num - 1:
                        msg = "isolcpus number must be lager than 0 and " \
                              "less than %d" % (
                                  cpu_num - 1)
                        LOG.error(msg)
                        raise HTTPForbidden(explanation=msg,
                                            request=req,
                                            content_type="text/plain")

    def _check_and_update_hugepage(self, req, id, host_meta, orig_host_meta):
        if host_meta.get('os_status', None) != 'init' and \
                orig_host_meta.get('os_status', None) == 'active':
            if host_meta.get(
                    'hugepages', None) and int(
                    host_meta['hugepages']) != orig_host_meta['hugepages']:
                msg = _("Forbidden to update hugepages of %s"
                        " when os_status is active if "
                        "you don't want to install os") % host_meta['name']
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)
        else:
            if 'hugepages' in host_meta:
                if not orig_host_meta.get('memory', {}).get('total', None):
                    msg = "The host %s has no memory" % id
                    LOG.error(msg)
                    raise HTTPNotFound(explanation=msg)
                memory = orig_host_meta.get('memory', {}).get('total', None)
                if host_meta['hugepages'] is None:
                    host_meta['hugepages'] = 0
                if int(host_meta['hugepages']) < 0:
                    msg = "The parameter hugepages must be zero or " \
                          "positive integer."
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg)
                if 'hugepagesize' not in host_meta and \
                        orig_host_meta.get('hugepagesize', None):
                    self._compute_hugepage_memory(host_meta['hugepages'],
                                                  int(memory.strip().split(
                                                      ' ')[0]),
                                                  orig_host_meta[
                                                      'hugepagesize'])
                if 'hugepagesize' not in host_meta and \
                        not orig_host_meta.get('hugepagesize', None):
                    self._compute_hugepage_memory(
                        host_meta['hugepages'], int(
                            memory.strip().split(' ')[0]))

        if host_meta.get('os_status', None) != 'init' and \
                orig_host_meta.get('os_status', None) == 'active':
            if host_meta.get('hugepagesize', None) and \
                    host_meta['hugepagesize'] != \
                    orig_host_meta['hugepagesize']:
                msg = _(
                    "Forbidden to update hugepagesize of %s"
                    " when os_status is active if you don't "
                    "want to install os") % host_meta['name']
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)
        else:
            if 'hugepagesize' in host_meta:
                if not orig_host_meta.get('memory', {}).get('total', None):
                    msg = "The host %s has no memory" % id
                    LOG.error(msg)
                    raise HTTPNotFound(explanation=msg)
                memory = orig_host_meta.get('memory', {}).get('total', None)
                if host_meta['hugepagesize'] is None:
                    host_meta['hugepagesize'] = '1G'
                else:
                    host_meta['hugepagesize'].upper()
                    if host_meta['hugepagesize'] not in SUPPORT_HOST_PAGE_SIZE:
                        msg = "The value 0f parameter hugepagesize " \
                              "is not supported."
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg)
                if host_meta['hugepagesize'] == '2M' and \
                        int(host_meta['hugepagesize'][0]) * 1024 > \
                        int(memory.strip().split(' ')[0]):
                    msg = "The host %s forbid to use hugepage because it's " \
                          "memory is too small" % id
                    LOG.error(msg)
                    raise HTTPForbidden(explanation=msg)
                if host_meta['hugepagesize'] == '1G' and \
                        int(host_meta['hugepagesize'][0]) * 1024 * 1024 > \
                        int(memory.strip().split(' ')[0]):
                    msg = "The hugepagesize is too big, you can choose 2M " \
                          "for a try."
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg)
                if 'hugepages' in host_meta:
                    self._compute_hugepage_memory(host_meta['hugepages'], int(
                        memory.strip().split(' ')[0]),
                        host_meta['hugepagesize'])
                if 'hugepages' not in host_meta and \
                        orig_host_meta.get('hugepages', None):
                    self._compute_hugepage_memory(orig_host_meta['hugepages'],
                                                  int(
                        memory.strip().split(' ')[0]),
                        host_meta['hugepagesize'])

    def _check_and_update_role(self, req, id, host_meta, orig_host_meta):
        params = self._get_query_params(req)
        role_list = registry.get_roles_detail(req.context, **params)
        if 'role' in host_meta:
            role_id_list = []
            if 'cluster' in host_meta:
                host_roles = list()
                for role_name in role_list:
                    if role_name['cluster_id'] == host_meta['cluster']:
                        host_roles = list(host_meta['role'])
                        for host_role in host_roles:
                            if role_name['name'] == host_role:
                                role_id_list.append(role_name['id'])
                                continue
                if len(role_id_list) != len(
                        host_roles) and host_meta['role'] != u"[u'']":
                    msg = "The role of params %s is not exist, " \
                          "please use the right name" % host_roles
                    LOG.error(msg)
                    raise HTTPNotFound(msg)
                host_meta['role'] = role_id_list
            else:
                msg = "cluster params is none"
                LOG.error(msg)
                raise HTTPNotFound(msg)

    def _check_supported_os_status(self, host_meta):
        if 'os_status' in host_meta:
            if host_meta['os_status'] not in \
                    ['init', 'installing', 'active', 'failed', 'none']:
                msg = "os_status is not valid."
                LOG.error(msg)
                raise HTTPNotFound(msg)

    def _check_and_update_os_version(self, req, id, host_meta, orig_host_meta):
        if host_meta.get('os_status', None) != 'init' \
                and orig_host_meta.get('os_status', None) == 'active':
            if host_meta.get('os_version', None) and utils.is_uuid_like(
                    host_meta['os_version']) and host_meta['os_version'] != \
                    orig_host_meta['os_version_id']:
                msg = _("Forbidden to update os version of %s "
                        "when os status is active if "
                        "you don't want to install os") % host_meta['name']
                raise HTTPForbidden(explanation=msg)
            if host_meta.get('os_version', None) and not utils.is_uuid_like(
                    host_meta['os_version']) and host_meta['os_version'] != \
                    orig_host_meta['os_version_file']:
                msg = _("Forbidden to update os version of %s "
                        "when os status is active if "
                        "you don't want to install os") % host_meta['name']
                raise HTTPForbidden(explanation=msg)
            if host_meta.get('group_list', None) and \
                    host_meta['group_list'] != \
                    orig_host_meta['group_list']:
                msg = _("Forbidden to update group list of %s "
                        "when os status is active if "
                        "you don't want to install os") % host_meta['name']
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)
        else:
            os_version = self._get_os_version(host_meta, orig_host_meta)
            if os_version:
                self._check_os_version(req, os_version)
                os_version_type = self._get_os_version_type(req, os_version)
                host_meta, group_list = self._get_group_list(host_meta,
                                                             orig_host_meta,
                                                             os_version_type)
                self._check_group_list(os_version_type, group_list)

    def _check_and_update_config_set(self, req, id, host_meta, orig_host_meta):
        if (host_meta.get('config_set_id') and
                host_meta['config_set_id'] !=
                orig_host_meta.get('config_set_id')):
            self.get_config_set_meta_or_404(req,
                                            host_meta['config_set_id'])

    @utils.mutating
    def update_host(self, req, id, host_meta):
        """
        Updates an existing host with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'update_host')
        orig_host_meta = self._get_orig_host_meta(req, id)
        self._verify_host_name(req, id, orig_host_meta, host_meta)

        orig_mac_list = \
            self._check_interface_on_update_host(req, host_meta,
                                                 orig_host_meta)

        # Parameters sainty checks
        self._check_supported_resource_type(host_meta)
        self._check_supported_os_status(host_meta)

        # Host baisc status checks        
        self._verify_host_cluster(req, id, orig_host_meta, host_meta)

        # Do real checks and updates based upon parameters
        self._check_and_update_root_disk(req, id, host_meta, orig_host_meta)
        self._check_and_update_root_lv_size(req, id, host_meta, orig_host_meta)
        self._check_and_update_swap_lv_size(req, id, host_meta, orig_host_meta)
        self._check_and_update_root_passwd(req, id, host_meta, orig_host_meta)
        self._check_and_update_isolcpus(req, id, host_meta, orig_host_meta)
        self._check_and_update_hugepage(req, id, host_meta, orig_host_meta)
        self._check_and_update_role(req, id, host_meta, orig_host_meta)
        self._check_dvs_huge(host_meta, orig_host_meta)
        self._check_and_update_os_version(req, id, host_meta, orig_host_meta)
        self._check_and_update_config_set(req, id, host_meta, orig_host_meta)

        # Check if we are ready for discovering the host

        if host_meta.get('os_status') == 'init' and orig_host_meta.get(
                'os_status') == 'active':
            self._ready_to_discover_host(req, host_meta, orig_host_meta)

            # Call extension when we ready to discover a host
            path = os.path.join(os.path.abspath(os.path.dirname(
                os.path.realpath(__file__))), 'ext')
            for root, dirs, names in os.walk(path):
                filename = 'router.py'
                if filename in names:
                    ext_name = root.split(path)[1].strip('/')
                    ext_func = "%s.api.hosts" % ext_name
                    extension = importutils.import_module(
                        'daisy.api.v1.ext.%s' % ext_func)
                    extension.update_host_state(orig_host_meta)

        try:
            # Do real data update into DB
            host_meta = registry.update_host_metadata(req.context, id,
                                                      host_meta)

            # Check if the host was discovered successfully

            if host_meta.get('cluster', None):
                pxe_macs = [interface['mac'] for interface in orig_host_meta[
                    'interfaces'] if interface['is_deployment']]
                if not pxe_macs:
                    daisy_cmn.add_ssh_host_to_cluster_and_assigned_network(
                        req, host_meta['cluster'], id)

            if orig_mac_list:
                orig_min_mac = min(orig_mac_list)
                discover_host = self._get_discover_host_by_mac(req,
                                                               orig_min_mac)
                if discover_host:
                    discover_host_params = {
                        "mac": orig_min_mac,
                        "status": "DISCOVERY_SUCCESSFUL"
                    }
                    self.update_pxe_host(req, discover_host['id'],
                                         discover_host_params)

        except exception.Invalid as e:
            msg = (_("Failed to update host metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find host to update: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update host: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.error(utils.exception_to_str(e))
            raise HTTPConflict(body=_('Host operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('host.update', host_meta)

        return {'host_meta': host_meta}

    def update_progress_to_db(self, req, update_info, discover_host_meta):
        discover = {}
        discover['status'] = update_info['status']
        discover['message'] = update_info['message']
        if update_info.get('host_id'):
            discover['host_id'] = update_info['host_id']
        LOG.info("discover:%s", discover)
        registry.update_discover_host_metadata(req.context,
                                               discover_host_meta['id'],
                                               discover)

    def is_host_discover_success_4_ssh(self, req, host_id):
        orig_host_meta = self.get_host_meta_or_404(req, host_id)
        return True \
            if (orig_host_meta.get("discover_mode")) and \
               (orig_host_meta.get("discover_mode") == 'SSH') else False

    def thread_bin(self, req, cluster_id, discover_host_meta):
        cmd = 'mkdir -p /var/log/daisy/discover_host/'
        daisy_cmn.subprocess_call(cmd)
        if not discover_host_meta['passwd']:
            msg = "the passwd of ip %s is none." % discover_host_meta['ip']
            LOG.error(msg)
            raise HTTPForbidden(msg)
        var_log_path = "/var/log/daisy/discover_host/%s_discovery_host.log" \
                       % discover_host_meta['ip']
        backends = get_backend()
        with open(var_log_path, "w+") as fp:
            for backend in backends:
                backend_driver = driver.load_deployment_driver(backend)
                backend_driver.prepare_ssh_discovered_node(req, fp,
                                                           discover_host_meta)
            try:
                exc_result = subprocess.check_output(
                    'clush -S -w %s /home/daisy/discover_host/getnodeinfo.sh'
                    % (discover_host_meta['ip'],),
                    shell=True, stderr=subprocess.STDOUT)
                if 'Failed connect to' in exc_result:
                    # when daisy-discoverd.service has problem
                    update_info = {}
                    update_info['status'] = 'DISCOVERY_FAILED'
                    update_info['message'] = "Do getnodeinfo.sh %s failed!" \
                                             % discover_host_meta['ip']
                    self.update_progress_to_db(req, update_info,
                                               discover_host_meta)
                    msg = (_("Do trustme.sh %s failed!" %
                             discover_host_meta['ip']))
                    LOG.warning(msg)
                    fp.write(msg)
                else:
                    mac_info = re.search(r'"mac": ([^,\n]*)', exc_result)
                    mac = eval(mac_info.group(1))
                    filters = {'mac': mac}
                    update_info = {}
                    host_interfaces =\
                        registry.get_all_host_interfaces(req.context, filters)
                    if host_interfaces and \
                            (self.is_host_discover_success_4_ssh(
                            req, host_interfaces[0]['host_id'])):
                        update_info['status'] = 'DISCOVERY_SUCCESSFUL'
                        update_info['message'] =\
                            "discover host for %s successfully!" %\
                            discover_host_meta['ip']
                        update_info['host_id'] = host_interfaces[0]['host_id']
                        LOG.info("update_info['host_id']:%s",
                                 update_info['host_id'])
                        self.update_progress_to_db(req, update_info,
                                                   discover_host_meta)
                        LOG.info(_("discover host for %s successfully!"
                                   % discover_host_meta['ip']))
                        fp.write(exc_result)
                    else:
                        update_info['status'] = 'DISCOVERY_FAILED'
                        update_info['message'] = \
                            "discover host for %s failed!please view" \
                            " the daisy api log" % discover_host_meta['ip']
                        self.update_progress_to_db(req, update_info,
                                                   discover_host_meta)
                        LOG.error(_("discover host for %s failed!" %
                                    discover_host_meta['ip']))
                        fp.write(exc_result)
                        return
            except subprocess.CalledProcessError as e:
                update_info = {}
                update_info['status'] = 'DISCOVERY_FAILED'
                update_info['message'] = "discover host for %s failed!" %\
                                         discover_host_meta['ip']
                self.update_progress_to_db(
                    req, update_info, discover_host_meta)
                LOG.error(_("discover host for %s failed!" %
                            discover_host_meta['ip']))
                fp.write(e.output.strip())
                return

            discover_host_info = \
                registry.get_discover_host_metadata(req.context,
                                                    discover_host_meta['id'])
            if not discover_host_info['host_id']:
                update_info = {}
                update_info['status'] = 'DISCOVERY_FAILED'
                update_info['message'] = "discover host for %s failed!" \
                                         % discover_host_info['ip']
                self.update_progress_to_db(
                    req, update_info, discover_host_info)
                msg = (_("discover host for %s failed!" %
                         discover_host_info['ip']))
                LOG.error(msg)
                return
            else:
                daisy_cmn.add_ssh_host_to_cluster_and_assigned_network(
                    req, cluster_id, discover_host_info['host_id'])

    @utils.mutating
    def discover_host_bin(self, req, host_meta):
        params = {}
        cluster_id = host_meta.get('cluster_id', None)
        if cluster_id:
            params = {'cluster_id': cluster_id}
        discover_host_meta_list =\
            registry.get_discover_hosts_detail(req.context, **params)
        filters = {}
        host_interfaces = \
            registry.get_all_host_interfaces(req.context, filters)
        existed_host_ip = [host['ip'] for host in host_interfaces]
        LOG.info('existed_host_ip**: %s', existed_host_ip)

        for discover_host in discover_host_meta_list:
            if discover_host['status'] != 'DISCOVERY_SUCCESSFUL' and \
                    discover_host['ip']:
                update_info = {}
                update_info['status'] = 'DISCOVERING'
                update_info['message'] = 'DISCOVERING'
                update_info['host_id'] = 'None'
                self.update_progress_to_db(req, update_info, discover_host)
        threads = []
        for discover_host_meta in discover_host_meta_list:
            if discover_host_meta['ip'] \
                    and discover_host_meta['ip'] in existed_host_ip:
                update_info = {}
                update_info['status'] = 'DISCOVERY_SUCCESSFUL'
                update_info['message'] = "discover host for %s successfully!" \
                                         % discover_host_meta['ip']
                host_id_list = \
                    [host['host_id'] for host in host_interfaces
                     if discover_host_meta['ip'] == host['ip']]
                update_info['host_id'] = host_id_list[0]
                self.update_progress_to_db(
                    req, update_info, discover_host_meta)
                continue
            if discover_host_meta['ip'] and discover_host_meta['status'] \
                    != 'DISCOVERY_SUCCESSFUL':
                t = threading.Thread(
                    target=self.thread_bin, args=(
                        req, cluster_id, discover_host_meta))
                t.setDaemon(True)
                t.start()
                threads.append(t)
        LOG.info(_("all host discovery threads have started, "
                   "please waiting...."))

        try:
            for t in threads:
                t.join()
        except Exception:
            LOG.warning(_("Join discover host thread %s failed!" % t))

    @utils.mutating
    def discover_host(self, req, host_meta):
        cluster_id = host_meta.get('cluster_id', None)
        if cluster_id:
            self.get_cluster_meta_or_404(req, cluster_id)

        config = ConfigParser.ConfigParser()
        config.read(daisy_cmn.daisy_conf_file)
        daisy_management_ip = config.get("DEFAULT", "daisy_management_ip")
        if daisy_management_ip:
            backends = get_backend()
            for backend in backends:
                backend_driver = driver.load_deployment_driver(backend)
                backend_driver.getnodeinfo_ip(daisy_management_ip)
        config_discoverd = ConfigParser.ConfigParser(
            defaults=DISCOVER_DEFAULTS)
        config_discoverd.read("/etc/daisy-discoverd/discoverd.conf")
        listen_port = config_discoverd.get("discoverd", "listen_port")
        if listen_port:
            backends = get_backend()
            for backend in backends:
                backend_driver = driver.load_deployment_driver(backend)
                backend_driver.getnodeinfo_listen_port(listen_port)

        discovery_host_thread = threading.Thread(
            target=self.discover_host_bin, args=(req, host_meta))
        discovery_host_thread.start()
        return {"status": "begin discover host"}

    @utils.mutating
    def add_discover_host(self, req, host_meta):
        """
        Adds a new discover host to Daisy

        :param req: The WSGI/Webob Request object
        :param host_meta: Mapping of metadata about host

        :raises HTTPBadRequest if x-host-name is missing
        """
        self._enforce(req, 'add_discover_host')
        LOG.warning("host_meta: %s" % host_meta)
        if not host_meta.get('ip', None):
            msg = "IP parameter can not be None."
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

        discover_hosts_ip = self._get_discover_host_ip(req)
        host_interfaces = []
        if host_meta.get('mac'):
            filters = {'mac': host_meta['mac']}
            host_interfaces = registry.get_all_host_interfaces(req.context,
                                                               filters)
        if host_meta['ip'] in discover_hosts_ip:
            host = self._get_discover_host_filter_by_ip(req, host_meta['ip'])
            if host and host['status'] != 'DISCOVERY_SUCCESSFUL':
                host_info = {}
                host_info['ip'] = host_meta.get('ip', host.get('ip'))
                host_info['passwd'] = \
                    host_meta.get('passwd', host.get('passwd'))
                host_info['user'] = host_meta.get('user', host.get('user'))
                host_info['status'] = 'init'
                host_info['message'] = 'None'
                if host_interfaces:
                    host_info['host_id'] = host_interfaces[0]['host_id']
                discover_host_info = \
                    registry.update_discover_host_metadata(req.context,
                                                           host['id'],
                                                           host_info)
            else:
                msg = (_("ip %s already existed and this host has been "
                         "discovered successfully. " % host_meta['ip']))
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg,
                                    request=req,
                                    content_type="text/plain")
        else:
            self.validate_ip_format(host_meta['ip'])
            if not host_meta.get('user', None):
                host_meta['user'] = 'root'
            if not host_meta.get('passwd', None):
                msg = "PASSWD parameter can not be None."
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")
            if not host_meta.get('status', None):
                host_meta['status'] = 'init'
            if host_interfaces:
                host_meta['host_id'] = host_interfaces[0]['host_id']
            try:
                discover_host_info = \
                    registry.add_discover_host_metadata(req.context, host_meta)
            except exception.Invalid as e:
                raise HTTPBadRequest(explanation=e.msg, request=req)
        return {'host_meta': discover_host_info}

    @utils.mutating
    def delete_discover_host(self, req, id):
        """
        Deletes a discover host from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about host

        :raises HTTPBadRequest if x-host-name is missing
        """
        self._enforce(req, 'delete_discover_host')
        try:
            registry.delete_discover_host_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find host to delete: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete host: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("Host %(id)s could not be deleted because it is in use: "
                     "%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.error(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            # self.notifier.info('host.delete', host)
            return Response(body='', status=200)

    def detail_discover_host(self, req):
        """
        Returns detailed information for all available nodes

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'nodes': [
                {'id': <ID>,
                 'name': <NAME>,
                 'description': <DESCRIPTION>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """

        self._enforce(req, 'get_discover_hosts')
        params = self._get_query_params(req)
        try:
            nodes = registry.get_discover_hosts_detail(req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)

        return dict(nodes=nodes)

    def update_discover_host(self, req, id, host_meta):
        '''
        '''
        self._enforce(req, 'update_discover_host')
        orig_host_meta = registry.get_discover_host_metadata(req.context, id)
        if host_meta.get('ip', None):
            discover_hosts_ip = self._get_discover_host_ip(req)
            if host_meta['ip'] in discover_hosts_ip:
                host_status = host_meta.get('status', orig_host_meta['status'])
                if host_status == 'DISCOVERY_SUCCESSFUL':
                    msg = (_("Host with ip %s already has been discovered "
                             "successfully, can not change host ip to %s " %
                             (orig_host_meta['ip'], host_meta['ip'])))
                    LOG.error(msg)
                    raise HTTPForbidden(explanation=msg,
                                        request=req,
                                        content_type="text/plain")
            self.validate_ip_format(host_meta['ip'])
        if orig_host_meta['ip'] != host_meta.get('ip', None):
            host_meta['status'] = 'init'
        try:
            host_meta = registry.update_discover_host_metadata(req.context,
                                                               id,
                                                               host_meta)

        except exception.Invalid as e:
            msg = (_("Failed to update host metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find host to update: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update host: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.error(utils.exception_to_str(e))
            raise HTTPConflict(body=_('Host operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('host.update', host_meta)

        return {'host_meta': host_meta}

    def _get_discover_host_ip(self, req):
        params = {}
        hosts_ip = list()
        discover_hosts =\
            registry.get_discover_hosts_detail(req.context, **params)
        for host in discover_hosts:
            if host.get('ip', None):
                hosts_ip.append(host['ip'])
        return hosts_ip

    def _get_discover_host_filter_by_ip(self, req, host_ip):
        params = {}
        discover_hosts = \
            registry.get_discover_hosts_detail(req.context, **params)
        for host in discover_hosts:
            if host.get('ip') == host_ip:
                return host
        return

    def get_discover_host_detail(self, req, discover_host_id):
        '''
        '''
        try:
            host_meta = registry.get_discover_host_metadata(req.context,
                                                            discover_host_id)
        except exception.Invalid as e:
            msg = (_("Failed to update host metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find host to update: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update host: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.error(utils.exception_to_str(e))
            raise HTTPConflict(body=_('Host operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('host.update', host_meta)

        return {'host_meta': host_meta}

    def _get_discover_host_mac(self, req):
        params = dict()
        hosts_mac = list()
        discover_hosts =\
            registry.get_discover_hosts_detail(req.context, **params)
        for host in discover_hosts:
            if host.get('mac'):
                hosts_mac.append(host['mac'])
        return hosts_mac

    def _get_discover_host_by_mac(self, req, host_mac):
        params = dict()
        discover_hosts = \
            registry.get_discover_hosts_detail(req.context, **params)
        for host in discover_hosts:
            if host.get('mac') == host_mac:
                return host
        return

    @utils.mutating
    def add_pxe_host(self, req, host_meta):
        """
        Adds a new pxe host to Daisy

        :param req: The WSGI/Webob Request object
        :param host_meta: Mapping of metadata about host

        :raises HTTPBadRequest if x-host-name is missing
        """
        self._enforce(req, 'add_pxe_host')
        LOG.warning("host_meta: %s" % host_meta)
        if not host_meta.get('mac'):
            msg = "MAC parameter can not be None."
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

        self.validate_mac_format(host_meta['mac'])
        pxe_hosts_mac = self._get_discover_host_mac(req)
        if host_meta['mac'] in pxe_hosts_mac:
            host = self._get_discover_host_by_mac(req, host_meta['mac'])
            host_meta = registry.update_discover_host_metadata(
                req.context, host['id'], host_meta)
            return {'host_meta': host_meta}

        if not host_meta.get('status', None):
            host_meta['status'] = 'None'

        try:
            pxe_host_info = \
                registry.add_discover_host_metadata(req.context, host_meta)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return {'host_meta': pxe_host_info}

    @utils.mutating
    def update_pxe_host(self, req, id, host_meta):
        """
        Update a new pxe host to Daisy
        """
        self._enforce(req, 'update_pxe_host')
        if not host_meta.get('mac'):
            msg = "MAC parameter can not be None."
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

        self.validate_mac_format(host_meta['mac'])
        orig_host_meta = registry.get_discover_host_metadata(req.context, id)
        try:
            if host_meta['mac'] == orig_host_meta['mac']:
                host_meta = registry.update_discover_host_metadata(
                    req.context, id, host_meta)

        except exception.Invalid as e:
            msg = (_("Failed to update discover host metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find discover host to update: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update discover host: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.error(utils.exception_to_str(e))
            raise HTTPConflict(body=_('Host operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('host.update', host_meta)

        return {'host_meta': host_meta}

    def _host_ipmi_check(self, host_id, host_meta):
        ipmi_check_result = {}
        if host_meta['os_status'] == 'active':
            ipmi_check_result['ipmi_check_result'] = \
                'active host do not need ipmi check'
            LOG.info('active host %s do not need ipmi '
                     'check' % host_id)
        else:
            ipmi_ip = host_meta.get('ipmi_addr', None)
            ipmi_user = host_meta.get('ipmi_user', None)
            ipmi_password = host_meta.get('ipmi_passwd', None)
            ipmi_config = [{'ipmi address': ipmi_ip},
                           {'ipmi user': ipmi_user}
                           ]
            for i in ipmi_config:
                if not i.values()[0]:
                    ipmi_check_result['ipmi_check_result'] = \
                        "No %s configed for host %s, please " \
                        "check" % (i.keys()[0], host_id)
                    LOG.info('No %s configed for host %s' %
                             (i.keys()[0], host_id))
                    return ipmi_check_result
            cmd = 'ipmitool -I lanplus -H %s  -U %s -P %s chassis ' \
                  'power status' % (ipmi_ip, ipmi_user, ipmi_password)
            obj = subprocess.Popen(cmd,
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            (stdoutput, erroutput) = obj.communicate()
            if 'Chassis Power is on' in stdoutput:
                ipmi_check_result['ipmi_check_result'] = \
                    'ipmi check successfully'
                LOG.info('host %s ipmi check '
                         'successfully' % host_id)
            elif 'Unable to get Chassis Power Status' in erroutput:
                ipmi_check_result['ipmi_check_result'] = \
                    'ipmi check failed'
                LOG.info('host %s ipmi check failed' % host_id)
        return ipmi_check_result

    @utils.mutating
    def host_check(self, req, host_meta):
        host_id = host_meta['id']
        orig_host_meta = self.get_host_meta_or_404(req, host_id)
        check_item = host_meta['check_item']
        if check_item == 'ipmi':
            path = os.path.join(os.path.abspath(os.path.dirname(
                os.path.realpath(__file__))), 'ext')
            for root, dirs, names in os.walk(path):
                filename = 'router.py'
                if filename in names:
                    ext_name = root.split(path)[1].strip('/')
                    ext_func = "%s.api.hosts" % ext_name
                    extension = importutils.import_module(
                        'daisy.api.v1.ext.%s' % ext_func)
                    if 'check_hwm_host_with_ipmi' in dir(extension):
                        ipmi_check_result = extension.check_hwm_host_with_ipmi(
                            host_id, orig_host_meta)
                        if ipmi_check_result:
                            return {'check_result': ipmi_check_result}
            ipmi_check_result = self._host_ipmi_check(host_id, orig_host_meta)
            return {'check_result': ipmi_check_result}


class HostDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["host_meta"] = utils.get_host_meta(request)
        return result

    def add_host(self, request):
        return self._deserialize(request)

    def update_host(self, request):
        return self._deserialize(request)

    def discover_host(self, request):
        return self._deserialize(request)

    def add_discover_host(self, request):
        return self._deserialize(request)

    def update_discover_host(self, request):
        return self._deserialize(request)

    def add_pxe_host(self, request):
        return self._deserialize(request)

    def update_pxe_host(self, request):
        return self._deserialize(request)

    def host_check(self, request):
        return self._deserialize(request)


class HostSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_host(self, response, result):
        host_meta = result['host_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host=host_meta))
        return response

    def delete_host(self, response, result):
        host_meta = result['host_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host=host_meta))
        return response

    def get_host(self, response, result):
        host_meta = result['host_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host=host_meta))
        return response

    def discover_host(self, response, result):
        host_meta = result
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host_meta))
        return response

    def add_discover_host(self, response, result):
        host_meta = result['host_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host=host_meta))
        return response

    def update_discover_host(self, response, result):
        host_meta = result['host_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host=host_meta))

    def get_discover_host_detail(self, response, result):
        host_meta = result['host_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host=host_meta))
        return response

    def add_pxe_host(self, response, result):
        host_meta = result['host_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host=host_meta))
        return response

    def update_pxe_host(self, response, result):
        host_meta = result['host_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host=host_meta))

    def host_check(self, response, result):
        host_meta = result['check_result']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host=host_meta))


def create_resource():
    """Hosts resource factory method"""
    deserializer = HostDeserializer()
    serializer = HostSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
