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

import threading

from daisy import i18n

from daisy.common import exception
from daisy.api.backends import driver
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.proton.common as proton_cmn
import daisy.api.backends.proton.install as instl
import daisy.api.backends.proton.uninstall as unstl


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

proton_state = proton_cmn.PROTON_STATE


class API(driver.DeploymentDriver):
    """
    The hosts API is a RESTful web service for host data. The API
    is as follows::

        GET  /hosts -- Returns a set of brief metadata about hosts
        GET  /hosts/detail -- Returns a set of detailed metadata about
                              hosts
        HEAD /hosts/<ID> -- Return metadata about an host with id <ID>
        GET  /hosts/<ID> -- Return host data for host with id <ID>
        POST /hosts -- Store host data and return metadata about the
                        newly-stored host
        PUT  /hosts/<ID> -- Update host metadata and/or upload host
                            data for a previously-reserved host
        DELETE /hosts/<ID> -- Delete the host with id <ID>
    """
    def __init__(self):
        super(API, self).__init__()
        return

    def install(self, req, cluster_id):
        """
        Install PROTON to a cluster.
        cluster_id:cluster id
        """
        proton_install_task = instl.ProtonInstallTask(req, cluster_id)
        proton_install_task.start()

    def _uninstall(self, req, role_id, threads):
        try:
            for t in threads:
                t.setDaemon(True)
                t.start()
            LOG.info(_("uninstall threads have started,"
                       " please waiting...."))

            for t in threads:
                t.join()
        except:
            LOG.warn(_("Join uninstall thread failed!"))
        else:
            uninstall_failed_flag = False
            role = daisy_cmn.get_role_detail(req, role_id)
            if role['progress'] == 100:
                unstl.update_progress_to_db(
                    req, role_id, proton_state['UNINSTALL_FAILED'])
                uninstall_failed_flag = True
                return
            if role['status'] == proton_state['UNINSTALL_FAILED']:
                uninstall_failed_flag = True
                return
            if not uninstall_failed_flag:
                LOG.info(_("all uninstall threads have done,"
                           " set role of proton status to 'init'!"))
                unstl.update_progress_to_db(req, role_id,
                                            proton_state['INIT'])

    def uninstall(self, req, cluster_id):
        """
        Uninstall PROTON to a cluster.
        :raises HTTPBadRequest if x-install-cluster is missing
        """
        (role_id, hosts_list) = proton_cmn.get_roles_and_hosts_list(req,
                                                                    cluster_id)
        if role_id:
            if not hosts_list:
                msg = _("there is no host in cluster %s") % cluster_id
                raise exception.ThreadBinException(msg)

            unstl.update_progress_to_db(req, role_id,
                                        proton_state['UNINSTALLING'], 0.0)
            uninstall_progress_percentage = \
                round(1 * 1.0 / len(hosts_list), 2) * 100

            threads = []
            for host in hosts_list:
                host_detail = proton_cmn.get_host_detail(req, host['host_id'])
                t = threading.Thread(target=unstl.thread_bin,
                                     args=(req,
                                           host_detail['interfaces'][0]['ip'],
                                           role_id,
                                           uninstall_progress_percentage))
                threads.append(t)

            self._uninstall(req, role_id, threads)
