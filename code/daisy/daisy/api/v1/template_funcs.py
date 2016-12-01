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
/template_funcs endpoint for Daisy v1 API
"""

from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden
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

FUNC_ITEMS = ['name', 'config']


def check_template_func_format(template):
    if not template:
        raise HTTPBadRequest('Template function is null!')
    for value in template.values():
        for item in FUNC_ITEMS:
            if not value.get(item):
                raise HTTPBadRequest('No configs found in template function!')
        if not isinstance(value['config'], dict):
            raise HTTPBadRequest('Config in template function should be dict '
                                 'type')


class Controller(controller.BaseController):
    """
    WSGI controller for template_funcs resource in Daisy v1 API

    The template_funcs resource API is a RESTful web service for template_func.
    The API is as follows::

        GET  /template_funcs -- Returns a set of brief metadata about
                            template_funcs
        GET  /template_funcs/detail -- Returns a set of detailed metadata about
                              template_funcs
        HEAD /template_funcs/<ID> --
        Return metadata about an template_func with id <ID>
        GET  /template_funcs/<ID> --
        Return template_func data for template_func with id <ID>
        POST /template_funcs --
        Store template_func data and return metadata about the
                        newly-stored template_func
        PUT  /template_funcs/<ID> --
        Update template_func metadata and/or upload template_func
                            data for a previously-reserved template_func
        DELETE /template_funcs/<ID> -- Delete the template_funcs with id <ID>
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
    def get_template_func(self, req, id, template_func_meta):
        """
        Returns metadata about an template_func in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque template_func identifier

        :raises HTTPNotFound if template_func metadata is not available to user
        """
        self._enforce(req, 'get_template_func')
        params = {'filters': {}}

        if template_func_meta.get('cluster_id'):
            params['filters'].update({'cluster_id':
                                     template_func_meta['cluster_id']})
        template_func_meta = self.get_template_func_meta_or_404(req, id,
                                                                **params)
        return {'template_func_meta': template_func_meta}

    def list_template_func(self, req):
        """
        Returns detailed information for all available template_funcs

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'template_funcs': [
                {'id': <ID>,
                 'func_name': <FUNC_NAME>,
                 'cn_desc': <CH_DESC>,
                 'en_desc': <EN_DESC>,
                 'data_check_script': <DATA_CHECK_SCRIPT>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._enforce(req, 'list_template_func')
        params = self._get_query_params(req)
        try:
            template_funcs = registry.list_template_func_metadata(
                req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(template_funcs=template_funcs)

    @utils.mutating
    def import_template_func(self, req, template_func_meta):
        self._enforce(req, 'import_template_func')
        try:
            template = json.loads(template_func_meta.get('template', None))
        except ValueError as e:
            LOG.error(e.message)
            raise HTTPBadRequest(explanation=e.message, request=req)
        check_template_func_format(template)
        template_func_meta = registry.import_template_func_metadata(
            req.context, template_func_meta)
        return {'template_func_meta': template_func_meta}


class TemplateFuncSetDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["template_func_meta"] = utils.get_dict_meta(request)
        return result

    def add_template_func(self, request):
        return self._deserialize(request)

    def update_template_func(self, request):
        return self._deserialize(request)

    def get_template_func(self, request):
        return self._deserialize(request)

    def import_template_func(self, request):
        return self._deserialize(request)


class TemplateFuncSetSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_template_func(self, response, result):
        template_func_meta = result['template_func_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(template_func=template_func_meta))
        return response

    def delete_template_func(self, response, result):
        template_func_meta = result['template_func_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(template_func=template_func_meta))
        return response

    def get_template_func(self, response, result):
        template_func_meta = result['template_func_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(template_func=template_func_meta))
        return response

    def import_template_func(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response


def create_resource():
    """template_funcs resource factory method"""
    deserializer = TemplateFuncSetDeserializer()
    serializer = TemplateFuncSetSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
