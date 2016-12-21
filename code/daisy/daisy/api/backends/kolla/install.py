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
import subprocess
import time
from oslo_log import log as logging
from webob.exc import HTTPForbidden
from threading import Thread
import threading
from daisy import i18n
import daisy.api.v1
from daisy.common import exception
from daisy.api.backends.kolla import config
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.kolla.common as kolla_cmn
import ConfigParser

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE


host_os_status = {
    'INIT': 'init',
    'INSTALLING': 'installing',
    'ACTIVE': 'active',
    'FAILED': 'install-failed'
}

kolla_state = kolla_cmn.KOLLA_STATE
daisy_kolla_path = kolla_cmn.daisy_kolla_path
install_kolla_progress = 0.0
install_mutex = threading.Lock()
kolla_file = "/home/kolla_install"
kolla_config_file = "/etc/kolla/globals.yml"


def update_progress_to_db(req, role_id_list,
                          status, progress=0.0):
    """
    Write install progress and status to db, we use global lock object
    'install_mutex' to make sure this function is thread safety.
    :param req: http req.
    :param role_id_list: Column neeb be update in role table.
    :param status: install status.
    :return:
    """

    global install_mutex
    install_mutex.acquire(True)
    role = {}
    for role_id in role_id_list:
        role['status'] = status
        role['progress'] = progress
        daisy_cmn.update_role(req, role_id, role)
    install_mutex.release()


def update_host_progress_to_db(req, role_id_list, host,
                               status, message, progress=0.0):
    for role_id in role_id_list:
        role_hosts = daisy_cmn.get_hosts_of_role(req, role_id)
        for role_host in role_hosts:
            if role_host['host_id'] == host['id']:
                role_host['status'] = status
                role_host['progress'] = progress
                role_host['messages'] = message
                daisy_cmn.update_role_host(req, role_host['id'], role_host)


def update_all_host_progress_to_db(req, role_id_list, host_id_list,
                                   status, message, progress=0.0):
    for host_id in host_id_list:
        for role_id in role_id_list:
            role_hosts = daisy_cmn.get_hosts_of_role(req, role_id)
            for role_host in role_hosts:
                if role_host['host_id'] == host_id:
                    role_host['status'] = status
                    role_host['progress'] = progress
                    role_host['messages'] = message
                    daisy_cmn.update_role_host(req, role_host['id'], role_host)


