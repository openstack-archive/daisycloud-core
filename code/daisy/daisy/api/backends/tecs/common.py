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
/install endpoint for tecs API
"""
import os
import copy
import subprocess
import re
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden
from daisy import i18n
from daisy.common import utils

from daisy.common import exception
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn
from daisyclient.v1 import client as daisy_client
import ConfigParser


STR_MASK = '*' * 8
LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

daisy_tecs_path = '/var/lib/daisy/tecs/'
tecs_install_path = '/home/tecs_install'

TECS_STATE = {
    'INIT': 'init',
    'INSTALLING': 'installing',
    'ACTIVE': 'active',
    'INSTALL_FAILED': 'install-failed',
    'UNINSTALLING': 'uninstalling',
    'UNINSTALL_FAILED': 'uninstall-failed',
    'UPDATING': 'updating',
    'UPDATE_FAILED': 'update-failed',
}


def get_daisyclient():
    """Get Daisy client instance."""
    config_daisy = ConfigParser.ConfigParser()
    config_daisy.read("/etc/daisy/daisy-api.conf")
    daisy_port = config_daisy.get("DEFAULT", "bind_port")
    args = {'version': 1.0, 'endpoint': 'http://127.0.0.1:' + daisy_port}
    return daisy_client.Client(**args)


def mkdir_tecs_install(host_ips=None):
    if not host_ips:
        cmd = "mkdir -p %s" % tecs_install_path
        daisy_cmn.subprocess_call(cmd)
        return
    for host_ip in host_ips:
        cmd = 'clush -S -w %s "mkdir -p %s"' % (host_ip, tecs_install_path)
        daisy_cmn.subprocess_call(cmd)


def _get_cluster_network(cluster_networks, network_name):
    network = [cn for cn in cluster_networks if cn['name'] == network_name]
    if not network or not network[0]:
        msg = "network %s is not exist" % (network_name)
        raise exception.InvalidNetworkConfig(msg)
    else:
        return network[0]


def get_host_interface_by_network(host_detail, network_name):
    host_detail_info = copy.deepcopy(host_detail)
    interface_list = [hi for hi in host_detail_info['interfaces']
                      for assigned_network in hi['assigned_networks']
                      if assigned_network and
                      network_name == assigned_network['name']]
    interface = {}
    if interface_list:
        interface = interface_list[0]

    if not interface and 'MANAGEMENT' == network_name:
        msg = "network %s of host %s is not exist" % (
            network_name, host_detail_info['id'])
        raise exception.InvalidNetworkConfig(msg)

    return interface


def get_host_network_ip(req, host_detail, cluster_networks, network_name):
    interface_network_ip = ''
    host_interface = get_host_interface_by_network(host_detail, network_name)
    if host_interface:
        network = _get_cluster_network(cluster_networks, network_name)
        assigned_network = daisy_cmn.get_assigned_network(req,
                                                          host_interface['id'],
                                                          network['id'])
        interface_network_ip = assigned_network['ip']

    if not interface_network_ip and 'MANAGEMENT' == network_name:
        msg = "%s network ip of host %s can't be empty" % (
            network_name, host_detail['id'])
        raise exception.InvalidNetworkConfig(msg)
    return interface_network_ip


def get_storage_name_ip_dict(req, cluster_id, network_type):
    name_ip_list = []
    ip_list = []
    roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
    cluster_networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)

    networks_list = [network for network in cluster_networks
                     if network['network_type'] == network_type]
    networks_name_list = [network['name'] for network in networks_list]

    for role in roles:
        role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
        for role_host in role_hosts:
            host_detail = daisy_cmn.get_host_detail(req, role_host['host_id'])
            for network_name in networks_name_list:
                ip = get_host_network_ip(req, host_detail, cluster_networks,
                                         network_name)

                name_ip_dict = {}
                if ip and ip not in ip_list:
                    ip_list.append(ip)
                    name_ip_dict.update({host_detail['name'] + '.' +
                                         network_name: ip})
                    name_ip_list.append(name_ip_dict)

    return name_ip_list


def get_network_netmask(cluster_networks, network_name):
    network = _get_cluster_network(cluster_networks, network_name)
    cidr = network['cidr']
    if not cidr:
        msg = "cidr of network %s is not exist" % (network_name)
        raise exception.InvalidNetworkConfig(msg)

    netmask = daisy_cmn.cidr_to_netmask(cidr)
    if not netmask:
        msg = "netmask of network %s is not exist" % (network_name)
        raise exception.InvalidNetworkConfig(msg)
    return netmask


# every host only have one gateway
def get_network_gateway(cluster_networks, network_name):
    network = _get_cluster_network(cluster_networks, network_name)
    gateway = network['gateway']
    return gateway


def get_network_cidr(cluster_networks, network_name):
    network = _get_cluster_network(cluster_networks, network_name)
    cidr = network['cidr']
    if not cidr:
        msg = "cidr of network %s is not exist" % (network_name)
        raise exception.InvalidNetworkConfig(msg)
    return cidr


def get_mngt_network_vlan_id(cluster_networks):
    mgnt_vlan_id = ""
    management_network = [network for network in cluster_networks if network[
        'network_type'] == 'MANAGEMENT']
    if (not management_network or
            not management_network[0] or
            # not management_network[0].has_key('vlan_id')):
            'vlan_id' not in management_network[0]):
        msg = "can't get management network vlan id"
        raise exception.InvalidNetworkConfig(msg)
    else:
        mgnt_vlan_id = management_network[0]['vlan_id']
    return mgnt_vlan_id


def get_network_vlan_id(cluster_networks, network_type):
    vlan_id = ""
    general_network = [network for network in cluster_networks
                       if network['network_type'] == network_type]
    if (not general_network or not general_network[0] or
            # not general_network[0].has_key('vlan_id')):
            'vlan_id' not in general_network[0]):
        msg = "can't get %s network vlan id" % network_type
        raise exception.InvalidNetworkConfig(msg)
    else:
        vlan_id = general_network[0]['vlan_id']
    return vlan_id


def sort_interfaces_by_pci(networks, host_detail):
    """
    Sort interfaces by pci segment, if interface type is bond,
    user the pci of first memeber nic.This function is fix bug for
    the name length of ovs virtual port, because if the name length large than
    15 characters, the port will create failed.
    :param interfaces: interfaces info of the host
    :return:
    """
    interfaces = eval(host_detail.get('interfaces', None)) \
        if isinstance(host_detail, unicode) else \
        host_detail.get('interfaces', None)
    if not interfaces:
        LOG.info("This host has no interfaces info.")
        return host_detail

    tmp_interfaces = copy.deepcopy(interfaces)

    slaves_name_list = []
    for interface in tmp_interfaces:
        if interface.get('type', None) == "bond" and\
                interface.get('slave1', None) and\
                interface.get('slave2', None):
            slaves_name_list.append(interface['slave1'])
            slaves_name_list.append(interface['slave2'])

    for interface in interfaces:
        if interface.get('name') not in slaves_name_list:
            vlan_id_len_list = [len(network['vlan_id'])
                                for assigned_network in interface.get(
                                    'assigned_networks', [])
                                for network in networks
                                if assigned_network.get('name') ==
                                network.get('name') and network.get('vlan_id')]
            max_vlan_id_len = max(vlan_id_len_list) if vlan_id_len_list else 0
            interface_name_len = len(interface['name'])
            redundant_bit = interface_name_len + max_vlan_id_len - 14
            interface['name'] = interface['name'][
                redundant_bit:] if redundant_bit > 0 else interface['name']
    return host_detail


def check_and_get_tecs_version(daisy_tecs_pkg_path):
    tecs_version_pkg_file = ""
    get_tecs_version_pkg = "ls %s| grep ^ZXTECS.*\.bin$" % daisy_tecs_pkg_path
    obj = subprocess.Popen(get_tecs_version_pkg,
                           shell=True,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    if stdoutput:
        tecs_version_pkg_name = stdoutput.split('\n')[0]
        tecs_version_pkg_file = daisy_tecs_pkg_path + tecs_version_pkg_name
        chmod_for_tecs_version = 'chmod +x %s' % tecs_version_pkg_file
        daisy_cmn.subprocess_call(chmod_for_tecs_version)
    return tecs_version_pkg_file


def get_service_disk_list(req, params):
    try:
        service_disks = registry.list_service_disk_metadata(
            req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return service_disks


def get_cinder_volume_list(req, params):
    try:
        cinder_volumes = registry.list_cinder_volume_metadata(
            req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return cinder_volumes


def mask_string(unmasked, mask_list=None, replace_list=None):
    """
    Replaces words from mask_list with MASK in unmasked string.
    If words are needed to be transformed before masking, transformation
    could be describe in replace list. For example [("'","'\\''")]
    replaces all ' characters with '\\''.
    """
    mask_list = mask_list or []
    replace_list = replace_list or []

    masked = unmasked
    for word in sorted(mask_list, lambda x, y: len(y) - len(x)):
        if not word:
            continue
        for before, after in replace_list:
            word = word.replace(before, after)
        masked = masked.replace(word, STR_MASK)
    return masked


def run_scrip(script, ip=None, password=None, msg=None):
    try:
        _run_scrip(script, ip, password)
    except:
        msg1 = 'Error occurred during running scripts.'
        message = msg1 + msg if msg else msg1
        LOG.error(message)
        raise HTTPForbidden(explanation=message)
    else:
        LOG.info('Running scripts successfully!')


def _run_scrip(script, ip=None, password=None):
    mask_list = []
    repl_list = [("'", "'\\''")]
    script = "\n".join(script)
    _PIPE = subprocess.PIPE
    if ip:
        cmd = ["sshpass", "-p", "%s" % password,
               "ssh", "-o StrictHostKeyChecking=no",
               "%s" % ip, "bash -x"]
    else:
        cmd = ["bash", "-x"]
    environ = os.environ
    environ['LANG'] = 'en_US.UTF8'
    obj = subprocess.Popen(cmd, stdin=_PIPE, stdout=_PIPE, stderr=_PIPE,
                           close_fds=True, shell=False, env=environ)

    script = "function t(){ exit $? ; } \n trap t ERR \n" + script
    out, err = obj.communicate(script)
    masked_out = mask_string(out, mask_list, repl_list)
    masked_err = mask_string(err, mask_list, repl_list)
    if obj.returncode:
        pattern = (r'^ssh\:')
        if re.search(pattern, err):
            LOG.error(_("Network error occured when run script."))
            raise exception.NetworkError(masked_err, stdout=out, stderr=err)
        else:
            msg = ('Failed to run remote script, stdout: %s\nstderr: %s' %
                   (masked_out, masked_err))
            LOG.error(msg)
            raise exception.ScriptRuntimeError(msg, stdout=out, stderr=err)
    return obj.returncode, out


def inform_provider_cloud_state(context, cluster_id, **kwargs):
    params = dict()
    daisyclient = get_daisyclient()
    cluster = registry.get_cluster_metadata(context, cluster_id)
    params['operation'] = kwargs.get('operation')
    params['name'] = cluster.get('name')
    params['url'] = "http://" + cluster.get('public_vip')
    params['provider_ip'] = cluster.get('hwm_ip')
    daisyclient.node.cloud_state(**params)


def get_disk_array_nodes_addr(req, cluster_id):
    controller_ha_nodes = {}
    computer_ips = set()

    roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
    cluster_networks =\
        daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    for role in roles:
        if role['deployment_backend'] != daisy_cmn.tecs_backend_name:
            continue
        role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
        for role_host in role_hosts:
            # host has installed tecs are exclusive
            if (role_host['status'] == TECS_STATE['ACTIVE'] or
                    role_host['status'] == TECS_STATE['UPDATING'] or
                    role_host['status'] == TECS_STATE['UPDATE_FAILED']):
                continue
            host_detail = daisy_cmn.get_host_detail(req,
                                                    role_host['host_id'])
            host_ip = get_host_network_ip(req,
                                          host_detail,
                                          cluster_networks,
                                          'MANAGEMENT')
            if role['name'] == "CONTROLLER_HA":
                min_mac = utils.get_host_min_mac(host_detail['interfaces'])
                controller_ha_nodes[host_ip] = min_mac
            if role['name'] == "COMPUTER":
                computer_ips.add(host_ip)
    return {'ha': controller_ha_nodes, 'computer': computer_ips}


def get_ctl_ha_nodes_min_mac(req, cluster_id):
    '''
    ctl_ha_nodes_min_mac = {'host_name1':'min_mac1', ...}
    '''
    ctl_ha_nodes_min_mac = {}
    roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
    cluster_networks =\
        daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    for role in roles:
        if role['deployment_backend'] != daisy_cmn.tecs_backend_name:
            continue
        role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
        for role_host in role_hosts:
            # host has installed tecs are exclusive
            if (role_host['status'] == TECS_STATE['ACTIVE'] or
                    role_host['status'] == TECS_STATE['UPDATING'] or
                    role_host['status'] == TECS_STATE['UPDATE_FAILED']):
                continue
            host_detail = daisy_cmn.get_host_detail(req,
                                                    role_host['host_id'])
            host_name = host_detail['name']
            if role['name'] == "CONTROLLER_HA":
                min_mac = utils.get_host_min_mac(host_detail['interfaces'])
                ctl_ha_nodes_min_mac[host_name] = min_mac
    return ctl_ha_nodes_min_mac


class TecsShellExector(object):

    """
    Class config task before install tecs bin.
    """

    def __init__(self, mgnt_ip, task_type, params={}):
        self.task_type = task_type
        self.mgnt_ip = mgnt_ip
        self.params = params
        self.clush_cmd = ""
        self.rpm_name =\
            daisy_cmn.get_rpm_package_by_name(daisy_tecs_path,
                                              'network-configuration')
        self.NETCFG_RPM_PATH = daisy_tecs_path + self.rpm_name
        self.oper_type = {
            'install_rpm': self._install_netcfg_rpm,
            'uninstall_rpm': self._uninstall_netcfg_rpm,
            'update_rpm': self._update_netcfg_rpm,
        }
        self.oper_shell = {
            'CMD_SSHPASS_PRE': "sshpass -p ossdbg1 %(ssh_ip)s %(cmd)s",
            'CMD_RPM_UNINSTALL': "rpm -e network-configuration",
            'CMD_RPM_INSTALL': "rpm -i /home/%(rpm)s" % {'rpm': self.rpm_name},
            'CMD_RPM_UPDATE': "rpm -U /home/%(rpm)s" % {'rpm': self.rpm_name},
            'CMD_RPM_SCP': "scp -o StrictHostKeyChecking=no \
                                        %(path)s root@%(ssh_ip)s:/home" %
                           {'path': self.NETCFG_RPM_PATH, 'ssh_ip': mgnt_ip}
        }
        LOG.info(_("<<<Network configuration rpm is %s>>>" % self.rpm_name))
        self._execute()

    def _uninstall_netcfg_rpm(self):
        self.clush_cmd = self.oper_shell['CMD_SSHPASS_PRE'] % \
            {"ssh_ip": "ssh -o StrictHostKeyChecking=no " + self.mgnt_ip,
                "cmd": self.oper_shell['CMD_RPM_UNINSTALL']}
        subprocess.check_output(
            self.clush_cmd, shell=True, stderr=subprocess.STDOUT)

    def _update_netcfg_rpm(self):
        self.clush_cmd = self.oper_shell['CMD_SSHPASS_PRE'] % \
            {"ssh_ip": "ssh -o StrictHostKeyChecking=no " + self.mgnt_ip,
                "cmd": self.oper_shell['CMD_RPM_UPDATE']}
        subprocess.check_output(
            self.clush_cmd, shell=True, stderr=subprocess.STDOUT)

    def _install_netcfg_rpm(self):
        if not os.path.exists(self.NETCFG_RPM_PATH):
            LOG.error(_("<<<Rpm %s not exist>>>" % self.NETCFG_RPM_PATH))
            return

        self.clush_cmd = "%s;%s" % \
            (self.oper_shell['CMD_SSHPASS_PRE'] %
             {"ssh_ip": "", "cmd": self.oper_shell['CMD_RPM_SCP']},
             self.oper_shell['CMD_SSHPASS_PRE'] %
             {"ssh_ip": "ssh -o StrictHostKeyChecking=no " +
              self.mgnt_ip, "cmd": self.oper_shell['CMD_RPM_INSTALL']})
        subprocess.check_output(
            self.clush_cmd, shell=True, stderr=subprocess.STDOUT)

    def _execute(self):
        try:
            if not self.task_type or not self.mgnt_ip:
                LOG.error(
                    _("<<<TecsShellExector::execute, input params invalid on \
                        %s!>>>" % self.mgnt_ip, ))
                return

            self.oper_type[self.task_type]()
        except subprocess.CalledProcessError as e:
            LOG.warn(_("<<<TecsShellExector::execute:Execute command failed on\
                %s! Reason:%s>>>" % (
                self.mgnt_ip, e.output.strip())))
        except Exception as e:
            LOG.exception(_(e.message))
        else:
            LOG.info(_("<<<TecsShellExector::execute:Execute command:\
                            %s,successful on %s!>>>" % (
                self.clush_cmd, self.mgnt_ip)))
