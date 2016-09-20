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
import time
import webob.exc

from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden

from threading import Thread

from daisy import i18n
from daisy import notifier

from daisy.api import policy
import daisy.api.v1

from daisy.common import exception
from daisy.common import utils
from daisy.common import wsgi
import daisy.registry.client.v1.api as registry
from daisy.api.v1 import controller
from daisy.api.v1 import filters
import daisy.api.backends.common as daisy_cmn
from daisy.api.backends import driver
from daisy.api.backends.os import osdriver as os_handle
import ConfigParser


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE

# if some backends have order constraint, please add here
# if backend not in the next three order list, we will be
# think it does't have order constraint.
BACKENDS_INSTALL_ORDER = ['proton', 'zenic', 'tecs', 'kolla']
BACKENDS_UPGRADE_ORDER = ['proton', 'zenic', 'tecs', 'kolla']
BACKENDS_UNINSTALL_ORDER = []

config = ConfigParser.ConfigParser()
config.read('/home/daisy_install/daisy.conf')
OS_INSTALL_TYPE = config.get("OS", "os_install_type")
os_driver = os_handle.load_install_os_driver(OS_INSTALL_TYPE)
os_install = os_driver(self.req, self.cluster_id)


def get_deployment_backends(req, cluster_id, backends_order):
    cluster_roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
    cluster_backends = set([role['deployment_backend']
                            for role in cluster_roles if
                            daisy_cmn.get_hosts_of_role(req, role['id'])])
    ordered_backends = [
        backend for backend in backends_order if backend in cluster_backends]
    other_backends = [
        backend for backend in cluster_backends if
        backend not in backends_order]
    deployment_backends = ordered_backends + other_backends
    return deployment_backends


class InstallTask(object):
    """
    Class for install OS and TECS.
    """
    """ Definition for install states."""

    def __init__(self, req, cluster_id):
        self.req = req
        self.cluster_id = cluster_id

    def _backends_install(self):
        backends = get_deployment_backends(
            self.req, self.cluster_id, BACKENDS_INSTALL_ORDER)
        if not backends:
            LOG.info(_("No backends need to install."))
            return
        for backend in backends:
            backend_driver = driver.load_deployment_dirver(backend)
            backend_driver.install(self.req, self.cluster_id)
    # this will be raise raise all the exceptions of the thread to log file

    def run(self):
        try:
            self._run()
        except Exception as e:
            LOG.exception(e.message)

    def _run(self):
        """
        Exectue os installation with sync mode.
        :return:
        """
        # get hosts config which need to install OS
        all_hosts_need_os = os_handle.get_cluster_hosts_config(
            self.req, self.cluster_id)
        if all_hosts_need_os:
            hosts_with_role_need_os = [
                host_detail for host_detail in all_hosts_need_os if
                host_detail['status'] == 'with-role']
            hosts_without_role_need_os = [
                host_detail for host_detail in all_hosts_need_os if
                host_detail['status'] != 'with-role']
        else:
            LOG.info(_("No host need to install os, begin to install "
                       "backends for cluster %s." % self.cluster_id))
            self._backends_install()
            return

        run_once_flag = True
        # if no hosts with role need os, install backend applications
        # immediately
        if not hosts_with_role_need_os:
            run_once_flag = False
            role_hosts_need_os = []
            LOG.info(_("All of hosts with role is 'active', begin to install "
                       "backend applications for cluster %s first." %
                       self.cluster_id))
            self._backends_install()
        else:
            role_hosts_need_os = [host_detail['id']
                                  for host_detail in hosts_with_role_need_os]

        # hosts with role put the head of the list
        order_hosts_need_os = hosts_with_role_need_os + \
            hosts_without_role_need_os
        while order_hosts_need_os:
            os_driver = os_handle.load_install_os_driver(OS_INSTALL_TYPE)
            os_install = os_driver(self.req, self.cluster_id)
            # all os will be installed batch by batch with
            # max_parallel_os_number which was set in daisy-api.conf
            (order_hosts_need_os, role_hosts_need_os) = os_install.install_os(
                order_hosts_need_os, role_hosts_need_os)
            # after a batch of os install over, judge if all
            # role hosts install os completely,
            # if role_hosts_need_os is empty, install TECS immediately
            if run_once_flag and not role_hosts_need_os:
                run_once_flag = False
                # wait to reboot os after new os installed
                time.sleep(10)
                LOG.info(_("All hosts with role install successfully, "
                           "begin to install backend applications "
                           "for cluster %s." %
                           self.cluster_id))
                self._backends_install()


