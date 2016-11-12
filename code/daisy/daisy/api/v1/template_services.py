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
/template_services endpoint for Daisy v1 API
"""

from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPConflict
from webob.exc import HTTPForbidden
from webob.exc import HTTPNotFound
from webob import Response
import copy
import json

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

CONF = cfg.CONF
CONF.import_opt('disk_formats', 'daisy.common.config', group='image_format')
CONF.import_opt('container_formats', 'daisy.common.config',
                group='image_format')
CONF.import_opt('image_property_quota', 'daisy.common.config')


class Controller(controller.BaseController):
    """
    WSGI controller for template_services resource in Daisy v1 API

    The template_services resource API is a RESTful web service for
    template_service data.
    The API is as follows::

        GET  /template_services -- Returns a set of brief metadata about
                                    template_services
        GET  /template_services/detail -- Returns a set of detailed metadata
                                    about template_services
        HEAD /template_services/<ID> --
        Return metadata about an template_service with id <ID>
        GET  /template_services/<ID> --
        Return template_service data for template_service with id <ID>
        POST /template_services --
        Store template_service data and return metadata about the
                        newly-stored template_service
        PUT  /template_services/<ID> --
        Update template_service metadata and/or upload template_service
                            data for a previously-reserved template_service
        DELETE /template_services/<ID> -- Delete the template_services with id
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
    def get_template_service(self, req, id):
        """
        Returns metadata about an template_service in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque template_service identifier

        :raises HTTPNotFound if template_service metadata is not available to user
        """
        self._enforce(req, 'get_template_service')
        template_service_meta = self.get_template_service_meta_or_404(req, id)
        return {'template_service_meta': template_service_meta}

    def list_template_service(self, req):
        """
        Returns detailed information for all available template_services

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'template_services': [
                {'id': <ID>,
                 'service_name': <SERVICE_NAME>,
                 'force_type': <FORCE_TYPE>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._enforce(req, 'list_template_service')
        params = self._get_query_params(req)
        try:
            template_services = registry.list_template_service_metadata(
                req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(template_services=template_services)


class TemplateServiceSetDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["template_service_meta"] = utils.get_dict_meta(request)
        return result

    def add_template_service(self, request):
        return self._deserialize(request)

    def update_template_service(self, request):
        return self._deserialize(request)

    def import_template_service(self, request):
        return self._deserialize(request)


class TemplateServiceSetSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_template_service(self, response, result):
        template_service_meta = result['template_service_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(
            dict(template_service=template_service_meta))
        return response

    def delete_template_service(self, response, result):
        template_service_meta = result['template_service_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(
            dict(template_service=template_service_meta))
        return response

    def get_template_service(self, response, result):
        template_service_meta = result['template_service_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(
            dict(template_service=template_service_meta))
        return response

    def import_template_service(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response


def create_resource():
    """template_services resource factory method"""
    deserializer = TemplateServiceSetDeserializer()
    serializer = TemplateServiceSetSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
