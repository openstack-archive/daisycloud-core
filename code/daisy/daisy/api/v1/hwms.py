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
/Hwm endpoint for Daisy v1 API
"""

from oslo_config import cfg
from oslo_log import log as logging
import webob.exc
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
from daisy.registry.api.v1 import hwms

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

SUPPORTED_PARAMS = hwms.SUPPORTED_PARAMS
SUPPORTED_FILTERS = hwms.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE
CONF = cfg.CONF
CONF.import_opt('disk_formats', 'daisy.common.config',
                group='image_format')
CONF.import_opt('container_formats', 'daisy.common.config',
                group='image_format')
CONF.import_opt('image_property_quota', 'daisy.common.config')


class Controller(controller.BaseController):
    """
    WSGI controller for hwms resource in Daisy v1 API

    The Templates resource API is a RESTful web Template for Template data.
    The API is as follows::

        GET  /Templates -- Returns a set of brief metadata about Templates
        GET  /Templates/detail -- Returns a set of detailed metadata about
                              Templates
        HEAD /Templates/<ID> -- Return metadata about an Template with id <ID>
        GET  /Templates/<ID> -- Return Template data for Template with id <ID>
        POST /Templates -- Store Template data and return metadata about the
                        newly-stored Template
        PUT  /Templates/<ID> -- Update Template metadata and/or upload Template
                            data for a previously-reserved Template
        DELETE /Templates/<ID> -- Delete the Template with id <ID>
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
            msg = _("Cluster with identifier %s has been deleted.") % \
                cluster_id
            raise webob.exc.HTTPNotFound(msg)

    def get_clusters_hwm_ip(self, req):
        params = self._get_query_params(req)
        clusters_hwm_ip = list()
        clusters = registry.get_clusters_detail(req.context, **params)
        for cluster in clusters:
            clusters_hwm_ip.append(cluster.get('hwm_ip'))
        return clusters_hwm_ip

    @utils.mutating
    def add_hwm(self, req, hwm):
        """
        Adds a new hwm to Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about Template

        :raises HTTPBadRequest if x-Template-name is missing
        """
        self._enforce(req, 'add_template')
        hwm = registry.add_hwm_metadata(req.context, hwm)

        return {'hwm': hwm}

    @utils.mutating
    def update_hwm(self, req, id, hwm):
        """
        Updates an existing hwm with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'update_hwm')
        hwm_meta = registry.hwm_detail_metadata(req.context, id)
        hwm_ip = hwm_meta['hwm_ip']
        clusters_hwm_ip = self.get_clusters_hwm_ip(req)
        if hwm_ip in clusters_hwm_ip:
            msg = (_("Hwm %s has already used in cluster, "
                     "it can not be update. " % hwm_ip))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg, request=req,
                                content_type="text/plain")
        try:
            hwm = registry.update_hwm_metadata(req.context, id, hwm)
        except exception.Invalid as e:
            msg = (_("Failed to update hwm metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find hwm to update: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update hwm: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.warn(utils.exception_to_str(e))
            raise HTTPConflict(body=_('hwm operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('hwm.update', hwm)

        return {'hwm': hwm}

    @utils.mutating
    def delete_hwm(self, req, id):
        """
        delete a existing hwm template with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'delete_hwm')
        hwm_meta = registry.hwm_detail_metadata(req.context, id)
        hwm_ip = hwm_meta['hwm_ip']
        clusters_hwm_ip = self.get_clusters_hwm_ip(req)
        if hwm_ip in clusters_hwm_ip:
            msg = (_("Hwm %s has already used in cluster, "
                     "it can not be deleted. " % hwm_ip))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg, request=req,
                                content_type="text/plain")
        try:
            registry.delete_hwm_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find hwm to delete: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPNotFound(explanation=msg, request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete hwm: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg, request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_(
                "hwm %(id)s could not be deleted because it is in "
                "use:%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.error(msg)
            raise HTTPConflict(explanation=msg, request=req,
                               content_type="text/plain")
        else:
            return Response(body='', status=200)

    @utils.mutating
    def detail(self, req, id):
        """
        delete a existing hwm with the registry.
        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifie
        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'detail')
        context = req.context
        try:
            hwm_meta = registry.hwm_detail_metadata(context, id)
        except exception.NotFound:
            msg = "Hwm with identifier %s not found" % id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=req, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden hwm access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=req,
                                          content_type='text/plain')
        return {'hwm': hwm_meta}

    @utils.mutating
    def list(self, req):
        self._enforce(req, 'list')
        params = self._get_query_params(req)
        try:
            hwm_list = registry.hwm_list_metadata(req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(hwm=hwm_list)


class HwmDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""
    def _deserialize(self, request):
        result = {}
        result["hwm"] = utils.get_hwm_meta(request)
        return result

    def add_hwm(self, request):
        return self._deserialize(request)

    def update_hwm(self, request):
        return self._deserialize(request)


class HwmSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""
    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_hwm(self, response, result):
        hwm = result['hwm']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(hwm=hwm))
        return response

    def delete_hwm(self, response, result):
        hwm = result['hwm']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(hwm=hwm))
        return response

    def get_detail(self, response, result):
        hwm = result['hwm']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(hwm=hwm))
        return response

    def update_hwm(self, response, result):
        hwm = result['hwm']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(hwm=hwm))
        return response


def create_resource():
    """Templates resource factory method"""
    deserializer = HwmDeserializer()
    serializer = HwmSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
