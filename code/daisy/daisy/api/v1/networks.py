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
import copy
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
from daisy.common import utils
from daisy.common import wsgi
from daisy.api import common
from daisy import i18n
from daisy import notifier
import daisy.registry.client.v1.api as registry
from functools import reduce

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE


SUPPORT_NETWORK_TYPE = (
    'PUBLICAPI',
    'DATAPLANE',
    'STORAGE',
    'MANAGEMENT',
    'EXTERNAL',
    'DEPLOYMENT',
    'HEARTBEAT',
    'OUTBAND')
SUPPORT_NETWORK_TEMPLATE_TYPE = ('custom', 'template', 'default', 'system')
SUPPORT_ML2_TYPE = ('ovs', 'sriov(direct)', 'sriov(macvtap)',
                    'ovs,sriov(direct)', 'ovs,sriov(macvtap)')
SUPPORT_NETWORK_CAPABILITY = ('high', 'low')


class Controller(controller.BaseController):
    """
    WSGI controller for networks resource in Daisy v1 API

    The networks resource API is a RESTful web service for host data. The API
    is as follows::

        GET  /networks -- Returns a set of brief metadata about networks
        GET  /networks/detail -- Returns a set of detailed metadata about
                              networks
        HEAD /networks/<ID> -- Return metadata about an host with id <ID>
        GET  /networks/<ID> -- Return host data for host with id <ID>
        POST /networks -- Store host data and return metadata about the
                        newly-stored host
        PUT  /networks/<ID> -- Update host metadata and/or upload host
                            data for a previously-reserved host
        DELETE /networks/<ID> -- Delete the host with id <ID>
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

    def _raise_404_if_network_deleted(self, req, network_id):
        network = self.get_network_meta_or_404(req, network_id)
        if network['deleted']:
            msg = _("Network with identifier %s has been deleted.") % \
                network_id
            raise HTTPNotFound(msg)

    def _raise_404_if_cluster_delete(self, req, cluster_id):
        cluster_id = self.get_cluster_meta_or_404(req, cluster_id)
        if cluster_id['deleted']:
            msg = _("cluster_id with identifier %s has been deleted.") % \
                cluster_id
            raise HTTPNotFound(msg)

    def _get_network_name_by_cluster_id(self, context, cluster_id):
        networks = registry.get_networks_detail(context, cluster_id)
        network_name_list = []
        for network in networks:
            network_name_list.append(network['name'])
        return network_name_list

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

    def _ip_into_int(self, ip):
        """
        Switch ip string to decimalism integer..
        :param ip: ip string
        :return: decimalism integer
        """
        return reduce(lambda x, y: (x << 8) + y, map(int, ip.split('.')))

    def _is_in_network_range(self, ip, network):
        """
        Check ip is in range
        :param ip: Ip will be checked, like:192.168.1.2.
        :param network: Ip range,like:192.168.0.0/24.
        :return: If ip in range,return True,else return False.
        """
        network = network.split('/')
        mask = ~(2**(32 - int(network[1])) - 1)
        return (
            self._ip_into_int(ip) & mask) == (
            self._ip_into_int(
                network[0]) & mask)

    def _verify_uniqueness_of_network_name(
            self, req, network_list, network_meta, is_update=False):
        """
        Network name is match case and uniqueness in cluster.
        :param req:
        :param network_list: network plane in cluster
        :param network_meta: network plane need be verified
        :return:
        """
        if not network_list or not network_meta or not network_meta.get(
                'name', None):
            msg = _("Input params invalid for verifying uniqueness of "
                    "network name.")
            raise HTTPBadRequest(msg, request=req, content_type="text/plain")

        network_name = network_meta['name']
        for network in network_list['networks']:
            if (is_update and
                    network_name == network['name'] and
                    network_meta['id'] == network['id']):
                return

        # network name don't match case
        network_name_list = [network['name'].lower() for network in
                             network_list['networks'] if
                             network.get('name', None)]
        if network_name.lower() in network_name_list:
            msg = _(
                "Name of network isn't match case and %s already exits "
                "in the cluster." %
                network_name)
            raise HTTPConflict(msg, request=req, content_type="text/plain")

        if not is_update:
            # Input networks type can't be same with db record
            # which is all ready exit,
            # except PRIVATE network.
            network_type_exist_list = \
                [network['network_type'] for network in
                 network_list['networks']
                 if network.get('network_type', None) and
                 network['network_type'] != "DATAPLANE" and
                 network['network_type'] != "STORAGE" and
                 network['network_type'] != "HEARTBEAT"]
            if network_meta.get(
                    "network_type",
                    None) in network_type_exist_list:
                msg = _(
                    "The %s network plane %s must be unique, "
                    "except DATAPLANE/STORAGE/HEARTBEAT network." %
                    (network_meta['network_type'], network_name))
                raise HTTPConflict(msg, request=req, content_type="text/plain")

    def _verify_uniqueness_of_network_custom_name(
            self, req, network_list, network_meta, is_update=False):
        """custom name of network in cluster must be unique"""
        custom_name = network_meta['custom_name']
        for network in network_list['networks']:
            if is_update and custom_name == network.get('custom_name', None) \
                    and network_meta['id'] == network['id']:
                return
        network_custom_name_list = [network['custom_name'] for network
                                    in network_list['networks'] if
                                    network.get('custom_name', None)]
        if custom_name in network_custom_name_list:
            msg = _("Custom name %s of network already exits in the "
                    "cluster." % custom_name)
            raise HTTPConflict(msg, request=req, content_type="text/plain")

    def _verify_heartbeat_network(self, req, network_list, network_meta):
        heartbeat_networks = [
            network for network in network_list['networks'] if network.get(
                'network_type',
                None) and network['network_type'] == "HEARTBEAT"]
        if len(heartbeat_networks) >= 3:
            raise HTTPBadRequest(
                explanation="HEARTBEAT network plane number must be "
                            "less than three",
                request=req)

    @utils.mutating
    def add_network(self, req, network_meta):
        """
        Adds a new networks to Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about network

        :raises HTTPBadRequest if x-host-name is missing
        """
        self._enforce(req, 'add_network')
        cluster_id = network_meta.get('cluster_id', None)
        if cluster_id:
            self._raise_404_if_cluster_delete(req, cluster_id)
            network_list = self.detail(req, cluster_id)
            self._verify_uniqueness_of_network_name(
                req, network_list, network_meta)
            if network_meta.get('custom_name', None):
                self._verify_uniqueness_of_network_custom_name(
                    req, network_list, network_meta)
            if 'network_type' in network_meta and network_meta[
                    'network_type'] == "HEARTBEAT":
                self._verify_heartbeat_network(req, network_list, network_meta)
        # else:
        #     if network_meta.get('type',None) != "template":
        #         raise HTTPBadRequest(explanation="cluster id must be given",
        # request=req)
        network_name = network_meta.get('name', None)
        network_name_split = network_name.split('_')
        for network_name_info in network_name_split:
            if not network_name_info.isalnum():
                raise ValueError(
                    'network name must be numbers or letters or underscores !')
        if 'network_type' not in network_meta:
            raise HTTPBadRequest(
                explanation="network-type must be given",
                request=req)
        if network_meta['network_type'] not in SUPPORT_NETWORK_TYPE:
            raise HTTPBadRequest(
                explanation="unsupported network-type",
                request=req)

        if ('type' in network_meta and
                network_meta['type'] not in SUPPORT_NETWORK_TEMPLATE_TYPE):
            raise HTTPBadRequest(explanation="unsupported type", request=req)

        if ('capability' in network_meta and
                network_meta['capability'] not in SUPPORT_NETWORK_CAPABILITY):
            raise HTTPBadRequest(
                explanation="unsupported capability type",
                request=req)

        common.valid_network_range(req, network_meta)

        if network_meta.get('ip_ranges', None) and \
                network_meta['ip_ranges']:
            cidr = None
            if 'cidr' not in network_meta and \
                    network_meta['network_type'] != 'DATAPLANE':
                msg = (
                    _("When ip range was specified, the CIDR parameter "
                      "can not be empty."))
                LOG.warning(msg)
                raise HTTPForbidden(msg)
            else:
                ip_ranges = network_meta['ip_ranges']
                if network_meta['network_type'] != 'DATAPLANE':
                    cidr = network_meta['cidr']
                    utils.valid_cidr(cidr)
                    net_ip_ranges_list = []
                    for ip_pair in ip_ranges:
                        if not set(['start', 'end']).issubset(ip_pair.keys()):
                            msg = (
                                _("IP range was not start with 'start:' or "
                                  "end with 'end:'."))
                            LOG.warning(msg)
                            raise HTTPForbidden(msg)
                        ip_start = ip_pair['start']
                        ip_end = ip_pair['end']
                        net_ip_ranges_list.append({'start': ip_start,
                                                   'end': ip_end})
                    common.valid_ip_ranges(net_ip_ranges_list, cidr)
                else:
                    common.valid_ip_ranges_with_cidr(ip_ranges)

        if network_meta.get('cidr', None) \
                and network_meta.get('vlan_id', None) \
                and cluster_id:
            networks = registry.get_networks_detail(req.context, cluster_id)
            for network in networks:
                if network['cidr'] and network['vlan_id']:
                    if network_meta['cidr'] == network['cidr'] \
                            and network_meta['vlan_id'] != network['vlan_id']:
                        msg = (_('Networks with the same cidr must '
                                 'have the same vlan_id'))
                        raise HTTPBadRequest(explanation=msg)
                    if network_meta['vlan_id'] == network['vlan_id'] \
                            and network_meta['cidr'] != network['cidr']:
                        msg = (_('Networks with the same vlan_id must '
                                 'have the same cidr'))
                        raise HTTPBadRequest(explanation=msg)

        if network_meta.get('gateway', None) and \
                network_meta.get('cidr', None):
            gateway = network_meta['gateway']
            cidr = network_meta['cidr']

            utils.validate_ip_format(gateway)

        network_meta = registry.add_network_metadata(req.context, network_meta)
        return {'network_meta': network_meta}

    @utils.mutating
    def delete_network(self, req, network_id):
        """
        Deletes a network from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about host

        :raises HTTPBadRequest if x-host-name is missing
        """
        self._enforce(req, 'delete_network')
        # self._raise_404_if_cluster_deleted(req, cluster_id)
        # self._raise_404_if_network_deleted(req, network_id)
        network = self.get_network_meta_or_404(req, network_id)
        if network['deleted']:
            msg = _("Network with identifier %s has been deleted.") % \
                network_id
            raise HTTPNotFound(msg)
        if network['type'] != 'custom':
            msg = _("Type of network was not custom, can not "
                    "delete this network.")
            raise HTTPForbidden(msg)
        try:
            registry.delete_network_metadata(req.context, network_id)
        except exception.NotFound as e:
            msg = (_("Failed to find network to delete: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete network: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("Network %(id)s could not be deleted "
                     "because it is in use: "
                     "%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.warning(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            # self.notifier.info('host.delete', host)
            return Response(body='', status=200)

    @utils.mutating
    def get_network(self, req, id):
        """
        Returns metadata about an network in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque host identifier

        :raises HTTPNotFound if host metadata is not available to user
        """
        self._enforce(req, 'get_network')
        network_meta = self.get_network_meta_or_404(req, id)
        return {'network_meta': network_meta}

    def get_all_network(self, req):
        """
        List all network.
        :param req:
        :return:
        """
        self._enforce(req, 'get_all_network')
        params = self._get_query_params(req)
        filters = params.get('filters')
        if filters and filters.get('type'):
            if filters['type'] not in SUPPORT_NETWORK_TEMPLATE_TYPE:
                msg = "type '%s' is not support." % filters['type']
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)

        try:
            networks = registry.get_all_networks(req.context, **params)
        except Exception:
            raise HTTPBadRequest(
                explanation="Get all networks failed.",
                request=req)
        return dict(networks=networks)

    def detail(self, req, id):
        """
        Returns detailed information for all available hosts

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'networks': [
                {'id': <ID>,
                 'name': <NAME>,
                 'description': <DESCRIPTION>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._raise_404_if_cluster_delete(req, id)
        self._enforce(req, 'get_networks')
        params = self._get_query_params(req)
        try:
            networks = registry.get_networks_detail(req.context, id, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(networks=networks)

    def _is_dataplane_in_use(self, context, network_meta,
                             network_id, orig_segment_type):
        if network_meta.get('custom_name', None):
            network_name = network_meta.get('custom_name', None)
        else:
            network_name = network_meta.get('name', None)
        update_segment_type = network_meta.get('segmentation_type')
        try:
            assigned_network = \
                registry.get_assigned_networks_data_by_network_id(
                    context, network_id)
        except exception.NotFound as e:
            msg = (_("Failed to find assigned network, %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPNotFound(explanation=msg)
        if assigned_network:
            if update_segment_type != orig_segment_type:
                msg = (_("DATAPLANE %s is in use, can not "
                         "change segment type ") % network_name)
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg)

    @utils.mutating
    def update_network(self, req, network_id, network_meta):
        """
        Updates an existing host with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        if 'name' in network_meta:
            network_name = network_meta.get('name', None)
            network_name_split = network_name.split('_')
            for network_name_info in network_name_split:
                if not network_name_info.isalnum():
                    raise ValueError(
                        'network name must be numbers or '
                        'letters or underscores !')
        self._enforce(req, 'update_network')
        # orig_cluster_meta = self.get_cluster_meta_or_404(req, cluster_id)
        orig_network_meta = self.get_network_meta_or_404(req, network_id)
        # Do not allow any updates on a deleted network.
        if orig_network_meta['deleted']:
            msg = _("Forbidden to update deleted host.")
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        if ('network_type' in network_meta and
                network_meta['network_type'] not in SUPPORT_NETWORK_TYPE):
            raise HTTPBadRequest(
                explanation="unsupported network-type",
                request=req)
        if ('type' in network_meta and
                network_meta['type'] not in SUPPORT_NETWORK_TEMPLATE_TYPE):
            raise HTTPBadRequest(explanation="unsupported type", request=req)
        if ('type' in network_meta and
                network_meta['type'] == 'template'):
            raise HTTPBadRequest(
                explanation="network template type is not allowed to update",
                request=req)

        if ('capability' in network_meta and
                network_meta['capability'] not in SUPPORT_NETWORK_CAPABILITY):
            raise HTTPBadRequest(
                explanation="unsupported capability type",
                request=req)

        common.valid_network_range(req, network_meta)

        network_name = network_meta.get('name', None)
        cluster_id = orig_network_meta['cluster_id']
        if network_name and cluster_id:
            network_updated = copy.deepcopy(network_meta)
            network_updated['id'] = network_id
            network_type = network_meta.get('network_type', None)
            network_updated['network_type'] = orig_network_meta[
                'network_type'] if not network_type else network_type
            network_list = self.detail(req, cluster_id)
            self._verify_uniqueness_of_network_name(
                req, network_list, network_updated, True)
        if network_meta.get('custom_name', None) and cluster_id:
            network_list = self.detail(req, cluster_id)
            network_updated = copy.deepcopy(network_meta)
            network_updated['id'] = network_id
            self._verify_uniqueness_of_network_custom_name(
                req, network_list, network_updated, True)

        cidr = network_meta.get('cidr', orig_network_meta['cidr'])
        vlan_id = network_meta.get('vlan_id', orig_network_meta['vlan_id'])
        if cidr:
            utils.valid_cidr(cidr)

        if cidr and vlan_id and cluster_id:
            networks = registry.get_networks_detail(req.context, cluster_id)
            for network in networks:
                if network['cidr'] and network['vlan_id']:
                    if cidr == network['cidr'] \
                            and vlan_id != network['vlan_id'] \
                            and network['id'] != network_id:
                        msg = (_('Networks with the same cidr must have '
                                 'the same vlan_id'))
                        raise HTTPBadRequest(explanation=msg)
                    if vlan_id == network['vlan_id'] \
                            and cidr != network['cidr'] \
                            and network['id'] != network_id:
                        msg = (_('Networks with the same vlan_id must '
                                 'have the same cidr'))
                        raise HTTPBadRequest(explanation=msg)
        dataplane_type = network_meta.get('network_type',
                                          orig_network_meta['network_type'])
        if dataplane_type == 'DATAPLANE':
            orig_segment_type = orig_network_meta.get('segmentation_type')
            if network_meta.get('segmentation_type'):
                self._is_dataplane_in_use(req.context,
                                          network_meta, network_id,
                                          orig_segment_type)

        if network_meta.get('ip_ranges', None) and \
                network_meta['ip_ranges']:
            dataplane_type = \
                network_meta.get('network_type',
                                 orig_network_meta['network_type'])
            if not cidr and dataplane_type != 'DATAPLANE':
                msg = (
                    _("When ip range was specified, "
                      "the CIDR parameter can not be empty."))
                LOG.warning(msg)
                raise HTTPForbidden(msg)
            ip_ranges = network_meta['ip_ranges']
            if dataplane_type != 'DATAPLANE':
                net_ip_ranges_list = []
                for ip_pair in ip_ranges:
                    if not set(['start', 'end']).issubset(ip_pair.keys()):
                        msg = (
                            _("IP range was not start with 'start:' or "
                              "end with 'end:'."))
                        LOG.warning(msg)
                        raise HTTPForbidden(msg)
                    ip_start = ip_pair['start']
                    ip_end = ip_pair['end']
                    net_ip_ranges_list.append({'start': ip_start,
                                               'end': ip_end})
                common.valid_ip_ranges(net_ip_ranges_list, cidr)
            else:
                common.valid_ip_ranges_with_cidr(ip_ranges, cidr)

        if network_meta.get('gateway', orig_network_meta['gateway']) \
                and network_meta.get('cidr', orig_network_meta['cidr']):
            gateway = network_meta.get('gateway', orig_network_meta['gateway'])
            cidr = network_meta.get('cidr', orig_network_meta['cidr'])
            utils.validate_ip_format(gateway)

        try:
            network_meta = registry.update_network_metadata(req.context,
                                                            network_id,
                                                            network_meta)
        except exception.Invalid as e:
            msg = (_("Failed to update network metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find network to update: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            LOG.warning(e)
            raise HTTPForbidden(e)
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.warning(utils.exception_to_str(e))
            raise HTTPConflict(body=_('Network operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('network.update', network_meta)

        return {'network_meta': network_meta}


class HostDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["network_meta"] = utils.get_network_meta(request)
        return result

    def add_network(self, request):
        return self._deserialize(request)

    def update_network(self, request):
        return self._deserialize(request)


class HostSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_network(self, response, result):
        network_meta = result['network_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(network=network_meta))
        return response

    def delete_network(self, response, result):
        network_meta = result['network_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(network=network_meta))
        return response

    def get_network(self, response, result):
        network_meta = result['network_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(network=network_meta))
        return response


def create_resource():
    """Hosts resource factory method"""
    deserializer = HostDeserializer()
    serializer = HostSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
