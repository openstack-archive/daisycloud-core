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

from oslo_log import log as logging
from daisy import i18n
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.tecs.common as tecs_cmn

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

tecs_state = tecs_cmn.TECS_STATE


def update_progress_to_db(req, role_id_list, status, hosts_list, host_ip=None):
    """
    Write uninstall progress and status to db,
    we use global lock object 'uninstall_mutex'
    to make sure this function is thread safety.
    :param req: http req.
    :param role_id_list: Column neeb be update in role table.
    :param status: Uninstall status.
    :return:
    """
    for role_id in role_id_list:
        role_hosts = daisy_cmn.get_hosts_of_role(req, role_id)
        for host_id_ip in hosts_list:
            host_ip_tmp = host_id_ip.values()[0]
            host_id_tmp = host_id_ip.keys()[0]
            if host_ip:
                for role_host in role_hosts:
                    if (host_ip_tmp == host_ip and
                            role_host['host_id'] == host_id_tmp):
                        role_host_meta = {}
                        if 0 == cmp(status, tecs_state['UNINSTALLING']):
                            role_host_meta['progress'] = 10
                            role_host_meta['messages'] = 'TECS uninstalling'
                        if 0 == cmp(status, tecs_state['UNINSTALL_FAILED']):
                            role_host_meta[
                                'messages'] = 'TECS uninstalled failed'
                        elif 0 == cmp(status, tecs_state['INIT']):
                            role_host_meta['progress'] = 100
                            role_host_meta[
                                'messages'] = 'TECS uninstalled successfully'
                        if role_host_meta:
                            role_host_meta['status'] = status
                            daisy_cmn.update_role_host(req, role_host['id'],
                                                       role_host_meta)
            else:
                role = {}
                if 0 == cmp(status, tecs_state['UNINSTALLING']):
                    for role_host in role_hosts:
                        role_host_meta = {}
                        role_host_meta['status'] = status
                        role_host_meta['progress'] = 0
                        daisy_cmn.update_role_host(req,
                                                   role_host['id'],
                                                   role_host_meta)
                    role['progress'] = 0
                    role['messages'] = 'TECS uninstalling'
                if 0 == cmp(status, tecs_state['UNINSTALL_FAILED']):
                    role['messages'] = 'TECS uninstalled failed'
                elif 0 == cmp(status, tecs_state['INIT']):
                    role['progress'] = 100
                    role['messages'] = 'TECS uninstalled successfully'
                if role:
                    role['status'] = status
                    daisy_cmn.update_role(req, role_id, role)


def _thread_bin(req, host_ip, role_id_list, hosts_list):
    # uninstall network-configuration-1.1.1-15.x86_64.rpm
    update_progress_to_db(
        req, role_id_list, tecs_state['UNINSTALLING'], hosts_list, host_ip)
    tecs_cmn.TecsShellExector(host_ip, 'uninstall_rpm')

    cmd = 'mkdir -p /var/log/daisy/daisy_uninstall/'
    daisy_cmn.subprocess_call(cmd)
    password = "ossdbg1"
    var_log_path = "/var/log/daisy/daisy_uninstall/\
                    %s_uninstall_tecs.log" % host_ip
    with open(var_log_path, "w+") as fp:
        cmd = '/var/lib/daisy/tecs/trustme.sh %s %s' % (host_ip, password)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'clush -S -b -w %s "rm -rf /home/daisy_uninstall"' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'clush -S -w %s "mkdir -p /home/daisy_uninstall"' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)

        try:
            subprocess.check_output(
                'clush -S -w %s -c /var/lib/daisy/tecs/ZXTECS*.bin \
                                --dest=/home/daisy_uninstall' % (
                    host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            update_progress_to_db(
                req, role_id_list, tecs_state[
                    'UNINSTALL_FAILED'], hosts_list, host_ip)
            LOG.error(_("scp TECS bin for %s failed!" % host_ip))
            fp.write(e.output.strip())

        cmd = 'clush -S -w %s "chmod 777 /home/daisy_uninstall/*"' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)

        try:
            exc_result = subprocess.check_output(
                'clush -S -w %s /home/daisy_uninstall/ZXTECS*.bin clean' % (
                    host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            update_progress_to_db(
                req, role_id_list, tecs_state[
                    'UNINSTALL_FAILED'], hosts_list, host_ip)
            LOG.error(_("Uninstall TECS for %s failed!" % host_ip))
            fp.write(e.output.strip())
        else:
            update_progress_to_db(req, role_id_list, tecs_state['INIT'],
                                  hosts_list, host_ip)
            LOG.info(_("Uninstall TECS for %s successfully!" % host_ip))
            fp.write(exc_result)
# this will be raise raise all the exceptions of the thread to log file


def thread_bin(req, host_ip, role_id_list, hosts_list):
    try:
        _thread_bin(req, host_ip, role_id_list, hosts_list)
    except Exception as e:
        LOG.exception(e.message)
