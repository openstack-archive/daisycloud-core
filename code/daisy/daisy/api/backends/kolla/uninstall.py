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
/uninstall endpoint for Daisy v1 API
"""

import subprocess
from oslo_log import log as logging
from daisy import i18n
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.kolla.common as kolla_cmn
import daisy.registry.client.v1.api as registry
from threading import Thread
from daisy.common import exception


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

kolla_state = kolla_cmn.KOLLA_STATE


def update_all_host_progress_to_db(req, hosts_id_list, role_host_meta={}):
    for host_id in hosts_id_list:
        host_roles = registry.get_host_roles_by_host_id(req.context, host_id)
        for host_role_id in host_roles:
            if role_host_meta:
                daisy_cmn.update_role_host(req, host_role_id['id'],
                                           role_host_meta)


class KOLLAUninstallTask(Thread):
    """
    Class for kolla uninstall openstack.
    """

    def __init__(self, req, cluster_id):
        super(KOLLAUpgradeTask, self).__init__()
        self.req = req
        self.cluster_id = cluster_id
        self.message = ""
        self.kolla_file = "/home/kolla_install"
        self.log_file = "/var/log/daisy/kolla_%s_uninstall.log" \
            % self.cluster_id

    def run(self):
        hosts = registry.get_cluster_hosts(self.req.context, self.cluster_id)
        hosts_id_list = [host['host_id'] for host in hosts]
        self.message = "precheck envirnoment"
        update_all_host_progress_to_db(self.req, hosts_id_list,
                                       {'progress': 0,
                                        'status': kolla_state['UNINSTALLING'],
                                        'messages': self.message})

        for host in hosts:
            host_meta = daisy_cmn.get_host_detail(self.req, host["host_id"])
            host_ip = daisy_cmn.get_management_ip(host_meta)
            host_ip_set = set()
            host_ip_set.add(host_ip)
            unreached_hosts = daisy_cmn.check_ping_hosts(host_ip_set, 3)
            if unreached_hosts:
                self.message = "hosts %s ping failed" % unreached_hosts
                update_all_host_progress_to_db(self.req, hosts_id_list,
                                               {'progress': 0,
                                                'status': kolla_state[
                                                    'UNINSTALL_FAILED'],
                                                'messages': self.message})
                raise exception.NotFound(message=self.message)

        LOG.info(_("precheck envirnoment successfully ..."))
        self.message = "uninstalling openstack"
        update_all_host_progress_to_db(self.req, hosts_id_list,
                                       {'progress': 10,
                                        'status': kolla_state[
                                            'UNINSTALLING'],
                                        'messages': self.message})

        with open(self.log_file, "w+") as fp:
            try:
                LOG.info(_("begin kolla-ansible destory"))
                exc_result = subprocess.check_output(
                    'cd %s/kolla && ./tools/kolla-ansible destroy '
                    '--include-images -i '
                    '%s/kolla/ansible/inventory/multinode '
                    '--yes-i-really-really-mean-it' %
                    (self.kolla_file, self.kolla_file),
                    shell=True, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                LOG.error("kolla-ansible destory failed!")
                self.message = "kolla-ansible destory failed!"
                update_all_host_progress_to_db(self.req, hosts_id_list,
                                               {'progress': 10,
                                                'status': kolla_state[
                                                    'UNINSTALL_FAILED'],
                                                'messages': self.message})
                fp.write(e.output.strip())
                exit()
            else:
                LOG.info(_("openstack uninstall successfully"))
                fp.write(exc_result)
                self.message = "openstack uninstall successfully"
                update_all_host_progress_to_db(self.req, hosts_id_list,
                                               {'progress': 100,
                                                'status': kolla_state[
                                                    'INIT'],
                                                'messages': self.message})
                for host_id in hosts_id_list:
                    daisy_cmn.update_db_host_status(
                        self.req, host_id, {'tecs_version_id': '',
                                            'tecs_patch_id': ''})

                cluster_meta = {}
                cluster_meta['tecs_version_id'] = ''
                cluster_meta = registry.update_cluster_metadata(
                    self.req.context, self.cluster_id, cluster_meta)

                LOG.info(_("openstack uninstalled for cluster %s successfully."
                           % self.cluster_id))
