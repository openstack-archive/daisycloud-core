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
import daisy.api.backends.proton.common as proton_cmn

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

proton_state = proton_cmn.PROTON_STATE
daisy_proton_path = proton_cmn.daisy_proton_path

# uninstall init progress is 100, when uninstall succefully,
# uninstall progress is 0, and web display progress is reverted
uninstall_proton_progress = 100.0
uninstall_mutex = threading.Lock()


def update_progress_to_db(req, role_id, status, progress_percentage_step=0.0):
    """
    Write uninstall progress and status to db, we use global lock object
    'uninstall_mutex' to make sure this function is thread safety.
    :param req: http req.
    :param role_id_list: Column neeb be update in role table.
    :param status: Uninstall status.
    :return:
    """
    global uninstall_mutex
    global uninstall_proton_progress
    uninstall_mutex.acquire(True)
    uninstall_proton_progress -= progress_percentage_step
    role = {}

    role_hosts = daisy_cmn.get_hosts_of_role(req, role_id)
    if status == proton_state['UNINSTALLING']:
        role['status'] = status
        role['progress'] = uninstall_proton_progress
        role['messages'] = 'Proton uninstalling'
        for role_host in role_hosts:
            role_host_meta = dict()
            role_host_meta['status'] = status
            role_host_meta['progress'] = uninstall_proton_progress
            daisy_cmn.update_role_host(req, role_host['id'], role_host_meta)
    if status == proton_state['UNINSTALL_FAILED']:
        role['status'] = status
        role['messages'] = 'Uninstall-failed'
        for role_host in role_hosts:
            role_host_meta = dict()
            role_host_meta['status'] = status
            daisy_cmn.update_role_host(req, role_host['id'], role_host_meta)
    elif status == proton_state['INIT']:
        role['status'] = status
        role['progress'] = 0
        role['messages'] = 'Proton uninstall successfully'
        daisy_cmn.delete_role_hosts(req, role_id)

    daisy_cmn.update_role(req, role_id, role)
    uninstall_mutex.release()


def _thread_bin(req, host_ip, role_id, uninstall_progress_percentage):
    try:
        proton_version_name = \
            proton_cmn.check_and_get_proton_version(daisy_proton_path)
        proton_cmn.ProtonShellExector(host_ip, proton_version_name,
                                      'uninstall')
    except subprocess.CalledProcessError:
        update_progress_to_db(req, role_id, proton_state['UNINSTALL_FAILED'])
        LOG.info(_("Uninstall PROTON for %s failed!" % host_ip))
    else:
        update_progress_to_db(req, role_id, proton_state['UNINSTALLING'],
                              uninstall_progress_percentage)
        LOG.info(_("Uninstall PROTON for %s successfully!" % host_ip))


def thread_bin(req, host_ip, role_id, uninstall_progress_percentage):
    try:
        _thread_bin(req, host_ip, role_id, uninstall_progress_percentage)
    except Exception as e:
        LOG.exception(e.message)
