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

DISPLAY_FIELDS_IN_INDEX = ['id', 'name', 'section_name', 'ch_desc',
                           'en_desc', 'data_type', 'default_value', 'length',
                           'suggested_range', 'config_file',
                           'data_check_script']

SUPPORTED_FILTERS = ['id', 'name', 'func_id']

SUPPORTED_SORT_KEYS = ('id', 'name', 'created_at', 'updated_at')

SUPPORTED_SORT_DIRS = ('asc', 'desc')

SUPPORTED_PARAMS = ('limit', 'marker', 'sort_key', 'sort_dir')


class Controller(object):
    def __init__(self):
        self.db_api = daisy.db.get_api()

    def _list_template_config(self, context, filters=None, **params):
        """Get template configs, wrapping in exception if necessary."""
        try:
            return self.db_api.template_config_get_all(context,
                                                       filters=filters,
                                                       **params)
        except exception.NotFound:
            LOG.warn(_LW("Invalid marker. template config %(id)s could not be "
                         "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. template config could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warn(_LW("Access denied to template config %(id)s but "
                         "returning 'not found'") %
                     {'id': params.get('marker')})
            msg = _("Invalid marker. template config could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get template configs"))
            raise

    def list_template_config(self, req):
        """Return a filtered list of public, non-deleted template configs

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(template_configs=[template_config_list])

        Where template_config_list is a sequence of mappings containing
        all template config model fields.
        """
        params = self._get_query_params(req)
        template_configs = self._list_template_config(req.context, **params)
        func_id = params.get('filters', {}).get('func_id', None)
        if template_configs and func_id:
            func_configs = self.db_api._template_func_configs_get_by_func_id(
                req.context,
                func_id)
            if func_configs:
                config_ids = \
                    [func_config["config_id"] for func_config in func_configs]
                template_configs = \
                    [template_config for template_config in template_configs
                     if template_config["id"] in config_ids]
        return dict(template_configs=template_configs)

    def _get_query_params(self, req):
        """Extract necessary query parameters from http request.

        :param req: the Request object coming from the wsgi layer
        :retval dictionary of filters to apply to list of template configs
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
    def import_template_config(self, req, body):
        """Import template configs with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the template config

        :retval Returns the newly-created template function
                information as a mapping,
                which will include the newly-created template
                function's internal id
                in the 'id' field
        """

        template_config_data = body["template_config_metadata"]

        try:
            template_config_data = self.db_api.template_config_import(
                req.context, template_config_data)
            msg = (_LI("Successfully import template function %s") %
                   template_config_data)
            LOG.info(msg)
            template_config_data = dict(
                template_config_metadata=template_config_data)
            return template_config_data
        except exception.Duplicate:
            msg = (_("template function with identifier %s already exists!") %
                   template_config_data)
            LOG.warn(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add template function metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to create template function %s"),
                          template_config_data)
            raise

    @utils.mutating
    def delete_template_config(self, req, template_config_id):
        """Deletes an existing template config with the registry.

        :param req: wsgi Request object
        :param id:  The opaque internal identifier for the image

        :retval Returns 200 if delete was successful, a fault if not. On
        success, the body contains the deleted image information as a mapping.
        """
        try:
            template_config = self.db_api.template_config_destroy(
                req.context, template_config_id)
            msg = _LI("Successfully deleted template config %(id)s") % {
                'id': template_config_id}
            LOG.info(msg)
            return dict(template_config=template_config)
        except exception.ForbiddenPublicImage:
            msg = _LI("Delete denied for public template config %(id)s") % {
                'id': template_config_id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to template config %(id)s but returning"
                      " 'not found'") % {'id': template_config_id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except exception.NotFound:
            msg = _LI("template config %(id)s not found") % {
                'id': template_config_id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to delete template_config_id %s")
                          % template_config_id)
            raise

    @utils.mutating
    def get_template_config(self, req, template_config_id):
        """Return data about the given template config id."""
        try:
            template_config_data = self.db_api.template_config_get(
                req.context, template_config_id)
            msg = "Successfully retrieved template config %(id)s" \
                  % {'id': template_config_id}
            LOG.debug(msg)
        except exception.NotFound:
            msg = _LI("template_config %(id)s not found") \
                % {'id': template_config_id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to template_config %(id)s but returning"
                      " 'not found'") % {'id': template_config_id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show template_config %s")
                          % template_config_id)
            raise
        template_config = dict(template_config=template_config_data)
        return template_config


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
