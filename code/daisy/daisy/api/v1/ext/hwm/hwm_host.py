# Copyright 2011 OpenStack Foundation
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

from daisy.common import wsgi
from oslo_config import cfg
import daisy.registry.client.v1.api as registry
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden
from webob.exc import HTTPNotFound
from oslo_log import log as logging
from daisy.common import utils
from daisy import i18n
import daisy.api.v1
from daisy.common import exception
from daisy.api.v1 import filters
from daisy import notifier
from daisy.api import policy
from daisy.api.v1 import controller

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

DISCOVER_DEFAULTS = {
    'listen_port': '5050',
    'ironic_url': 'http://127.0.0.1:6385/v1',
}

ML2_TYPE = [
    'ovs',
    'dvs',
    'ovs,sriov(macvtap)',
    'ovs,sriov(direct)',
    'sriov(macvtap)',
    'sriov(direct)']
SUPPORT_HOST_PAGE_SIZE = ['2M', '1G']


class Controller(controller.BaseController):
    """
    WSGI controller for hosts resource in Daisy v1 API

    The hosts resource API is a RESTful web service for host data. The API
    is as follows::

        GET  /nodes -- Returns a set of brief metadata about hosts
        GET  /nodes -- Returns a set of detailed metadata about
                              hosts
        HEAD /nodes/<ID> -- Return metadata about an host with id <ID>
        GET  /nodes/<ID> -- Return host data for host with id <ID>
        POST /nodes -- Store host data and return metadata about the
                        newly-stored host
        PUT  /nodes/<ID> -- Update host metadata and/or upload host
                            data for a previously-reserved host
        DELETE /nodes/<ID> -- Delete the host with id <ID>
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
        if network is None or network['deleted']:
            msg = _("Network with identifier %s has been deleted.") % \
                network_id
            LOG.error(msg)
            raise HTTPNotFound(msg)

    def _raise_404_if_cluster_deleted(self, req, cluster_id):
        cluster = self.get_cluster_meta_or_404(req, cluster_id)
        if cluster is None or cluster['deleted']:
            msg = _("Cluster with identifier %s has been deleted.") % \
                cluster_id
            LOG.error(msg)
            raise HTTPNotFound(msg)

    def _raise_404_if_role_deleted(self, req, role_id):
        role = self.get_role_meta_or_404(req, role_id)
        if role is None or role['deleted']:
            msg = _("Cluster with identifier %s has been deleted.") % role_id
            LOG.error(msg)
            raise HTTPNotFound(msg)

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

    def _update_hwm_host(self, req, hwm_host, hosts, hwm_ip):
        hwm_host_mac = list()
        for hwm_host_interface in hwm_host.get('interfaces'):
            if hwm_host_interface.get('mac'):
                hwm_host_interface['mac'] = hwm_host_interface['mac'].lower()
                hwm_host_mac.append(hwm_host_interface['mac'])

        for host in hosts:
            host_update_meta = dict()
            host_meta = self.get_host_meta_or_404(req, host['id'])
            host_mac = [host_interface['mac'] for host_interface
                        in host_meta.get('interfaces')]
            set_same_mac = set(hwm_host_mac) & set(host_mac)

            if set_same_mac:
                host_update_meta['hwm_id'] = hwm_host['id']
                host_update_meta['hwm_ip'] = hwm_ip
                node = registry.update_host_metadata(req.context, host['id'],
                                                     host_update_meta)
                return node

        if not hwm_host_mac:
            raise HTTPBadRequest()

        host_add_meta = dict()
        host_add_meta['name'] = str(hwm_host['id'])
        host_add_meta['description'] = 'default'
        host_add_meta['os_status'] = 'init'
        host_add_meta['hwm_id'] = str(hwm_host['id'])
        host_add_meta['hwm_ip'] = str(hwm_ip)
        host_add_meta['interfaces'] = str(hwm_host['interfaces'])
        node = registry.add_host_metadata(req.context, host_add_meta)
        return node

    def update_hwm_host(self, req, host_meta):
        self._enforce(req, 'get_hosts')
        params = self._get_query_params(req)
        try:
            hosts = registry.get_hosts_detail(req.context, **params)
            hosts_without_hwm_id = list()
            hosts_hwm_id_list = list()
            for host in hosts:
                if host.get('hwm_id'):
                    hosts_hwm_id_list.append(host['hwm_id'])
                else:
                    hosts_without_hwm_id.append(host)

            hwm_hosts = host_meta['nodes']
            hwm_ip = host_meta['hwm_ip']
            nodes, nodes_without_interface = list(), list()
            for hwm_host in eval(hwm_hosts):
                if hwm_host['id'] in hosts_hwm_id_list:
                    continue
                try:
                    node = self._update_hwm_host(req, hwm_host,
                                                 hosts_without_hwm_id, hwm_ip)
                except HTTPBadRequest:
                    nodes_without_interface.append(hwm_host['id'])
                else:
                    nodes.append(node)
            if nodes_without_interface:
                msg = 'No Interface in hosts, %s' % nodes_without_interface
                LOG.error(msg)
                raise HTTPBadRequest(msg)

            return dict(nodes=nodes)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)


class HostDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["host_meta"] = utils.get_host_meta(request)
        return result

    def update_hwm_host(self, request):
        return self._deserialize(request)


class HostSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()


def create_resource():
    """Hosts resource factory method"""
    deserializer = HostDeserializer()
    serializer = HostSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
