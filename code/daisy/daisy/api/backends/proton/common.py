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
/install endpoint for proton API
"""
import subprocess
from oslo_log import log as logging
from webob.exc import HTTPBadRequest

from daisy import i18n

from daisy.common import exception
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

daisy_proton_path = '/var/lib/daisy/proton/'
PROTON_STATE = {
    'INIT': 'init',
    'INSTALLING': 'installing',
    'ACTIVE': 'active',
    'INSTALL_FAILED': 'install-failed',
    'UNINSTALLING': 'uninstalling',
    'UNINSTALL_FAILED': 'uninstall-failed',
    'UPDATING': 'updating',
    'UPDATE_FAILED': 'update-failed',
}


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


def get_roles_and_hosts_list(req, cluster_id):
    roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
    for role in roles:
        if role['deployment_backend'] == daisy_cmn.proton_backend_name:
            role_hosts = get_hosts_of_role(req, role['id'])
            return (role['id'], role_hosts)


def get_role_detail(req, role_id):
    try:
        role = registry.get_role_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return role


def check_and_get_proton_version(daisy_proton_path):
    proton_version_pkg_name = ""
    get_proton_version_pkg = "ls %s| grep ^ZXDTC-PROTON.*\.bin$" \
                             % daisy_proton_path
    obj = subprocess.Popen(
        get_proton_version_pkg, shell=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    if stdoutput:
        proton_version_pkg_name = stdoutput.split('\n')[0]
        proton_version_pkg_file = daisy_proton_path + proton_version_pkg_name
        chmod_for_proton_version = 'chmod +x %s' % proton_version_pkg_file
        daisy_cmn.subprocess_call(chmod_for_proton_version)
    return proton_version_pkg_name


class ProtonShellExector():
    """
    Install proton bin.
    """
    def __init__(self, mgt_ip, proton_version_name, task_type, rmc_ip=''):
        self.task_type = task_type
        self.mgt_ip = mgt_ip
        self.proton_version_file = daisy_proton_path + proton_version_name
        self.rmc_ip = rmc_ip
        self.clush_cmd = ""
        self.oper_type = {
            'install': self._install_proton,
            'uninstall': self._uninstall_proton
        }
        self.oper_shell = {
            'CMD_SSHPASS_PRE': "sshpass -p ossdbg1 %(ssh_ip)s %(cmd)s",
            'CMD_BIN_SCP':
                "scp %(path)s root@%(ssh_ip)s:/home" %
                {'path': self.proton_version_file, 'ssh_ip': mgt_ip},
            'CMD_BIN_INSTALL': "sudo /home/%s install %s 7777" %
                               (proton_version_name, self.rmc_ip),
            'CMD_BIN_UNINSTALL': "sudo /home/%s uninstall" %
                                 proton_version_name,
            'CMD_BIN_REMOVE': "sudo rm -rf /home/%s" % proton_version_name
        }

        self._execute()

    def _install_proton(self):
        self.clush_cmd = \
            "%s;%s" % (
                self.oper_shell['CMD_SSHPASS_PRE'] %
                {"ssh_ip": "", "cmd": self.oper_shell['CMD_BIN_SCP']},
                self.oper_shell['CMD_SSHPASS_PRE'] %
                {
                    "ssh_ip": "ssh " + self.mgt_ip, "cmd":
                    self.oper_shell['CMD_BIN_INSTALL']
                }
            )

        subprocess.check_output(self.clush_cmd, shell=True,
                                stderr=subprocess.STDOUT)

    def _uninstall_proton(self):
        self.clush_cmd = \
            "%s;%s" % (
                self.oper_shell['CMD_SSHPASS_PRE'] %
                {"ssh_ip": "", "cmd": self.oper_shell['CMD_BIN_SCP']},
                self.oper_shell['CMD_SSHPASS_PRE'] %
                {
                    "ssh_ip": "ssh " + self.mgt_ip,
                    "cmd": self.oper_shell['CMD_BIN_UNINSTALL']
                }
            )

        subprocess.check_output(self.clush_cmd, shell=True,
                                stderr=subprocess.STDOUT)

    def _execute(self):
        try:
            if not self.task_type or not self.mgt_ip:
                LOG.error(_("<<<ProtonShellExector::execute,"
                            " input params invalid!>>>"))
                return

            self.oper_type[self.task_type]()
        except subprocess.CalledProcessError as e:
            LOG.warn(_("<<<ProtonShellExector::execute:Execute command "
                       "failed! Reason:%s>>>" % e.output.strip()))
        except Exception as e:
            LOG.exception(_(e.message))
        else:
            LOG.info(_("<<<ProtonShellExector::execute:Execute command:%s,"
                       "successful!>>>" % self.clush_cmd))
