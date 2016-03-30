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
/config_files endpoint for Daisy v1 API
"""

from oslo_config import cfg
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
from daisy.common import property_utils
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

CONF = cfg.CONF
CONF.import_opt('disk_formats', 'daisy.common.config', group='image_format')
CONF.import_opt('container_formats', 'daisy.common.config',
                group='image_format')
CONF.import_opt('image_property_quota', 'daisy.common.config')

class Controller(controller.BaseController):
    """
    WSGI controller for config_files resource in Daisy v1 API

    The config_files resource API is a RESTful web service for config_file data. The API
    is as follows::

        GET  /config_files -- Returns a set of brief metadata about config_files
        GET  /config_files/detail -- Returns a set of detailed metadata about
                              config_files
        HEAD /config_files/<ID> -- Return metadata about an config_file with id <ID>
        GET  /config_files/<ID> -- Return config_file data for config_file with id <ID>
        POST /config_files -- Store config_file data and return metadata about the
                        newly-stored config_file
        PUT  /config_files/<ID> -- Update config_file metadata and/or upload config_file
                            data for a previously-reserved config_file
        DELETE /config_files/<ID> -- Delete the config_file with id <ID>
    """

    def __init__(self):
        self.notifier = notifier.Notifier()
        registry.configure_registry_client()
        self.policy = policy.Enforcer()
        if property_utils.is_property_protection_enabled():
            self.prop_enforcer = property_utils.PropertyRules(self.policy)
        else:
            self.prop_enforcer = None

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
    def add_config_file(self, req, config_file_meta):
        """
        Adds a new config_file to Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about config_file

        :raises HTTPBadRequest if x-config_file-name is missing
        """
        self._enforce(req, 'add_config_file')
        #config_file_id=config_file_meta["id"]
        config_file_name = config_file_meta["name"]
        config_file_description = config_file_meta["description"]
        #print config_file_id
        print config_file_name
        print config_file_description
        config_file_meta = registry.add_config_file_metadata(req.context, config_file_meta)

        return {'config_file_meta': config_file_meta}

    @utils.mutating
    def delete_config_file(self, req, id):
        """
        Deletes a config_file from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about config_file

        :raises HTTPBadRequest if x-config_file-name is missing
        """
        self._enforce(req, 'delete_config_file')

        try:
            registry.delete_config_file_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find config_file to delete: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete config_file: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("config_file %(id)s could not be deleted because it is in use: "
                     "%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.warn(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            #self.notifier.info('config_file.delete', config_file)
            return Response(body='', status=200)

    @utils.mutating
    def get_config_file(self, req, id):
        """
        Returns metadata about an config_file in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque config_file identifier

        :raises HTTPNotFound if config_file metadata is not available to user
        """
        self._enforce(req, 'get_config_file')
        config_file_meta = self.get_config_file_meta_or_404(req, id)
        return {'config_file_meta': config_file_meta}

    def detail(self, req):
        """
        Returns detailed information for all available config_files

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'config_files': [
                {'id': <ID>,
                 'name': <NAME>,
                 'description': <DESCRIPTION>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._enforce(req, 'get_config_files')
        params = self._get_query_params(req)
        try:
            config_files = registry.get_config_files_detail(req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(config_files=config_files)

    @utils.mutating
    def update_config_file(self, req, id, config_file_meta):
        """
        Updates an existing config_file with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'modify_image')
        orig_config_file_meta = self.get_config_file_meta_or_404(req, id)

        # Do not allow any updates on a deleted image.
        # Fix for LP Bug #1060930
        if orig_config_file_meta['deleted']:
            msg = _("Forbidden to update deleted config_file.")
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        try:
            config_file_meta = registry.update_config_file_metadata(req.context,
                                                                    id,
                                                                    config_file_meta)

        except exception.Invalid as e:
            msg = (_("Failed to update config_file metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find config_file to update: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update config_file: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.warn(utils.exception_to_str(e))
            raise HTTPConflict(body=_('config_file operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('config_file.update', config_file_meta)

        return {'config_file_meta': config_file_meta}

class Config_fileDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["config_file_meta"] = utils.get_config_file_meta(request)
        return result

    def add_config_file(self, request):
        return self._deserialize(request)

    def update_config_file(self, request):
        return self._deserialize(request)

class Config_fileSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_config_file(self, response, result):
        config_file_meta = result['config_file_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config_file=config_file_meta))
        return response

    def delete_config_file(self, response, result):
        config_file_meta = result['config_file_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config_file=config_file_meta))
        return response

    def get_config_file(self, response, result):
        config_file_meta = result['config_file_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config_file=config_file_meta))
        return response

def create_resource():
    """config_files resource factory method"""
    deserializer = Config_fileDeserializer()
    serializer = Config_fileSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)