def _ping_hosts_test(ips):
    ping_cmd = 'fping'
    for ip in set(ips):
        ping_cmd = ping_cmd + ' ' + ip
    obj = subprocess.Popen(ping_cmd, shell=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    _returncode = obj.returncode
    if _returncode == 0 or _returncode == 1:
        ping_result = stdoutput.split('\n')
        unreachable_hosts = [result.split()[0] for
                             result in ping_result if
                             result and result.split()[2] != 'alive']
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
            LOG.debug(_("ping host %s for %s times"
                        % (','.join(ips), ping_count)))
            if ping_count >= max_ping_times:
                LOG.info(_("ping host %s timeout for %ss"
                           % (','.join(ips), ping_count*time_step)))
                return ips
            time.sleep(time_step)
        else:
            LOG.info(_("ping host %s success" % ','.join(ping_ips)))
            time.sleep(120)
            LOG.info(_("120s after ping host %s success" % ','.join(ping_ips)))
            return ips


def _get_local_ip():
    config = ConfigParser.ConfigParser()
    config.read(daisy_cmn.daisy_conf_file)
    local_ip = config.get("DEFAULT", "daisy_management_ip")
    return local_ip


def get_cluster_kolla_config(req, cluster_id):
    LOG.info(_("get kolla config from database..."))
    mgt_ip_list = set()
    kolla_config = {}
    controller_ip_list = []
    computer_ip_list = []
    mgt_macname_list = []
    pub_macname_list = []
    dat_macname_list = []
    ext_macname_list = []
    sto_macname_list = []
    openstack_version = '3.0.0'
    docker_namespace = 'kolla'
    host_name_ip = {}
    host_name_ip_list = []
    for line in open(kolla_config_file):
        if '#openstack_release:' in line:
            kolla_openstack_version = line.strip()
            openstack_version = kolla_openstack_version.split(":")[1]
    docker_registry_ip = _get_local_ip()
    docker_registry = docker_registry_ip + ':4000'
    cluster_networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)
    all_roles = kolla_cmn.get_roles_detail(req)
    roles = [role for role in all_roles if
             (role['cluster_id'] == cluster_id and
              role['deployment_backend'] == daisy_cmn.kolla_backend_name)]
    for role in roles:
        if role['name'] == 'CONTROLLER_LB':
            kolla_vip = role['vip']
            role_hosts = kolla_cmn.get_hosts_of_role(req, role['id'])
            for role_host in role_hosts:
                host_detail = kolla_cmn.get_host_detail(
                    req, role_host['host_id'])
                deploy_host_cfg = kolla_cmn.get_controller_node_cfg(
                    req, host_detail, cluster_networks)
                mgt_ip = deploy_host_cfg['mgtip']
                host_name_ip = {
                    deploy_host_cfg['host_name']: deploy_host_cfg['mgtip']}
                controller_ip_list.append(mgt_ip)
                mgt_macname = deploy_host_cfg['mgt_macname']
                pub_macname = deploy_host_cfg['pub_macname']
                sto_macname = deploy_host_cfg['sto_macname']
                mgt_macname_list.append(mgt_macname)
                pub_macname_list.append(pub_macname)
                sto_macname_list.append(sto_macname)
                if host_name_ip not in host_name_ip_list:
                    host_name_ip_list.append(host_name_ip)
            if len(set(mgt_macname_list)) != 1 or \
                    len(set(pub_macname_list)) != 1 or \
                    len(set(sto_macname_list)) != 1:
                msg = (_("hosts interface name of public and \
                         management and storage must be same!"))
                LOG.error(msg)
                raise HTTPForbidden(msg)
            kolla_config.update({'Version': openstack_version})
            kolla_config.update({'Namespace': docker_namespace})
            kolla_config.update({'VIP': kolla_vip})
            kolla_config.update({'IntIfMac': mgt_macname})
            kolla_config.update({'PubIfMac': pub_macname})
            kolla_config.update({'StoIfMac': sto_macname})
            kolla_config.update({'LocalIP': docker_registry})
            kolla_config.update({'Controller_ips': controller_ip_list})
            kolla_config.update({'Network_ips': controller_ip_list})
            kolla_config.update({'Storage_ips': controller_ip_list})
        if role['name'] == 'COMPUTER':
            role_hosts = kolla_cmn.get_hosts_of_role(req, role['id'])
            for role_host in role_hosts:
                host_detail = kolla_cmn.get_host_detail(
                    req, role_host['host_id'])
                deploy_host_cfg = kolla_cmn.get_computer_node_cfg(
                    req, host_detail, cluster_networks)
                mgt_ip = deploy_host_cfg['mgtip']
                host_name_ip = {
                    deploy_host_cfg['host_name']: deploy_host_cfg['mgtip']}
                computer_ip_list.append(mgt_ip)
                if host_name_ip not in host_name_ip_list:
                    host_name_ip_list.append(host_name_ip)
                dat_macname = deploy_host_cfg['dat_macname']
                dat_macname_list.append(dat_macname)
                ext_macname = deploy_host_cfg['ext_macname']
                ext_macname_list.append(ext_macname)
            if len(set(dat_macname_list)) != 1 or \
                    len(set(ext_macname_list)) != 1:
                msg = (_("computer hosts interface name of dataplane \
                         and external must be same!"))
                LOG.error(msg)
                raise HTTPForbidden(msg)
            kolla_config.update({'Computer_ips': computer_ip_list})
            kolla_config.update({'TulIfMac': dat_macname})
            kolla_config.update({'ExtIfMac': ext_macname})
    mgt_ip_list = set(controller_ip_list + computer_ip_list)
    return (kolla_config, mgt_ip_list, host_name_ip_list)


def generate_kolla_config_file(cluster_id, kolla_config):
    LOG.info(_("generate kolla config..."))
    if kolla_config:
        config.update_globals_yml(kolla_config)
        config.update_password_yml()
        config.add_role_to_inventory(kolla_file, kolla_config)


