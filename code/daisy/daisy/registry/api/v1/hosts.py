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

import sys
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

reload(sys)
sys.setdefaultencoding('utf-8')

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

CONF = cfg.CONF

DISPLAY_FIELDS_IN_INDEX = ['id', 'name', 'size',
                           'disk_format', 'container_format',
                           'checksum']

SUPPORTED_FILTERS = ['name', 'status', 'id', 'cluster_id', 'func_id',
                     'auto_scale', 'container_format', 'disk_format',

                     'changes-since', 'protected']

SUPPORTED_SORT_KEYS = ('name', 'status', 'cluster_id',
                       'container_format', 'disk_format',
                       'size', 'id', 'created_at', 'updated_at')

SUPPORTED_SORT_DIRS = ('asc', 'desc')

SUPPORTED_PARAMS = ('limit', 'marker', 'sort_key', 'sort_dir', 'cluster_id')


class Controller(object):

    def __init__(self):
        self.db_api = daisy.db.get_api()

    def _get_hosts(self, context, filters, **params):
        """Get hosts, wrapping in exception if necessary."""
        try:
            return self.db_api.host_get_all(context, filters=filters,
                                            **params)
        except exception.NotFound:
            LOG.warning(_LW("Invalid marker. Host %(id)s could not be "
                            "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. Host could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warning(_LW("Access denied to host %(id)s but returning "
                            "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. Host could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get hosts"))
            raise

    def _get_clusters(self, context, filters, **params):
        """Get clusters, wrapping in exception if necessary."""
        try:
            return self.db_api.cluster_get_all(context, filters=filters,
                                               **params)
        except exception.NotFound:
            LOG.warning(_LW("Invalid marker. Cluster %(id)s could not be "
                            "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. Cluster could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warning(_LW("Access denied to cluster %(id)s but returning "
                            "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. Cluster could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get clusters"))
            raise

    def detail_host(self, req):
        """Return a filtered list of public, non-deleted hosts in detail

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(nodes=[host_list])

        Where host_list is a sequence of mappings containing
        all host model fields.
        """
        params = self._get_query_params(req)

        nodes = self._get_hosts(req.context, **params)
        nodes.sort(key=lambda x: x['name'])

        for node in nodes:
            node = self._host_additional_info(req, node)
        return dict(nodes=nodes)

    def _get_query_params(self, req):
        """Extract necessary query parameters from http request.

        :param req: the Request object coming from the wsgi layer
        :retval dictionary of filters to apply to list of hosts
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
    def add_host(self, req, body):
        """Registers a new host with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the host

        :retval Returns the newly-created host information as a mapping,
                which will include the newly-created host's internal id
                in the 'id' field
        """

        host_data = body["host"]

        host_id = host_data.get('id')

        if host_id and not utils.is_uuid_like(host_id):
            msg = _LI("Rejecting host creation request for invalid host "
                      "id '%(bad_id)s'") % {'bad_id': host_id}
            LOG.info(msg)
            msg = _("Invalid host id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            if host_id is None:
                host_data = self.db_api.host_add(req.context, host_data)
            else:
                orig_config_set_id = None
                if 'config_set_id' in host_data:
                    orig_host_data = self.db_api.host_get(req.context, host_id)
                    orig_config_set_id = orig_host_data.get('config_set_id')

                host_data = self.db_api.host_update(
                    req.context, host_id, host_data)

                if orig_config_set_id:
                    try:
                        self.db_api.config_set_destroy(req.context,
                                                       orig_config_set_id)
                    except exception.NotFound as e:
                        msg = _LI("config_set %s has been deleted") \
                            % orig_config_set_id
                        LOG.info(msg)
                    except exception.Forbidden:
                        msg = _LE("Forbidden to delete config_set %s") \
                            % orig_config_set_id
                        LOG.error(msg)
                        return exc.HTTPForbidden(msg)
                    except Exception:
                        msg = _LE("Unable to delete config_set %s") \
                            % orig_config_set_id
                        LOG.error(msg)
                        return exc.HTTPBadRequest(msg)

            # host_data = dict(host=make_image_dict(host_data))
            msg = (_LI("Successfully created node %s") %
                   host_data["id"])
            LOG.info(msg)
            if 'host' not in host_data:
                host_data = dict(host=host_data)
            return host_data
        except exception.Duplicate:
            msg = _("node with identifier %s already exists!") % host_id
            LOG.warning(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add node metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.Forbidden as e:
            msg = (_("%s") % utils.exception_to_str(e))
            LOG.error(msg)
            raise exc.HTTPForbidden(msg)
        except Exception:
            LOG.exception(_LE("Unable to create node %s"), host_id)
            raise

    @utils.mutating
    def delete_host(self, req, id):
        """Deletes an existing host with the registry.

        :param req: wsgi Request object
        :param id:  The opaque internal identifier for the image

        :retval Returns 200 if delete was successful, a fault if not. On
        success, the body contains the deleted image information as a mapping.
        """
        try:
            host_interface = self.db_api.get_host_interface(req.context, id)
            deleted_host = self.db_api.host_destroy(req.context, id)
            msg = _LI("Successfully deleted host %(id)s") % {'id': id}
            LOG.info(msg)
            members = self.db_api.cluster_host_member_find(req.context,
                                                           host_id=id)
            if members:
                for member in members:
                    self.db_api.cluster_host_member_delete(
                        req.context, member['id'])

            self.db_api.role_host_member_delete(req.context, host_id=id)
            orig_config_set_id = deleted_host.config_set_id
            if orig_config_set_id:
                try:
                    self.db_api.config_set_destroy(req.context,
                                                   orig_config_set_id)
                except exception.NotFound as e:
                    msg = _LI("config_set %s has been deleted") \
                        % orig_config_set_id
                    LOG.info(msg)
                except exception.Forbidden:
                    msg = _LE("Forbidden to delete config_set %s") \
                        % orig_config_set_id
                    LOG.error(msg)
                    return exc.HTTPForbidden(msg)
                except Exception:
                    msg = _LE("Unable to delete config_set %s") \
                        % orig_config_set_id
                    LOG.error(msg)
                    return exc.HTTPBadRequest(msg)

            # TODO delete discovered host by mac
            return dict(host=deleted_host)
        except exception.ForbiddenPublicImage:
            msg = _LI("Delete denied for public host %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to host %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            return exc.HTTPForbidden()
        except exception.NotFound:
            msg = _LI("Host %(id)s not found") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to delete host %s") % id)
            raise

    def _host_additional_info(self, req, host_data):
        host_id = host_data.get("id")
        host_status = host_data.get("status")
        if 'host' not in host_data:
            host_data = dict(host=host_data)
        host_interface = self.db_api.get_host_interface(req.context, host_id)
        if host_interface:
            host_data['host']['interfaces'] = host_interface
        role_name = []
        backends = set()
        if host_status == "with-role":
            host_roles = self.db_api.role_host_member_get(
                req.context, None, host_id)
            for host_role in host_roles:
                role_info = self.db_api.role_get(
                    req.context, host_role.role_id)
                role_name.append(role_info['name'])
                backends.add(role_info.get('deployment_backend'))
        if role_name:
            host_data['host']['role'] = role_name
            host_data['host']['deployment_backends'] = backends
        host_cluster = self.db_api.cluster_host_member_find(
            req.context, None, host_id)
        if host_cluster:
            cluster_info = self.db_api.cluster_get(
                req.context, host_cluster[0]['cluster_id'])
            cluster_name = cluster_info['name']
        else:
            cluster_name = None
        if cluster_name:
            host_data['host']['cluster'] = cluster_name
        return host_data

    @utils.mutating
    def get_host(self, req, id):
        """Return data about the given node id."""
        try:
            host_data = self.db_api.host_get(req.context, id)
            msg = "Successfully retrieved host %(id)s" % {'id': id}
            LOG.debug(msg)
        except exception.NotFound:
            msg = _LI("Host %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to host %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show host %s") % id)
            raise
        host = self._host_additional_info(req, host_data)
        return host

        # Currently not used

        #host_interface = self.db_api.get_host_interface(req.context, id)

        #role_name = []
        #backends = set()
        #if host_data.status == "with-role":
        #    host_roles = self.db_api.role_host_member_get(
        #        req.context, None, id)
        #    for host_role in host_roles:
        #        role_info = self.db_api.role_get(
        #            req.context, host_role.role_id)
        #        role_name.append(role_info['name'])
        #        backends.add(role_info.get('deployment_backend'))
        #host_cluster = self.db_api.cluster_host_member_find(
        #    req.context, None, id)
        #if host_cluster:
        #    cluster_info = self.db_api.cluster_get(
        #        req.context, host_cluster[0]['cluster_id'])
        #    cluster_name = cluster_info['name']
        #else:
        #    cluster_name = None

        #if 'host' not in host_data:
        #    host_data = dict(host=host_data)
        #if host_interface:
        #    host_data['host']['interfaces'] = host_interface
        #if role_name:
        #    host_data['host']['role'] = role_name
        #    host_data['host']['deployment_backends'] = backends
        #if cluster_name:
        #    host_data['host']['cluster'] = cluster_name
        #return host_data

    @utils.mutating
    def get_host_interface(self, req, body):
        orig_interfaces = list(body['interfaces'])
        for orig_interface in orig_interfaces:
            host_interface = self.db_api.get_host_interface_mac(
                req.context, orig_interface['mac'])
        return host_interface

    @utils.mutating
    def get_host_interface_by_host_id(self, req, id):
        host_interface = self.db_api.get_host_interface(req.context, id)
        return host_interface

    @utils.mutating
    def get_host_roles_by_host_id(self, req, host_id):
        try:
            roles = self.db_api.role_host_member_get(req.context, None,
                                                     host_id)
        except exception.NotFound:
            msg = _LI("Roles of host %(id)s not found") % {'id': host_id}
            LOG.error(msg)
            raise exc.HTTPNotFound(msg)
        except Exception:
            msg = _LE("Unable to get role of host %s") % host_id
            LOG.error(msg)
            raise exc.HTTPBadRequest(msg)
        return roles

    @utils.mutating
    def get_all_host_interfaces(self, req, body, **params):
        """Return all_host_interfaces about the given filter."""
        filters = body['filters']
        try:
            host_interfaces = self.db_api.host_interfaces_get_all(
                req.context, filters)
            return host_interfaces
        except exception.NotFound:
            LOG.warning(_LW("Invalid marker. template %(id)s could not be "
                            "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. template could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warning(_LW("Access denied to template %(id)s but returning "
                            "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. template could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to list template"))
            raise
        return

    @utils.mutating
    def get_assigned_network(self, req, interface_id, network_id):
        try:
            host_assigned_network = self.db_api.get_assigned_network(
                req.context,
                interface_id, network_id)
        except exception.NotFound:
            LOG.warning(_LW("Invalid marker.Assigned_network with if %("
                            "interface_id)s and network %(network_id)s"
                            " could not be found.") % {
                'interface_id': interface_id, 'network_id': network_id})
            msg = _("Invalid marker.  Assigned_network could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warning(_LW("Access denied for assigned_network with if %("
                            "interface_id)s "
                            "and network %(network_id)s") % {
                'interface_id': interface_id, 'network_id': network_id})
            msg = _("Invalid marker. Assigned_network denied to get.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get assigned_network"))
            raise
        return host_assigned_network

    @utils.mutating
    def add_discover_host(self, req, body):
        """Registers a new host with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the host

        :retval Returns the newly-created host information as a mapping,
                which will include the newly-created host's internal id
                in the 'id' field
        """

        discover_host_data = body["discover_host"]
        discover_host_id = discover_host_data.get('id')

        if discover_host_id and not utils.is_uuid_like(discover_host_id):
            msg = _LI("Rejecting host creation request for invalid host "
                      "id '%(bad_id)s'") % {'bad_id': discover_host_id}
            LOG.info(msg)
            msg = _("Invalid host id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            if discover_host_id is None:
                discover_host_data = self.db_api.discover_host_add(
                    req.context, discover_host_data)
            else:
                discover_host_data = self.db_api.discover_host_update(
                    req.context, discover_host_id, discover_host_data)
            # host_data = dict(host=make_image_dict(host_data))
            msg = (_LI("Successfully created node %s") %
                   discover_host_data["id"])
            LOG.info(msg)
            if 'discover_host' not in discover_host_data:
                discover_host_data = dict(discover_host=discover_host_data)
            return discover_host_data
        except exception.Duplicate:
            msg = _("node with identifier %s already exists!") % \
                discover_host_id
            LOG.warning(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add node metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to create node %s"), discover_host_id)
            raise

    @utils.mutating
    def delete_discover_host(self, req, id):
        """Deletes an existing discover host with the registry.

        :param req: wsgi Request object
        :param id:  The opaque internal identifier for the image

        :retval Returns 200 if delete was successful, a fault if not. On
        success, the body contains the deleted image information as a mapping.
        """
        try:
            deleted_host = self.db_api.discover_host_destroy(req.context, id)
            msg = _LI("Successfully deleted host %(id)s") % {'id': id}
            return dict(discover_host=deleted_host)
        except exception.Forbidden:
            msg = _LI("Access denied to host %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except exception.NotFound:
            msg = _LI("Host %(id)s not found") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to delete host %s") % id)
            raise

    def detail_discover_host(self, req):
        """Return a filtered list of public, non-deleted hosts in detail

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(nodes=[host_list])

        Where host_list is a sequence of mappings containing
        all host model fields.
        """
        params = self._get_query_params(req)
        try:
            nodes = self.db_api.discover_host_get_all(req.context,
                                                      **params)
        except exception.NotFound:
            LOG.warning(_LW("Invalid marker. Host %(id)s could not be "
                            "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. Host could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warning(_LW("Access denied to host %(id)s but returning "
                            "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. Host could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get hosts"))
            raise

        return dict(nodes=nodes)

    @utils.mutating
    def update_discover_host(self, req, id, body):
        '''
        '''
        discover_host_data = body["discover_host"]
        if id and not utils.is_uuid_like(id):
            msg = _LI("Rejecting host creation request for invalid host "
                      "id '%(bad_id)s'") % {'bad_id': id}
            LOG.info(msg)
            msg = _("Invalid host id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            updated_host = self.db_api.discover_host_update(
                req.context, id, discover_host_data)
            msg = _LI("Updating metadata for host %(id)s") % {'id': id}
            LOG.info(msg)
            if 'discover_host' not in updated_host:
                host_data = dict(discover_host=updated_host)
            return host_data
        except exception.Invalid as e:
            msg = (_("Failed to update host metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("Host %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='Host not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public host %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            raise
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='Host operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except Exception:
            LOG.exception(_LE("Unable to update host %s") % id)
            raise

    def get_discover_host(self, req, discover_host_id):
        '''
        '''
        if discover_host_id and not utils.is_uuid_like(discover_host_id):
            msg = _LI("Rejecting host creation request for invalid host "
                      "id '%(bad_id)s'") % {'bad_id': discover_host_id}
            LOG.info(msg)
            msg = _("Invalid host id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            host_detail_info = self.db_api.get_discover_host_detail(
                req.context, discover_host_id)
            msg = _LI("Updating metadata for host %(id)s") % {
                'id': discover_host_id}
            LOG.info(msg)
            if 'discover_host' not in host_detail_info:
                host_data = dict(discover_host=host_detail_info)
            LOG.info("host_data: %s" % host_data)
            return host_data
        except exception.Invalid as e:
            msg = (_("Failed to update host metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("Host %(id)s not found") % {'id': discover_host_id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='Host not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public host %(id)s") % {
                'id': discover_host_id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            raise
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='Host operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except Exception:
            LOG.exception(_LE("Unable to update host %s") % discover_host_id)
            raise

    @utils.mutating
    def add_cluster(self, req, body):
        """Registers a new host with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the host

        :retval Returns the newly-created host information as a mapping,
                which will include the newly-created host's internal id
                in the 'id' field
        """

        cluster_data = body["cluster"]

        cluster_id = cluster_data.get('id')

        if cluster_id and not utils.is_uuid_like(cluster_id):
            msg = _LI("Rejecting host creation request for invalid cluster "
                      "id '%(bad_id)s'") % {'bad_id': cluster_id}
            LOG.info(msg)
            msg = _("Invalid cluster id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            cluster_data = self.db_api.cluster_add(req.context, cluster_data)
            msg = (_LI("Successfully created cluster %s") %
                   cluster_data["id"])
            LOG.info(msg)
            if 'cluster' not in cluster_data:
                cluster_data = dict(cluster=cluster_data)
            return cluster_data
        except exception.Duplicate:
            msg = _("cluster with identifier %s already exists!") % cluster_id
            LOG.warning(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add cluster metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to create cluster %s"), cluster_id)
            raise

    @utils.mutating
    def delete_cluster(self, req, id):
        """Deletes an existing cluster with the registry.

        :param req: wsgi Request object
        :param id:  The opaque internal identifier for the image

        :retval Returns 200 if delete was successful, a fault if not. On
        success, the body contains the deleted image information as a mapping.
        """
        try:
            deleted_cluster = self.db_api.cluster_destroy(req.context, id)
            msg = _LI("Successfully deleted cluster %(id)s") % {'id': id}
            LOG.info(msg)
            # Look up an existing membership
            members = self.db_api.cluster_host_member_find(req.context,
                                                           cluster_id=id)
            if members:
                for member in members:
                    self.db_api.cluster_host_member_delete(
                        req.context, member['id'])

            return dict(cluster=deleted_cluster)
        except exception.ForbiddenPublicImage:
            msg = _LI("Delete denied for public cluster %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to cluster %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except exception.NotFound:
            msg = _LI("cluster %(id)s not found") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to delete cluster %s") % id)
            raise

    @utils.mutating
    def get_cluster(self, req, id):
        """Return data about the given cluster id."""
        try:
            cluster_data = self.db_api.cluster_get(req.context, id)
            networking_parameters = {}
            networking_parameters['gre_id_range'] = [
                cluster_data['gre_id_start'], cluster_data['gre_id_end']]
            networking_parameters['vlan_range'] = [
                cluster_data['vlan_start'], cluster_data['vlan_end']]
            networking_parameters['vni_range'] = [
                cluster_data['vni_start'], cluster_data['vni_end']]
            networking_parameters['net_l23_provider'] = cluster_data[
                'net_l23_provider']
            networking_parameters['base_mac'] = cluster_data['base_mac']
            networking_parameters['segmentation_type'] = cluster_data[
                'segmentation_type']
            networking_parameters['public_vip'] = cluster_data['public_vip']
            cluster_data['networking_parameters'] = networking_parameters
        except exception.NotFound:
            msg = _LI("cluster %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to cluster %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show cluster %s") % id)
            raise
        cluster_host_member_list = []
        cluster_network_member_list = []
        cluster_id = id
        cluster_host_member = self.db_api.cluster_host_member_find(
            req.context, cluster_id)
        if len(cluster_host_member) > 0:
            for cluster_host in list(cluster_host_member):
                cluster_host_member_list.append(cluster_host['host_id'])
            cluster_data['nodes'] = cluster_host_member_list

        cluster_network_member = self.db_api.network_get_all(
            req.context, cluster_id)
        if len(cluster_network_member) > 0:
            for cluster_network in list(cluster_network_member):
                cluster_network_member_list.append(cluster_network['id'])
            cluster_data['networks'] = cluster_network_member_list

        logic_networks = self.db_api.get_logic_network(req.context, id)
        cluster_data['logic_networks'] = logic_networks

        routers = self.db_api.router_get(req.context, cluster_id)
        cluster_data['routers'] = routers
        return cluster_data

    def detail_cluster(self, req):
        """Return a filtered list of public, non-deleted hosts in detail

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(hosts=[host_list])

        Where host_list is a sequence of mappings containing
        all host model fields.
        """
        params = self._get_query_params(req)
        cluster_host_member_list = []
        cluster_network_member_list = []

        clusters = self._get_clusters(req.context, **params)
        for cluster in clusters:
            cluster_id = cluster['id']
            filters = {'deleted': False, 'cluster_id': cluster_id}
            roles = self._get_roles(req.context, filters)
            roles_status = [role['status'] for role in roles]
            if len(set(roles_status)) == 1:
                cluster['status'] = roles_status[0]
            else:
                cluster['status'] = "init"
            cluster_host_member = self.db_api.cluster_host_member_find(
                req.context, cluster_id)
            if len(cluster_host_member) > 0:
                for cluster_host in list(cluster_host_member):
                    cluster_host_member_list.append(cluster_host['host_id'])
                cluster['nodes'] = cluster_host_member_list

            cluster_network_member = self.db_api.network_get_all(
                req.context, cluster_id)
            if len(cluster_network_member) > 0:
                for cluster_network in list(cluster_network_member):
                    cluster_network_member_list.append(cluster_network['id'])
                cluster['networks'] = cluster_network_member_list

        return dict(clusters=clusters)

    @utils.mutating
    def add_component(self, req, body):
        """Registers a new host with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the host

        :retval Returns the newly-created host information as a mapping,
                which will include the newly-created host's internal id
                in the 'id' field
        """

        component_data = body["component"]

        component_id = component_data.get('id')

        if component_id and not utils.is_uuid_like(component_id):
            msg = _LI("Rejecting host creation request for invalid component "
                      "id '%(bad_id)s'") % {'bad_id': component_id}
            LOG.info(msg)
            msg = _("Invalid component id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            component_data = self.db_api.component_add(
                req.context, component_data)
            # host_data = dict(host=make_image_dict(host_data))
            msg = (_LI("Successfully created component %s") %
                   component_data["id"])
            LOG.info(msg)
            if 'component' not in component_data:
                component_data = dict(component=component_data)
            return component_data
        except exception.Duplicate:
            msg = (_("component with identifier %s already exists!")
                   % component_id)
            LOG.warning(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add component metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to create component %s"), component_id)
            raise

    @utils.mutating
    def delete_component(self, req, id):
        """Deletes an existing component with the registry.

        :param req: wsgi Request object
        :param id:  The opaque internal identifier for the image

        :retval Returns 200 if delete was successful, a fault if not. On
        success, the body contains the deleted image information as a mapping.
        """
        try:
            deleted_component = self.db_api.component_destroy(req.context, id)
            msg = _LI("Successfully deleted component %(id)s") % {'id': id}
            LOG.info(msg)
            return dict(component=deleted_component)
        except exception.ForbiddenPublicImage:
            msg = _LI("Delete denied for public component %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to component %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except exception.NotFound:
            msg = _LI("Component %(id)s not found") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to delete component %s") % id)
            raise

    def _get_components(self, context, filters, **params):
        """Get components, wrapping in exception if necessary."""
        try:
            return self.db_api.component_get_all(context, filters=filters,
                                                 **params)
        except exception.NotFound:
            LOG.warning(_LW("Invalid marker. Project %(id)s could not be "
                            "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. Project could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warning(_LW("Access denied to component %(id)s but returning "
                            "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. Project could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get components"))
            raise

    @utils.mutating
    def get_component(self, req, id):
        """Return data about the given component id."""
        try:
            component_data = self.db_api.component_get(req.context, id)
            msg = "Successfully retrieved component %(id)s" % {'id': id}
            LOG.debug(msg)
        except exception.NotFound:
            msg = _LI("component %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to component %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show component %s") % id)
            raise
        if 'component' not in component_data:
            component_data = dict(component=component_data)
        return component_data

    def detail_component(self, req):
        """Return a filtered list of public, non-deleted hosts in detail

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(hosts=[host_list])

        Where host_list is a sequence of mappings containing
        all host model fields.
        """
        params = self._get_query_params(req)

        components = self._get_components(req.context, **params)

        return dict(components=components)

    @utils.mutating
    def update_component(self, req, id, body):
        """Updates an existing component with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the image
        :param id:  The opaque internal identifier for the image

        :retval Returns the updated image information as a mapping,
        """
        component_data = body['component']
        try:
            updated_component = self.db_api.component_update(
                req.context, id, component_data)

            msg = _LI("Updating metadata for component %(id)s") % {'id': id}
            LOG.info(msg)
            if 'component' not in updated_component:
                component_data = dict(component=updated_component)
            return component_data
        except exception.Invalid as e:
            msg = (_("Failed to update component metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("Component %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='Component not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public component %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to component %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='Component not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='Component operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except Exception:
            LOG.exception(_LE("Unable to update component %s") % id)
            raise

    @utils.mutating
    def add_service(self, req, body):
        """Registers a new host with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the host

        :retval Returns the newly-created host information as a mapping,
                which will include the newly-created host's internal id
                in the 'id' field
        """

        service_data = body["service"]

        service_id = service_data.get('id')

        if service_id and not utils.is_uuid_like(service_id):
            msg = _LI("Rejecting host creation request for invalid service "
                      "id '%(bad_id)s'") % {'bad_id': service_id}
            LOG.info(msg)
            msg = _("Invalid service id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            print service_data
            service_data = self.db_api.service_add(req.context, service_data)
            # host_data = dict(host=make_image_dict(host_data))
            msg = (_LI("Successfully created service %s") %
                   service_data["id"])
            LOG.info(msg)
            if 'service' not in service_data:
                service_data = dict(service=service_data)
            return service_data
        except exception.Duplicate:
            msg = _("service with identifier %s already exists!") % service_id
            LOG.warning(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add service metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to create service %s"), service_id)
            raise

    @utils.mutating
    def delete_service(self, req, id):
        """Deletes an existing service with the registry.

        :param req: wsgi Request object
        :param id:  The opaque internal identifier for the image

        :retval Returns 200 if delete was successful, a fault if not. On
        success, the body contains the deleted image information as a mapping.
        """
        try:
            deleted_service = self.db_api.service_destroy(req.context, id)
            msg = _LI("Successfully deleted service %(id)s") % {'id': id}
            LOG.info(msg)
            return dict(service=deleted_service)
        except exception.ForbiddenPublicImage:
            msg = _LI("Delete denied for public service %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to service %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except exception.NotFound:
            msg = _LI("Service %(id)s not found") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to delete service %s") % id)
            raise

    def _get_services(self, context, filters, **params):
        """Get services, wrapping in exception if necessary."""
        try:
            return self.db_api.service_get_all(context, filters=filters,
                                               **params)
        except exception.NotFound:
            LOG.warning(_LW("Invalid marker. Project %(id)s could not be "
                            "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. Project could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warning(_LW("Access denied to service %(id)s but returning "
                            "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. Project could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get services"))
            raise

    @utils.mutating
    def get_service(self, req, id):
        """Return data about the given service id."""
        try:
            service_data = self.db_api.service_get(req.context, id)
            msg = "Successfully retrieved service %(id)s" % {'id': id}
            LOG.debug(msg)
        except exception.NotFound:
            msg = _LI("service %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to service %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show service %s") % id)
            raise
        if 'service' not in service_data:
            service_data = dict(service=service_data)
        return service_data

    def detail_service(self, req):
        """Return a filtered list of public, non-deleted hosts in detail

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(hosts=[host_list])

        Where host_list is a sequence of mappings containing
        all host model fields.
        """
        params = self._get_query_params(req)

        services = self._get_services(req.context, **params)

        return dict(services=services)

    @utils.mutating
    def update_service(self, req, id, body):
        """Updates an existing service with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the image
        :param id:  The opaque internal identifier for the image

        :retval Returns the updated image information as a mapping,
        """
        service_data = body['service']
        try:
            updated_service = self.db_api.service_update(
                req.context, id, service_data)

            msg = _LI("Updating metadata for service %(id)s") % {'id': id}
            LOG.info(msg)
            if 'service' not in updated_service:
                service_data = dict(service=updated_service)
            return service_data
        except exception.Invalid as e:
            msg = (_("Failed to update service metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("Service %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='Service not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public service %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to service %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='Service not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='Service operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except Exception:
            LOG.exception(_LE("Unable to update service %s") % id)
            raise

    @utils.mutating
    def add_role(self, req, body):
        """Registers a new host with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the host

        :retval Returns the newly-created host information as a mapping,
                which will include the newly-created host's internal id
                in the 'id' field
        """

        role_data = body["role"]

        role_id = role_data.get('id')

        if role_id and not utils.is_uuid_like(role_id):
            msg = _LI("Rejecting host creation request for invalid role "
                      "id '%(bad_id)s'") % {'bad_id': role_id}
            LOG.info(msg)
            msg = _("Invalid role id format")
            return exc.HTTPBadRequest(explanation=msg)

        try:
            print role_data
            role_data = self.db_api.role_add(req.context, role_data)
            # host_data = dict(host=make_image_dict(host_data))
            msg = (_LI("Successfully created role %s") %
                   role_data["id"])
            LOG.info(msg)
            if 'role' not in role_data:
                role_data = dict(role=role_data)
            return role_data
        except exception.Duplicate:
            msg = _("role with identifier %s already exists!") % role_id
            LOG.warning(msg)
            return exc.HTTPConflict(msg)
        except exception.Invalid as e:
            msg = (_("Failed to add role metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except Exception:
            LOG.exception(_LE("Unable to create role %s"), role_id)
            raise

    @utils.mutating
    def delete_role(self, req, id):
        """Deletes an existing role with the registry.

        :param req: wsgi Request object
        :param id:  The opaque internal identifier for the image

        :retval Returns 200 if delete was successful, a fault if not. On
        success, the body contains the deleted image information as a mapping.
        """
        try:
            deleted_role = self.db_api.role_destroy(req.context, id)
            msg = _LI("Successfully deleted role %(id)s") % {'id': id}
            LOG.info(msg)
            return dict(role=deleted_role)
        except exception.ForbiddenPublicImage:
            msg = _LI("Delete denied for public role %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to role %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except exception.NotFound:
            msg = _LI("Role %(id)s not found") % {'id': id}
            LOG.info(msg)
            return exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to delete role %s") % id)
            raise

    def _get_roles(self, context, filters, **params):
        """Get roles, wrapping in exception if necessary."""
        try:
            return self.db_api.role_get_all(context, filters=filters,
                                            **params)
        except exception.NotFound:
            LOG.warning(_LW("Invalid marker. Project %(id)s could not be "
                            "found.") % {'id': params.get('marker')})
            msg = _("Invalid marker. Project could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except exception.Forbidden:
            LOG.warning(_LW("Access denied to role %(id)s but returning "
                            "'not found'") % {'id': params.get('marker')})
            msg = _("Invalid marker. Project could not be found.")
            raise exc.HTTPBadRequest(explanation=msg)
        except Exception:
            LOG.exception(_LE("Unable to get roles"))
            raise

    @utils.mutating
    def get_role(self, req, id):
        """Return data about the given role id."""
        try:
            role_data = self.db_api.role_get(req.context, id)
            msg = "Successfully retrieved role %(id)s" % {'id': id}
            LOG.debug(msg)
        except exception.NotFound:
            msg = _LI("role %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to role %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show role %s") % id)
            raise
        role_services = self.db_api.role_services_get(req.context, id)
        service_name = []
        for role_service in role_services:
            service_info = self.db_api.service_get(
                req.context, role_service['service_id'])
            service_name.append(service_info['name'])
        if 'role' not in role_data:
            role_data = dict(role=role_data)
        if service_name:
            role_data['role']['service_name'] = service_name
        return role_data

    def detail_role(self, req):
        """Return a filtered list of public, non-deleted hosts in detail

        :param req: the Request object coming from the wsgi layer
        :retval a mapping of the following form::

            dict(hosts=[host_list])

        Where host_list is a sequence of mappings containing
        all host model fields.
        """
        params = self._get_query_params(req)

        roles = self._get_roles(req.context, **params)

        return dict(roles=roles)

    @utils.mutating
    def update_role(self, req, id, body):
        """Updates an existing role with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the image
        :param id:  The opaque internal identifier for the image

        :retval Returns the updated image information as a mapping,
        """
        role_data = body['role']
        try:
            updated_role = self.db_api.role_update(req.context, id, role_data)

            msg = _LI("Updating metadata for role %(id)s") % {'id': id}
            LOG.info(msg)
            if 'role' not in updated_role:
                role_data = dict(role=updated_role)
            return role_data
        except exception.Invalid as e:
            msg = (_("Failed to update role metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("Role %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='Role not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public role %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to role %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='Role not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='Role operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except Exception:
            LOG.exception(_LE("Unable to update role %s") % id)
            raise

    @utils.mutating
    def role_services(self, req, id):
        """Return service list of the role."""
        try:
            role_data = self.db_api.role_services_get(req.context, id)
            msg = "Successfully retrieved services of role %(id)s" % {'id': id}
            LOG.debug(msg)
        except exception.NotFound:
            msg = _LI("role %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access services of role %(id)s denied but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show services of role %s") % id)
            raise
        if 'role' not in role_data:
            role_data = dict(role=role_data)
        return role_data

    @utils.mutating
    def update_host(self, req, id, body):
        """Updates an existing host with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the image
        :param id:  The opaque internal identifier for the image

        :retval Returns the updated image information as a mapping,
        """
        host_data = body['host']
        try:
            orig_config_set_id = None
            if 'config_set_id' in host_data:
                orig_host_data = self.db_api.host_get(req.context, id)
                orig_config_set_id = orig_host_data.get('config_set_id', None)

            updated_host = self.db_api.host_update(req.context, id, host_data)

            if orig_config_set_id:
                try:
                    self.db_api.config_set_destroy(req.context,
                                                   orig_config_set_id)
                except exception.NotFound as e:
                    msg = _LI("config_set %s has been deleted") \
                        % orig_config_set_id
                    LOG.info(msg)
                except exception.Forbidden:
                    msg = _LE("Forbidden to delete config_set %s") \
                        % orig_config_set_id
                    LOG.error(msg)
                    return exc.HTTPForbidden(msg)
                except Exception:
                    msg = _LE("Unable to delete config_set %s") \
                        % orig_config_set_id
                    LOG.error(msg)
                    return exc.HTTPBadRequest(msg)
            msg = _LI("Updating metadata for host %(id)s") % {'id': id}
            LOG.info(msg)
            if 'host' not in updated_host:
                host_data = dict(host=updated_host)
            return host_data
        except exception.Invalid as e:
            msg = (_("Failed to update host metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("Host %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='Host not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public host %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden as e:
            msg = (_("%s") % utils.exception_to_str(e))
            LOG.error(msg)
            raise exc.HTTPForbidden(msg)
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='Host operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except exception.Duplicate as e:
            msg = (_("%s") % utils.exception_to_str(e))
            LOG.error(msg)
            raise exc.HTTPForbidden(msg)
        except Exception:
            LOG.exception(_LE("Unable to update host %s") % id)
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

    @utils.mutating
    def host_roles(self, req, id):
        """Return host list in the host_roles."""
        try:
            role_data = self.db_api.get_host_roles(req.context, id)
            msg = "Successfully retrieved host of role %(id)s" % {'id': id}
            LOG.debug(msg)
        except exception.NotFound:
            msg = _LI("role %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access host of role %(id)s denied but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show host of role %s") % id)
            raise
        if 'role' not in role_data:
            role_data = dict(role=role_data)
        return role_data

    @utils.mutating
    def delete_role_hosts(self, req, id):
        """Return host list in the host_roles."""
        try:
            role_data = self.db_api.role_host_destroy(req.context, id)
            msg = "Successfully retrieved host of role %(id)s" % {'id': id}
            LOG.debug(msg)
        except exception.NotFound:
            msg = _LI("role %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access host of role %(id)s denied but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound()
        except Exception:
            LOG.exception(_LE("Unable to show host of role %s") % id)
            raise
        if 'role' not in role_data:
            role_data = dict(role=role_data)
        return role_data

    @utils.mutating
    def update_role_hosts(self, req, id, body):
        """Return role hosts list in the host_roles."""
        role_data = body['role']
        try:
            updated_role = self.db_api.role_host_update(
                req.context, id, role_data)

            msg = _LI("Updating metadata for role_host id %(id)s") % {'id': id}
            return updated_role
        except exception.Invalid as e:
            msg = (_("Failed to update role host metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        except exception.NotFound:
            msg = _LI("HostRole %(id)s not found") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='HostRole not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.ForbiddenPublicImage:
            msg = _LI("Update denied for public host_role %(id)s") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPForbidden()
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LI("Access denied to host_role %(id)s but returning"
                      " 'not found'") % {'id': id}
            LOG.info(msg)
            raise exc.HTTPNotFound(body='Role not found',
                                   request=req,
                                   content_type='text/plain')
        except exception.Conflict as e:
            LOG.info(utils.exception_to_str(e))
            raise exc.HTTPConflict(body='HostRole operation conflicts',
                                   request=req,
                                   content_type='text/plain')
        except Exception:
            LOG.exception(_LE("Unable to update host_role %s") % id)
            raise

    @utils.mutating
    def config_interface(self, req, body):
        """Registers a new config_interface with the registry.

        :param req: wsgi Request object
        :param body: Dictionary of information about the host

        :retval Returns the newly-created host information as a mapping,
                which will include the newly-created host's internal id
                in the 'id' field
        """
        config_interface_meta = body
        try:
            config_interface_meta = self.db_api.config_interface(
                req.context, config_interface_meta)
        except exception.Invalid as e:
            msg = (_("Failed to add role metadata. "
                     "Got error: %s") % utils.exception_to_str(e))
            LOG.error(msg)
            return exc.HTTPBadRequest(msg)
        if 'config_interface_meta' not in config_interface_meta:
            config_interface_meta = dict(
                config_interface_meta=config_interface_meta)
        return config_interface_meta


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
