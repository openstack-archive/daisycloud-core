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
import copy
import subprocess
import time
import json

from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
import threading

from daisy import i18n

from daisy.common import exception
from daisy.api import common
from daisy.common import utils
import daisy.registry.client.v1.api as registry
from daisyclient.v1 import client as daisy_client
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.tecs.common as tecs_cmn


import ConfigParser

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

CONF = cfg.CONF
install_opts = [
    cfg.StrOpt('max_parallel_os_number', default=10,
               help='Maximum number of hosts install os at the same time.'),
]
CONF.register_opts(install_opts)
upgrade_opts = [
    cfg.StrOpt('max_parallel_os_upgrade_number', default=10,
               help='Maximum number of hosts upgrade os at the same time.'),
]
CONF.register_opts(upgrade_opts)

host_os_status = {
    'INIT': 'init',
    'PRE_INSTALL': 'pre-install',
    'INSTALLING': 'installing',
    'ACTIVE': 'active',
    'INSTALL_FAILED': 'install-failed',
    'UPDATING': 'updating',
    'UPDATE_FAILED': 'update-failed'
}

LINUX_BOND_MODE = {'balance-rr': '0', 'active-backup': '1',
                   'balance-xor': '2', 'broadcast': '3',
                   '802.3ad': '4', 'balance-tlb': '5',
                   'balance-alb': '6'}

daisy_tecs_path = tecs_cmn.daisy_tecs_path


def get_daisyclient():
    """Get Daisy client instance."""
    config_daisy = ConfigParser.ConfigParser()
    config_daisy.read("/etc/daisy/daisy-api.conf")
    daisy_port = config_daisy.get("DEFAULT", "bind_port")
    args = {'version': 1.0, 'endpoint': 'http://127.0.0.1:' + daisy_port}
    return daisy_client.Client(**args)


def pxe_server_build(req, install_meta):
    params = {'filters': {'type': 'system'}}
    try:
        networks = registry.get_all_networks(req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)

    ip_inter = lambda x: sum([256 ** j * int(i)
                              for j, i in enumerate(x.split('.')[::-1])])
    inter_ip = lambda x: '.'.join(
        [str(x / (256**i) % 256) for i in range(3, -1, -1)])
    for network in networks:
        if 'system' in network['type']:
            network_cidr = network.get('cidr')
            if not network_cidr:
                msg = "Error:The CIDR is blank of pxe server!"
                LOG.error(msg)
                raise exception.Forbidden(msg)
            cidr_end = network_cidr.split('/')[1]
            mask = ~(2**(32 - int(cidr_end)) - 1)
            net_mask = inter_ip(mask)
            pxe_server_ip = network.get('ip')
            ip_ranges = network.get('ip_ranges')
            for ip_range in ip_ranges:
                client_ip_begin = ip_range.get('start')
                client_ip_end = ip_range.get('end')
                ip_addr = network_cidr.split('/')[0]
                ip_addr_int = ip_inter(ip_addr)
                ip_addr_min = inter_ip(ip_addr_int & (mask & 0xffffffff))
                ip_addr_max = inter_ip(ip_addr_int | (~mask & 0xffffffff))
                if not client_ip_begin and not client_ip_end:
                    client_ip_begin = inter_ip((ip_inter(ip_addr_min)) + 2)
                    client_ip_end = ip_addr_max
                if pxe_server_ip:
                    ip_in_cidr = utils.is_ip_in_cidr(pxe_server_ip,
                                                     network_cidr)
                    if not ip_in_cidr:
                        msg = "Error:The ip '%s' is not in cidr '%s'" \
                              " range." % (pxe_server_ip, network_cidr)
                        LOG.error(msg)
                        raise HTTPBadRequest(explanation=msg)
                else:
                    pxe_server_ip = inter_ip((ip_inter(ip_addr_min)) + 1)

    eth_name = install_meta.get('deployment_interface')
    if not eth_name:
        msg = "Error:The nic name is blank of build pxe server!"
        LOG.error(msg)
        raise exception.Forbidden(msg)
    args = {'build_pxe': 'yes',
            'ethname_l': eth_name,
            'ip_addr_l': pxe_server_ip,
            'net_mask_l': net_mask,
            'client_ip_begin': client_ip_begin,
            'client_ip_end': client_ip_end}
    with open('/var/log/ironic/pxe.json', 'w') as f:
        json.dump(args, f, indent=2)
    f.close()
    try:
        _PIPE = subprocess.PIPE
        cmd = "/usr/bin/pxe_server_install /var/log/ironic/pxe.json && \
               chmod 755 /tftpboot -R"
        obj = subprocess.Popen(cmd,
                               shell=True,
                               stdout=_PIPE,
                               stderr=_PIPE)
        out, error = obj.communicate()
    except Exception as ex:
        LOG.error("%s: execute set pxe command failed.", ex)
        msg = "build pxe server failed"
        raise exception.InvalidNetworkConfig(msg)