def config_nodes_hosts(host_name_ip_list, host_ip):
    config_scripts = []
    hosts_file = "/etc/hosts"
    for name_ip in host_name_ip_list:
        config_scripts.append("linenumber=`grep -n '%s$' %s | "
                              "awk -F ':' '{print $1}'` && "
                              "[ ! -z $linenumber ] && "
                              "sed -i ${linenumber}d %s" %
                              (name_ip.keys()[0],
                               hosts_file, hosts_file))
        config_scripts.append("echo '%s %s' >> %s" % (name_ip.values()[0],
                                                      name_ip.keys()[0],
                                                      hosts_file))
    kolla_cmn.run_scrip(config_scripts, host_ip, "ossdbg1",
                        msg='Failed to config /etc/hosts on %s' % host_ip)


def _calc_progress(log_file):
    progress = 20
    mariadb_result = subprocess.call(
        'cat %s |grep "Running MariaDB"' % log_file,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if mariadb_result == 0:
        progress = 30
    keystone_result = subprocess.call(
        'cat %s |grep "Running Keystone"' % log_file,
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if keystone_result == 0:
        progress = 40
    nova_result = subprocess.call(
        'cat %s |grep "Running Nova"' % log_file, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if nova_result == 0:
        progress = 60
    neutron_result = subprocess.call(
        'cat %s |grep "Running Neutron"' % log_file, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if neutron_result == 0:
        progress = 80
    return progress


class KOLLAInstallTask(Thread):
    """
    Class for kolla install openstack.
    """
    """ Definition for install states."""
    INSTALL_STATES = {
        'INIT': 'init',
        'INSTALLING': 'installing',
        'ACTIVE': 'active',
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
        self.log_file = "/var/log/daisy/kolla_%s_deploy.log" % self.cluster_id
        self.host_prepare_file = "/home/kolla"
        self.kolla_file = "/home/kolla_install"

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
        (kolla_config, self.mgt_ip_list, host_name_ip_list) = \
            get_cluster_kolla_config(self.req, self.cluster_id)
        if not self.mgt_ip_list:
            msg = _("there is no host in cluster %s") % self.cluster_id
            raise exception.ThreadBinException(msg)
        unreached_hosts = _check_ping_hosts(self.mgt_ip_list, self.ping_times)
        if unreached_hosts:
            self.state = kolla_state['INSTALL_FAILED']
            self.message = "hosts %s ping failed" % unreached_hosts
            raise exception.NotFound(message=self.message)
        generate_kolla_config_file(self.cluster_id, kolla_config)
        (role_id_list, host_id_list, hosts_list) = \
            kolla_cmn.get_roles_and_hosts_list(self.req, self.cluster_id)
        self.message = "Begin install"
        update_all_host_progress_to_db(self.req, role_id_list,
                                       host_id_list, kolla_state['INSTALLING'],
                                       self.message, 0)
        docker_registry_ip = _get_local_ip()
        with open(self.log_file, "w+") as fp:
            for host in hosts_list:
                host_ip = host['mgtip']
                cmd = '/var/lib/daisy/kolla/trustme.sh %s ossdbg1' % host_ip
                daisy_cmn.subprocess_call(cmd, fp)
                config_nodes_hosts(host_name_ip_list, host_ip)
                cmd = 'sshpass -p ossdbg1 ssh -o StrictHostKeyChecking=no %s \
                      "if [ ! -d %s ];then mkdir %s;fi" ' % \
                      (host_ip, self.host_prepare_file, self.host_prepare_file)
                daisy_cmn.subprocess_call(cmd, fp)
                cmd = "scp -o ConnectTimeout=10 \
                       /var/lib/daisy/kolla/prepare.sh \
                       root@%s:%s" % (host_ip, self.host_prepare_file)
                daisy_cmn.subprocess_call(cmd, fp)
                cmd = 'sshpass -p ossdbg1 ssh -o StrictHostKeyChecking=no %s \
                      chmod u+x %s/prepare.sh' % \
                      (host_ip, self.host_prepare_file)
                daisy_cmn.subprocess_call(cmd, fp)
                try:
                    exc_result = subprocess.check_output(
                        'sshpass -p ossdbg1 ssh -o StrictHostKeyChecking='
                        'no %s %s/prepare.sh %s' %
                        (host_ip, self.host_prepare_file, docker_registry_ip),
                        shell=True, stderr=subprocess.STDOUT)
                except subprocess.CalledProcessError as e:
                    self.message = "Prepare install failed!"
                    update_host_progress_to_db(self.req, role_id_list, host,
                                               kolla_state['INSTALL_FAILED'],
                                               self.message)
                    LOG.info(_("prepare for %s failed!" % host_ip))
                    fp.write(e.output.strip())
                    exit()
                else:
                    LOG.info(_("prepare for %s successfully!" % host_ip))
                    fp.write(exc_result)
                    self.message = "Preparing for installation successful!"
                    update_host_progress_to_db(self.req, role_id_list, host,
                                               kolla_state['INSTALLING'],
                                               self.message, 10)
            try:
                exc_result = subprocess.check_output(
                    'cd %s/kolla && ./tools/kolla-ansible prechecks -i '
                    '%s/kolla/ansible/inventory/multinode' %
                    (self.kolla_file, self.kolla_file),
                    shell=True, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                self.message = "kolla-ansible preckecks failed!"
                update_all_host_progress_to_db(self.req, role_id_list,
                                               host_id_list,
                                               kolla_state['INSTALL_FAILED'],
                                               self.message)
                LOG.info(_("kolla-ansible preckecks failed!"))
                fp.write(e.output.strip())
                exit()
            else:
                LOG.info(_("kolla-ansible preckecks successfully!"))
                fp.write(exc_result)
                self.message = "Precheck for installation successfully!"
                update_all_host_progress_to_db(self.req, role_id_list,
                                               host_id_list,
                                               kolla_state['INSTALLING'],
                                               self.message, 20)
            cmd = subprocess.Popen(
                'cd %s/kolla && ./tools/kolla-ansible deploy -i '
                '%s/kolla/ansible/inventory/multinode' %
                (self.kolla_file, self.kolla_file),
                shell=True, stdout=fp, stderr=fp)
            self.message = "begin deploy openstack"
            self.progress = 20
            execute_times = 0
            while True:
                time.sleep(5)
                return_code = cmd.poll()
                if self.progress == 90:
                    break
                elif return_code == 0:
                    self.progress = 90
                elif return_code == 1:
                    self.message = "KOLLA deploy openstack failed"
                    update_all_host_progress_to_db(
                        self.req, role_id_list,
                        host_id_list,
                        kolla_state['INSTALL_FAILED'],
                        self.message)
                    LOG.info(_("kolla-ansible deploy failed!"))
                    exit()
                else:
                    self.progress = _calc_progress(self.log_file)
                if execute_times >= 720:
                    self.message = "KOLLA deploy openstack timeout for an hour"
                    raise exception.InstallTimeoutException(
                        cluster_id=self.cluster_id)
                else:
                    update_all_host_progress_to_db(self.req, role_id_list,
                                                   host_id_list,
                                                   kolla_state['INSTALLING'],
                                                   self.message, self.progress)
                execute_times += 1
            try:
                exc_result = subprocess.check_output(
                    'cd %s/kolla && ./tools/kolla-ansible post-deploy -i '
                    '%s/kolla/ansible/inventory/multinode' %
                    (self.kolla_file, self.kolla_file),
                    shell=True, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                self.message = "kolla-ansible post-deploy failed!"
                update_all_host_progress_to_db(self.req, role_id_list,
                                               host_id_list,
                                               kolla_state['INSTALL_FAILED'],
                                               self.message)
                LOG.info(_("kolla-ansible post-deploy failed!"))
                fp.write(e.output.strip())
                exit()
            else:
                LOG.info(_("kolla-ansible post-deploy successfully!"))
                fp.write(exc_result)
                self.message = "post-deploy successfully!"
                update_all_host_progress_to_db(self.req, role_id_list,
                                               host_id_list,
                                               kolla_state['ACTIVE'],
                                               self.message, 100)
                update_progress_to_db(self.req, role_id_list,
                                      kolla_state['ACTIVE'], 100)
