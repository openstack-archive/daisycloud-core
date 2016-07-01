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
import threading
from daisy import i18n
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.zenic.common as zenic_cmn

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

zenic_state = zenic_cmn.ZENIC_STATE

uninstall_zenic_progress = 100.0
uninstall_mutex = threading.Lock()


def update_progress_to_db(req, role_id_list, status,
                          progress_percentage_step=0.0):
    """
    Write uninstall progress and status to db,
    we use global lock object 'uninstall_mutex'
    to make sure this function is thread safety.
    :param req: http req.
    :param role_id_list: Column neeb be update in role table.
    :param status: Uninstall status.
    :return:
    """

    global uninstall_mutex
    global uninstall_zenic_progress
    uninstall_mutex.acquire(True)
    uninstall_zenic_progress -= progress_percentage_step
    role = {}
    for role_id in role_id_list:
        if 0 == cmp(status, zenic_state['UNINSTALLING']):
            role['status'] = status
            role['progress'] = uninstall_zenic_progress
        if 0 == cmp(status, zenic_state['UNINSTALL_FAILED']):
            role['status'] = status
        elif 0 == cmp(status, zenic_state['INIT']):
            role['status'] = status
            role['progress'] = 0
        daisy_cmn.update_role(req, role_id, role)
    uninstall_mutex.release()


def thread_bin(req, host, role_id_list, uninstall_progress_percentage):
    host_ip = host['mgtip']
    password = host['rootpwd']
    cmd = 'mkdir -p /var/log/daisy/daisy_uninstall/'
    daisy_cmn.subprocess_call(cmd)
    var_log_path =\
        "/var/log/daisy/daisy_uninstall/%s_uninstall_zenic.log" % host_ip
    with open(var_log_path, "w+") as fp:
        cmd = '/var/lib/daisy/zenic/trustme.sh %s %s' % (host_ip, password)
        daisy_cmn.subprocess_call(cmd, fp)

        try:
            exc_result = subprocess.check_output(
                'clush -S -b -w %s  /home/zenic/node_stop.sh' % (host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            update_progress_to_db(
                req, role_id_list, zenic_state['UNINSTALL_FAILED'])
            fp.write(e.output.strip())
        else:
            update_progress_to_db(
                req, role_id_list, zenic_state['UNINSTALLING'],
                uninstall_progress_percentage)
            fp.write(exc_result)
