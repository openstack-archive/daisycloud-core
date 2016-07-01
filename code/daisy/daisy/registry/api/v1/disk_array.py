# Copyright 2010-2011 OpenStack Foundation
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
Reference implementation registry server WSGI controller
"""

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import strutils
from oslo_utils import timeutils
from webob import exc

from daisy.common import exception
from daisy.common import utils
from daisy.common import wsgi
import daisy.db
from daisy import i18n


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

CONF = cfg.CONF

DISPLAY_FIELDS_IN_INDEX = ['id', 'name', 'size',
                           'disk_format', 'container_format',
                           'checksum']

SUPPORTED_FILTERS = ['name', 'status', 'role_id', 'container_format',
                     'disk_format',
                     'min_ram', 'min_disk', 'size_min', 'size_max',
                     'changes-since', 'protected']

SUPPORTED_SORT_KEYS = ('name', 'status', 'cluster_id', 'container_format',
                       'disk_format',
                       'size', 'id', 'created_at', 'updated_at')

SUPPORTED_SORT_DIRS = ('asc', 'desc')

SUPPORTED_PARAMS = ('limit', 'marker', 'sort_key', 'sort_dir', 'cluster_id')
SUPPORTED_SORT_KEYS = ('name', 'role_id', 'status', 'container_format',
                       'disk_format',
                       'size', 'id', 'created_at', 'updated_at')

SUPPORTED_SORT_DIRS = ('asc', 'desc')

SUPPORTED_PARAMS = ('role_id', 'limit', 'marker', 'sort_key', 'sort_dir')


class Controller(object):

    def __init__(self):
        self.db_api = daisy.db.get_api()

    def _get_query_params(self, req):
        """Extract necessary query parameters from http request.

        :param req: the Request object coming from the wsgi layer
        :retval dictionary of filters to apply to list of service_disks
        """
        params = {
            'filters': self._get_filters(req),
            'limit': self._get_limit(req),
            'sort_key': [self._get_sort_key(req)],
            'sort_dir': [self._get_sort_dir(req)],
            'marker': self._get_marker(req),
        }

        for key, value in params.items():
            if value is None:
                del params[key]

        return params

    def _get_filters(self, req):
        """Return a dictionary of query param filters from the request

        :param req: the Request object coming from the wsgi layer
        :retval a dict of key/value filters
        """
        filters = {}
        properties = {}

        for param in req.params:
            if param in SUPPORTED_FILTERS:
                filters[param] = req.params.get(param)
            if param.startswith('property-'):
                _param = param[9:]
                properties[_param] = req.params.get(param)

        if 'changes-since' in filters:
            isotime = filters['changes-since']
            try:
                filters['changes-since'] = timeutils.parse_isotime(isotime)
            except ValueError:
                raise exc.HTTPBadRequest(_("Unrecognized changes-since value"))

        if 'protected' in filters:
            value = self._get_bool(filters['protected'])
            if value is None:
                raise exc.HTTPBadRequest(_("protected must be True, or "
                                           "False"))

            filters['protected'] = value

        # only allow admins to filter on 'deleted'
        if req.context.is_admin:
            deleted_filter = self._parse_deleted_filter(req)
            if deleted_filter is not None:
                filters['deleted'] = deleted_filter
            elif 'changes-since' not in filters:
                filters['deleted'] = False
        elif 'changes-since' not in filters:
            filters['deleted'] = False

        if properties:
            filters['properties'] = properties

        return filters

    def _get_limit(self, req):
        """Parse a limit query param into something usable."""
        try:
            limit = int(req.params.get('limit', CONF.limit_param_default))
        except ValueError:
            raise exc.HTTPBadRequest(_("limit param must be an integer"))

        if limit < 0:
            raise exc.HTTPBadRequest(_("limit param must be positive"))

        return min(CONF.api_limit_max, limit)

    def _get_marker(self, req):
        """Parse a marker query param into something usable."""
        marker = req.params.get('marker', None)

        if marker and not utils.is_uuid_like(marker):
            msg = _('Invalid marker format')
            raise exc.HTTPBadRequest(explanation=msg)

        return marker

    def _get_sort_key(self, req):
        """Parse a sort key query param from the request object."""
        sort_key = req.params.get('sort_key', 'created_at')
        if sort_key is not None and sort_key not in SUPPORTED_SORT_KEYS:
            _keys = ', '.join(SUPPORTED_SORT_KEYS)
            msg = _("Unsupported sort_key. Acceptable values: %s") % (_keys,)
            raise exc.HTTPBadRequest(explanation=msg)
        return sort_key

    def _get_sort_dir(self, req):
        """Parse a sort direction query param from the request object."""
        sort_dir = req.params.get('sort_dir', 'desc')
        if sort_dir is not None and sort_dir not in SUPPORTED_SORT_DIRS:
            _keys = ', '.join(SUPPORTED_SORT_DIRS)
            msg = _("Unsupported sort_dir. Acceptable values: %s") % (_keys,)
            raise exc.HTTPBadRequest(explanation=msg)
        return sort_dir

    def _get_bool(self, value):
        value = value.lower()
        if value == 'true' or value == '1':
            return True
        elif value == 'false' or value == '0':
            return False

        return None

    def _parse_deleted_filter(self, req):
        """Parse deleted into something usable."""
        deleted = req.params.get('deleted')
        if deleted is None:
            return None
        return strutils.bool_from_string(deleted)

    @utils.mutating
    def service_disk_add(self, req, body):
        """Registers a new service_disk with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the service_disk

        :retval Returns the newly-created service_disk
        information as a mapping,
                which will include the newly-created service_disk's internal id
                in the 'id' field
        """

        service_disk_data = body["service_disk"]

        id = service_disk_data.get('id')

        # role = service_disk_data.get('role')
        # add id and role
        # if role
        # self.db_api.get_role(req.context,role)

        if id and not utils.is_uuid_like(id):
            msg = _LI("Rejecting service_disk creation request for "
                      "invalid service_disk "
                      "id '%(bad_id)s'") % {'bad_id': id}
            LOG.info(msg)
            msg = _("Invalid service_disk id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            service_disk_data = self.db_api.service_disk_add(
                req.context, service_disk_data)
            # service_disk_data = dict(service_disk=make_image_dict(
            # service_disk_data))
            msg = (_LI("Successfully created node %s") %
                   service_disk_data["id"])
            LOG.info(msg)
            if 'service_disk' not in service_disk_data:
                service_disk_data = dict(service_disk=service_disk_data)
            return service_disk_data
        except exception.Duplicate:
            msg = _("node with identifier %s already exists!") % id
            LOG.warn(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add node metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to create node %s"), id)
            raise

    @utils.mutating
    def service_disk_delete(self, req, id):
        """Deletes an existing service_disk with the registry.

        :param req: wsgi Request object
        :param id:  The opaque internal identifier for the image

        :retval Returns 200 if delete was successful, a fault if not. On
        success, the body contains the deleted image information as a mapping.
        """
        try:
            deleted_service_disk = self.db_api.service_disk_destroy(
                req.context, id)
            msg = _LI("Successfully deleted service_disk %(id)s") % {'id': id}
            LOG.info(msg)
            return dict(service_disk=deleted_service_disk)
        except exception.ForbiddenPublicImage:
            msg = _LI("Delete denied for public service_disk %(id)s") % {
                'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to service_disk %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except exception.NotFound:
            msg = _LI("service_disk %(id)s not found") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to delete service_disk %s") % id)
            raise

    @utils.mutating
    def service_disk_update(self, req, id, body):
        """Updates an existing service_disk with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the image
        :param id:  The opaque internal identifier for the image

        :retval Returns the updated image information as a mapping,
        """
        service_disk_data = body['service_disk']
        try:
            updated_service_disk = self.db_api.service_disk_update(
                req.context, id, service_disk_data)

            msg = _LI("Updating metadata for service_disk %(id)s") % {'id': id}
            LOG.info(msg)
            if 'service_disk' not in updated_service_disk:
                service_disk_data = dict(service_disk=updated_service_disk)
            return service_disk_data
        except exception.Invalid as e:
            msg = (_("Failed to update service_disk metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("service_disk %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='service_disk not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public service_disk %(id)s") % {
                'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            raise
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='service_disk operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except Exception:
            LOG.exception(_LE("Unable to update service_disk %s") % id)
            raise

    @utils.mutating
    def service_disk_detail(self, req, id):
        """Return data about the given service_disk id."""
        try:
            service_disk_data = self.db_api.service_disk_detail(
                req.context, id)
            msg = "Successfully retrieved service_disk %(id)s" % {'id': id}
            LOG.debug(msg)
        except exception.NotFound:
            msg = _LI("service_disk %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to service_disk %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show service_disk %s") % id)
            raise
        if 'service_disk' not in service_disk_data:
            service_disk_data = dict(service_disk=service_disk_data)
        return service_disk_data

    def _list_service_disks(self, context, filters, params):
        """Get service_disks, wrapping in exception if necessary."""
        try:
            return self.db_api.service_disk_list(context, filters=filters,
                                                 **params)
        except exception.NotFound:
            LOG.warn(_LW("Invalid marker. service_disk %(id)s could not be "
                         "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. service_disk could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warn(_LW("Access denied to service_disk %(id)s but returning "
                         "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. service_disk could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get service_disks"))
            raise

    def service_disk_list(self, req):
        """Return a filtered list of public,
        non-deleted service_disks in detail

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(service_disks=[service_disk_list])

        Where service_disk_list is a sequence of mappings containing
        all service_disk model fields.
        """
        params = self._get_query_params(req)
        filters = params.pop('filters')
        service_disks = self._list_service_disks(req.context, filters, params)
        return dict(service_disks=service_disks)

    @utils.mutating
    def cinder_volume_add(self, req, body):
        """Registers a new cinder_volume with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the cinder_volume

        :retval Returns the newly-created cinder_volume
        information as a mapping,
                which will include the newly-created
                cinder_volume's internal id
                in the 'id' field
        """

        cinder_volume_data = body["cinder_volume"]

        id = cinder_volume_data.get('id')

        # role = service_disk_data.get('role')
        # add id and role
        # if role
        # self.db_api.get_role(req.context,role)

        if id and not utils.is_uuid_like(id):
            msg = _LI("Rejecting cinder_volume creation request for "
                      "invalid cinder_volume "
                      "id '%(bad_id)s'") % {'bad_id': id}
            LOG.info(msg)
            msg = _("Invalid cinder_volume id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            cinder_volume_data = self.db_api.cinder_volume_add(
                req.context, cinder_volume_data)
            msg = (_LI("Successfully created cinder_volume %s") %
                   cinder_volume_data["id"])
            LOG.info(msg)
            if 'cinder_volume' not in cinder_volume_data:
                cinder_volume_data = dict(cinder_volume=cinder_volume_data)
            return cinder_volume_data
        except exception.Duplicate:
            msg = _("cinder_volume with identifier %s already exists!") % id
            LOG.warn(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add cinder_volume metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to create cinder_volume %s"), id)
            raise

    @utils.mutating
    def cinder_volume_delete(self, req, id):
        """Deletes an existing cinder_volume with the registry.

        :param req: wsgi Request object
        :param id:  The opaque internal identifier for the image

        :retval Returns 200 if delete was successful, a fault if not. On
        success, the body contains the deleted image information as a mapping.
        """
        try:
            deleted_cinder_volume = self.db_api.cinder_volume_destroy(
                req.context, id)
            msg = _LI("Successfully deleted cinder_volume %("
                      "cinder_volume_id)s") % {
                'cinder_volume_id': id}
            LOG.info(msg)
            return dict(cinder_volume=deleted_cinder_volume)
        except exception.ForbiddenPublicImage:
            msg = _LI("Delete denied for public cinder_volume %("
                      "cinder_volume_id)s") % {
                'cinder_volume_id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to cinder_volume %(id)s but returning"
                      " 'not found'") % {'cinder_volume_id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except exception.NotFound:
            msg = _LI("cinder_volume %(cinder_volume_id)s not found") % {
                'cinder_volume_id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to delete cinder_volume %s") % id)
            raise

    @utils.mutating
    def cinder_volume_update(self, req, id, body):
        """Updates an existing cinder_volume with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the image
        :param id:  The opaque internal identifier for the image

        :retval Returns the updated image information as a mapping,
        """
        cinder_volume_data = body['cinder_volume']
        try:
            updated_cinder_volume = self.db_api.cinder_volume_update(
                req.context, id, cinder_volume_data)

            msg = _LI("Updating metadata for cinder_volume %("
                      "cinder_volume_id)s") % {
                'cinder_volume_id': id}
            LOG.info(msg)
            if 'cinder_volume' not in updated_cinder_volume:
                cinder_volume_data = dict(cinder_volume=updated_cinder_volume)
            return cinder_volume_data
        except exception.Invalid as e:
            msg = (_("Failed to update cinder_volume metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("cinder_volume %(cinder_volume_id)s not found") % {
                'cinder_volume_id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='cinder_volume not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public cinder_volume %("
                      "cinder_volume_id)s") % {
                'cinder_volume_id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            raise
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='cinder_volume operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except Exception:
            LOG.exception(_LE("Unable to update cinder_volume %s") % id)
            raise

    @utils.mutating
    def cinder_volume_detail(self, req, id):
        """Return data about the given cinder_volume id."""
        try:
            cinder_volume_data = self.db_api.cinder_volume_detail(
                req.context, id)
            msg = "Successfully retrieved cinder_volume %(id)s" % {'id': id}
            LOG.debug(msg)
        except exception.NotFound:
            msg = _LI("cinder_volume %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to cinder_volume %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show cinder_volume %s") % id)
            raise
        if 'cinder_volume' not in cinder_volume_data:
            cinder_volume_data = dict(cinder_volume=cinder_volume_data)
        return cinder_volume_data

    def _list_cinder_volumes(self, context, filters, params):
        """Get cinder_volumes, wrapping in exception if necessary."""
        try:
            return self.db_api.cinder_volume_list(context, filters=filters,
                                                  **params)
        except exception.NotFound:
            LOG.warn(_LW("Invalid marker. cinder_volume %(id)s could not be "
                         "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. cinder_volume could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warn(_LW("Access denied to cinder_volume %(id)s but returning "
                         "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. cinder_volume could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get cinder_volumes"))
            raise

    def cinder_volume_list(self, req):
        """Return a filtered list of public, non-deleted
        cinder_volumes in detail

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(cinder_volumes=[cinder_volume_list])

        Where cinder_volume_list is a sequence of mappings containing
        all service_disk model fields.
        """
        params = self._get_query_params(req)
        filters = params.pop('filters')
        cinder_volumes = self._list_cinder_volumes(
            req.context, filters, params)

        return dict(cinder_volumes=cinder_volumes)


def create_resource():
    """Images resource factory method."""
    deserializer = wsgi.JSONRequestDeserializer()
    serializer = wsgi.JSONResponseSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