def _get_network_plat(req, host_config, cluster_networks, dhcp_mac):
    host_config['dhcp_mac'] = dhcp_mac
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
                host_config['interfaces'][count - 1]['assigned_networks'] = []
                alias = []
                for assigned_network in assigned_networks:
                    network_name = assigned_network['name']
                    cluster_network = [
                        network for network in cluster_networks
                        if network['name'] in network_name][0]
                    alias.append(cluster_network['alias'])
                    # convert cidr to netmask
                    cidr_to_ip = ""
                    assigned_networks_ip = tecs_cmn.get_host_network_ip(
                        req, host_config_orig, cluster_networks, network_name)
                    if cluster_network.get('cidr', None):
                        inter_ip = lambda x: '.'.join(
                            [str(x / (256**i) % 256) for i in
                             range(3, -1, -1)])
                        cidr_to_ip = inter_ip(
                            2**32 - 2**(32 - int(
                                cluster_network['cidr'].split('/')[1])))
                    if cluster_network['alias'] is None or len(alias) == 1:
                        network_type = cluster_network['network_type']
                        network_plat = dict(network_type=network_type,
                                            ml2_type=cluster_network[
                                                'ml2_type'],
                                            capability=cluster_network[
                                                'capability'],
                                            physnet_name=cluster_network[
                                                'physnet_name'],
                                            gateway=cluster_network.get(
                                                'gateway', ""),
                                            ip=assigned_networks_ip,
                                            # ip=cluster_network.get('ip', ""),
                                            netmask=cidr_to_ip,
                                            vlan_id=cluster_network.get(
                                                'vlan_id', ""))
                        host_config['interfaces'][
                            count - 1][
                            'assigned_networks'].append(network_plat)
            interface['ip'] = ""
            interface['netmask'] = ""
            interface['gateway'] = ""

    return host_config


def get_cluster_hosts_config(req, cluster_id):
    # params = dict(limit=1000000)
    try:
        cluster_data = registry.get_cluster_metadata(req.context, cluster_id)
        networks = registry.get_networks_detail(req.context, cluster_id)
        all_roles = registry.get_roles_detail(req.context)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)

    roles = [role for role in all_roles if role['cluster_id'] == cluster_id]
    all_hosts_ids = cluster_data['nodes']
    hosts_config = []
    for host_id in all_hosts_ids:
        host_detail = daisy_cmn.get_host_detail(req, host_id)
        role_host_db_lv_size_lists = list()
        # if host_detail.has_key('role') and host_detail['role']:
        if 'role' in host_detail and host_detail['role']:
            host_roles = host_detail['role']
            for role in roles:
                if role['name'] in host_detail['role'] and\
                        role['glance_lv_size']:
                    host_detail['glance_lv_size'] = role['glance_lv_size']
                if role.get('db_lv_size', None) and host_roles and\
                        role['name'] in host_roles:
                    role_host_db_lv_size_lists.append(role['db_lv_size'])
                if role['name'] == 'COMPUTER' and\
                        role['name'] in host_detail['role'] and\
                        role['nova_lv_size']:
                    host_detail['nova_lv_size'] = role['nova_lv_size']
                service_disks = tecs_cmn.get_service_disk_list(
                    req, {'role_id': role['id']})
                for service_disk in service_disks:
                    if service_disk['disk_location'] == 'local' and\
                       service_disk['service'] == 'mongodb':
                        host_detail['mongodb_lv_size'] = service_disk['size']
                        break
            if role_host_db_lv_size_lists:
                host_detail['db_lv_size'] = max(role_host_db_lv_size_lists)
            else:
                host_detail['db_lv_size'] = 0

        for interface in host_detail['interfaces']:
            if interface['type'] == 'bond'and\
               interface['mode'] in LINUX_BOND_MODE.keys():
                interface['mode'] = LINUX_BOND_MODE[interface['mode']]

        if (host_detail['os_status'] == host_os_status['INIT'] or
                host_detail['os_status'] == host_os_status['PRE_INSTALL'] or
                host_detail['os_status'] == host_os_status['INSTALLING'] or
                host_detail['os_status'] == host_os_status['INSTALL_FAILED']):
            pxe_macs = common.get_pxe_mac(host_detail)
            if not pxe_macs:
                msg = "cann't find dhcp interface on host %s" % host_detail[
                    'id']
                raise exception.InvalidNetworkConfig(msg)
            if len(pxe_macs) > 1:
                msg = "dhcp interface should only has one on host %s"\
                    % host_detail['id']
                raise exception.InvalidNetworkConfig(msg)

            host_config_detail = copy.deepcopy(host_detail)
            host_config = _get_network_plat(req, host_config_detail,
                                            networks,
                                            pxe_macs[0])
            hosts_config.append(tecs_cmn.sort_interfaces_by_pci(networks,
                                                                host_config))
    return hosts_config


