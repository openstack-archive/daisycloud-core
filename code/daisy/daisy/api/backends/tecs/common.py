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
import time
import re
import traceback
import webob.exc
from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden

from threading import Thread

from daisy import i18n
from daisy import notifier

from daisy.api import policy
import daisy.api.v1

from daisy.common import exception
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn


try:
    import simplejson as json
except ImportError:
    import json

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

daisy_tecs_path = '/var/lib/daisy/tecs/'

TECS_STATE = {
    'INIT' : 'init',
    'INSTALLING' : 'installing',
    'ACTIVE' : 'active',
    'INSTALL_FAILED': 'install-failed',
    'UNINSTALLING': 'uninstalling',
    'UNINSTALL_FAILED': 'uninstall-failed',
    'UPDATING': 'updating',
    'UPDATE_FAILED': 'update-failed',
}


def _get_cluster_network(cluster_networks, network_name):
    network = [cn for cn in cluster_networks 
                        if  cn['name'] in network_name]
    if not network or not network[0]:
        msg = "network %s is not exist" % (network_name)
        raise exception.InvalidNetworkConfig(msg)
    else:
        return network[0]

def get_host_interface_by_network(host_detail, network_name):
    host_detail_info = copy.deepcopy(host_detail)
    interface_list = [hi for hi in host_detail_info['interfaces'] 
                        for assigned_network in hi['assigned_networks']
                        if assigned_network and network_name == assigned_network['name']]
    interface = {}
    if interface_list:
        interface = interface_list[0]
        
    if not interface and 'MANAGEMENT' == network_name:
        msg = "network %s of host %s is not exist" % (network_name, host_detail_info['id'])
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

    if not interface_network_ip and  'MANAGEMENT' == network_name :
        msg = "%s network ip of host %s can't be empty" % (network_name, host_detail['id'])
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
    if not gateway and 'MANAGEMENT' == network_name:
        msg = "gateway of network %s can't be empty" % (network_name)
        raise exception.InvalidNetworkConfig(msg)
    return gateway

def get_mngt_network_vlan_id(cluster_networks):
    mgnt_vlan_id = ""
    management_network = [network for network in cluster_networks if network['network_type'] == 'MANAGEMENT']
    if (not management_network or
       not management_network[0] or
       not management_network[0].has_key('vlan_id')):
        msg = "can't get management network vlan id"
        raise exception.InvalidNetworkConfig(msg)
    else:
        mgnt_vlan_id = management_network[0]['vlan_id']
    return  mgnt_vlan_id


def get_network_vlan_id(cluster_networks, network_type):
    vlan_id = ""
    general_network = [network for network in cluster_networks
                       if network['network_type'] == network_type]
    if (not general_network or not general_network[0] or
       not general_network[0].has_key('vlan_id')):
        msg = "can't get %s network vlan id" % network_type
        raise exception.InvalidNetworkConfig(msg)
    else:
        vlan_id = general_network[0]['vlan_id']
    return vlan_id


