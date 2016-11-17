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
/template_configs endpoint for Daisy v1 API
"""

from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden
from webob.exc import HTTPNotFound
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
import daisy.api.backends.common as daisy_cmn

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
CONFIG_ITEMS = ['name', 'config_file', 'service', 'section_name', 'data_type']


def check_template_config_format(template):
    def check_service_format(services):
        """
        "service": {
                "compute": {"force_type": "service"},
                "glance": {"force_type": "none"}
        }
        """
        for service_name, service_value in services.items():
            if service_name not in daisy_cmn.service_map.keys():
                raise HTTPBadRequest("service '%s' not in service table" %
                                     service_name)
            if 'force_type' not in service_value \
                    or service_value['force_type'] not in ['service', 'node',
                                                           'none']:
                raise HTTPBadRequest("No force_type or error force_type value"
                                     " in service")

    def check_data_type(config):
        if config['data_type'] not in ['int', 'string', 'list', 'boolean',
                                       'float', 'ipaddr', 'password']:
            raise HTTPBadRequest("data_type '%s' in '%s' not support" % (
                config['data_type'], config['name']))

    if not template:
        raise HTTPBadRequest('Template config is null!')

    for value in template.values():
        for item in CONFIG_ITEMS:
            if not value.get(item):
                raise HTTPBadRequest('No service or config file found in '
                                     'template config!')
        check_data_type(value)
        check_service_format(value['service'])


class Controller(controller.BaseController):
    """
    WSGI controller for template_configs resource in Daisy v1 API

    The template_configs resource API is a RESTful web service for
    template_config data.
    The API is as follows::

        GET  /template_configs -- Returns a set of brief metadata about
                                    template_configs
        GET  /template_configs/detail -- Returns a set of detailed metadata
                                        about emplate_configs
        HEAD /template_configs/<ID> --
        Return metadata about an template_config with id <ID>
        GET  /template_configs/<ID> --
        Return template_config data for template_config with id <ID>
        POST /template_configs --
        Store template_config data and return metadata about the
                        newly-stored template_config
        PUT  /template_configs/<ID> --
        Update template_config metadata and/or upload template_config
                            data for a previously-reserved template_config
        DELETE /template_configs/<ID> -- Delete the template_config with <ID>
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

    def _raise_404_if_cluster_deleted(self, req, cluster_id):
        cluster = self.get_cluster_meta_or_404(req, cluster_id)
        if cluster['deleted']:
            msg = _("cluster with identifier %s has been deleted.") % \
                cluster_id
            raise HTTPNotFound(msg)

    @utils.mutating
    def get_template_config(self, req, id):
        """
        Returns metadata about an template_config in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque template_config identifier

        :raises HTTPNotFound if template_config metadata is not
                available to user
        """
        self._enforce(req, 'get_template_config')
        template_config_meta = self.get_template_config_meta_or_404(req, id)
        return {'template_config_meta': template_config_meta}

    def list_template_config(self, req):
        """
        Returns detailed information for all available template_configs

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'template_configs': [
                {'id': <ID>,
                 'name': <NAME>,
                 'description': <DESCRIPTION>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._enforce(req, 'list_template_config')
        params = self._get_query_params(req)
        try:
            template_configs = registry.list_template_config_metadata(
                req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(template_configs=template_configs)

    @utils.mutating
    def import_template_config(self, req, template_config_meta):
        self._enforce(req, 'import_template_config')
        try:
            template = json.loads(template_config_meta.get('template', None))
        except ValueError as e:
            LOG.error(e.message)
            raise HTTPBadRequest(explanation=e.message, request=req)
        check_template_config_format(template)
        template_config_meta = registry.import_template_config_metadata(
            req.context, template_config_meta)
        return {'template_config_meta': template_config_meta}


class TemplateConfigSetDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["template_config_meta"] = utils.get_dict_meta(request)
        return result

    def add_template_config(self, request):
        return self._deserialize(request)

    def update_template_config(self, request):
        return self._deserialize(request)

    def import_template_config(self, request):
        return self._deserialize(request)


class TemplateConfigSetSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_template_config(self, response, result):
        template_config_meta = result['template_config_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(
            dict(template_config=template_config_meta))
        return response

    def delete_template_config(self, response, result):
        template_config_meta = result['template_config_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(
            dict(template_config=template_config_meta))
        return response

    def get_template_config(self, response, result):
        template_config_meta = result['template_config_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(
            dict(template_config=template_config_meta))
        return response

    def import_template_config(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response


def create_resource():
    """template_configs resource factory method"""
    deserializer = TemplateConfigSetDeserializer()
    serializer = TemplateConfigSetSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
