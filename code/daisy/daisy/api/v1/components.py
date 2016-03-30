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
/components endpoint for Daisy v1 API
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
    WSGI controller for components resource in Daisy v1 API

    The components resource API is a RESTful web service for component data. The API
    is as follows::

        GET  /components -- Returns a set of brief metadata about components
        GET  /components/detail -- Returns a set of detailed metadata about
                              components
        HEAD /components/<ID> -- Return metadata about an component with id <ID>
        GET  /components/<ID> -- Return component data for component with id <ID>
        POST /components -- Store component data and return metadata about the
                        newly-stored component
        PUT  /components/<ID> -- Update component metadata and/or upload component
                            data for a previously-reserved component
        DELETE /components/<ID> -- Delete the component with id <ID>
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
    def add_component(self, req, component_meta):
        """
        Adds a new component to Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about component

        :raises HTTPBadRequest if x-component-name is missing
        """
        self._enforce(req, 'add_component')
        #component_id=component_meta["id"]
        #component_owner=component_meta["owner"]
        component_name = component_meta["name"]
        component_description = component_meta["description"]
        #print component_id
        #print component_owner
        print component_name
        print component_description
        component_meta = registry.add_component_metadata(req.context, component_meta)

        return {'component_meta': component_meta}

    @utils.mutating
    def delete_component(self, req, id):
        """
        Deletes a component from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about component

        :raises HTTPBadRequest if x-component-name is missing
        """
        self._enforce(req, 'delete_component')

        #component = self.get_component_meta_or_404(req, id)
        print "delete_component:%s" % id
        try:
            registry.delete_component_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find component to delete: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete component: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("component %(id)s could not be deleted because it is in use: "
                     "%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.warn(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            #self.notifier.info('component.delete', component)
            return Response(body='', status=200)

    @utils.mutating
    def get_component(self, req, id):
        """
        Returns metadata about an component in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque component identifier

        :raises HTTPNotFound if component metadata is not available to user
        """
        self._enforce(req, 'get_component')
        component_meta = self.get_component_meta_or_404(req, id)
        return {'component_meta': component_meta}

    def detail(self, req):
        """
        Returns detailed information for all available components

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'components': [
                {'id': <ID>,
                 'name': <NAME>,
                 'description': <DESCRIPTION>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._enforce(req, 'get_components')
        params = self._get_query_params(req)
        try:
            components = registry.get_components_detail(req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(components=components)

    @utils.mutating
    def update_component(self, req, id, component_meta):
        """
        Updates an existing component with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'modify_image')
        orig_component_meta = self.get_component_meta_or_404(req, id)

        # Do not allow any updates on a deleted image.
        # Fix for LP Bug #1060930
        if orig_component_meta['deleted']:
            msg = _("Forbidden to update deleted component.")
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        try:
            component_meta = registry.update_component_metadata(req.context,
                                                                id,
                                                                component_meta)

        except exception.Invalid as e:
            msg = (_("Failed to update component metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find component to update: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update component: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.warn(utils.exception_to_str(e))
            raise HTTPConflict(body=_('Host operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('component.update', component_meta)

        return {'component_meta': component_meta}

class ComponentDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["component_meta"] = utils.get_component_meta(request)
        return result

    def add_component(self, request):
        return self._deserialize(request)

    def update_component(self, request):
        return self._deserialize(request)

class ComponentSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_component(self, response, result):
        component_meta = result['component_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(component=component_meta))
        return response

    def delete_component(self, response, result):
        component_meta = result['component_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(component=component_meta))
        return response
    def get_component(self, response, result):
        component_meta = result['component_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(component=component_meta))
        return response

def create_resource():
    """Components resource factory method"""
    deserializer = ComponentDeserializer()
    serializer = ComponentSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)

