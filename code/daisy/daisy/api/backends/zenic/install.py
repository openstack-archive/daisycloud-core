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
import subprocess
import time

from oslo_config import cfg
from oslo_log import log as logging
import threading

from daisy import i18n

import daisy.api.v1

from daisy.common import exception
from daisy.api.backends.zenic import config
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.zenic.common as zenic_cmn


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
    'INIT': 'init',
    'INSTALLING': 'installing',
    'ACTIVE': 'active',
    'FAILED': 'install-failed'
}

zenic_state = zenic_cmn.ZENIC_STATE
daisy_zenic_path = zenic_cmn.daisy_zenic_path

install_zenic_progress = 0.0
install_mutex = threading.Lock()


def update_progress_to_db(req, role_id_list,
                          status, progress_percentage_step=0.0):
    """
    Write install progress and status to db,
    we use global lock object 'install_mutex'
    to make sure this function is thread safety.
    :param req: http req.
    :param role_id_list: Column neeb be update in role table.
    :param status: install status.
    :return:
    """

    global install_mutex
    global install_zenic_progress
    install_mutex.acquire(True)
    install_zenic_progress += progress_percentage_step
    role = {}
    for role_id in role_id_list:
        if 0 == cmp(status, zenic_state['INSTALLING']):
            role['status'] = status
            role['progress'] = install_zenic_progress
        if 0 == cmp(status, zenic_state['INSTALL_FAILED']):
            role['status'] = status
        elif 0 == cmp(status, zenic_state['ACTIVE']):
            role['status'] = status
            role['progress'] = 100
        daisy_cmn.update_role(req, role_id, role)
    install_mutex.release()


