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
/install endpoint for tecs API
"""
import subprocess
import commands

from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest

import threading

from daisy import i18n

from daisy.common import exception
from daisy.api.backends.tecs import config
from daisy.api.backends import driver
import daisy.api.backends.os as os_handle
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.tecs.common as tecs_cmn
import daisy.api.backends.tecs.install as instl
import daisy.api.backends.tecs.uninstall as unstl
import daisy.api.backends.tecs.upgrade as upgrd
import daisy.api.backends.tecs.disk_array as disk_array
from daisy.api.backends.tecs import write_configs
import daisy.registry.client.v1.api as registry


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
CONF = cfg.CONF
upgrade_opts = [
    cfg.StrOpt('max_parallel_os_upgrade_number', default=10,
               help='Maximum number of hosts upgrade os at the same time.'),
]
CONF.register_opts(upgrade_opts)

tecs_state = tecs_cmn.TECS_STATE
daisy_tecs_path = tecs_cmn.daisy_tecs_path


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
        Install TECS to a cluster.

        param req: The WSGI/Webob Request object
        cluster_id:cluster id
        """
        write_configs.update_configset(req, cluster_id)

        tecs_install_task = instl.TECSInstallTask(req, cluster_id)
        tecs_install_task.start()

    def _get_roles_and_hosts_ip_list(self, req, cluster_id):
        role_host_ips = {'ha': set(), 'lb': set(), 'all': set()}
        role_id_list = set()
        hosts_id_list = []
        hosts_list = []
        tecs_install_failed_list = set()

        roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
        cluster_networks = daisy_cmn.get_cluster_networks_detail(
            req, cluster_id)
        for role in roles:
            if role['deployment_backend'] != daisy_cmn.tecs_backend_name:
                continue
            role_hosts = daisy_cmn.get_hosts_of_role(req, role['id'])
            if role_hosts:
                for role_host in role_hosts:
                    host = daisy_cmn.get_host_detail(req, role_host['host_id'])
                    host_ip = tecs_cmn.get_host_network_ip(
                        req, host, cluster_networks, 'MANAGEMENT')
                    if role['name'] == "CONTROLLER_HA":
                        role_host_ips['ha'].add(host_ip)
                    if role['name'] == "CONTROLLER_LB":
                        role_host_ips['lb'].add(host_ip)
                    role_host_ips['all'].add(host_ip)
                    hosts_id_list.append({host['id']: host_ip})
                    if role_host['status'] == tecs_state['INSTALL_FAILED']:
                        tecs_install_failed_list.add(host_ip)
                role_id_list.add(role['id'])
        for host in hosts_id_list:
            if host not in hosts_list:
                hosts_list.append(host)
        return (role_id_list, role_host_ips,
                hosts_list, tecs_install_failed_list)

    def _query_progress(self, req, cluster_id, action=""):
        nodes_list = []
        roles = daisy_cmn.get_roles_detail(req)
        (role_id_list, role_host_ips, hosts_list, tecs_install_failed_list) =\
            self._get_roles_and_hosts_ip_list(req, cluster_id)
        for host in hosts_list:
            node = {}
            host_id = host.keys()[0]
            host = daisy_cmn.get_host_detail(req, host_id)
            node['id'] = host['id']
            node['name'] = host['name']

            if 0 == cmp("upgrade", action):
                node['os-progress'] = host['os_progress']
                node['os-status'] = host['os_status']
                node['os-messages'] = host['messages']

            if host['status'] == "with-role":
                host_roles = [role for role in roles if role['name'] in host[
                    'role'] and role['cluster_id'] == cluster_id]
                if host_roles:
                    node['role-status'] = host_roles[0]['status']
                    node['role-progress'] = str(host_roles[0]['progress'])
                    # node['role-message'] = host_roles[0]['messages']
            nodes_list.append(node)
        if nodes_list:
            return {'tecs_nodes': nodes_list}
        else:
            return {'tecs_nodes': "TECS uninstall successfully,\
                    the host has been removed from the host_roles table"}

    def _modify_running_version_of_configs(self, req,
                                           running_version, cluster_id):
        cluster_configs_list = daisy_cmn.get_cluster_configs_list(req,
                                                                  cluster_id)
        if cluster_configs_list:
            for cluster_config in cluster_configs_list:
                registry.update_config_metadata(req.context,
                                                cluster_config['id'],
                                                {'running_version':
                                                 running_version})

    def uninstall(self, req, cluster_id):
        """
        Uninstall TECS to a cluster.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-install-cluster is missing
        """
        (role_id_list, role_host_ips, hosts_list, tecs_install_failed_list) =\
            self._get_roles_and_hosts_ip_list(req, cluster_id)
        if role_id_list:
            if not role_host_ips['all']:
                msg = _("there is no host in cluster %s") % cluster_id
                raise exception.ThreadBinException(msg)

            unstl.update_progress_to_db(
                req, role_id_list, tecs_state['UNINSTALLING'], hosts_list)

            threads = []
            for host_ip in role_host_ips['all']:
                t = threading.Thread(
                    target=unstl.thread_bin, args=(req, host_ip, role_id_list,
                                                   hosts_list))
                t.setDaemon(True)
                t.start()
                threads.append(t)
            LOG.info(_("Uninstall threads have started, please waiting...."))

            try:
                for t in threads:
                    t.join()
            except:
                LOG.warn(_("Join uninstall thread %s failed!" % t))
            else:
                uninstall_failed_flag = False
                for role_id in role_id_list:
                    role_hosts = daisy_cmn.get_hosts_of_role(req, role_id)
                    for role_host in role_hosts:
                        if role_host['status'] ==\
                                tecs_state['UNINSTALL_FAILED']:
                            unstl.update_progress_to_db(
                                req, role_id_list, tecs_state[
                                    'UNINSTALL_FAILED'], hosts_list)
                            uninstall_failed_flag = True
                            break
                if not uninstall_failed_flag:
                    LOG.info(
                        _("All uninstall threads have done,\
                            set all roles status to 'init'!"))
                    unstl.update_progress_to_db(
                        req, role_id_list, tecs_state['INIT'], hosts_list)
                    LOG.info(_("modify the running_version of configs to 0"))
                    running_version = 0
                    self._modify_running_version_of_configs(
                        req, running_version, cluster_id)
                tecs_cmn.inform_provider_cloud_state(req.context, cluster_id,
                                                     operation='delete')
        try:
            (status, output) = commands.getstatusoutput('rpm -e --nodeps openstack-packstack\
                        openstack-packstack-puppet \
                        openstack-puppet-modules puppet')
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)

    def uninstall_progress(self, req, cluster_id):
        return self._query_progress(req, cluster_id, "uninstall")

    def upgrade(self, req, cluster_id):
        """
        update TECS to a cluster.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-install-cluster is missing
        """
        # daisy_update_path = '/home/daisy_update/'

        (role_id_list, role_host_ips, hosts_list, tecs_install_failed_list) =\
            self._get_roles_and_hosts_ip_list(req, cluster_id)
        if role_id_list:
            if not role_host_ips['all']:
                msg = _("there is no host in cluster %s") % cluster_id
                raise exception.ThreadBinException(msg)
            unreached_hosts = daisy_cmn.check_ping_hosts(
                role_host_ips['all'], 1)
            if unreached_hosts:
                self.message = "hosts %s ping failed" % unreached_hosts
                raise exception.NotFound(message=self.message)
            daisy_cmn.subprocess_call('rm -rf /root/.ssh/known_hosts')
            if os_handle.check_tfg_exist():
                os_handle.upgrade_os(req, hosts_list)
                unreached_hosts = daisy_cmn.check_ping_hosts(
                    role_host_ips['all'], 30)
                if unreached_hosts:
                    self.message = "hosts %s ping failed after tfg upgrade" \
                        % unreached_hosts
                    raise exception.NotFound(message=self.message)
            # check and get TECS version
            tecs_version_pkg_file = tecs_cmn.check_and_get_tecs_version(
                tecs_cmn.daisy_tecs_path)
            if not tecs_version_pkg_file:
                self.state = tecs_state['UPDATE_FAILED']
                self.message = "TECS version file not found in %s"\
                    % tecs_cmn.daisy_tecs_path
                raise exception.NotFound(message=self.message)
            threads = []
            LOG.info(
                _("Begin to update TECS controller nodes, please waiting...."))
            upgrd.update_progress_to_db(
                req, role_id_list, tecs_state['UPDATING'], hosts_list)
            for host_ip in role_host_ips['ha']:
                if host_ip in tecs_install_failed_list:
                    continue
                LOG.info(_("Update TECS controller node %s..." % host_ip))
                rc = upgrd.thread_bin(req, role_id_list, host_ip, hosts_list)
                if rc == 0:
                    LOG.info(_("Update TECS for %s successfully" % host_ip))
                else:
                    LOG.info(
                        _("Update TECS failed for %s, return %s"
                            % (host_ip, rc)))
                    return

            LOG.info(_("Begin to update TECS other nodes, please waiting...."))
            max_parallel_upgrade_number = int(
                CONF.max_parallel_os_upgrade_number)
            compute_ip_list = role_host_ips[
                'all'] - role_host_ips['ha'] - tecs_install_failed_list
            while compute_ip_list:
                threads = []
                if len(compute_ip_list) > max_parallel_upgrade_number:
                    upgrade_hosts = compute_ip_list[
                        :max_parallel_upgrade_number]
                    compute_ip_list = compute_ip_list[
                        max_parallel_upgrade_number:]
                else:
                    upgrade_hosts = compute_ip_list
                    compute_ip_list = []
                for host_ip in upgrade_hosts:
                    t = threading.Thread(
                        target=upgrd.thread_bin,
                        args=(req, role_id_list, host_ip, hosts_list))
                    t.setDaemon(True)
                    t.start()
                    threads.append(t)
                try:
                    for t in threads:
                        t.join()
                except:
                    LOG.warn(_("Join update thread %s failed!" % t))

            for role_id in role_id_list:
                role_hosts = daisy_cmn.get_hosts_of_role(req, role_id)
                for role_host in role_hosts:
                    if (role_host['status'] == tecs_state['UPDATE_FAILED'] or
                            role_host['status'] == tecs_state['UPDATING']):
                        role_id = [role_host['role_id']]
                        upgrd.update_progress_to_db(req,
                                                    role_id,
                                                    tecs_state[
                                                        'UPDATE_FAILED'],
                                                    hosts_list)
                        break
                    elif role_host['status'] == tecs_state['ACTIVE']:
                        role_id = [role_host['role_id']]
                        upgrd.update_progress_to_db(req,
                                                    role_id,
                                                    tecs_state['ACTIVE'],
                                                    hosts_list)

    def upgrade_progress(self, req, cluster_id):
        return self._query_progress(req, cluster_id, "upgrade")

    def export_db(self, req, cluster_id):
        """
        Export daisy db data to tecs.conf and HA.conf.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-install-cluster is missing
        """

        tecs_config =\
            instl.get_cluster_tecs_config(req, cluster_id)

        config_files = {'tecs_conf': '', 'ha_conf': ''}
        tecs_install_path = "/home/tecs_install"
        if tecs_config:
            cluster_conf_path = tecs_install_path + "/" + cluster_id
            create_cluster_conf_path =\
                "rm -rf %s;mkdir %s" % (cluster_conf_path, cluster_conf_path)
            daisy_cmn.subprocess_call(create_cluster_conf_path)
            config.update_tecs_config(tecs_config, cluster_conf_path)

            get_tecs_conf = "ls %s|grep tecs.conf" % cluster_conf_path
            obj = subprocess.Popen(get_tecs_conf,
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            (stdoutput, erroutput) = obj.communicate()
            tecs_conf_file = ""
            if stdoutput:
                tecs_conf_file = stdoutput.split('\n')[0]
                config_files['tecs_conf'] =\
                    cluster_conf_path + "/" + tecs_conf_file

            get_ha_conf_cmd = "ls %s|grep HA_1.conf" % cluster_conf_path
            obj = subprocess.Popen(get_ha_conf_cmd,
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            (stdoutput, erroutput) = obj.communicate()
            ha_conf_file = ""
            if stdoutput:
                ha_conf_file = stdoutput.split('\n')[0]
                config_files['ha_conf'] =\
                    cluster_conf_path + "/" + ha_conf_file
        else:
            LOG.info(_("No TECS config files generated."))

        return config_files

    def update_disk_array(self, req, cluster_id):
        (share_disk_info, volume_disk_info) =\
            disk_array.get_disk_array_info(req, cluster_id)
        array_nodes_addr =\
            tecs_cmn.get_disk_array_nodes_addr(req, cluster_id)

        ha_nodes_ip = array_nodes_addr['ha'].keys()
        all_nodes_ip = list(array_nodes_addr['computer']) + ha_nodes_ip

        if all_nodes_ip:
            compute_error_msg =\
                disk_array.config_compute_multipath(all_nodes_ip)
            if compute_error_msg:
                return compute_error_msg
            else:
                LOG.info(_("Config Disk Array multipath successfully"))

        if share_disk_info:
            ha_error_msg =\
                disk_array.config_ha_share_disk(share_disk_info,
                                                array_nodes_addr['ha'])
            if ha_error_msg:
                return ha_error_msg
            else:
                LOG.info(_("Config Disk Array for HA nodes successfully"))

        if volume_disk_info:
            cinder_error_msg =\
                disk_array.config_ha_cinder_volume(volume_disk_info,
                                                   ha_nodes_ip)
            if cinder_error_msg:
                return cinder_error_msg
            else:
                LOG.info(_("Config cinder volume for HA nodes successfully"))

        return 'update successfully'
