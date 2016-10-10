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
/install endpoint for daisy API
"""
import copy
import subprocess
import time
import json

from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest

from daisy import i18n

from daisy.common import exception
from daisy.common import utils
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn


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

    def _set_boot_or_power_state(self, user, passwd, addr, action):
        count = 0
        repeat_times = 24
        ipmi_result_flag = True
        while count < repeat_times:
            rc = daisy_cmn.set_boot_or_power_state(user, passwd, addr, action)
            if rc == 0:
                LOG.info(
                    _("Set %s to '%s' successfully for %s times" % (
                        addr, action, count + 1)))
                break
            else:
                count += 1
                LOG.info(
                    _("Try setting %s to '%s' failed for %s times"
                      % (addr, action, count)))
        if count >= repeat_times:
            ipmi_result_flag = False
            message = "Set %s to '%s' failed for 10 mins" % (addr, action)
            raise exception.IMPIOprationFailed(message=message)
        return ipmi_result_flag

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

        if (not host_detail['ipmi_user'] or
                not host_detail['ipmi_passwd'] or
                not host_detail['ipmi_addr']):
            self.message = "Invalid ipmi information configed for host %s" \
                           % host_detail['id']
            raise exception.NotFound(message=self.message)

            ipmi_result_flag = self._set_boot_or_power_state(
                host_detail['ipmi_user'],
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
        if host_detail.get('hwm_id') or ipmi_result_flag:
            rc, error = daisy_cmn.install_os(**kwargs)
            if rc != 0:
                install_os_description = error
                LOG.info(
                    _("install os config failed because of '%s'" % error))
                host_status = {'os_status': host_os_status['INSTALL_FAILED'],
                               'os_progress': 0,
                               'messages': error}
                daisy_cmn.update_db_host_status(self.req,
                                                host_detail['id'],
                                                host_status)
                msg = "ironic install os return failed for host %s" % \
                      host_detail['id']
                raise exception.OSInstallFailed(message=msg)

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
        install_result = daisy_cmn.get_install_progress(
            host_detail['dhcp_mac'])
        rc = int(install_result['return_code'])
        host_status['os_progress'] = int(install_result['progress'])
        if rc == 0:
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
        else:
            LOG.info(_("host %s install failed." % host_id))
            host_status['os_status'] = host_os_status['INSTALL_FAILED']
            host_status['messages'] = install_result['info']

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

    def pxe_server_build(req, install_meta):
        params = {'filters': {'type': 'system'}}
        try:
            networks = registry.get_all_networks(req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)

        try:
            ip_inter = lambda x: sum([256 ** j * int(i)
                                      for j, i in enumerate(
                                      x.split('.')[::-1])])
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
                        ip_addr_min = \
                            inter_ip(ip_addr_int & (mask & 0xffffffff))
                        ip_addr_max = \
                            inter_ip(ip_addr_int | (~mask & 0xffffffff))
                        if not client_ip_begin and not client_ip_end:
                            client_ip_begin = \
                                inter_ip((ip_inter(ip_addr_min)) + 2)
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
                            pxe_server_ip = \
                                inter_ip((ip_inter(ip_addr_min)) + 1)

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
            daisy_cmn.build_pxe_server(**args)
        except exception.Invalid as e:
            msg = "build pxe server failed"
            LOG.error(msg)
            raise exception.InvalidNetworkConfig(msg)

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