def check_tfg_exist():
    get_tfg_patch = "ls %s|grep CGSL_VPLAT-.*\.iso$" % daisy_tecs_path
    obj = subprocess.Popen(get_tfg_patch,
                           shell=True,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    tfg_patch_pkg_file = ""
    tfg_patch_pkg_name = ""
    if stdoutput:
        tfg_patch_pkg_name = stdoutput.split('\n')[0]
        tfg_patch_pkg_file = daisy_tecs_path + tfg_patch_pkg_name
        chmod_for_tfg_bin = 'chmod +x %s' % tfg_patch_pkg_file
        daisy_cmn.subprocess_call(chmod_for_tfg_bin)

    if not stdoutput or not tfg_patch_pkg_name:
        LOG.info(_("no CGSL_VPLAT iso file got in %s" % daisy_tecs_path))
        return ""
    return tfg_patch_pkg_file


def update_db_host_status(req, host_id, host_status):
    """
    Update host status and intallation progress to db.
    :return:
    """
    try:
        host_meta = {}
        host_meta['os_progress'] = host_status['os_progress']
        host_meta['os_status'] = host_status['os_status']
        host_meta['messages'] = host_status['messages']
        registry.update_host_metadata(req.context,
                                      host_id,
                                      host_meta)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)


class OSInstall():

    """
    Class for install OS.
    """
    """ Definition for install states."""

    def __init__(self, req, cluster_id):
        self.req = req
        self.cluster_id = cluster_id
        # 5s
        self.time_step = 5
        # 30 min
        self.single_host_install_timeout = 30 * (12 * self.time_step)

        self.max_parallel_os_num = int(CONF.max_parallel_os_number)
        self.cluster_hosts_install_timeout = (
            self.max_parallel_os_num / 4 + 2) * 60 * (12 * self.time_step)
        self.daisyclient = get_daisyclient()

    def _set_boot_or_power_state(self, user, passwd, addr, action):
        count = 0
        repeat_times = 24
        while count < repeat_times:
            if action in ['on', 'off', 'reset']:
                device = 'power'
            elif action in ['pxe', 'disk']:
                device = 'bootdev'

            cmd = ['ipmitool', '-I', 'lanplus', '-H', addr, '-U', user,
                   '-P', passwd, 'chassis', device, state]

            if device == 'bootdev':
                cmd.append('options=persistent')

            try:
                _PIPE = subprocess.PIPE
                obj = subprocess.Popen(cmd,
                                       stdin=_PIPE,
                                       stdout=_PIPE,
                                       stderr=_PIPE,
                                       shell=False,
                                       cwd=None,
                                       env=None)
                out, error = obj.communicate()
            except Exception as ex:
                count += 1
                LOG.info(
                    _("Try setting %s to '%s' failed for %s times"
                      % (addr, action, count)))
                time.sleep(count * 2)
            else:
                LOG.info(
                    _("Set %s to '%s' successfully for %s times" % (
                      addr, action, count + 1)))
                break
        if count >= repeat_times:
            message = "Set %s to '%s' failed for 10 mins" % (addr, action)
            raise exception.IMPIOprationFailed(message=message)

    def _install_os_for_baremetal(self, host_detail):
        # os_install_disk = 'sda'
        os_version_file = host_detail['os_version_file']
        if os_version_file:
            test_os_version_exist = 'test -f %s' % os_version_file
            daisy_cmn.subprocess_call(test_os_version_exist)
        else:
            self.message = "no OS version file configed for host %s"\
                % host_detail['id']
            raise exception.NotFound(message=self.message)
        if host_detail.get('root_disk', None):
            root_disk = host_detail['root_disk']
        else:
            root_disk = 'sda'
        if host_detail.get('root_lv_size', None):
            root_lv_size_m = host_detail['root_lv_size']
        else:
            root_lv_size_m = 102400
        memory_size_b_str = str(host_detail['memory']['total'])
        memory_size_b_int = int(memory_size_b_str.strip().split()[0])
        memory_size_m = memory_size_b_int // 1024
        memory_size_g = memory_size_m // 1024
        swap_lv_size_m = host_detail['swap_lv_size']
        cinder_vg_size_m = 0
        disk_list = []
        disk_storage_size_b = 0
        for key in host_detail['disks']:
            if host_detail['disks'][key]['disk'].find("-fc-") != -1 \
                    or host_detail['disks'][key]['disk'].\
                    find("-iscsi-") != -1 \
                    or host_detail['disks'][key]['name'].\
                    find("mpath") != -1 \
                    or host_detail['disks'][key]['name'].\
                    find("spath") != -1:
                continue
            disk_list.append(host_detail['disks'][key]['name'])
            stroage_size_str = host_detail['disks'][key]['size']
            stroage_size_b_int = int(stroage_size_str.strip().split()[0])
            disk_storage_size_b = disk_storage_size_b + stroage_size_b_int
        disk_list = ','.join(disk_list)
        disk_storage_size_m = disk_storage_size_b // (1024 * 1024)

        if 'root_pwd' in host_detail and host_detail['root_pwd']:
            root_pwd = host_detail['root_pwd']
        else:
            root_pwd = 'ossdbg1'

        isolcpus = None
        if 'os_cpus' in host_detail and host_detail['os_cpus']:
            os_cpus = utils.cpu_str_to_list(host_detail['os_cpus'])
            host_cpu = host_detail.get('cpu', {})
            if 'total' in host_cpu:
                total_cpus = range(0, host_cpu['total'])
                isolcpus_list = list(set(total_cpus) - set(os_cpus))
                isolcpus_list.sort()
                isolcpus = utils.cpu_list_to_str(isolcpus_list)

        if host_detail.get('hugepages', None):
            hugepages = host_detail['hugepages']
        else:
            hugepages = 0

        if host_detail.get('hugepagesize', None):
            hugepagesize = host_detail['hugepagesize']
        else:
            hugepagesize = '1G'
        # tfg_patch_pkg_file = check_tfg_exist()

        if host_detail.get('hwm_id'):
            host_hwm_meta = {
                "hwm_ip": host_detail.get('hwm_ip'),
                "hwm_id": host_detail.get('hwm_id'),
                "boot_type": "pxe"
            }
            self.daisyclient.node.set_boot(**host_hwm_meta)
        else:
            if (not host_detail['ipmi_user'] or
                    not host_detail['ipmi_passwd'] or
                    not host_detail['ipmi_addr']):
                self.message = "Invalid ipmi information configed for host %s"\
                    % host_detail['id']
                raise exception.NotFound(message=self.message)

            self._set_boot_or_power_state(host_detail['ipmi_user'],
                                          host_detail['ipmi_passwd'],
                                          host_detail['ipmi_addr'],
                                          'pxe')

        kwargs = {'hostname': host_detail['name'],
                  'iso_path': os_version_file,
                  # 'tfg_bin':tfg_patch_pkg_file,
                  'dhcp_mac': host_detail['dhcp_mac'],
                  'storage_size': disk_storage_size_m,
                  'memory_size': memory_size_g,
                  'interfaces': host_detail['interfaces'],
                  'root_lv_size': root_lv_size_m,
                  'swap_lv_size': swap_lv_size_m,
                  'cinder_vg_size': cinder_vg_size_m,
                  'disk_list': disk_list,
                  'root_disk': root_disk,
                  'root_pwd': root_pwd,
                  'isolcpus': isolcpus,
                  'hugepagesize': hugepagesize,
                  'hugepages': hugepages,
                  'reboot': 'no'}

        # if host_detail.has_key('glance_lv_size'):
        if 'glance_lv_size' in host_detail:
            kwargs['glance_lv_size'] = host_detail['glance_lv_size']
        else:
            kwargs['glance_lv_size'] = 0

        # if host_detail.has_key('db_lv_size') and host_detail['db_lv_size']:
        if 'db_lv_size' in host_detail and host_detail['db_lv_size']:
            kwargs['db_lv_size'] = host_detail['db_lv_size']
        else:
            kwargs['db_lv_size'] = 0

        # if host_detail.has_key('mongodb_lv_size') and
        # host_detail['mongodb_lv_size']:
        if 'mongodb_lv_size' in host_detail and host_detail['mongodb_lv_size']:
            kwargs['mongodb_lv_size'] = host_detail['mongodb_lv_size']
        else:
            kwargs['mongodb_lv_size'] = 0

        # if host_detail.has_key('nova_lv_size') and
        # host_detail['nova_lv_size']:
        if 'nova_lv_size' in host_detail and host_detail['nova_lv_size']:
            kwargs['nova_lv_size'] = host_detail['nova_lv_size']
        else:
            kwargs['nova_lv_size'] = 0
        json_file = "/var/log/ironic/%s.json" % kwargs['dhcp_mac']
        with open(json_file, 'w') as f:
            json.dump(kwargs, f, indent=2)
        f.close()
        try:
            _PIPE = subprocess.PIPE
            cmd = "/usr/bin/pxe_os_install /var/log/ironic/%s.json && \
                   chmod 755 /tftpboot -R && \
                   chmod 755 /home/install_share -R && \
                   chmod 755 /linuxinstall -R" % kwargs['dhcp_mac']
            obj = subprocess.Popen(cmd,
                                   shell=True,
                                   stdout=_PIPE,
                                   stderr=_PIPE)
            out, error = obj.communicate()
        except Exception as ex:
            msg = "%s: execute build os command failed." % ex
            LOG.error(msg)
            host_status = {'os_status': host_os_status['INSTALL_FAILED'],
                           'os_progress': 0,
                           'messages': msg}
            update_db_host_status(self.req, host_detail['id'], host_status)
            msg = "install os return failed for host %s" % host_detail['id']
            raise exception.OSInstallFailed(message=msg)

        if host_detail.get('hwm_id'):
            host_hwm_meta = {
                "hwm_ip": host_detail.get('hwm_ip'),
                "hwm_id": host_detail.get('hwm_id')
            }
            self.daisyclient.node.restart(**host_hwm_meta)
        else:
            self._set_boot_or_power_state(host_detail['ipmi_user'],
                                          host_detail['ipmi_passwd'],
                                          host_detail['ipmi_addr'],
                                          'reset')

    def _begin_install_os(self, hosts_detail):
        # all hosts status is set to 'pre-install' before os installing
        for host_detail in hosts_detail:
            host_status = {'os_status': host_os_status['PRE_INSTALL'],
                           'os_progress': 0,
                           'messages': 'Preparing for OS installation'}
            update_db_host_status(self.req, host_detail['id'], host_status)

        for host_detail in hosts_detail:
            self._install_os_for_baremetal(host_detail)

    def _set_disk_start_mode(self, host_detail):
        LOG.info(_("Set boot from disk for host %s" % (host_detail['id'])))
        if host_detail.get('hwm_id'):
            host_hwm_meta = {
                "hwm_ip": host_detail.get('hwm_ip'),
                "hwm_id": host_detail.get('hwm_id'),
                "boot_type": "disk"
            }
            self.daisyclient.node.set_boot(**host_hwm_meta)
            LOG.info(_("reboot host %s" % (host_detail['id'])))
            host_hwm_meta.pop('boot_type')
            self.daisyclient.node.restart(**host_hwm_meta)
        else:
            self._set_boot_or_power_state(host_detail['ipmi_user'],
                                          host_detail['ipmi_passwd'],
                                          host_detail['ipmi_addr'],
                                          'disk')
            LOG.info(_("reboot host %s" % (host_detail['id'])))
            self._set_boot_or_power_state(host_detail['ipmi_user'],
                                          host_detail['ipmi_passwd'],
                                          host_detail['ipmi_addr'],
                                          'reset')

    def _init_progress(self, host_detail, hosts_status):
        host_id = host_detail['id']

        host_status = hosts_status[host_id] = {}
        host_status['os_status'] = host_os_status['INSTALLING']
        host_status['os_progress'] = 0
        host_status['count'] = 0
        if host_detail['resource_type'] == 'docker':
            host_status['messages'] = "docker container is creating"
        else:
            host_status['messages'] = "OS installing"

        update_db_host_status(self.req, host_id, host_status)

    def _query_host_progress(self, host_detail, host_status, host_last_status):
        host_id = host_detail['id']
        try:
            _PIPE = subprocess.PIPE
            dhcp_mac = host_detail['dhcp_mac']
            cmd = "/usr/bin/pxe_os_install_progress %s" % dhcp_mac
            obj = subprocess.Popen(cmd,
                                   shell=True,
                                   stdout=_PIPE,
                                   stderr=_PIPE)
            out, error = obj.communicate()
            return_code = obj.returncode
            progress_list = out.split()
            progress = progress_list.pop(0)
            info = ' '.join(progress_list)
            host_status['os_progress'] = int(progress)
            if host_status['os_progress'] == 100:
                time_cost = str(
                    round((time.time() -
                           daisy_cmn.os_install_start_time) / 60, 2))
                LOG.info(
                    _("It takes %s min for host %s to install os"
                        % (time_cost, host_id)))
                LOG.info(_("host %s install os completely." % host_id))
                host_status['os_status'] = host_os_status['ACTIVE']
                host_status['messages'] = "OS installed successfully"
                # wait for nicfix script complete
                time.sleep(10)
                self._set_disk_start_mode(host_detail)
            else:
                if host_status['os_progress'] ==\
                        host_last_status['os_progress']:
                    host_status['count'] = host_status['count'] + 1
                    LOG.debug(_("host %s has kept %ss when progress is %s."
                                % (host_id,
                                   host_status['count'] * self.time_step,
                                   host_status['os_progress'])))
        except Exception as ex:
            LOG.error('%s: execute get install progress failed.', ex)
            host_status['os_status'] = host_os_status['INSTALL_FAILED']
            host_status['messages'] = info

    def _query_progress(self, hosts_last_status, hosts_detail):
        hosts_status = copy.deepcopy(hosts_last_status)
        for host_detail in hosts_detail:
            host_id = host_detail['id']
            # if not hosts_status.has_key(host_id):
            if host_id not in hosts_status:
                self._init_progress(host_detail, hosts_status)
                continue

            host_status = hosts_status[host_id]
            host_last_status = hosts_last_status[host_id]
            # only process installing hosts after init, other hosts info will
            # be kept in hosts_status
            if host_status['os_status'] != host_os_status['INSTALLING']:
                continue
            self._query_host_progress(
                host_detail, host_status, host_last_status)

            if host_status['count'] * self.time_step >=\
                    self.single_host_install_timeout:
                host_status['os_status'] = host_os_status['INSTALL_FAILED']
                if host_detail['resource_type'] == 'docker':
                    host_status[
                        'messages'] = "docker container created timeout"
                else:
                    host_status['messages'] = "os installed timeout"
            if (host_status['os_progress'] !=
                host_last_status['os_progress'] or
                    host_status['os_status'] != host_last_status['os_status']):
                host_status['count'] = 0
                update_db_host_status(self.req, host_id, host_status)
        return hosts_status

    def _get_install_status(self, hosts_detail):
        query_count = 0
        hosts_last_status = {}
        while True:
            hosts_install_status = self._query_progress(
                hosts_last_status, hosts_detail)
            # if all hosts install over, break
            installing_hosts = [id for id in hosts_install_status.keys()
                                if hosts_install_status[id]['os_status'] ==
                                host_os_status['INSTALLING']]
            if not installing_hosts:
                break
            # after 3h, if some hosts are not 'active', label them to 'failed'.
            elif query_count * self.time_step >=\
                    self.cluster_hosts_install_timeout:
                for host_id, host_status in hosts_install_status.iteritems():
                    if (host_status['os_status'] !=
                        host_os_status['ACTIVE'] and
                        host_status['os_status'] !=
                            host_os_status['INSTALL_FAILED']):
                        # label the host install failed because of time out for
                        # 3h
                        host_status['os_status'] = host_os_status[
                            'INSTALL_FAILED']
                        host_status[
                            'messages'] = "cluster os installed timeout"
                        update_db_host_status(self.req, host_id, host_status)
                break
            else:
                query_count += 1
                hosts_last_status = hosts_install_status
                time.sleep(self.time_step)
        return hosts_install_status

    def install_os(self, hosts_detail, role_hosts_ids):
        if len(hosts_detail) > self.max_parallel_os_num:
            install_hosts = hosts_detail[:self.max_parallel_os_num]
            hosts_detail = hosts_detail[self.max_parallel_os_num:]
        else:
            install_hosts = hosts_detail
            hosts_detail = []

        install_hosts_id = [host_detail['id'] for host_detail in install_hosts]
        LOG.info(
            _("Begin install os for hosts %s." % ','.join(install_hosts_id)))
        daisy_cmn.os_install_start_time = time.time()
        self._begin_install_os(install_hosts)
        LOG.info(_("Begin to query install progress..."))
        # wait to install completely
        cluster_install_status = self._get_install_status(install_hosts)
        total_time_cost = str(
            round((time.time() - daisy_cmn.os_install_start_time) / 60, 2))
        LOG.info(
            _("It totally takes %s min for all host to install os"
              % total_time_cost))
        LOG.info(_("OS install in cluster %s result is:" % self.cluster_id))
        LOG.info(_("%s                                %s        %s" %
                   ('host-id', 'os-status', 'description')))

        for host_id, host_status in cluster_install_status.iteritems():
            LOG.info(
                _("%s   %s   %s" % (host_id, host_status['os_status'],
                                    host_status['messages'])))
            if host_id in role_hosts_ids:
                if host_status['os_status'] ==\
                   host_os_status['INSTALL_FAILED']:
                    break
                else:
                    role_hosts_ids.remove(host_id)
        return (hosts_detail, role_hosts_ids)


