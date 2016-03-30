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
/config_sets endpoint for Daisy v1 API
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
from daisy.api.configset import manager

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
    WSGI controller for config_sets resource in Daisy v1 API

    The config_sets resource API is a RESTful web service for config_set data. The API
    is as follows::

        GET  /config_sets -- Returns a set of brief metadata about config_sets
        GET  /config_sets/detail -- Returns a set of detailed metadata about
                              config_sets
        HEAD /config_sets/<ID> -- Return metadata about an config_set with id <ID>
        GET  /config_sets/<ID> -- Return config_set data for config_set with id <ID>
        POST /config_sets -- Store config_set data and return metadata about the
                        newly-stored config_set
        PUT  /config_sets/<ID> -- Update config_set metadata and/or upload config_set
                            data for a previously-reserved config_set
        DELETE /config_sets/<ID> -- Delete the config_set with id <ID>
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

    def _raise_404_if_cluster_deleted(self, req, cluster_id):
        cluster = self.get_cluster_meta_or_404(req, cluster_id)
        if cluster['deleted']:
            msg = _("cluster with identifier %s has been deleted.") % cluster_id
            raise HTTPNotFound(msg)

    @utils.mutating
    def add_config_set(self, req, config_set_meta):
        """
        Adds a new config_set to Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about config_set

        :raises HTTPBadRequest if x-config_set-name is missing
        """
        self._enforce(req, 'add_config_set')
        #config_set_id=config_set_meta["id"]
        config_set_name = config_set_meta["name"]
        config_set_description = config_set_meta["description"]
        #print config_set_id
        print config_set_name
        print config_set_description
        config_set_meta = registry.add_config_set_metadata(req.context, config_set_meta)

        return {'config_set_meta': config_set_meta}

    @utils.mutating
    def delete_config_set(self, req, id):
        """
        Deletes a config_set from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about config_set

        :raises HTTPBadRequest if x-config_set-name is missing
        """
        self._enforce(req, 'delete_config_set')

        try:
            registry.delete_config_set_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find config_set to delete: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete config_set: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("config_set %(id)s could not be deleted because it is in use: "
                     "%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.warn(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            #self.notifier.info('config_set.delete', config_set)
            return Response(body='', status=200)

    @utils.mutating
    def get_config_set(self, req, id):
        """
        Returns metadata about an config_set in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque config_set identifier

        :raises HTTPNotFound if config_set metadata is not available to user
        """
        self._enforce(req, 'get_config_set')
        config_set_meta = self.get_config_set_meta_or_404(req, id)
        return {'config_set_meta': config_set_meta}

    def detail(self, req):
        """
        Returns detailed information for all available config_sets

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'config_sets': [
                {'id': <ID>,
                 'name': <NAME>,
                 'description': <DESCRIPTION>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._enforce(req, 'get_config_sets')
        params = self._get_query_params(req)
        try:
            config_sets = registry.get_config_sets_detail(req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(config_sets=config_sets)

    @utils.mutating
    def update_config_set(self, req, id, config_set_meta):
        """
        Updates an existing config_set with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'modify_image')
        orig_config_set_meta = self.get_config_set_meta_or_404(req, id)

        # Do not allow any updates on a deleted image.
        # Fix for LP Bug #1060930
        if orig_config_set_meta['deleted']:
            msg = _("Forbidden to update deleted config_set.")
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        try:
            config_set_meta = registry.update_config_set_metadata(req.context,
                                                                  id,
                                                                  config_set_meta)

        except exception.Invalid as e:
            msg = (_("Failed to update config_set metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find config_set to update: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update config_set: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.warn(utils.exception_to_str(e))
            raise HTTPConflict(body=_('config_set operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('config_set.update', config_set_meta)

        return {'config_set_meta': config_set_meta}
        
    def _raise_404_if_role_exist(self,req,config_set_meta):
        role_id_list=[]
        try:
            roles = registry.get_roles_detail(req.context)
            for role in roles:
                for role_name in eval(config_set_meta['role']):
                    if role['cluster_id'] == config_set_meta['cluster'] and role['name'] == role_name:
                        role_id_list.append(role['id'])
                        break
        except exception.Invalid as e:
                raise HTTPBadRequest(explanation=e.msg, request=req)
        return role_id_list

    @utils.mutating
    def cluster_config_set_update(self, req, config_set_meta):
        if config_set_meta.has_key('cluster'):
            orig_cluster = str(config_set_meta['cluster'])
            self._raise_404_if_cluster_deleted(req, orig_cluster)
            try:
                if config_set_meta.get('role',None):
                    role_id_list=self._raise_404_if_role_exist(req,config_set_meta)
                    if len(role_id_list) == len(eval(config_set_meta['role'])):
                        for role_id in role_id_list:
                            backend=manager.configBackend('clushshell', req, role_id)
                            backend.push_config()
                    else:
                        msg = "the role is not exist"
                        LOG.error(msg)
                        raise HTTPNotFound(msg)
                else:
                    roles = registry.get_roles_detail(req.context)
                    for role in roles:
                        if role['cluster_id'] == config_set_meta['cluster']:
                            backend=manager.configBackend('clushshell', req, role['id'])
                            backend.push_config()
                    
            except exception.Invalid as e:
                raise HTTPBadRequest(explanation=e.msg, request=req)
            
            config_status={"status":"config successful"}
            return {'config_set':config_status}
        else:
            msg = "the cluster is not exist"
            LOG.error(msg)
            raise HTTPNotFound(msg)

    @utils.mutating
    def cluster_config_set_progress(self, req, config_set_meta):
        role_list = []
        if config_set_meta.has_key('cluster'):
            orig_cluster = str(config_set_meta['cluster'])
            self._raise_404_if_cluster_deleted(req, orig_cluster)
            try:
                if config_set_meta.get('role',None):
                    role_id_list=self._raise_404_if_role_exist(req,config_set_meta)
                    if len(role_id_list) == len(eval(config_set_meta['role'])):
                        for role_id in role_id_list:
                            role_info = {}
                            role_meta=registry.get_role_metadata(req.context, role_id)
                            role_info['role-name']=role_meta['name']
                            role_info['config_set_update_progress']=role_meta['config_set_update_progress']
                            role_list.append(role_info)
                    else:
                        msg = "the role is not exist"
                        LOG.error(msg)
                        raise HTTPNotFound(msg)
                else:
                    roles = registry.get_roles_detail(req.context)
                    for role in roles:
                        if role['cluster_id'] == config_set_meta['cluster']:
                            role_info = {}
                            role_info['role-name']=role['name']
                            role_info['config_set_update_progress']=role['config_set_update_progress']
                            role_list.append(role_info)

            except exception.Invalid as e:
                raise HTTPBadRequest(explanation=e.msg, request=req)
            return role_list
            
        else:
            msg = "the cluster is not exist"
            LOG.error(msg)
            raise HTTPNotFound(msg)

class Config_setDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["config_set_meta"] = utils.get_config_set_meta(request)
        return result

    def add_config_set(self, request):
        return self._deserialize(request)

    def update_config_set(self, request):
        return self._deserialize(request)

    def cluster_config_set_update(self, request):
        return self._deserialize(request)

    def cluster_config_set_progress(self, request):
        return self._deserialize(request)

class Config_setSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_config_set(self, response, result):
        config_set_meta = result['config_set_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config_set=config_set_meta))
        return response

    def delete_config_set(self, response, result):
        config_set_meta = result['config_set_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config_set=config_set_meta))
        return response

    def get_config_set(self, response, result):
        config_set_meta = result['config_set_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config_set=config_set_meta))
        return response

    def cluster_config_set_update(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def cluster_config_set_progress(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(config_set=result))
        return response

def create_resource():
    """config_sets resource factory method"""
    deserializer = Config_setDeserializer()
    serializer = Config_setSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)