class Controller(controller.BaseController):
    """
    WSGI controller for hosts resource in Daisy v1 API

    The hosts resource API is a RESTful web service for host data. The API
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
        self.notifier = notifier.Notifier()
        registry.configure_registry_client()
        self.policy = policy.Enforcer()

    def _enforce(self, req, action, target=None):
        """Authorize an action against our policies"""
        if target is None:
            target = {}
        try:
            self.policy.enforce(req.context, action, target)
        except exception.Forbidden:
            raise HTTPForbidden()

    def _raise_404_if_cluster_deleted(self, req, cluster_id):
        cluster = self.get_cluster_meta_or_404(req, cluster_id)
        if cluster['deleted']:
            msg = _("Cluster with identifier %s has been deleted.") % \
                cluster_id
            raise webob.exc.HTTPNotFound(msg)

    def _get_filters(self, req):
        """
        Return a dictionary of query param filters from the request

        :param req: the Request object coming from the wsgi layer
        :retval a dict of key/value filters
        """
        query_filters = {}
        for param in req.params:
            if param in SUPPORTED_FILTERS:
                query_filters[param] = req.params.get(param)
                if not filters.validate(param, query_filters[param]):
                    raise HTTPBadRequest(_('Bad value passed to filter '
                                           '%(filter)s got %(val)s')
                                         % {'filter': param,
                                            'val': query_filters[param]})
        return query_filters

    def _get_query_params(self, req):
        """
        Extracts necessary query params from request.

        :param req: the WSGI Request object
        :retval dict of parameters that can be used by registry client
        """
        params = {'filters': self._get_filters(req)}

        for PARAM in SUPPORTED_PARAMS:
            if PARAM in req.params:
                params[PARAM] = req.params.get(PARAM)
        return params

    @utils.mutating
    def install_cluster(self, req, install_meta):
        """
        Install TECS to a cluster.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-install-cluster is missing
        """
        if 'deployment_interface' in install_meta:
            os_install.pxe_server_build(req, install_meta)
            return {"status": "pxe is installed"}

        cluster_id = install_meta['cluster_id']
        self._enforce(req, 'install_cluster')
        self._raise_404_if_cluster_deleted(req, cluster_id)

        daisy_cmn.set_role_status_and_progress(
            req, cluster_id, 'install',
            {'messages': 'Waiting for TECS installation', 'progress': '0'},
            'tecs')
        # if have hosts need to install os,
        # TECS installataion executed in InstallTask
        os_install_obj = InstallTask(req, cluster_id)
        os_install_thread = Thread(target=os_install_obj.run)
        os_install_thread.start()
        return {"status": "begin install"}

    @utils.mutating
    def uninstall_cluster(self, req, cluster_id):
        """
        Uninstall TECS to a cluster.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-install-cluster is missing
        """
        self._enforce(req, 'uninstall_cluster')
        self._raise_404_if_cluster_deleted(req, cluster_id)

        backends = get_deployment_backends(
            req, cluster_id, BACKENDS_UNINSTALL_ORDER)
        for backend in backends:
            backend_driver = driver.load_deployment_dirver(backend)
            uninstall_thread = Thread(
                target=backend_driver.uninstall, args=(
                    req, cluster_id))
            uninstall_thread.start()
        return {"status": "begin uninstall"}

    @utils.mutating
    def uninstall_progress(self, req, cluster_id):
        self._enforce(req, 'uninstall_progress')
        self._raise_404_if_cluster_deleted(req, cluster_id)

        all_nodes = {}
        backends = get_deployment_backends(
            req, cluster_id, BACKENDS_UNINSTALL_ORDER)
        if not backends:
            LOG.info(_("No backends need to uninstall."))
            return all_nodes
        for backend in backends:
            backend_driver = driver.load_deployment_dirver(backend)
            nodes_process = backend_driver.uninstall_progress(req, cluster_id)
            all_nodes.update(nodes_process)
        return all_nodes

    @utils.mutating
    def update_cluster(self, req, cluster_id):
        """
        Uninstall TECS to a cluster.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-install-cluster is missing
        """
        self._enforce(req, 'update_cluster')
        self._raise_404_if_cluster_deleted(req, cluster_id)

        backends = get_deployment_backends(
            req, cluster_id, BACKENDS_UPGRADE_ORDER)
        if not backends:
            LOG.info(_("No backends need to update."))
            return {"status": ""}
        daisy_cmn.set_role_status_and_progress(
            req, cluster_id, 'upgrade',
            {'messages': 'Waiting for TECS upgrading', 'progress': '0'},
            'tecs')
        for backend in backends:
            backend_driver = driver.load_deployment_dirver(backend)
            update_thread = Thread(target=backend_driver.upgrade,
                                   args=(req, cluster_id))
            update_thread.start()
        return {"status": "begin update"}

    @utils.mutating
    def update_progress(self, req, cluster_id):
        self._enforce(req, 'update_progress')
        self._raise_404_if_cluster_deleted(req, cluster_id)

        backends = get_deployment_backends(
            req, cluster_id, BACKENDS_UPGRADE_ORDER)
        all_nodes = {}
        for backend in backends:
            backend_driver = driver.load_deployment_dirver(backend)
            nodes_process = backend_driver.upgrade_progress(req, cluster_id)
            all_nodes.update(nodes_process)
        return all_nodes

    @utils.mutating
    def export_db(self, req, install_meta):
        """
        Export daisy db data to tecs.conf and HA.conf.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-install-cluster is missing
        """
        self._enforce(req, 'export_db')
        cluster_id = install_meta['cluster_id']
        self._raise_404_if_cluster_deleted(req, cluster_id)

        all_config_files = {}
        backends = get_deployment_backends(
            req, cluster_id, BACKENDS_INSTALL_ORDER)
        if not backends:
            LOG.info(_("No backends need to export."))
            return all_config_files
        for backend in backends:
            backend_driver = driver.load_deployment_dirver(backend)
            backend_config_files = backend_driver.export_db(req, cluster_id)
            all_config_files.update(backend_config_files)
        return all_config_files

    @utils.mutating
    def update_disk_array(self, req, cluster_id):
        """
        update TECS Disk Array config for a cluster.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-cluster is missing
        """
        self._enforce(req, 'update_disk_array')
        self._raise_404_if_cluster_deleted(req, cluster_id)

        tecs_backend_name = 'tecs'
        backends = get_deployment_backends(
            req, cluster_id, BACKENDS_UNINSTALL_ORDER)
        if tecs_backend_name not in backends:
            message = "No tecs backend"
            LOG.info(_(message))
        else:
            backend_driver = driver.load_deployment_dirver(tecs_backend_name)
            message = backend_driver.update_disk_array(req, cluster_id)
        return {'status': message}


class InstallDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["install_meta"] = utils.get_dict_meta(request)
        return result

    def install_cluster(self, request):
        return self._deserialize(request)

    def export_db(self, request):
        return self._deserialize(request)

    def update_disk_array(self, request):
        return {}


class InstallSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def install_cluster(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def export_db(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def update_disk_array(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response


def create_resource():
    """Image members resource factory method"""
    deserializer = InstallDeserializer()
    serializer = InstallSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
