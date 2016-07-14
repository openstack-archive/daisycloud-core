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
/install endpoint for kolla API
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
from webob.exc import HTTPServerError

from threading import Thread, Lock
import threading

from daisy import i18n
from daisy import notifier

from daisy.api import policy
import daisy.api.v1

from daisy.common import exception
import daisy.registry.client.v1.api as registry
from daisy.api.backends.kolla import config
from daisy.api.backends import driver
from daisy.api.network_api import network as neutron
from ironicclient import client as ironic_client
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.kolla.common as kolla_cmn
import re
import commands

try:
    import simplejson as json
except ImportError:
    import json

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE

CONF = cfg.CONF
install_opts = [
    cfg.StrOpt('max_parallel_os_number', default=10,
               help='Maximum number of hosts install os at the same time.'),
]
CONF.register_opts(install_opts)

CONF.import_opt('disk_formats', 'daisy.common.config', group='image_format')
CONF.import_opt('container_formats', 'daisy.common.config',
                group='image_format')
CONF.import_opt('image_property_quota', 'daisy.common.config')


host_os_status = {
    'INIT' : 'init',
    'INSTALLING' : 'installing',
    'ACTIVE' : 'active',
    'FAILED': 'install-failed'
}

kolla_state = kolla_cmn.KOLLA_STATE
daisy_kolla_path = kolla_cmn.daisy_kolla_path

install_kolla_progress=0.0
install_mutex = threading.Lock()

def update_progress_to_db(req, role_id_list, status, progress_percentage_step=0.0):
    """
    Write install progress and status to db, we use global lock object 'install_mutex'
    to make sure this function is thread safety.
    :param req: http req.
    :param role_id_list: Column neeb be update in role table.
    :param status: install status.
    :return:
    """

    global install_mutex
    global install_kolla_progress
    install_mutex.acquire(True)
    install_kolla_progress += progress_percentage_step
    role = {}
    for role_id in role_id_list:
        if 0 == cmp(status, kolla_state['INSTALLING']):
            role['status'] = status
            role['progress'] = install_kolla_progress
        if 0 == cmp(status,  kolla_state['INSTALL_FAILED']):
            role['status'] = status
        elif 0 == cmp(status, kolla_state['ACTIVE']):
            role['status'] = status
            role['progress'] = 100
        daisy_cmn.update_role(req, role_id, role)
    install_mutex.release()

