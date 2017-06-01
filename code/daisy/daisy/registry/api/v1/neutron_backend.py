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
DISPLAY_FIELDS_IN_INDEX = ['id', 'role_id', 'user_name', 'user_pwd',
                           'controller_ip', 'neutron_backends_type',
                           'sdn_type', 'port']
SUPPORTED_FILTERS = ['role_id', 'user_name', 'user_pwd',
                     'controller_ip', 'neutron_backends_type',
                     'sdn_type', 'port']
SUPPORTED_SORT_KEYS = ('id', 'role_id', 'user_name', 'user_pwd',
                       'controller_ip', 'neutron_backends_type',
                       'sdn_type', 'port', 'created_at', 'updated_at')
SUPPORTED_SORT_DIRS = ('asc', 'desc')
SUPPORTED_PARAMS = ('limit', 'marker', 'sort_key', 'sort_dir', 'name',
                    'description')


class Controller(object):

    def __init__(self):
        self.db_api = daisy.db.get_api()

    def _get_query_params(self, req):
        """Extract necessary query parameters from http request.

        :param req: the Request object coming from the wsgi layer
        :retval dictionary of filters to apply to list of templates
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
    def neutron_backend_add(self, req, body):
        """Registers a new neutron_backend with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the templatae

        :retval Returns the newly-created template information as a mapping,
                which will include the newly-created template's internal id
                in the 'id' field
        """
        neutron_backend_data = body["neutron_backend"]
        id = neutron_backend_data.get('id')

        if id and not utils.is_uuid_like(id):
            msg = _LI("Rejecting neutron_backend creation "
                      "request for invalid neutron_backend "
                      "id '%(bad_id)s'") % {'bad_id': id}
            LOG.info(msg)
            msg = _("Invalid neutron_backend id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            neutron_backend_data = self.db_api.neutron_backend_add(
                req.context, neutron_backend_data)
            msg = (_LI("Successfully created neutron_backend %s") %
                   neutron_backend_data["id"])
            LOG.info(msg)
            if 'neutron_backend' not in neutron_backend_data:
                neutron_backend_data = dict(
                    neutron_backend=neutron_backend_data)
            return neutron_backend_data
        except exception.Duplicate:
            msg = _("neutron_backend with identifier %s already exists!") % id
            LOG.warning(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add neutron_backend metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to create neutron_backend %s"), id)
            raise

    @utils.mutating
    def neutron_backend_update(self, req, id, body):
        """Registers a new neutron_backend with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the template

        :retval Returns the newly-created template information as a mapping,
                which will include the newly-created template's internal id
                in the 'id' field
        """
        neutron_backend_data = body["neutron_backend"]
        if id and not utils.is_uuid_like(id):
            msg = _LI("Rejecting cluster neutron_backend "
                      "creation request for invalid "
                      "neutron_backend id '%(bad_id)s'") % {'bad_id': id}
            LOG.info(msg)
            msg = _("Invalid neutron_backend id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            neutron_backend_data = self.db_api.neutron_backend_update(
                req.context, id, neutron_backend_data)
            msg = (_LI("Successfully updated neutron_backend %s") %
                   neutron_backend_data["id"])
            LOG.info(msg)
            if 'neutron_backend' not in neutron_backend_data:
                neutron_backend_data = dict(
                    neutron_backend=neutron_backend_data)
            return neutron_backend_data
        except exception.Duplicate:
            msg = _("neutron_backend with identifier %s already exists!") % id
            LOG.warning(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to update neutron_backend "
                     "metadata.Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to update neutron_backend %s"), id)
            raise

    @utils.mutating
    def neutron_backend_delete(self, req, id):
        """Registers a new neutron_backend with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the template

        :retval Returns the newly-created template information as a mapping,
                which will include the newly-created template's internal id
                in the 'id' field
        """
        if id and not utils.is_uuid_like(id):
            msg = _LI("Rejecting neutron_backend delete "
                      "request for invalid neutron_backend "
                      "id '%(bad_id)s'") % {'bad_id': id}
            LOG.info(msg)
            msg = _("Invalid neutron_backend id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            neutron_backend_data = self.db_api.neutron_backend_destroy(
                req.context, id)
            msg = (_LI("Successfully deleted neutron_backend %s") % id)
            LOG.info(msg)
            if 'neutron_backend' not in neutron_backend_data:
                neutron_backend_data = dict(
                    neutron_backend=neutron_backend_data)
            return neutron_backend_data
        except exception.Invalid as e:
            msg = (_("Failed to delete neutron_backend metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to delete neutron_backend %s"), id)
            raise

    def _list_neutron_backends(self, context, filters, params):
        """Get neutron_backends, wrapping in exception if necessary."""
        try:
            return self.db_api.neutron_backend_list(context, filters=filters,
                                                    **params)
        except exception.NotFound:
            LOG.warning(_LW("Invalid marker. neutron_backend %(id)s not"
                            "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. neutron_backend could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warning(_LW("Access denied to neutron_backend "
                            "%(id)s but returning "
                            "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. neutron_backend could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get neutron_backends"))
            raise

    def neutron_backend_list(self, req):
        """Return a filtered list of non-deleted neutron_backends in detail

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(neutron_backends=[neutron_backend_list])

        Where neutron_backend_list is a sequence of mappings containing
        all neutron_backend model fields.
        """
        params = self._get_query_params(req)
        filters = params.pop('filters')
        neutron_backends = self._list_neutron_backends(
            req.context, filters, params)
        return dict(neutron_backends=neutron_backends)

    @utils.mutating
    def neutron_backend_detail(self, req, id):
        """Registers a new neutron_backend with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the template

        :retval Returns the newly-created template information as a mapping,
                which will include the newly-created template's internal id
                in the 'id' field
        """
        if id and not utils.is_uuid_like(id):
            msg = _LI("Rejecting neutron_backend delete "
                      "request for invalid neutron_backend "
                      "id '%(bad_id)s'") % {'bad_id': id}
            LOG.info(msg)
            msg = _("Invalid neutron_backend id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            neutron_backend_data = self.db_api.neutron_backend_detail(
                req.context, id)
            msg = (_LI("Successfully get neutron_backend information:%s") % id)
            LOG.info(msg)
            if 'neutron_backend' not in neutron_backend_data:
                neutron_backend_data = dict(
                    neutron_backend=neutron_backend_data)
            return neutron_backend_data
        except exception.Invalid as e:
            msg = (_("Failed to get neutron_backend metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to get neutron_backend %s"), id)
            raise


def create_resource():
    """neutron_backends resource factory method."""
    deserializer = wsgi.JSONRequestDeserializer()
    serializer = wsgi.JSONResponseSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
