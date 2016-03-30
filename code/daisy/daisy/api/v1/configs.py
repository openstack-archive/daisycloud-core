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
/configs endpoint for Daisy v1 API
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
    WSGI controller for configs resource in Daisy v1 API

    The configs resource API is a RESTful web service for config data. The API
    is as follows::

        GET  /configs -- Returns a set of brief metadata about configs
        GET  /configs/detail -- Returns a set of detailed metadata about
                              configs
        HEAD /configs/<ID> -- Return metadata about an config with id <ID>
        GET  /configs/<ID> -- Return config data for config with id <ID>
        POST /configs -- Store config data and return metadata about the
                        newly-stored config
        PUT  /configs/<ID> -- Update config metadata and/or upload config
                            data for a previously-reserved config
        DELETE /configs/<ID> -- Delete the config with id <ID>
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
    def _raise_404_if_config_set_delete(self, req, config_set_id):
        config_set = self.get_config_set_meta_or_404(req, config_set_id)
        if config_set['deleted']:
            msg = _("config_set with identifier %s has been deleted.") % config_set_id
            raise HTTPNotFound(msg)

    def _raise_404_if_config_file_delete(self, req, config_file_id):
        config_file = self.get_config_file_meta_or_404(req, config_file_id)
        if config_file['deleted']:
            msg = _("config_file with identifier %s has been deleted.") % config_file_id
            raise HTTPNotFound(msg)
    def _raise_404_if_role_exist(self,req,config_meta):
        role_id=""
        try:
            roles = registry.get_roles_detail(req.context)
            for role in roles:
                if role['cluster_id'] == config_meta['cluster'] and role['name'] == config_meta['role']:
                    role_id=role['id']
                    break
        except exception.Invalid as e:
                raise HTTPBadRequest(explanation=e.msg, request=req)
        return role_id
    def _raise_404_if_cluster_deleted(self, req, cluster_id):
        cluster = self.get_cluster_meta_or_404(req, cluster_id)
        if cluster['deleted']:
            msg = _("cluster with identifier %s has been deleted.") % cluster_id
            raise HTTPNotFound(msg)

    @utils.mutating
    def add_config(self, req, config_meta):
        """
        Adds a new config to Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about config

        :raises HTTPBadRequest if x-config-name is missing
        """
        self._enforce(req, 'add_config')
        
        if config_meta.has_key('cluster'):
            orig_cluster = str(config_meta['cluster'])
            self._raise_404_if_cluster_deleted(req, orig_cluster)
        
        if config_meta.has_key('role'):
            role_id=self._raise_404_if_role_exist(req,config_meta)
            if not role_id:
                msg = "the role name is not exist"
                LOG.error(msg)
                raise HTTPNotFound(msg)

        config_meta = registry.config_interface_metadata(req.context, config_meta)
        return config_meta

    @utils.mutating
    def delete_config(self, req, config_meta):
        """
        Deletes a config from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about config

        :raises HTTPBadRequest if x-config-name is missing
        """
        self._enforce(req, 'delete_config')

        try:
            for id in eval(config_meta['config']):
                registry.delete_config_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find config to delete: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete config: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("config %(id)s could not be deleted because it is in use: "
                     "%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.warn(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            #self.notifier.info('config.delete', config)
            return Response(body='', status=200)

    @utils.mutating
    def get_config(self, req, id):
        """
        Returns metadata about an config in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque config identifier

        :raises HTTPNotFound if config metadata is not available to user
        """
        self._enforce(req, 'get_config')
        config_meta = self.get_config_meta_or_404(req, id)
        return {'config_meta': config_meta}

    def detail(self, req):
        """
        Returns detailed information for all available configs

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'configs': [
                {'id': <ID>,
                 'name': <NAME>,
                 'description': <DESCRIPTION>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._enforce(req, 'get_configs')
        params = self._get_query_params(req)
        try:
            configs = registry.get_configs_detail(req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(configs=configs)

class ConfigDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["config_meta"] = utils.get_config_meta(request)
        return result

    def add_config(self, request):
        return self._deserialize(request)
        
    def delete_config(self, request):
        return self._deserialize(request)

class ConfigSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_config(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def delete_config(self, response, result):
        config_meta = result['config_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config=config_meta))
        return response

    def get_config(self, response, result):
        config_meta = result['config_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config=config_meta))
        return response

def create_resource():
    """configs resource factory method"""
    deserializer = ConfigDeserializer()
    serializer = ConfigSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)

