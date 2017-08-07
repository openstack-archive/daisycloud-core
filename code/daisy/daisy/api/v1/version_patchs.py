# Copyright 2013 OpenStack Foundation
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
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
/versions endpoint for Daisy v1 API
"""

from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPConflict
from webob.exc import HTTPForbidden
from webob.exc import HTTPNotFound
from webob import Response

from daisy.api import policy
import daisy.api.v1
from daisy.api.v1 import controller
from daisy.api.v1 import filters
from daisy.common import exception
from daisy.common import utils
from daisy.common import wsgi
from daisy import i18n
from daisy import notifier
import daisy.registry.client.v1.api as registry

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE
SUPPORTED_DEPLOYMENT_BACKENDS = ('tecs', 'zenic', 'proton', 'kolla')
SUPPORT_DISK_LOCATION = ('local', 'share')


class Controller(controller.BaseController):
    """
    WSGI controller for versions resource in Daisy v1 API

    The versions resource API is a RESTful web role for role data. The API
    is as follows::

        GET  /versions -- Returns a set of brief metadata about versions
        GET  /versions/detail -- Returns a set of detailed metadata about
                              versions
        HEAD /versions/<ID> -- Return metadata about an role with id <ID>
        GET  /versions/<ID> -- Return role data for role with id <ID>
        POST /versions -- Store role data and return metadata about the
                        newly-stored role
        PUT  /versions/<ID> -- Update role metadata and/or upload role
                            data for a previously-reserved role
        DELETE /versions/<ID> -- Delete the role with id <ID>
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
    def add_version_patch(self, req, version_patch_meta):
        """
        Adds a new version to Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about role

        :raises HTTPBadRequest if x-role-name is missing
        """
        self._enforce(req, 'add_version_patch')
        version_patch_name = version_patch_meta.get('name')
        if not version_patch_meta.get('status', None):
            version_patch_meta['status'] = "unused"
        if not version_patch_name:
            raise ValueError('version patch name is null!')
        version_patch_meta = \
            registry.add_version_patch_metadata(req.context,
                                                version_patch_meta)

        return {'version_patch_meta': version_patch_meta}

    @utils.mutating
    def delete_version_patch(self, req, id):
        """
        Deletes a version patch from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about role

        :raises HTTPBadRequest if x-role-name is missing
        """
        self._enforce(req, 'delete_version_patch')
        self.get_version_patch_meta_or_404(req, id)
        print "delete_version_patch:%s" % id
        try:
            registry.delete_version_patch_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find version patch to delete: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete version patch: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("version patch %(id)s could not be deleted "
                     "because it is in use: " "%(exc)s")
                   % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.warning(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            # self.notifier.info('role.delete', role)
            return Response(body='', status=200)

    @utils.mutating
    def get_version_patch(self, req, id):
        """
        Returns metadata about an version patch in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque version patch identifier

        :raises HTTPNotFound if version patch metadata is not available to user
        """
        self._enforce(req, 'get_version_patch')
        version_patch_meta = self.get_version_patch_meta_or_404(req, id)
        return {'version_patch_meta': version_patch_meta}

    @utils.mutating
    def add_host_patch_history(self, req, version_patch_meta):
        """
        Returns metadata about an patch history in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque version patch identifier

        """
        self._enforce(req, 'add_host_patch_history')
        patch_history_meta = \
            registry.add_host_patch_history_metadata(req.context,
                                                     version_patch_meta)
        return {'patch_history_meta': patch_history_meta}

    @utils.mutating
    def list_host_patch_history(self, req):
        """
        Returns metadata about an patch history in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque version patch identifier

        :raises HTTPNotFound if version patch metadata is not available to user
        """
        self._enforce(req, 'get_host_patch_history')
        params = self._get_query_params(req)
        try:
            patch_history_meta = registry.list_host_patch_history_metadata(
                req.context, **params)
        except Exception:
            msg = "host patch history list error"
            LOG.error(msg)
            raise HTTPBadRequest(explanation=msg, request=req)
        return dict(patch_history_meta=patch_history_meta)

    @utils.mutating
    def update_version_patch(self, req, id, version_patch_meta):
        """
        Updates an existing version patch with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'update_version_patch')
        orig_version_meta = self.get_version_patch_meta_or_404(req, id)

        if orig_version_meta['deleted']:
            msg = _("Forbidden to update deleted version patch.")
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        try:
            version_patch_meta = registry.update_version_patch_metadata(
                req.context,
                id,
                version_patch_meta)

        except exception.Invalid as e:
            msg = (_("Failed to update version patch. Got error: %s")
                   % utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find version patch to update: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update version patch: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.warning(utils.exception_to_str(e))
            raise HTTPConflict(body=_('Host operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('version_patchs.update', version_patch_meta)

        return {'version_patch_meta': version_patch_meta}


class VersionPatchDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["version_patch_meta"] = utils.get_dict_meta(request)
        return result

    def add_version_patch(self, request):
        return self._deserialize(request)

    def add_host_patch_history(self, request):
        return self._deserialize(request)

    def update_version_patch(self, request):
        return self._deserialize(request)


class VersionPatchserializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_version_patch(self, response, result):
        version_patch_meta = result['version_patch_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(version_patch=version_patch_meta))
        return response

    def add_host_patch_history(self, response, result):
        version_patch_meta = result['patch_history_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(patch_history=version_patch_meta))
        return response

    def delete_version_patch(self, response, result):
        version_patch_meta = result['version_patch_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(version_patch=version_patch_meta))
        return response

    def get_version_patch(self, response, result):
        version_patch_meta = result['version_patch_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(version_patch=version_patch_meta))
        return response

    def list_host_patch_history(self, response, result):
        history_meta = result['patch_history_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(patch_history=history_meta))
        return response


def create_resource():
    """versions resource factory method"""
    deserializer = VersionPatchDeserializer()
    serializer = VersionPatchserializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
