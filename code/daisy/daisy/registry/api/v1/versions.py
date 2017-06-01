# Copyright 2010-2011 OpenStack Foundation
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
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

SUPPORTED_FILTERS = ['name', 'status', 'version', 'disk_format',
                     'changes-since', 'protected', 'type']

SUPPORTED_SORT_KEYS = ('name', 'status', 'container_format', 'disk_format',
                       'size', 'id', 'created_at', 'updated_at')

SUPPORTED_SORT_DIRS = ('asc', 'desc')

SUPPORTED_PARAMS = ('limit', 'marker', 'sort_key', 'sort_dir')


class Controller(object):
    def __init__(self):
        self.db_api = daisy.db.get_api()

    def _get_versions(self, context, filters=None, **params):
        """Get versions, wrapping in exception if necessary."""
        try:
            return self.db_api.version_get_all(context,
                                               filters=filters,
                                               **params)
        except exception.NotFound:
            LOG.warning(_LW("Invalid marker. version %(id)s could not be "
                         "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. version could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warning(_LW("Access denied to version %(id)s but returning "
                         "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. version could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get versions"))
            raise

    def get_all_versions(self, req):
        """Return a filtered list of public, non-deleted versions in detail

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(versions=[version_list])

        Where version_list is a sequence of mappings containing
        all version model fields.
        """
        params = self._get_query_params(req)
        versions = self._get_versions(req.context, **params)
        for version in versions:
            filters = {'version_id': version['id']}
            version_patchs = []
            version_patchs = self.db_api.version_patch_get_all(req.context,
                                                               filters=filters)
            if version_patchs:
                version['version_patch'] = version_patchs
        return dict(version=versions)

    def _get_query_params(self, req):
        """Extract necessary query parameters from http request.

        :param req: the Request object coming from the wsgi layer
        :retval dictionary of filters to apply to list of versions
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
    def add_version(self, req, body):
        """Registers a new version with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the version

        :retval Returns the newly-created version information as a mapping,
                which will include the newly-created version's internal id
                in the 'id' field
        """

        version_data = body["version_metadata"]

        try:
            version_data = self.db_api.version_add(req.context, version_data)
            # version_data = dict(version=make_image_dict(version_data))
            msg = (_LI("Successfully created node %s") %
                   version_data["id"])
            LOG.info(msg)
            version_data = dict(version_metadata=version_data)
            return version_data
        except exception.Duplicate:
            msg = (_("version with identifier %s already exists!") %
                   version_data['name'])
            LOG.warning(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add version metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to create version %s"),
                          version_data['name'])
            raise

    @utils.mutating
    def delete_version(self, req, version_id):
        """Deletes an existing version with the registry.

        :param req: wsgi Request object
        :param id:  The opaque internal identifier for the image

        :retval Returns 200 if delete was successful, a fault if not. On
        success, the body contains the deleted image information as a mapping.
        """
        try:
            deleted_version = self.db_api.version_destroy(
                req.context, version_id)
            msg = _LI("Successfully deleted version %(version_id)s") % {
                'version_id': version_id}
            LOG.info(msg)
            filters = {'version_id': version_id}
            version_patchs = self.db_api.version_patch_get_all(req.context,
                                                               filters=filters)
            for version_patch in version_patchs:
                self.db_api.version_patch_destroy(
                    req.context, version_patch['id'])
            return dict(version=deleted_version)
        except exception.ForbiddenPublicImage:
            msg = _LI("Delete denied for public version %(version_id)s") % {
                'version_id': version_id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to version %(version_id)s but returning"
                      " 'not found'") % {'version_id': version_id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except exception.NotFound:
            msg = _LI("version %(version_id)s not found") % {
                'version_id': version_id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to delete version %s") % version_id)
            raise

    @utils.mutating
    def get_version(self, req, version_id):
        """Return data about the given version id."""
        try:
            version_data = self.db_api.version_get(req.context, version_id)
            msg = "Successfully retrieved version %(id)s" % {'id': version_id}
            LOG.debug(msg)
            filters = {'version_id': version_id}
            version_patchs = []
            version_patchs = self.db_api.version_patch_get_all(req.context,
                                                               filters=filters)
            if version_patchs:
                version_data['version_patch'] = version_patchs
        except exception.NotFound:
            msg = _LI("version %(id)s not found") % {'id': version_id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to version %(id)s but returning"
                      " 'not found'") % {'id': version_id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show version %s") % version_id)
            raise
        #if 'version' not in version_data:
        version_data = dict(version=version_data)
        return version_data

    @utils.mutating
    def update_version(self, req, version_id, body):
        """Updates an existing version with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the image
        :param id:  The opaque internal identifier for the image

        :retval Returns the updated image information as a mapping,
        """
        version_data = body['version_metadata']
        try:
            updated_version = self.db_api.version_update(
                req.context, version_id, version_data)

            msg = _LI("Updating metadata for version %(version_id)s") % {
                'version_id': version_id}
            LOG.info(msg)
            version_data = dict(version_metadata=updated_version)
            return version_data
        except exception.Invalid as e:
            msg = (_("Failed to update version metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("version %(version_id)s not found") % {
                'version_id': version_id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='version not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public version %(version_id)s") % {
                'version_id': version_id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden as e:
            LOG.info(e)
            raise exc.HTTPForbidden(e)
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='version operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except Exception:
            LOG.exception(_LE("Unable to update version %s") % version_id)
            raise


def _limit_locations(image):
    locations = image.pop('locations', [])
    image['location_data'] = locations
    image['location'] = None
    for loc in locations:
        if loc['status'] == 'active':
            image['location'] = loc['url']
            break


def make_image_dict(image):
    """Create a dict representation of an image which we can use to
    serialize the image.
    """

    def _fetch_attrs(d, attrs):
        return dict([(a, d[a]) for a in attrs
                     if a in d.keys()])

    # TODO(sirp): should this be a dict, or a list of dicts?
    # A plain dict is more convenient, but list of dicts would provide
    # access to created_at, etc
    properties = dict((p['name'], p['value'])
                      for p in image['properties'] if not p['deleted'])

    image_dict = _fetch_attrs(image, daisy.db.IMAGE_ATTRS)
    image_dict['properties'] = properties
    _limit_locations(image_dict)

    return image_dict


def create_resource():
    """Images resource factory method."""
    deserializer = wsgi.JSONRequestDeserializer()
    serializer = wsgi.JSONResponseSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