def _ping_hosts_test(ips):
    ping_cmd = 'fping'
    for ip in set(ips):
        ping_cmd = ping_cmd + ' ' + ip
    obj = subprocess.Popen(
        ping_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    _returncode = obj.returncode
    if _returncode == 0 or _returncode == 1:
        ping_result = stdoutput.split('\n')
        unreachable_hosts = [result.split(
        )[0] for result in ping_result if result and
            result.split()[2] != 'alive']
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
            LOG.debug(
                _("ping host %s for %s times" % (','.join(ips), ping_count)))
            if ping_count >= max_ping_times:
                LOG.info(_("ping host %s timeout for %ss" %
                           (','.join(ips), ping_count * time_step)))
                return ips
            time.sleep(time_step)
        else:
            LOG.info(_("ping host %s success" % ','.join(ping_ips)))
            time.sleep(120)
            LOG.info(_("120s after ping host %s success" % ','.join(ping_ips)))
            return ips


def _get_host_private_networks(host_detail, cluster_private_networks_name):
    host_private_networks = [hi for pn in cluster_private_networks_name
                             for hi in
                             host_detail['interfaces'] if pn in
                             hi['assigned_networks']]
    # If port type is bond,use pci segment of member port replace pci1 & pci2
    # segments of bond port
    for interface_outer in host_private_networks:
        if 0 != cmp(interface_outer.get('type', None), "bond"):
            continue
        slave1 = interface_outer.get('slave1', None)
        slave2 = interface_outer.get('slave2', None)
        if not slave1 or not slave2:
            continue
        interface_outer.pop('pci')
        for interface_inner in host_detail['interfaces']:
            if 0 == cmp(interface_inner.get('name', None), slave1):
                interface_outer['pci1'] = interface_inner['pci']
            elif 0 == cmp(interface_inner.get('name', None), slave2):
                interface_outer['pci2'] = interface_inner['pci']
    return host_private_networks


def get_cluster_zenic_config(req, cluster_id):
    LOG.info(_("get zenic config from database..."))
    # params = dict(limit=1000000)

    zenic_config = {}

    deploy_hosts = []
    deploy_host_cfg = {}

    mgt_ip = ''
    zbp_ip_list = set()
    mgt_ip_list = set()

    zamp_ip_list = set()
    zamp_vip = ''

    mongodb_ip_list = set()
    mongodb_vip = ''

    cluster_networks = daisy_cmn.get_cluster_networks_detail(req, cluster_id)

    all_roles = zenic_cmn.get_roles_detail(req)

    roles = [role for role in all_roles if (role['cluster_id'] ==
                                            cluster_id and role[
                                            'deployment_backend'] ==
                                            daisy_cmn.zenic_backend_name)]
    for role in roles:
        if not (role['name'] == 'ZENIC_CTL' or role['name'] == 'ZENIC_NFM'):
            continue
        if role['name'] == 'ZENIC_NFM':
            if not zamp_vip:
                zamp_vip = role['vip']
            if not mongodb_vip:
                mongodb_vip = role['mongodb_vip']
        role_hosts = zenic_cmn.get_hosts_of_role(req, role['id'])

        for role_host in role_hosts:
            mgt_ip = ''
            for deploy_host in deploy_hosts:
                if role_host['host_id'] == deploy_host['hostid']:
                    mgt_ip = deploy_host['mgtip']
                    deploy_ip = deploy_host['nodeip']
                    break
            if not mgt_ip:
                host_detail = zenic_cmn.get_host_detail(
                    req, role_host['host_id'])
                deploy_host_cfg = zenic_cmn.get_deploy_node_cfg(
                    req, host_detail, cluster_networks)
                deploy_hosts.append(deploy_host_cfg)
                mgt_ip = deploy_host_cfg['mgtip']
                deploy_ip = deploy_host_cfg['nodeip']

            mgt_ip_list.add(mgt_ip)
            if role['name'] == 'ZENIC_CTL':
                zbp_ip_list.add(deploy_ip)
            elif role['name'] == 'ZENIC_NFM':
                zamp_ip_list.add(deploy_ip)
                mongodb_ip_list.add(deploy_ip)
            else:
                LOG.warn(
                    _("<<<Zenic Install role %s is invalid >>>"
                      % role['name']))

    zenic_config.update({'deploy_hosts': deploy_hosts})
    zenic_config.update({'zbp_ips': zbp_ip_list})
    zenic_config.update({'zbp_node_num': len(zbp_ip_list)})
    zenic_config.update({'zamp_ips': zamp_ip_list})
    zenic_config.update({'zamp_node_num': len(zamp_ip_list)})
    zenic_config.update({'mongodb_ips': mongodb_ip_list})
    zenic_config.update({'mongodb_node_num': len(mongodb_ip_list)})
    zenic_config.update({'zamp_vip': zamp_vip})
    zenic_config.update({'mongodb_vip': mongodb_vip})
    return (zenic_config, mgt_ip_list)


def generate_zenic_config_file(cluster_id, zenic_config):
    LOG.info(_("generate zenic config..."))
    if zenic_config:
        cluster_conf_path = daisy_zenic_path + cluster_id
        config.update_zenic_conf(zenic_config, cluster_conf_path)


def thread_bin(req, host, role_id_list, pkg_name, install_progress_percentage):
    host_ip = host['mgtip']
    password = host['rootpwd']

    cmd = 'mkdir -p /var/log/daisy/daisy_install/'
    daisy_cmn.subprocess_call(cmd)

    var_log_path =\
        "/var/log/daisy/daisy_install/%s_install_zenic.log" % host_ip
    with open(var_log_path, "w+") as fp:

        cmd = '/var/lib/daisy/zenic/trustme.sh %s %s' % (host_ip, password)
        daisy_cmn.subprocess_call(cmd, fp)

        cmd = 'clush -S -b -w %s  mkdir -p /home/workspace' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)

        cmd = 'clush -S -b -w %s  mkdir -p /etc/zenic' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)

        cmd = 'clush -S -b -w %s  rm -rf /etc/zenic/config' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)

        cmd = 'clush -S -b -w %s  rm -rf /home/zenic' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)

        cmd = 'clush -S -b -w %s  rm -rf /home/workspace/unipack' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)

        pkg_file = daisy_zenic_path + pkg_name
        cmd = 'clush -S -b -w %s  rm -rf /home/workspace/%s' % (
            host_ip, pkg_name)
        daisy_cmn.subprocess_call(cmd, fp)

        cfg_file = daisy_zenic_path + host_ip + "_zenic.conf"
        try:
            exc_result = subprocess.check_output(
                'sshpass -p ossdbg1 scp %s root@%s:/etc/zenic/config' % (
                    cfg_file, host_ip,),
                shell=True, stderr=fp)
        except subprocess.CalledProcessError as e:
            update_progress_to_db(
                req, role_id_list, zenic_state['INSTALL_FAILED'])
            LOG.info(_("scp zenic pkg for %s failed!" % host_ip))
            fp.write(e.output.strip())
            exit()
        else:
            LOG.info(_("scp zenic config for %s successfully!" % host_ip))
            fp.write(exc_result)

        try:
            exc_result = subprocess.check_output(
                'sshpass -p ossdbg1 scp %s root@%s:/home/workspace/' % (
                    pkg_file, host_ip,),
                shell=True, stderr=fp)
        except subprocess.CalledProcessError as e:
            update_progress_to_db(
                req, role_id_list, zenic_state['INSTALL_FAILED'])
            LOG.info(_("scp zenic pkg for %s failed!" % host_ip))
            fp.write(e.output.strip())
            exit()
        else:
            LOG.info(_("scp zenic pkg for %s successfully!" % host_ip))
            fp.write(exc_result)

        cmd = 'clush -S -b -w %s unzip /home/workspace/%s \
            -d /home/workspace/unipack' % (
            host_ip, pkg_name,)
        daisy_cmn.subprocess_call(cmd)

        try:
            exc_result = subprocess.check_output(
                'clush -S -b -w %s  /home/workspace/unipack/node_install.sh'
                % (host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            update_progress_to_db(
                req, role_id_list, zenic_state['INSTALL_FAILED'])
            LOG.info(_("install zenic for %s failed!" % host_ip))
            fp.write(e.output.strip())
            exit()
        else:
            LOG.info(_("install zenic for %s successfully!" % host_ip))
            fp.write(exc_result)

        try:
            exc_result = subprocess.check_output(
                'clush -S -b -w %s  /home/zenic/node_start.sh' % (host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            update_progress_to_db(
                req, role_id_list, zenic_state['INSTALL_FAILED'])
            LOG.info(_("start zenic for %s failed!" % host_ip))
            fp.write(e.output.strip())
            exit()
        else:
            update_progress_to_db(
                req, role_id_list, zenic_state['INSTALLING'],
                install_progress_percentage)
            LOG.info(_("start zenic for %s successfully!" % host_ip))
            fp.write(exc_result)


class ZENICInstallTask(Thread):

    """
    Class for install tecs bin.
    """
    """ Definition for install states."""
    INSTALL_STATES = {
        'INIT': 'init',
        'INSTALLING': 'installing',
        'ACTIVE': 'active',
        'FAILED': 'install-failed'
    }

    def __init__(self, req, cluster_id):
        super(ZENICInstallTask, self).__init__()
        self.req = req
        self.cluster_id = cluster_id
        self.progress = 0
        self.state = ZENICInstallTask.INSTALL_STATES['INIT']
        self.message = ""
        self.zenic_config_file = ''
        self.mgt_ip_list = ''
        self.install_log_fp = None
        self.last_line_num = 0
        self.need_install = False
        self.ping_times = 36
        self.log_file = "/var/log/daisy/zenic_%s_install.log" % self.cluster_id

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
            self.state = zenic_state['ACTIVE']
            self.message = "Zenic install successfully"
            LOG.info(_("install Zenic for cluster %s successfully."
                       % self.cluster_id))

    def _run(self):

        (zenic_config, self.mgt_ip_list) = get_cluster_zenic_config(
            self.req, self.cluster_id)

        if not self.mgt_ip_list:
            msg = _("there is no host in cluster %s") % self.cluster_id
            raise exception.ThreadBinException(msg)

        unreached_hosts = _check_ping_hosts(self.mgt_ip_list, self.ping_times)
        if unreached_hosts:
            self.state = zenic_state['INSTALL_FAILED']
            self.message = "hosts %s ping failed" % unreached_hosts
            raise exception.NotFound(message=self.message)

        generate_zenic_config_file(self.cluster_id, zenic_config)

        # check and get ZENIC version
        (zenic_version_pkg_file, zenic_version_pkg_name) =\
            zenic_cmn.check_and_get_zenic_version(
            daisy_zenic_path)
        if not zenic_version_pkg_file:
            self.state = zenic_state['INSTALL_FAILED']
            self.message = \
                "ZENIC version file not found in %s" % daisy_zenic_path
            raise exception.NotFound(message=self.message)

        (role_id_list, hosts_list) = zenic_cmn.get_roles_and_hosts_list(
            self.req, self.cluster_id)

        update_progress_to_db(
            self.req, role_id_list, zenic_state['INSTALLING'], 0.0)
        install_progress_percentage = round(1 * 1.0 / len(hosts_list), 2) * 100

        threads = []
        for host in hosts_list:
            t = threading.Thread(target=thread_bin, args=(
                self.req, host, role_id_list,
                zenic_version_pkg_name, install_progress_percentage))
            t.setDaemon(True)
            t.start()
            threads.append(t)
        LOG.info(_("install threads have started, please waiting...."))

        try:
            for t in threads:
                t.join()
        except:
            LOG.warn(_("Join install thread %s failed!" % t))
        else:
            install_failed_flag = False
            for role_id in role_id_list:
                role = daisy_cmn.get_role_detail(self.req, role_id)
                if role['progress'] == 0:
                    update_progress_to_db(
                        self.req, role_id_list, zenic_state['INSTALL_FAILED'])
                    install_failed_flag = True
                    break
                if role['status'] == zenic_state['INSTALL_FAILED']:
                    install_failed_flag = True
                    break
            if not install_failed_flag:
                LOG.info(
                    _("all install threads have done, \
                        set all roles status to 'active'!"))
                update_progress_to_db(
                    self.req, role_id_list, zenic_state['ACTIVE'])