def sort_interfaces_by_pci(host_detail):
    """
    Sort interfaces by pci segment, if interface type is bond,
    user the pci of first memeber nic.This function is fix bug for
    the name length of ovs virtual port, because if the name length large than
    15 characters, the port will create failed.
    :param interfaces: interfaces info of the host
    :return:
    """
    interfaces = eval(host_detail.get('interfaces', None)) \
        if isinstance(host_detail, unicode) else host_detail.get('interfaces', None)
    if not interfaces:
        LOG.info("This host don't have /interfaces info.")
        return host_detail

    tmp_interfaces = copy.deepcopy(interfaces)
    if not [interface for interface in tmp_interfaces
            if interface.get('name', None) and len(interface['name']) > 8]:
        LOG.info("The interfaces name of host is all less than 9 character, no need sort.")
        return host_detail

    # add pci segment for the bond nic, the pci is equal to the first member nic pci
    slaves_name_list = []
    for interface in tmp_interfaces:
        if interface.get('type', None) == "bond" and \
            interface.get('slave1', None) and interface.get('slave2', None):

            slaves_name_list.append(interface['slave1'])
            slaves_name_list.append(interface['slave2'])
            first_member_nic_name = interface['slave1']

            tmp_pci = [interface_tmp['pci']
                       for interface_tmp in tmp_interfaces
                       if interface_tmp.get('name', None) and
                       interface_tmp.get('pci', None) and
                       interface_tmp['name'] == first_member_nic_name]

            if len(tmp_pci) != 1:
                LOG.error("This host have two nics with same pci.")
                continue
            interface['pci'] = tmp_pci[0]

    tmp_interfaces = [interface for interface in tmp_interfaces
                      if interface.get('name', None) and
                      interface['name'] not in slaves_name_list]

    tmp_interfaces = sorted(tmp_interfaces, key = lambda interface: interface['pci'])
    for index in range(0, len(tmp_interfaces)):
        for interface in interfaces:
            if interface['name'] != tmp_interfaces[index]['name']:
                continue

            interface['name'] = "b" + str(index) if interface['type'] == "bond" else "e" + str(index)

    tmp_host_detail = copy.deepcopy(host_detail)
    tmp_host_detail.update({'interfaces': interfaces})
    return tmp_host_detail
    
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
        service_disks = registry.list_service_disk_metadata(req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return service_disks

def get_cinder_volume_list(req, params):
    try:
        cinder_volumes = registry.list_cinder_volume_metadata(req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return cinder_volumes


def get_network_configuration_rpm_name():
    cmd = "ls %s | grep ^network-configuration.*\.rpm" % daisy_tecs_path
    try:
        network_rpm_name = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.STDOUT).split('\n')[0]
    except subprocess.CalledProcessError:
        msg = _("Get network-configuration rpm name by subprocess failed!")
        raise exception.SubprocessCmdFailed(message=msg) 
    return network_rpm_name


def run_scrip(script, ip=None, password=None):
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
    return out, err


class TecsShellExector(object):
    """
    Class config task before install tecs bin.
    """
    def __init__(self, mgnt_ip, task_type,  params={}):
        self.task_type = task_type
        self.mgnt_ip = mgnt_ip
        self.params = params
        self.clush_cmd = ""
        self.rpm_name = get_network_configuration_rpm_name()
        self.NETCFG_RPM_PATH = daisy_tecs_path + self.rpm_name
        self.oper_type = {
            'install_rpm' : self._install_netcfg_rpm,
            'uninstall_rpm' : self._uninstall_netcfg_rpm,
            'update_rpm' : self._update_netcfg_rpm,
        }
        self.oper_shell = {
            'CMD_SSHPASS_PRE': "sshpass -p ossdbg1 %(ssh_ip)s %(cmd)s",
            'CMD_RPM_UNINSTALL': "rpm -e network-configuration",
            'CMD_RPM_INSTALL': "rpm -i /home/%(rpm)s" % {'rpm': self.rpm_name},
            'CMD_RPM_UPDATE': "rpm -U /home/%(rpm)s" % {'rpm': self.rpm_name},
            'CMD_RPM_SCP': "scp -o StrictHostKeyChecking=no %(path)s root@%(ssh_ip)s:/home" %
                           {'path': self.NETCFG_RPM_PATH, 'ssh_ip': mgnt_ip}
        }
        LOG.info(_("<<<Network configuration rpm is %s>>>" % self.rpm_name))
        self._execute()

    def _uninstall_netcfg_rpm(self):
        self.clush_cmd = self.oper_shell['CMD_SSHPASS_PRE'] % \
                        {"ssh_ip":"ssh -o StrictHostKeyChecking=no " + self.mgnt_ip, "cmd":self.oper_shell['CMD_RPM_UNINSTALL']}
        subprocess.check_output(self.clush_cmd, shell = True, stderr=subprocess.STDOUT)

    def _update_netcfg_rpm(self):
        self.clush_cmd = self.oper_shell['CMD_SSHPASS_PRE'] % \
                        {"ssh_ip":"ssh -o StrictHostKeyChecking=no " + self.mgnt_ip, "cmd":self.oper_shell['CMD_RPM_UPDATE']}
        subprocess.check_output(self.clush_cmd, shell = True, stderr=subprocess.STDOUT)

    def _install_netcfg_rpm(self):
        if not os.path.exists(self.NETCFG_RPM_PATH):
            LOG.error(_("<<<Rpm %s not exist>>>" % self.NETCFG_RPM_PATH))
            return

        self.clush_cmd = "%s;%s" % \
                        (self.oper_shell['CMD_SSHPASS_PRE'] %
                            {"ssh_ip":"", "cmd":self.oper_shell['CMD_RPM_SCP']}, \
                         self.oper_shell['CMD_SSHPASS_PRE'] %
                            {"ssh_ip":"ssh -o StrictHostKeyChecking=no " + self.mgnt_ip, "cmd":self.oper_shell['CMD_RPM_INSTALL']})
        subprocess.check_output(self.clush_cmd, shell = True, stderr=subprocess.STDOUT)

    def _execute(self):
        try:
            if not self.task_type or not self.mgnt_ip :
                LOG.error(_("<<<TecsShellExector::execute, input params invalid on %s!>>>" % self.mgnt_ip, ))
                return

            self.oper_type[self.task_type]()
        except subprocess.CalledProcessError as e:
            LOG.warn(_("<<<TecsShellExector::execute:Execute command failed on %s! Reason:%s>>>" % (self.mgnt_ip, e.output.strip())))
        except Exception as e:
            LOG.exception(_(e.message))
        else:
            LOG.info(_("<<<TecsShellExector::execute:Execute command:%s,successful on %s!>>>" % (self.clush_cmd, self.mgnt_ip)))
