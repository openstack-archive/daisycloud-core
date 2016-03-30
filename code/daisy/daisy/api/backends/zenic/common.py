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
import os
import copy
import subprocess
import time

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

daisy_zenic_path = '/var/lib/daisy/zenic/'
ZENIC_STATE = {
    'INIT' : 'init',
    'INSTALLING' : 'installing',
    'ACTIVE' : 'active',
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
    host_deploy_network = get_host_interface_by_network(host_detail, 'DEPLOYMENT')
    host_deploy_ip = get_host_network_ip(req, host_detail, cluster_networks, 'DEPLOYMENT')
    if not host_deploy_ip:
        msg = "deployment ip of host %s can't be empty" % host_detail['id']
        raise exception.InvalidNetworkConfig(msg)
    host_deploy_macname = host_deploy_network['name']
    if not host_deploy_macname:
        msg = "deployment macname of host %s can't be empty" % host_detail['id']
        raise exception.InvalidNetworkConfig(msg)

    host_mgt_ip = get_host_network_ip(req, host_detail, cluster_networks, 'MANAGEMENT')
    if not host_mgt_ip:
        msg = "management ip of host %s can't be empty" % host_detail['id']
        raise exception.InvalidNetworkConfig(msg)
        
    memmode = 'tiny'
    host_memory = 0
    
    if host_detail.has_key('memory'):
        host_memory = (int(host_detail['memory']['total'].strip().split()[0]))/(1024*1024)
        
    if host_memory < 8:
        memmode = 'tiny'
    elif host_memory < 16:
        memmode = 'small'
    elif host_memory < 32:
        memmode = 'medium'
    else:
        memmode = 'large'
    
    
    deploy_node_cfg = {}
    deploy_node_cfg.update({'hostid':host_detail['id']})
    deploy_node_cfg.update({'hostname':host_detail['name']})
    deploy_node_cfg.update({'nodeip':host_deploy_ip})
    deploy_node_cfg.update({'MacName':host_deploy_macname})
    deploy_node_cfg.update({'memmode':memmode})
    deploy_node_cfg.update({'mgtip':host_mgt_ip})    
    return deploy_node_cfg

def get_roles_and_hosts_list(req, cluster_id):    
    roles_id_list = set()
    hosts_id_list = set()    
    hosts_list = []

    cluster_networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    roles = daisy_cmn.get_cluster_roles_detail(req,cluster_id)
    for role in roles:
        if role['deployment_backend'] != daisy_cmn.zenic_backend_name:
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
    
def check_and_get_zenic_version(daisy_zenic_pkg_path):
    zenic_version_pkg_file = ""
    zenic_version_pkg_name = ""
    get_zenic_version_pkg = "ls %s| grep ^ZENIC.*\.zip$" % daisy_zenic_pkg_path
    obj = subprocess.Popen(get_zenic_version_pkg,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    if stdoutput:
        zenic_version_pkg_name = stdoutput.split('\n')[0]
        zenic_version_pkg_file = daisy_zenic_pkg_path + zenic_version_pkg_name
        chmod_for_zenic_version = 'chmod +x %s' % zenic_version_pkg_file
        daisy_cmn.subprocess_call(chmod_for_zenic_version)
    return (zenic_version_pkg_file,zenic_version_pkg_name)
            
class ZenicShellExector():
    """
    Class config task before install zenic bin.
    """
    def __init__(self, mgt_ip, task_type,  params={}):
        self.task_type = task_type
        self.mgt_ip = mgt_ip
        self.params = params
        self.clush_cmd = ""        
        self.PKG_NAME = self.params['pkg_name']
        self.PKG_PATH = daisy_zenic_path +  self.PKG_NAME
        self.CFG_PATH =daisy_zenic_path + mgt_ip + "_zenic.conf"
        self.oper_type = {
            'install' : self._install_pkg
        }
        self.oper_shell = {
            'CMD_SSHPASS_PRE' : "sshpass -p ossdbg1 %(ssh_ip)s %(cmd)s",
            'CMD_CFG_SCP' : "scp %(path)s root@%(ssh_ip)s:/etc/zenic/config" %
                            {'path': self.CFG_PATH, 'ssh_ip':mgt_ip},
            'CMD_PKG_UNZIP' : "unzip /home/workspace/%(pkg_name)s -d /home/workspace/PKG" % {'pkg_name':self.PKG_NAME},
            'CMD_PKG_SCP' : "scp %(path)s root@%(ssh_ip)s:/home/workspace/" %
                            {'path': self.PKG_PATH, 'ssh_ip':mgt_ip}
        }

        self._execute()

    def _install_pkg(self):
        if not os.path.exists(self.CFG_PATH):
            LOG.error(_("<<<CFG %s not exist>>>" % self.CFG_PATH))
            return
            
        if not os.path.exists(self.PKG_PATH):
            LOG.error(_("<<<PKG %s not exist>>>" % self.PKG_PATH))
            return
        
        self.clush_cmd = "%s;%s;%s" % \
                        (self.oper_shell['CMD_SSHPASS_PRE'] %
                            {"ssh_ip":"", "cmd":self.oper_shell['CMD_PKG_SCP']}, \
                         self.oper_shell['CMD_SSHPASS_PRE'] %
                            {"ssh_ip":"", "cmd":self.oper_shell['CMD_CFG_SCP']}, \
                         self.oper_shell['CMD_SSHPASS_PRE'] %
                            {"ssh_ip":"ssh " + self.mgt_ip, "cmd":self.oper_shell['CMD_PKG_UNZIP']})

        subprocess.check_output(self.clush_cmd, shell = True, stderr=subprocess.STDOUT)

    def _execute(self):
        try:
            if not self.task_type or not self.mgt_ip :
                LOG.error(_("<<<ZenicShellExector::execute, input params invalid!>>>"))
                return

            self.oper_type[self.task_type]()
        except subprocess.CalledProcessError as e:
            LOG.warn(_("<<<ZenicShellExector::execute:Execute command failed! Reason:%s>>>" % e.output.strip()))
        except Exception as e:
            LOG.exception(_(e.message))
        else:
            LOG.info(_("<<<ZenicShellExector::execute:Execute command:%s,successful!>>>" % self.clush_cmd))