def _os_thread_bin(req, host_ip, host_id):
    host_meta = {}
    password = "ossdbg1"
    LOG.info(_("Begin update os for host %s." % (host_ip)))
    cmd = 'mkdir -p /var/log/daisy/daisy_update/'
    daisy_cmn.subprocess_call(cmd)

    var_log_path = "/var/log/daisy/daisy_update/%s_update_tfg.log" % host_ip
    with open(var_log_path, "w+") as fp:
        cmd = '/var/lib/daisy/tecs/trustme.sh %s %s' % (host_ip, password)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'clush -S -w %s "mkdir -p /home/daisy_update/"' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'clush -S -b -w %s  "rm -rf /home/daisy_update/*"' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'clush -S -w %s -c /var/lib/daisy/tecs/*CGSL_VPLAT*.iso\
                 /var/lib/daisy/tecs/tfg_upgrade.sh \
                 --dest=/home/daisy_update' % (
            host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'clush -S -w %s "chmod 777 /home/daisy_update/*"' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)
        host_meta['os_progress'] = 30
        host_meta['os_status'] = host_os_status['UPDATING']
        host_meta['messages'] = "os updating,copy iso successfully"
        update_db_host_status(req, host_id, host_meta)
        try:
            exc_result = subprocess.check_output(
                'clush -S -w %s "/home/daisy_update/tfg_upgrade.sh"' % (
                    host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            if e.returncode == 255 and "reboot" in e.output.strip():
                host_meta['os_progress'] = 100
                host_meta['os_status'] = host_os_status['ACTIVE']
                host_meta['messages'] = "upgrade tfg successfully,os reboot"
                LOG.info(
                    _("Update tfg for %s successfully,os reboot!" % host_ip))
                daisy_cmn.check_reboot_ping(host_ip)
            else:
                host_meta['os_progress'] = 0
                host_meta['os_status'] = host_os_status['UPDATE_FAILED']
                host_meta[
                    'messages'] =\
                    e.output.strip()[-400:-200].replace('\n', ' ')
                LOG.error(_("Update tfg for %s failed!" % host_ip))
            update_db_host_status(req, host_id, host_meta)
            fp.write(e.output.strip())
        else:
            host_meta['os_progress'] = 100
            host_meta['os_status'] = host_os_status['ACTIVE']
            host_meta['messages'] = "upgrade tfg successfully"
            update_db_host_status(req, host_id, host_meta)
            LOG.info(_("Update os for %s successfully!" % host_ip))
            fp.write(exc_result)
            if "reboot" in exc_result:
                daisy_cmn.check_reboot_ping(host_ip)


# this will be raise raise all the exceptions of the thread to log file
def os_thread_bin(req, host_ip, host_id):
    try:
        _os_thread_bin(req, host_ip, host_id)
    except Exception as e:
        LOG.exception(e.message)
        raise exception.ThreadBinException(message=e.message)


def _get_host_os_version(host_ip, host_pwd='ossdbg1'):
    version = ""
    tfg_version_file = '/usr/sbin/tfg_showversion'
    try:
        subprocess.check_output("sshpass -p %s ssh -o StrictHostKeyChecking=no"
                                " %s test -f %s" % (host_pwd, host_ip,
                                                    tfg_version_file),
                                shell=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        LOG.info(_("Host %s os version is TFG" % host_ip))
        return version
    try:
        process =\
            subprocess.Popen(["sshpass", "-p", "%s" % host_pwd, "ssh",
                              "-o StrictHostKeyChecking=no", "%s" % host_ip,
                              'tfg_showversion'], shell=False,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        version = process.stdout.read().strip('\n')
    except subprocess.CalledProcessError:
        msg = _("Get host %s os version by subprocess failed!" % host_ip)
        raise exception.SubprocessCmdFailed(message=msg)

    if version:
        LOG.info(_("Host %s os version is %s" % (host_ip, version)))
        return version
    else:
        msg = _("Get host %s os version by tfg_showversion failed!" % host_ip)
        LOG.error(msg)
        raise exception.Invalid(message=msg)


def _cmp_os_version(new_os_file, old_os_version,
                    target_host_ip, password='ossdbg1'):
    shell_file = '/usr/sbin/tfg_showversion'
    if old_os_version:
        try:
            subprocess.check_output("test -f %s" % shell_file, shell=True,
                                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            scripts = ["sshpass -p %s scp -r -o\
                        StrictHostKeyChecking=no %s:%s "
                       "/usr/sbin/" % (password, target_host_ip, shell_file)]
            tecs_cmn.run_scrip(scripts)

        cmp_script = "tfg_showversion %s %s" % (new_os_file, old_os_version)
        try:
            result = subprocess.check_output(cmp_script, shell=True,
                                             stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            return -1
    else:
        if new_os_file.find("Mimosa") != -1:
            return 0
        else:
            msg = _("Please use Mimosa os to upgrade instead of TFG")
            LOG.error(msg)
            raise exception.Forbidden(message=msg)
    return result.find("yes")


def upgrade_os(req, hosts_list):
    upgrade_hosts = []
    max_parallel_os_upgrade_number = int(CONF.max_parallel_os_upgrade_number)
    while hosts_list:
        host_meta = {}
        threads = []
        if len(hosts_list) > max_parallel_os_upgrade_number:
            upgrade_hosts = hosts_list[:max_parallel_os_upgrade_number]
            hosts_list = hosts_list[max_parallel_os_upgrade_number:]
        else:
            upgrade_hosts = hosts_list
            hosts_list = []

        new_os_file = check_tfg_exist()
        for host_info in upgrade_hosts:
            host_id = host_info.keys()[0]
            host_ip = host_info.values()[0]
            host_detail = daisy_cmn.get_host_detail(req, host_id)
            target_host_os = _get_host_os_version(
                host_ip, host_detail['root_pwd'])

            if _cmp_os_version(new_os_file, target_host_os, host_ip) != -1:
                host_meta['os_progress'] = 10
                host_meta['os_status'] = host_os_status['UPDATING']
                host_meta['messages'] = "os updating,begin copy iso"
                update_db_host_status(req, host_id, host_meta)
                t = threading.Thread(target=os_thread_bin, args=(req, host_ip,
                                                                 host_id))
                t.setDaemon(True)
                t.start()
                threads.append(t)
            else:
                LOG.warn(_("new os version is lower than or equal to that of "
                           "host %s, don't need to upgrade!" % host_ip))
        try:
            for t in threads:
                t.join()
        except:
            LOG.warn(_("Join update thread %s failed!" % t))
        else:
            for host_info in upgrade_hosts:
                update_failed_flag = False
                host_id = host_info.keys()[0]
                host_ip = host_info.values()[0]
                host = registry.get_host_metadata(req.context, host_id)
                if host['os_status'] == host_os_status['UPDATE_FAILED'] or\
                        host['os_status'] == host_os_status['INIT']:
                    update_failed_flag = True
                    raise exception.ThreadBinException(
                        "%s update tfg failed! %s" % (
                            host_ip, host['messages']))
                if not update_failed_flag:
                    host_meta = {}
                    host_meta['os_progress'] = 100
                    host_meta['os_status'] = host_os_status['ACTIVE']
                    host_meta['messages'] = "upgrade tfg successfully"
                    update_db_host_status(req, host_id, host_meta)
