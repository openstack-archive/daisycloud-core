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
/update endpoint for Daisy v1 API
"""

import subprocess

from oslo_log import log as logging
import threading
from daisy import i18n

from daisy.common import exception
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.zenic.common as zenic_cmn

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

zenic_state = zenic_cmn.ZENIC_STATE
daisy_zenic_path = zenic_cmn.daisy_zenic_path


update_zenic_progress = 0.0
update_mutex = threading.Lock()


def update_progress_to_db(req, role_id_list, status,
                          progress_percentage_step=0.0):
    """
    Write update progress and status to db,
    we use global lock object 'update_mutex'
    to make sure this function is thread safety.
    :param req: http req.
    :param role_id_list: Column neeb be update in role table.
    :param status: Update status.
    :return:
    """

    global update_mutex
    global update_zenic_progress
    update_mutex.acquire(True)
    update_zenic_progress += progress_percentage_step
    role = {}
    for role_id in role_id_list:
        if 0 == cmp(status, zenic_state['UPDATING']):
            role['status'] = status
            role['progress'] = update_zenic_progress
        if 0 == cmp(status, zenic_state['UPDATE_FAILED']):
            role['status'] = status
        elif 0 == cmp(status, zenic_state['ACTIVE']):
            role['status'] = status
            role['progress'] = 100
        daisy_cmn.update_role(req, role_id, role)
    update_mutex.release()


def thread_bin(req, host, role_id_list, update_progress_percentage):

    (zenic_version_pkg_file, zenic_version_pkg_name) = \
        zenic_cmn.check_and_get_zenic_version(
        daisy_zenic_path)
    if not zenic_version_pkg_file:
        # selfstate = zenic_state['INSTALL_FAILED']
        selfmessage = "ZENIC version file not found in %s" % daisy_zenic_path
        raise exception.NotFound(message=selfmessage)

    host_ip = host['mgtip']
    password = host['rootpwd']

    cmd = 'mkdir -p /var/log/daisy/daisy_upgrade/'
    daisy_cmn.subprocess_call(cmd)

    var_log_path = \
        "/var/log/daisy/daisy_upgrade/%s_upgrade_zenic.log" % host_ip
    with open(var_log_path, "w+") as fp:
        cmd = '/var/lib/daisy/zenic/trustme.sh %s %s' % (host_ip, password)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'clush -S -b -w %s  /home/zenic/node_stop.sh' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)

        cmd = 'clush -S -b -w %s  rm -rf /home/workspace/%s' % (
            host_ip, zenic_version_pkg_name)
        daisy_cmn.subprocess_call(cmd, fp)

        cmd = 'clush -S -b -w %s  rm -rf /home/workspace/unipack' % (host_ip,)
        daisy_cmn.subprocess_call(cmd, fp)

        try:
            exc_result = subprocess.check_output(
                'sshpass -p ossdbg1 scp %s root@%s:/home/workspace/' % (
                    zenic_version_pkg_file, host_ip,),
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
            -d /home/workspace/unipack' % (host_ip, zenic_version_pkg_name,)
        daisy_cmn.subprocess_call(cmd)

        try:
            exc_result = subprocess.check_output(
                'clush -S -b -w %s  /home/workspace/unipack/node_upgrade.sh'
                % (host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            update_progress_to_db(
                req, role_id_list, zenic_state['UPDATE_FAILED'])
            LOG.info(_("Upgrade zenic for %s failed!" % host_ip))
            fp.write(e.output.strip())
        else:
            update_progress_to_db(
                req, role_id_list, zenic_state['UPDATING'],
                update_progress_percentage)
            LOG.info(_("Upgrade zenic for %s successfully!" % host_ip))
            fp.write(exc_result)

        try:
            exc_result = subprocess.check_output(
                'clush -S -b -w %s  /home/zenic/node_start.sh' % (host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            update_progress_to_db(
                req, role_id_list, zenic_state['UPDATE_FAILED'])
            LOG.info(_("Start zenic for %s failed!" % host_ip))
            fp.write(e.output.strip())
        else:
            update_progress_to_db(
                req, role_id_list, zenic_state['UPDATING'],
                update_progress_percentage)
            LOG.info(_("Start zenic for %s successfully!" % host_ip))
            fp.write(exc_result)
