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
import time
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


class KOLLAUpgradeTask(Thread):
    """
    Class for kolla upgrade openstack.
    """

    def __init__(self, req, cluster_id, version_id, update_file):
        super(KOLLAUpgradeTask, self).__init__()
        self.req = req
        self.cluster_id = cluster_id
        self.progress = 0
        self.version_id = version_id
        self.update_file = update_file
        self.message = ""
        self.kolla_file = "/home/kolla_install"
        self.log_file = "/var/log/daisy/kolla_%s_upgrade.log" % self.cluster_id


    def run(self):
        hosts = registry.get_cluster_hosts(self.req.context, self.cluster_id)
        hosts_id_list = [host['host_id'] for host in hosts]
        cluster_meta = registry.get_cluster_metadata(self.req.context, self.cluster_id)
        self.message = "prechecking envirnoment"
        update_all_host_progress_to_db(self.req, hosts_id_list, 
                                       {'progress': 0,
                                        'status': kolla_state['UPDATING'],
                                        'messages': self.message})
        kolla_version_pkg_file = kolla_cmn.check_and_get_kolla_version(
            kolla_cmn.daisy_kolla_ver_path, self.update_file)
        if not kolla_version_pkg_file:
            self.message = "kolla version file not found in %s"\
                % kolla_cmn.daisy_kolla_path
            update_all_host_progress_to_db(self.req, hosts_id_list,
                                           {'progress': 0,
                                            'status': kolla_state['UPDATE_FAILED'],
                                            'messages': self.message})
            raise exception.NotFound(message=self.message)
        if cluster_meta['tecs_version_id']:
            version_data = registry.get_version_metadata(
                self.req.context, cluster_meta['tecs_version_id'])
            if version_data['name'] == self.update_file:
                LOG.error(_("kolla version %s is not need to upgrade!"
                            % version_data['name']))
                self.message = "kolla version %s is not need to upgrade!" % version_data['name']
                update_all_host_progress_to_db(self.req, hosts_id_list,
                                               {'progress': 0,
                                                'status': kolla_state['UPDATE_FAILED'],
                                                'messages': self.message})
                return
        for host in hosts:
            host_meta = daisy_cmn.get_host_detail(self.req, host["host_id"])
            host_ip = daisy_cmn.get_management_ip(host_meta)
            host_ip_set = set()
            host_ip_set.add(host_ip)
            unreached_hosts = daisy_cmn.check_ping_hosts(
                host_ip_set, 3)
            if unreached_hosts:
                self.message = "hosts %s ping failed" % unreached_hosts
                update_all_host_progress_to_db(self.req, hosts_id_list,
                                               {'progress': 0,
                                                'status': kolla_state['UPDATE_FAILED'],
                                                'messages': self.message})
                raise exception.NotFound(message=self.message)

        LOG.info(_("precheck envirnoment successfully ..."))
        self.message = "openstack upgrading"
        update_all_host_progress_to_db(self.req, hosts_id_list, 
                                       {'progress': 10,
                                        'status': kolla_state['UPDATING'],
                                        'messages': self.message})
        with open(self.log_file, "w+") as fp:
            kolla_cmn.version_load(kolla_version_pkg_file, fp)
            update_all_host_progress_to_db(self.req, hosts_id_list, 
                                           {'progress': 20,
                                            'status': kolla_state['UPDATING'],
                                            'messages': self.message})
            try:
                LOG.info(_("begin to kolla-ansible "
                           "upgrade for all nodes..."))
                exc_result = subprocess.check_output(
                    'cd %s/kolla && ./tools/kolla-ansible upgrade -i '
                    '%s/kolla/ansible/inventory/multinode' %
                    (self.kolla_file, self.kolla_file),
                    shell=True, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                LOG.error("kolla-ansible upgrade failed!")
                self.message = "kolla-ansible upgrade failed!"
                update_all_host_progress_to_db(self.req, hosts_id_list,
                                               {'progress': 20,
                                                'status': kolla_state['UPDATE_FAILED'],
                                                'messages': self.message})
                LOG.info(_("kolla-ansible upgrade failed!"))
                fp.write(e.output.strip())
                exit()
            else:
                LOG.info(_("openstack upgraded successfully"))
                fp.write(exc_result)
                self.message = "openstack upgraded successfully"
                update_all_host_progress_to_db(self.req, hosts_id_list,
                                               {'progress': 100,
                                                'status': kolla_state['ACTIVE'],
                                                'messages': self.message})
                for host_id in hosts_id_list:
                    daisy_cmn.update_db_host_status(
                        self.req, host_id, {'tecs_version_id': self.version_id,
                                            'tecs_patch_id': ''})
                cluster_meta = {}
                cluster_meta['tecs_version_id'] = self.version_id
                cluster_meta = registry.update_cluster_metadata(
                    self.req.context, self.cluster_id, cluster_meta)
                LOG.info(_("openstack upgraded for cluster %s successfully."
                           % self.cluster_id))

