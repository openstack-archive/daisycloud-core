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
/hosts endpoint for Daisy v1 API
"""
import ast

from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden
from webob.exc import HTTPNotFound
from webob.exc import HTTPConflict
from webob import Response

from daisy import i18n
from daisy import notifier

from daisy.api import policy
import daisy.api.v1

from daisy.common import exception
from daisy.common import property_utils
from daisy.common import utils
from daisy.common import wsgi
import daisy.registry.client.v1.api as registry
from daisy.api.v1 import controller
from daisy.api.v1 import filters


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE
SERVICE_DISK_SERVICE = ('db', 'glance', 'db_backup', 'mongodb', 'nova')
DISK_LOCATION = ('local', 'share', 'share_cluster')
PROTOCOL_TYPE = ('FIBER', 'ISCSI', 'CEPH')
CINDER_VOLUME_BACKEND_PARAMS = ('management_ips', 'data_ips', 'pools',
                                'volume_driver', 'volume_type',
                                'role_id', 'user_name', 'user_pwd')
CINDER_VOLUME_BACKEND_DRIVER = ['KS3200_IPSAN', 'KS3200_FCSAN',
                                'FUJITSU_ETERNUS', 'HP3PAR_FCSAN']


class Controller(controller.BaseController):
    """
    WSGI controller for hosts resource in Daisy v1 API

    The hosts resource API is a RESTful web service for host data. The API
    is as follows::

        GET  /hosts -- Returns a set of brief metadata about hosts
        GET  /hosts/detail -- Returns a set of detailed metadata about
                              hosts
        HEAD /hosts/<ID> -- Return metadata about an host with id <ID>
        GET  /hosts/<ID> -- Return host data for host with id <ID>
        POST /hosts -- Store host data and return metadata about the
                        newly-stored host
        PUT  /hosts/<ID> -- Update host metadata and/or upload host
                            data for a previously-reserved host
        DELETE /hosts/<ID> -- Delete the host with id <ID>
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

    def _raise_404_if_role_deleted(self, req, role_id):
        role = self.get_role_meta_or_404(req, role_id)
        if role is None or role['deleted']:
            msg = _("role with identifier %s has been deleted.") % role_id
            raise HTTPNotFound(msg)
        if role['type'] == 'template':
            msg = "role type of %s is 'template'" % role_id
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

    def _raise_404_if_service_disk_deleted(self, req, service_disk_id):
        service_disk = self.get_service_disk_meta_or_404(req, service_disk_id)
        if service_disk is None or service_disk['deleted']:
            msg = _(
                "service_disk with identifier %s has been deleted.") % \
                service_disk_id
            raise HTTPNotFound(msg)

    def _default_value_set(self, disk_meta):
        if ('disk_location' not in disk_meta or
                not disk_meta['disk_location'] or
                disk_meta['disk_location'] == ''):
            disk_meta['disk_location'] = 'local'
        if 'lun' not in disk_meta:
            disk_meta['lun'] = 0
        if 'size' not in disk_meta:
            disk_meta['size'] = -1
        if 'protocol_type' not in disk_meta:
            disk_meta['protocol_type'] = 'ISCSI'

    def _unique_service_in_role(self, req, disk_meta):
        params = {'filters': {'role_id': disk_meta['role_id']}}
        service_disks = registry.list_service_disk_metadata(
            req.context, **params)
        if disk_meta['disk_location'] == 'share_cluster':
            for disk in service_disks:
                if disk['service'] == disk_meta['service'] and \
                        disk['disk_location'] != 'share_cluster':
                    id = disk['id']
                    registry.delete_service_disk_metadata(req.context, id)
        else:
            for service_disk in service_disks:
                if service_disk['disk_location'] == 'share_cluster' and \
                        service_disk['service'] == disk_meta['service']:
                    id = service_disk['id']
                    registry.delete_service_disk_metadata(req.context, id)
                elif service_disk['service'] == disk_meta['service']:
                    msg = "disk service %s has existed in role %s" % (
                        disk_meta['service'], disk_meta['role_id'])
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg,
                                         request=req,
                                         content_type="text/plain")

    def _service_disk_add_meta_valid(self, req, disk_meta):
        if 'role_id' not in disk_meta:
            msg = "'role_id' must be given"
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        else:
            self._raise_404_if_role_deleted(req, disk_meta['role_id'])

        if 'service' not in disk_meta:
            msg = "'service' must be given"
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        else:
            if disk_meta['service'] not in SERVICE_DISK_SERVICE:
                msg = "service '%s' is not supported" % disk_meta['service']
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")

        if disk_meta['disk_location'] not in DISK_LOCATION:
            msg = "disk_location %s is not supported" % disk_meta[
                'disk_location']
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        if disk_meta['disk_location'] in ['share', 'share_cluster'] \
                and 'data_ips' not in disk_meta:
            msg = "'data_ips' must be given when disk_location was not local"
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

        if disk_meta['lun'] < 0:
            msg = "'lun' should not be less than 0"
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

        disk_meta['size'] = ast.literal_eval(str(disk_meta['size']))
        if not isinstance(disk_meta['size'], int):
            msg = "'size' is not integer"
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        if disk_meta['size'] < -1:
            msg = "'size' is invalid"
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

        if disk_meta.get('protocol_type', None) \
                and disk_meta['protocol_type'] not in PROTOCOL_TYPE:
            msg = "protocol type %s is not supported" % disk_meta[
                'protocol_type']
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

        self._unique_service_in_role(req, disk_meta)

    def _service_disk_update_meta_valid(self, req, id, disk_meta):
        orig_disk_meta = self.get_service_disk_meta_or_404(req, id)
        if 'role_id' in disk_meta:
            self._raise_404_if_role_deleted(req, disk_meta['role_id'])

        if 'service' in disk_meta:
            if disk_meta['service'] not in SERVICE_DISK_SERVICE:
                msg = "service '%s' is not supported" % disk_meta['service']
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")

        if 'disk_location' in disk_meta:
            if disk_meta['disk_location'] not in DISK_LOCATION:
                msg = "disk_location '%s' is not supported" % disk_meta[
                    'disk_location']
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")
            if (disk_meta['disk_location'] == 'share' and
                    'data_ips' not in disk_meta and
                    not orig_disk_meta['data_ips']):
                msg = "'data_ips' must be given when disk_location is share"
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")

        if 'size' in disk_meta:
            disk_meta['size'] = ast.literal_eval(str(disk_meta['size']))
            if not isinstance(disk_meta['size'], int):
                msg = "'size' is not integer"
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")
            if disk_meta['size'] < -1:
                msg = "'size' is invalid"
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")

        if disk_meta.get('protocol_type', None) \
                and disk_meta['protocol_type'] not in PROTOCOL_TYPE:
            msg = "protocol type %s is not supported" % disk_meta[
                'protocol_type']
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

    @utils.mutating
    def service_disk_add(self, req, disk_meta):
        """
        Export daisy db data to tecs.conf and HA.conf.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-install-cluster is missing
        """

        self._enforce(req, 'service_disk_add')
        self._default_value_set(disk_meta)
        self._service_disk_add_meta_valid(req, disk_meta)
        service_disk_meta = registry.add_service_disk_metadata(
            req.context, disk_meta)
        return {'disk_meta': service_disk_meta}

    @utils.mutating
    def service_disk_delete(self, req, id):
        """
        Deletes a service_disk from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about service_disk

        :raises HTTPBadRequest if x-service-disk-name is missing
        """
        self._enforce(req, 'delete_service_disk')
        try:
            registry.delete_service_disk_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find service_disk to delete: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete service_disk: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("service_disk %(id)s could not be deleted "
                     "because it is in use: "
                     "%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.warn(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            return Response(body='', status=200)

    @utils.mutating
    def service_disk_update(self, req, id, disk_meta):
        self._enforce(req, 'service_disk_update')
        self._service_disk_update_meta_valid(req, id, disk_meta)
        try:
            service_disk_meta = registry.update_service_disk_metadata(
                req.context, id, disk_meta)

        except exception.Invalid as e:
            msg = (_("Failed to update role metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find role to update: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update role: %s") %
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
            self.notifier.info('role.update', service_disk_meta)

        return {'disk_meta': service_disk_meta}

    @utils.mutating
    def service_disk_detail(self, req, id):
        """
        Returns metadata about an role in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque role identifier

        :raises HTTPNotFound if role metadata is not available to user
        """

        self._enforce(req, 'service_disk_detail')
        service_disk_meta = self.get_service_disk_meta_or_404(req, id)
        return {'disk_meta': service_disk_meta}

    def service_disk_list(self, req):
        self._enforce(req, 'service_disk_list')
        params = self._get_query_params(req)
        filters = params.get('filters', None)
        if 'role_id' in filters:
            role_id = filters['role_id']
            self._raise_404_if_role_deleted(req, role_id)
        try:
            service_disks = registry.list_service_disk_metadata(
                req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(disk_meta=service_disks)

    def _cinder_volume_list(self, req, params):
        try:
            cinder_volumes = registry.list_cinder_volume_metadata(
                req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return cinder_volumes

    def _is_cinder_volume_repeat(self, req, array_disk_info, update_id=None):
        params = {'filters': {}}

        if update_id:
            cinder_volume_metal = self.get_cinder_volume_meta_or_404(
                req, update_id)
            new_management_ips = array_disk_info.get(
                'management_ips', cinder_volume_metal[
                    'management_ips']).split(",")
            new_pools = array_disk_info.get(
                'pools', cinder_volume_metal['pools']).split(",")
        else:
            new_management_ips = array_disk_info['management_ips'].split(",")
            new_pools = array_disk_info['pools'].split(",")

        org_cinder_volumes = self._cinder_volume_list(req, params)
        for cinder_volume in org_cinder_volumes:
            if (set(cinder_volume['management_ips'].split(",")) == set(
                    new_management_ips) and
                    set(cinder_volume['pools'].split(",")) == set(new_pools)):
                if cinder_volume['id'] != update_id:
                    msg = 'cinder_volume array disks ' \
                          'conflict with cinder_volume %s' % cinder_volume[
                              'id']
                    raise HTTPBadRequest(explanation=msg, request=req)

    def _get_cinder_volume_backend_index(self, req, disk_array):
        params = {'filters': {}}
        cinder_volumes = self._cinder_volume_list(req, params)
        index = 1
        while True:
            backend_index = "%s-%s" % (disk_array['volume_driver'], index)
            flag = True
            for cinder_volume in cinder_volumes:
                if backend_index == cinder_volume['backend_index']:
                    index = index + 1
                    flag = False
                    break
            if flag:
                break
        return backend_index

    @utils.mutating
    def cinder_volume_add(self, req, disk_meta):
        """
        Export daisy db data to tecs.conf and HA.conf.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-install-cluster is missing
        """
        self._enforce(req, 'cinder_volume_add')
        if 'role_id' not in disk_meta:
            msg = "'role_id' must be given"
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        else:
            self._raise_404_if_role_deleted(req, disk_meta['role_id'])

        disk_arrays = eval(disk_meta['disk_array'])
        for disk_array in disk_arrays:
            for key in disk_array.keys():
                if (key not in CINDER_VOLUME_BACKEND_PARAMS and
                        key != 'data_ips'):
                    msg = "'%s' must be given for cinder volume config" % key
                    raise HTTPBadRequest(explanation=msg,
                                         request=req,
                                         content_type="text/plain")
                if disk_array[
                        'volume_driver'] not in CINDER_VOLUME_BACKEND_DRIVER:
                    msg = "volume_driver %s is not supported" % disk_array[
                        'volume_driver']
                    raise HTTPBadRequest(explanation=msg,
                                         request=req,
                                         content_type="text/plain")
                if (disk_array['volume_driver'] == 'FUJITSU_ETERNUS' and
                    ('data_ips' not in disk_array or
                     not disk_array['data_ips'])):
                    msg = "data_ips must be given " \
                          "when using FUJITSU Disk Array"
                    raise HTTPBadRequest(explanation=msg,
                                         request=req,
                                         content_type="text/plain")
            self._is_cinder_volume_repeat(req, disk_array)
            disk_array['role_id'] = disk_meta['role_id']
            disk_array['backend_index'] = \
                self._get_cinder_volume_backend_index(
                req, disk_array)
            cinder_volumes = registry.add_cinder_volume_metadata(
                req.context, disk_array)
        return {'disk_meta': cinder_volumes}

    @utils.mutating
    def cinder_volume_delete(self, req, id):
        """
        Deletes a service_disk from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about service_disk

        :raises HTTPBadRequest if x-service-disk-name is missing
        """
        self._enforce(req, 'delete_cinder_volume')
        try:
            registry.delete_cinder_volume_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find cinder volume to delete: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete cinder volume: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("cindre volume %(id)s could not "
                     "be deleted because it is in use: "
                     "%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.warn(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            return Response(body='', status=200)

    def _is_data_ips_valid(self, req, update_id, update_meta):
        orgin_cinder_volume = self.get_cinder_volume_meta_or_404(
            req, update_id)

        new_driver = update_meta.get('volume_driver',
                                     orgin_cinder_volume['volume_driver'])
        if new_driver != 'FUJITSU_ETERNUS':
            return

        new_data_ips = update_meta.get('data_ips',
                                       orgin_cinder_volume['data_ips'])
        if not new_data_ips:
            msg = "data_ips must be given when using FUJITSU Disk Array"
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

    @utils.mutating
    def cinder_volume_update(self, req, id, disk_meta):
        for key in disk_meta.keys():
            if key not in CINDER_VOLUME_BACKEND_PARAMS:
                msg = "'%s' must be given for cinder volume config" % key
                raise HTTPBadRequest(explanation=msg,
                                     request=req,
                                     content_type="text/plain")
        if 'role_id' in disk_meta:
            self._raise_404_if_role_deleted(req, disk_meta['role_id'])
        if ('volume_driver' in disk_meta and disk_meta[
                'volume_driver'] not in CINDER_VOLUME_BACKEND_DRIVER):
            msg = "volume_driver %s is not supported" % disk_meta[
                'volume_driver']
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

        self._is_cinder_volume_repeat(req, disk_meta, id)
        self._is_data_ips_valid(req, id, disk_meta)

        try:
            cinder_volume_meta = registry.update_cinder_volume_metadata(
                req.context, id, disk_meta)

        except exception.Invalid as e:
            msg = (
                _("Failed to update cinder_volume metadata. Got error: %s") %
                utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find cinder_volume to update: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update cinder_volume: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.warn(utils.exception_to_str(e))
            raise HTTPConflict(body=_('cinder_volume operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('cinder_volume.update', cinder_volume_meta)

        return {'disk_meta': cinder_volume_meta}

    @utils.mutating
    def cinder_volume_detail(self, req, id):
        """
        Returns metadata about an role in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque role identifier

        :raises HTTPNotFound if role metadata is not available to user
        """
        self._enforce(req, 'cinder_volume_detail')
        cinder_volume_meta = self.get_cinder_volume_meta_or_404(req, id)
        return {'disk_meta': cinder_volume_meta}

    def cinder_volume_list(self, req):
        self._enforce(req, 'cinder_volume_list')
        params = self._get_query_params(req)
        filters = params.get('filters', None)
        if 'role_id' in filters:
            role_id = filters['role_id']
            self._raise_404_if_role_deleted(req, role_id)
        cinder_volumes = self._cinder_volume_list(req, params)
        return dict(disk_meta=cinder_volumes)


class DiskArrayDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["disk_meta"] = utils.get_dict_meta(request)
        return result

    def service_disk_add(self, request):
        return self._deserialize(request)

    def service_disk_update(self, request):
        return self._deserialize(request)

    def cinder_volume_add(self, request):
        return self._deserialize(request)

    def cinder_volume_update(self, request):
        return self._deserialize(request)


class DiskArraySerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def service_disk_add(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def service_disk_update(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def cinder_volume_add(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def cinder_volume_update(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response


def create_resource():
    """Image members resource factory method"""
    deserializer = DiskArrayDeserializer()
    serializer = DiskArraySerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
