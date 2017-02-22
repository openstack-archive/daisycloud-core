# Copyright 2012 OpenStack Foundation.
# Copyright 2013 NTT corp.
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

from oslo_log import log as logging
import webob.exc

from daisy.api import policy
from daisy.api.v1 import controller
from daisy.common import exception
from daisy.common import utils
from daisy.common import wsgi
from daisy import i18n
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn

LOG = logging.getLogger(__name__)
_ = i18n._


class Controller(controller.BaseController):

    def __init__(self):
        self.policy = policy.Enforcer()

    def _enforce(self, req, action):
        """Authorize an action against our policies"""
        try:
            self.policy.enforce(req.context, action, {})
        except exception.Forbidden:
            raise webob.exc.HTTPForbidden()

    def _raise_404_if_host_deleted(self, req, host_id):
        host = self.get_host_meta_or_404(req, host_id)
        if host['deleted']:
            msg = _("Host with identifier %s has been deleted.") % host_id
            raise webob.exc.HTTPNotFound(msg)

    def _raise_404_if_project_deleted(self, req, cluster_id):
        project = self.get_cluster_meta_or_404(req, cluster_id)
        if project['deleted']:
            msg = _("Cluster with identifier %s has been deleted.") % \
                cluster_id
            raise webob.exc.HTTPNotFound(msg)

#   def get_cluster_hosts(self, req, cluster_id, host_id=None):
#       """
#       Return a list of dictionaries indicating the members of the
#       image, i.e., those tenants the image is shared with.
#
#       :param req: the Request object coming from the wsgi layer
#       :param image_id: The opaque image identifier
#       :retval The response body is a mapping of the following form::

#           {'members': [
#              {'host_id': <HOST>, ...}, ...
#          ]}
#       """
#       self._enforce(req, 'get_cluster_hosts')
#       self._raise_404_if_project_deleted(req, cluster_id)
#
#       try:
#           members = registry.get_cluster_hosts(
# req.context, cluster_id, host_id)
#       except exception.NotFound:
#           msg = _("Project with identifier %s not found") % cluster_id
#           LOG.warn(msg)
#           raise webob.exc.HTTPNotFound(msg)
#       except exception.Forbidden:
#           msg = _("Unauthorized project access")
#           LOG.warn(msg)
#           raise webob.exc.HTTPForbidden(msg)
#       return dict(members=members)

    @utils.mutating
    def add_cluster_host(self, req, cluster_id, host_id, body=None):
        """
        Adds a host with host_id to project with cluster_id.
        """
        self._enforce(req, 'add_cluster_host')
        self._raise_404_if_project_deleted(req, cluster_id)
        self._raise_404_if_host_deleted(req, host_id)

        try:
            registry.add_cluster_host(req.context, cluster_id, host_id)
        except exception.Invalid as e:
            LOG.debug(utils.exception_to_str(e))
            raise webob.exc.HTTPBadRequest(explanation=e.msg)
        except exception.NotFound as e:
            LOG.debug(utils.exception_to_str(e))
            raise webob.exc.HTTPNotFound(explanation=e.msg)
        except exception.Forbidden as e:
            LOG.debug(utils.exception_to_str(e))
            raise webob.exc.HTTPNotFound(explanation=e.msg)

        return webob.exc.HTTPNoContent()

    @utils.mutating
    def delete_cluster_host(self, req, cluster_id, host_id):
        """
        Delete a host with host_id from project with cluster_id.
        """
        self._enforce(req, 'delete_cluster_host')
        self._raise_404_if_project_deleted(req, cluster_id)
        self._raise_404_if_host_deleted(req, host_id)

        try:
            registry.delete_cluster_host(req.context, cluster_id, host_id)
            is_ssh_host = daisy_cmn._judge_ssh_host(req, host_id)
            if not is_ssh_host:
                host_data = {'os_status': 'init'}
                registry.update_host_metadata(req.context, host_id, host_data)
        except exception.NotFound as e:
            LOG.debug(utils.exception_to_str(e))
            raise webob.exc.HTTPNotFound(explanation=e.msg)
        except exception.Forbidden as e:
            LOG.debug(utils.exception_to_str(e))
            raise webob.exc.HTTPNotFound(explanation=e.msg)

        # return webob.exc.HTTPNoContent()

    def default(self, req, image_id, id, body=None):
        """This will cover the missing 'show' and 'create' actions"""
        raise webob.exc.HTTPMethodNotAllowed()

    def get_host_projects(self, req, host_id):
        """
        Retrieves list of image memberships for the given member.

        :param req: the Request object coming from the wsgi layer
        :param id: the opaque member identifier
        :retval The response body is a mapping of the following form::

            {'multi_projects': [
                {'cluster_id': <PROJECT>, ...}, ...
            ]}
        """
        try:
            members = registry.get_host_projects(req.context, host_id)
        except exception.NotFound as e:
            LOG.debug(utils.exception_to_str(e))
            raise webob.exc.HTTPNotFound(explanation=e.msg)
        except exception.Forbidden as e:
            LOG.debug(utils.exception_to_str(e))
            raise webob.exc.HTTPForbidden(explanation=e.msg)
        return dict(multi_projects=members)


def create_resource():
    """Image members resource factory method"""
    deserializer = wsgi.JSONRequestDeserializer()
    serializer = wsgi.JSONResponseSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