def _ping_hosts_test(ips):
    ping_cmd = 'fping'
    for ip in set(ips):
        ping_cmd = ping_cmd + ' ' + ip
    obj = subprocess.Popen(ping_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    _returncode = obj.returncode
    if _returncode == 0 or _returncode == 1:
        ping_result = stdoutput.split('\n')
        unreachable_hosts = [result.split()[0] for result in ping_result if result and result.split()[2] != 'alive']
    else:
        msg = "ping failed beaceuse there is invlid ip in %s" % ips
        raise exception.InvalidIP(msg)
    return unreachable_hosts

def _check_ping_hosts(ping_ips, max_ping_times):
    if not ping_ips:
        LOG.info(_("no ip got for ping test"))
        return ping_ips
    ping_count = 0
    time_step = 5
    LOG.info(_("begin ping test for %s" % ','.join(ping_ips)))
    while True:
        if ping_count == 0:
            ips = _ping_hosts_test(ping_ips)
        else:
            ips = _ping_hosts_test(ips)

        ping_count += 1
        if ips:
            LOG.debug(_("ping host %s for %s times" % (','.join(ips), ping_count)))
            if ping_count >= max_ping_times:
                LOG.info(_("ping host %s timeout for %ss" % (','.join(ips), ping_count*time_step)))
                return ips
            time.sleep(time_step)
        else:
            LOG.info(_("ping host %s success" % ','.join(ping_ips)))
            time.sleep(120)
            LOG.info(_("120s after ping host %s success" % ','.join(ping_ips)))
            return ips

def _get_local_ip():
    (status, output) = commands.getstatusoutput('ifconfig')
    netcard_pattern = re.compile('\S*: ')
    ip_str = '([0-9]{1,3}\.){3}[0-9]{1,3}'
    # ip_pattern = re.compile('(inet %s)' % ip_str)
    pattern = re.compile(ip_str)
    local_ip = ''
    nic_ip = {}
    for netcard in re.finditer(netcard_pattern, str(output)):
        nic_name = netcard.group().split(': ')[0]
        if nic_name == "lo":
            continue
        ifconfig_nic_cmd = "ifconfig %s" % nic_name
        (status, output) = commands.getstatusoutput(ifconfig_nic_cmd)
        if status:
            continue
        ip = pattern.search(str(output))
        if ip and ip.group().split('.')[0] != "172" and ip.group() != "127.0.0.1":
            nic_ip[nic_name] = ip.group()
            local_ip = nic_ip[nic_name]
    return local_ip

def get_cluster_kolla_config(req, cluster_id):
    LOG.info(_("get kolla config from database..."))
    params = dict(limit=1000000)    
    mgt_ip_list = set() 
    kolla_config = {}
    docker_registry_ip = _get_local_ip()
    docker_registry = docker_registry_ip + ':4000'
    cluster_networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    
    all_roles = kolla_cmn.get_roles_detail(req)    
    
    roles = [role for role in all_roles if (role['cluster_id'] == cluster_id and role['deployment_backend'] == daisy_cmn.kolla_backend_name)]
    for role in roles:    
        if role['name'] == 'CONTROLLER_LB':            
                kolla_vip = role['vip']        
        role_hosts = kolla_cmn.get_hosts_of_role(req, role['id'])
        
        for role_host in role_hosts:
            mgt_ip = ''
            if not mgt_ip:
                host_detail = kolla_cmn.get_host_detail(req, role_host['host_id'])
                deploy_host_cfg = kolla_cmn.get_deploy_node_cfg(req, host_detail, cluster_networks)
                mgt_ip = deploy_host_cfg['mgtip']
                mgt_macname=deploy_host_cfg['mgt_macname']
                pub_macname=deploy_host_cfg['pub_macname']
            mgt_ip_list.add(mgt_ip)
    kolla_config.update({'MGTIP':mgt_ip})
    kolla_config.update({'VIP':kolla_vip})
    kolla_config.update({'IntIfMac':mgt_macname})
    kolla_config.update({'ExtIfMac':pub_macname})
    kolla_config.update({'LocalIP':docker_registry})
    return (kolla_config, mgt_ip_list)
    
def generate_kolla_config_file(cluster_id, kolla_config):
    LOG.info(_("generate kolla config..."))
    if kolla_config:
        config.update_globals_yml(kolla_config)
        config.update_password_yml()
        config.update_all_in_one(kolla_config)
        
class KOLLAInstallTask(Thread):
    """
    Class for install tecs bin.
    """
    """ Definition for install states."""
    INSTALL_STATES = {
        'INIT' : 'init',
        'INSTALLING' : 'installing',
        'ACTIVE' : 'active',
        'FAILED': 'install-failed'
    }

    def __init__(self, req, cluster_id):
        super(KOLLAInstallTask, self).__init__()
        self.req = req
        self.cluster_id = cluster_id
        self.progress = 0
        self.state = KOLLAInstallTask.INSTALL_STATES['INIT']
        self.message = ""
        self.kolla_config_file = ''
        self.mgt_ip_list = ''
        self.install_log_fp = None
        self.last_line_num = 0
        self.need_install = False
        self.ping_times = 36
        self.log_file = "/var/log/daisy/kolla_%s_install.log" % self.cluster_id

               


    def run(self):
        try:
            self._run()
        except (exception.InstallException,
                exception.NotFound,
                exception.InstallTimeoutException) as e:
            LOG.exception(e.message)
        else:
            if not self.need_install:
                return
            self.progress = 100
            self.state = kolla_state['ACTIVE']
            self.message = "Kolla install successfully"
            LOG.info(_("install Kolla for cluster %s successfully."
                        % self.cluster_id))

    def _run(self):
        (kolla_config, self.mgt_ip_list) = get_cluster_kolla_config(self.req, self.cluster_id)

        if not self.mgt_ip_list:
            msg = _("there is no host in cluster %s") % self.cluster_id
            raise exception.ThreadBinException(msg)            
            
        unreached_hosts = _check_ping_hosts(self.mgt_ip_list, self.ping_times)
        if unreached_hosts:
            self.state = kolla_state['INSTALL_FAILED']
            self.message = "hosts %s ping failed" % unreached_hosts
            raise exception.NotFound(message=self.message)
            
        generate_kolla_config_file(self.cluster_id, kolla_config)

        (role_id_list, hosts_list) = kolla_cmn.get_roles_and_hosts_list(self.req, self.cluster_id)
        
        update_progress_to_db(self.req, role_id_list, kolla_state['INSTALLING'], 0.0)
        
        install_progress_percentage = round(1 * 1.0 / len(hosts_list), 2) * 100
        for host in hosts_list:
            host_ip = host['mgtip']
            cmd = 'mkdir -p /var/log/daisy/daisy_install/'
            daisy_cmn.subprocess_call(cmd)
            var_log_path = "/var/log/daisy/daisy_install/%s_install_kolla.log" % host_ip
            with open(var_log_path, "w+") as fp:
                cmd = 'clush -S -b -w %s  mkdir /home/kolla' % (host_ip,)
                daisy_cmn.subprocess_call(cmd,fp)
                cmd = "scp -o ConnectTimeout=10 /var/lib/daisy/kolla/prepare.sh root@%s:/home/kolla"  % host_ip
                daisy_cmn.subprocess_call(cmd,fp)
                cmd = 'clush -S -b -w %s  chmod u+x /home/kolla/prepare.sh' % (host_ip,)
                daisy_cmn.subprocess_call(cmd,fp)
                try:
                    exc_result = subprocess.check_output('clush -S -b -w %s  /home/kolla/prepare.sh' % (host_ip,), shell=True, stderr=subprocess.STDOUT)
                except subprocess.CalledProcessError as e:
                    update_progress_to_db(req, role_id_list, kolla_state['INSTALL_FAILED'])
                    LOG.info(_("prepare for %s failed!" % host_ip))
                    fp.write(e.output.strip())
                    exit()
                else:
                    LOG.info(_("prepare for %s successfully!" % host_ip))
                    fp.write(exc_result)
                
                try:
                    exc_result = subprocess.check_output('kolla-ansible prechecks', shell=True, stderr=subprocess.STDOUT)
                except subprocess.CalledProcessError as e:
                    update_progress_to_db(req, role_id_list, kolla_state['INSTALL_FAILED'])
                    LOG.info(_("kolla-ansible preckecks %s failed!" % host_ip))
                    fp.write(e.output.strip())
                    exit()
                else:
                    LOG.info(_("kolla-ansible preckecks for %s successfully!" % host_ip))
                    fp.write(exc_result)
                
                try:
                    exc_result = subprocess.check_output('kolla-ansible deploy', shell=True, stderr=subprocess.STDOUT)
                except subprocess.CalledProcessError as e:
                    update_progress_to_db(req, role_id_list, kolla_state['INSTALL_FAILED'])
                    LOG.info(_("kolla-ansible deploy %s failed!" % host_ip))
                    fp.write(e.output.strip())
                    exit()
                else:
                    LOG.info(_("kolla-ansible deploy for %s successfully!" % host_ip))
                    fp.write(exc_result)
                    update_progress_to_db(req, role_id_list, kolla_state['ACTIVE'], install_progress_percentage)
                
                 
