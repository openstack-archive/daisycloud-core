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
/install endpoint for zenic API
"""
import time

from oslo_log import log as logging

import threading
from daisy import i18n

from daisy.common import exception
from daisy.api.backends import driver
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.zenic.common as zenic_cmn
import daisy.api.backends.zenic.install as instl
import daisy.api.backends.zenic.uninstall as unstl
import daisy.api.backends.zenic.upgrade as upgrd


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

zenic_state = zenic_cmn.ZENIC_STATE


class API(driver.DeploymentDriver):

    def __init__(self):
        super(API, self).__init__()
        return

    def install(self, req, cluster_id):
        """
        Install zenic to a cluster.

        param req: The WSGI/Webob Request object
        cluster_id:cluster id
        """

        # instl.pxe_server_build(req, install_meta)
        # get hosts config which need to install OS
        # hosts_need_os = instl.get_cluster_hosts_config(req, cluster_id)
        # if have hosts need to install os, ZENIC installataion executed
        #   in OSInstallTask
        # if hosts_need_os:
        # os_install_obj = instl.OSInstallTask(req, cluster_id, hosts_need_os)
        # os_install_thread = Thread(target=os_install_obj.run)
        # os_install_thread.start()
        # else:
        LOG.info(
            _("No host need to install os, begin install ZENIC for cluster %s."
              % cluster_id))
        zenic_install_task = instl.ZENICInstallTask(req, cluster_id)
        zenic_install_task.start()

        LOG.info((_("begin install zenic, please waiting....")))
        time.sleep(5)
        LOG.info((_("install zenic successfully")))

    def uninstall(self, req, cluster_id):
        """
        Uninstall ZENIC to a cluster.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-install-cluster is missing
        """

        (role_id_list, hosts_list) = zenic_cmn.get_roles_and_hosts_list(
            req, cluster_id)
        if role_id_list:
            if not hosts_list:
                msg = _("there is no host in cluster %s") % cluster_id
                raise exception.ThreadBinException(msg)

            unstl.update_progress_to_db(
                req, role_id_list, zenic_state['UNINSTALLING'], 0.0)
            uninstall_progress_percentage =\
                round(1 * 1.0 / len(hosts_list), 2) * 100

            threads = []
            for host in hosts_list:
                t = threading.Thread(target=unstl.thread_bin, args=(
                    req, host, role_id_list, uninstall_progress_percentage))
                t.setDaemon(True)
                t.start()
                threads.append(t)
            LOG.info(_("uninstall threads have started, please waiting...."))

            try:
                for t in threads:
                    t.join()
            except:
                LOG.warn(_("Join uninstall thread %s failed!" % t))
            else:
                uninstall_failed_flag = False
                for role_id in role_id_list:
                    role = daisy_cmn.get_role_detail(req, role_id)
                    if role['progress'] == 100:
                        unstl.update_progress_to_db(
                            req, role_id_list, zenic_state['UNINSTALL_FAILED'])
                        uninstall_failed_flag = True
                        break
                    if role['status'] == zenic_state['UNINSTALL_FAILED']:
                        uninstall_failed_flag = True
                        break
                if not uninstall_failed_flag:
                    LOG.info(
                        _("all uninstall threads have done,\
                            set all roles status to 'init'!"))
                    unstl.update_progress_to_db(
                        req, role_id_list, zenic_state['INIT'])

        LOG.info((_("begin uninstall zenic, please waiting....")))
        time.sleep(5)
        LOG.info((_("uninstall zenic successfully")))

    def upgrade(self, req, cluster_id):
        """
        update zenic to a cluster.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-install-cluster is missing

        """
        (role_id_list, hosts_list) = zenic_cmn.get_roles_and_hosts_list(
            req, cluster_id)
        if not hosts_list:
            msg = _("there is no host in cluster %s") % cluster_id
            raise exception.ThreadBinException(msg)

        upgrd.update_progress_to_db(
            req, role_id_list, zenic_state['UPDATING'], 0.0)
        update_progress_percentage = round(1 * 1.0 / len(hosts_list), 2) * 100

        threads = []
        for host in hosts_list:
            t = threading.Thread(target=upgrd.thread_bin, args=(
                req, host, role_id_list, update_progress_percentage))
            t.setDaemon(True)
            t.start()
            threads.append(t)
        LOG.info(_("upgrade threads have started, please waiting...."))

        try:
            for t in threads:
                t.join()
        except:
            LOG.warn(_("Join upgrade thread %s failed!" % t))
        else:
            update_failed_flag = False
            for role_id in role_id_list:
                role = daisy_cmn.get_role_detail(req, role_id)
                if role['progress'] == 0:
                    upgrd.update_progress_to_db(
                        req, role_id_list, zenic_state['UPDATE_FAILED'])
                    update_failed_flag = True
                    break
                if role['status'] == zenic_state['UPDATE_FAILED']:
                    update_failed_flag = True
                    break
            if not update_failed_flag:
                LOG.info(
                    _("all update threads have done, \
                        set all roles status to 'active'!"))
                upgrd.update_progress_to_db(
                    req, role_id_list, zenic_state['ACTIVE'])
