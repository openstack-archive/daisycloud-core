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
from oslo_log import log as logging
from threading import Thread

from daisy import i18n
import daisy.api.v1

from daisy.common import exception
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.proton.common as proton_cmn


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE


proton_state = proton_cmn.PROTON_STATE
daisy_proton_path = proton_cmn.daisy_proton_path


def get_proton_ip(req, role_hosts):
    proton_ip_list = []
    for role_host in role_hosts:
        host_detail = proton_cmn.get_host_detail(req,
                                                 role_host['host_id'])
        for interface in host_detail['interfaces']:
            for network in interface['assigned_networks']:
                if network.get("name") == "MANAGEMENT":
                    proton_ip_list.append(network.get("ip"))

    return proton_ip_list


def get_proton_hosts(req, cluster_id):
    all_roles = proton_cmn.get_roles_detail(req)
    for role in all_roles:
        if role['cluster_id'] == cluster_id and role['name'] == 'PROTON':
            role_hosts = proton_cmn.get_hosts_of_role(req, role['id'])

            return get_proton_ip(req, role_hosts)


def get_rmc_host(req, cluster_id):
    return "10.43.211.63"


class ProtonInstallTask(Thread):
    """
    Class for install proton bin.
    """
    def __init__(self, req, cluster_id):
        super(ProtonInstallTask, self).__init__()
        self.req = req
        self.cluster_id = cluster_id
        self.progress = 0
        self.message = ""
        self.state = proton_state['INIT']
        self.proton_ip_list = []
        self.install_log_fp = None
        self.last_line_num = 0
        self.need_install = False
        self.ping_times = 36

    def _update_install_progress_to_db(self):
        """
        Update progress of intallation to db.
        :return:
        """
        roles = daisy_cmn.get_cluster_roles_detail(self.req, self.cluster_id)
        for role in roles:
            if role['deployment_backend'] != daisy_cmn.proton_backend_name:
                continue
            role_hosts = daisy_cmn.get_hosts_of_role(self.req, role['id'])
            for role_host in role_hosts:
                if role_host['status'] != proton_state['ACTIVE']:
                    self.need_install = True
                    role_host['status'] = self.state
                    daisy_cmn.update_role_host(self.req, role_host['id'],
                                               role_host)
                    role['status'] = self.state
                    role['messages'] = self.message
                    daisy_cmn.update_role(self.req, role['id'], role)

    def run(self):
        try:
            self._run()
        except (exception.InstallException,
                exception.NotFound,
                exception.InstallTimeoutException) as e:
            LOG.exception(e.message)
        else:
            self.progress = 100
            self.state = proton_state['ACTIVE']
            self.message = "Proton install successfully"
            LOG.info(_("Install PROTON for cluster %s successfully." %
                       self.cluster_id))
        finally:
            self._update_install_progress_to_db()

    def _run(self):
        """
        Exectue install file(.bin) with sync mode.
        :return:
        """
        if not self.cluster_id or not self.req:
            raise exception.InstallException(
                cluster_id=self.cluster_id, reason="invalid params.")

        self.proton_ip_list = get_proton_hosts(self.req, self.cluster_id)
        unreached_hosts = daisy_cmn.check_ping_hosts(self.proton_ip_list,
                                                     self.ping_times)
        if unreached_hosts:
            self.state = proton_state['INSTALL_FAILED']
            self.message = "hosts %s ping failed" % unreached_hosts
            raise exception.NotFound(message=self.message)

        proton_version_name = \
            proton_cmn.check_and_get_proton_version(daisy_proton_path)
        if not proton_version_name:
            self.state = proton_state['INSTALL_FAILED']
            self.message = "PROTON version file not found in %s" % \
                           daisy_proton_path
            raise exception.NotFound(message=self.message)

        rmc_ip = get_rmc_host(self.req, self.cluster_id)

        for proton_ip in self.proton_ip_list:
            proton_cmn.ProtonShellExector(proton_ip, proton_version_name,
                                          'install', rmc_ip)
