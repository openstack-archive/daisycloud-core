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

SUPPORTED_FILTERS = ['name', 'status', 'container_format', 'disk_format',
                     'min_ram', 'min_disk', 'size_min', 'size_max',
                     'changes-since', 'protected', 'type', 'cluster_id']

SUPPORTED_SORT_KEYS = ('name', 'status', 'container_format', 'disk_format',
                       'size', 'id', 'created_at', 'updated_at')

SUPPORTED_SORT_DIRS = ('asc', 'desc')

SUPPORTED_PARAMS = ('limit', 'marker', 'sort_key', 'sort_dir')


class Controller(object):

    def __init__(self):
        self.db_api = daisy.db.get_api()

    def _get_networks(self, context, cluster_id, filters=None, **params):
        """Get networks, wrapping in exception if necessary."""
        try:
            return self.db_api.network_get_all(context, cluster_id,
                                               filters=filters,
                                               **params)
        except exception.NotFound:
            LOG.warn(_LW("Invalid marker. Network %(id)s could not be "
                         "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. Network could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warn(_LW("Access denied to network %(id)s but returning "
                         "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. Network could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get networks"))
            raise

    def update_phyname_of_network(self, req, body):
        try:
            self.db_api.update_phyname_of_network(req.context, body)
            return {}
        except exception.NotFound:
            raise exc.HTTPServerError(
                explanation="Update database for phyname of network "
                            "table failed!")

    def get_all_networks(self, req):
        params = self._get_query_params(req)
        try:
            networks = self.db_api.network_get_all(req.context, **params)
        except Exception:
            raise exc.HTTPServerError(explanation="Get all networks failed")

        return networks

    def detail_network(self, req, id):
        """Return a filtered list of public, non-deleted networks in detail

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(networks=[network_list])

        Where network_list is a sequence of mappings containing
        all network model fields.
        """
        params = self._get_query_params(req)
        networks = self._get_networks(req.context, id, **params)

        return dict(networks=networks)

    def _get_query_params(self, req):
        """Extract necessary query parameters from http request.

        :param req: the Request object coming from the wsgi layer
        :retval dictionary of filters to apply to list of networks
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
    def add_network(self, req, body):
        """Registers a new network with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the network

        :retval Returns the newly-created network information as a mapping,
                which will include the newly-created network's internal id
                in the 'id' field
        """

        network_data = body["network"]

        network_id = network_data.get('id')

        # role = network_data.get('role')
        # add network_id and role
        # if role
        # self.db_api.get_role(req.context,role)

        if network_id and not utils.is_uuid_like(network_id):
            msg = _LI("Rejecting network creation request for invalid network "
                      "id '%(bad_id)s'") % {'bad_id': network_id}
            LOG.info(msg)
            msg = _("Invalid network id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            network_data = self.db_api.network_add(req.context, network_data)
            # network_data = dict(network=make_image_dict(network_data))
            msg = (_LI("Successfully created node %s") %
                   network_data["id"])
            LOG.info(msg)
            if 'network' not in network_data:
                network_data = dict(network=network_data)
            return network_data
        except exception.Duplicate:
            msg = _("node with identifier %s already exists!") % network_id
            LOG.warn(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add node metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to create node %s"), network_id)
            raise

    @utils.mutating
    def delete_network(self, req, network_id):
        """Deletes an existing network with the registry.

        :param req: wsgi Request object
        :param id:  The opaque internal identifier for the image

        :retval Returns 200 if delete was successful, a fault if not. On
        success, the body contains the deleted image information as a mapping.
        """
        try:
            deleted_network = self.db_api.network_destroy(
                req.context, network_id)
            msg = _LI("Successfully deleted network %(network_id)s") % {
                'network_id': network_id}
            LOG.info(msg)
            return dict(network=deleted_network)
        except exception.ForbiddenPublicImage:
            msg = _LI("Delete denied for public network %(network_id)s") % {
                'network_id': network_id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to network %(id)s but returning"
                      " 'not found'") % {'network_id': network_id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except exception.NotFound:
            msg = _LI("Network %(network_id)s not found") % {
                'network_id': network_id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to delete network %s") % id)
            raise

    @utils.mutating
    def get_network(self, req, id):
        """Return data about the given network id."""
        try:
            network_data = self.db_api.network_get(req.context, id)
            msg = "Successfully retrieved network %(id)s" % {'id': id}
            LOG.debug(msg)
        except exception.NotFound:
            msg = _LI("Network %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to network %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show network %s") % id)
            raise
        if 'network' not in network_data:
            network_data = dict(network=network_data)
        return network_data

    @utils.mutating
    def update_network(self, req, network_id, body):
        """Updates an existing network with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the image
        :param id:  The opaque internal identifier for the image

        :retval Returns the updated image information as a mapping,
        """
        network_data = body['network']
        try:
            updated_network = self.db_api.network_update(
                req.context, network_id, network_data)

            msg = _LI("Updating metadata for network %(network_id)s") % {
                'network_id': network_id}
            LOG.info(msg)
            if 'network' not in updated_network:
                network_data = dict(network=updated_network)
            return network_data
        except exception.Invalid as e:
            msg = (_("Failed to update network metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("Network %(network_id)s not found") % {
                'network_id': network_id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='Network not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public network %(network_id)s") % {
                'network_id': network_id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden as e:
            LOG.info(e)
            raise exc.HTTPForbidden(e)
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='Network operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except Exception:
            LOG.exception(_LE("Unable to update network %s") % network_id)
            raise

    @utils.mutating
    def update_cluster(self, req, id, body):
        """Updates an existing cluster with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the image
        :param id:  The opaque internal identifier for the image

        :retval Returns the updated image information as a mapping,
        """
        cluster_data = body['cluster']
        try:
            updated_cluster = self.db_api.cluster_update(
                req.context, id, cluster_data)

            msg = _LI("Updating metadata for cluster %(id)s") % {'id': id}
            LOG.info(msg)
            if 'cluster' not in updated_cluster:
                cluster_data = dict(cluster=updated_cluster)
            return cluster_data
        except exception.Invalid as e:
            msg = (_("Failed to update cluster metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("cluster %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='cluster not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public cluster %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to cluster %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='cluster not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='cluster operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except Exception:
            LOG.exception(_LE("Unable to update cluster %s") % id)
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
