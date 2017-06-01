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
/clusters endpoint for Daisy v1 API
"""
import copy

from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPConflict
from webob.exc import HTTPForbidden
from webob.exc import HTTPNotFound
from webob.exc import HTTPServerError
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
from functools import reduce

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE

CLUSTER_DEFAULT_NETWORKS = ['PUBLICAPI', 'DEPLOYMENT', 'DATAPLANE', 'EXTERNAL',
                            'STORAGE', 'MANAGEMENT']


class Controller(controller.BaseController):
    """
    WSGI controller for clusters resource in Daisy v1 API

    The clusters resource API is a RESTful web service for cluster data.
    The API is as follows::

        GET  /clusters -- Returns a set of brief metadata about clusters
        GET  /clusters -- Returns a set of detailed metadata about
                              clusters
        HEAD /clusters/<ID> -- Return metadata about an cluster with id <ID>
        GET  /clusters/<ID> -- Return cluster data for cluster with id <ID>
        POST /clusters -- Store cluster data and return metadata about the
                        newly-stored cluster
        PUT  /clusters/<ID> -- Update cluster metadata and/or upload cluster
                            data for a previously-reserved cluster
        DELETE /clusters/<ID> -- Delete the cluster with id <ID>
    """
    def check_params(f):
        """
        Cluster add and update operation params valid check.
        :param f: Function hanle for 'cluster_add' and 'cluster_update'.
        :return: f
        """
        def wrapper(*args, **kwargs):
            controller, req = args
            cluster_meta = kwargs.get('cluster_meta', None)
            cluster_id = kwargs.get('id', None)
            errmsg = (_("I'm params checker."))

            LOG.debug(
                _("Params check for cluster-add or cluster-update begin!"))

            def check_params_range(param, type=None):
                '''
                param : input a list ,such as [start, end]
                check condition: start must less than end,
                and existed with pair
                return True of False
                '''
                if len(param) != 2:
                    msg = '%s range must be existed in pairs.' % type
                    raise HTTPForbidden(explanation=msg)
                if param[0] is None or param[0] == '':
                    msg = 'The start value of %s range can not be None.' % type
                    raise HTTPForbidden(explanation=msg)
                if param[1] is None:
                    msg = 'The end value of %s range can not be None.' % type
                    raise HTTPForbidden(explanation=msg)
                if int(param[0]) > int(param[1]):
                    msg = 'The start value of the %s range must be less ' \
                          'than the end value.' % type
                    raise HTTPForbidden(explanation=msg)
                if type not in ['vni']:
                    if int(param[0]) < 0 or int(param[0]) > 4096:
                        msg = 'Invalid value of the start value(%s) of ' \
                              'the %s range .' % (param[
                                  0], type)
                        raise HTTPForbidden(explanation=msg)
                    if int(param[1]) < 0 or int(param[1]) > 4096:
                        msg = 'Invalid value of the end value(%s) of ' \
                              'the %s range .' % (param[
                                  1], type)
                        raise HTTPForbidden(explanation=msg)
                else:
                    if int(param[0]) < 0 or int(param[0]) > 16777216:
                        msg = 'Invalid value of the start value(%s) of ' \
                              'the %s range .' % (param[
                                  0], type)
                        raise HTTPForbidden(explanation=msg)
                    if int(param[1]) < 0 or int(param[1]) > 16777216:
                        msg = 'Invalid value of the end value(%s) of ' \
                              'the %s range .' % (param[
                                  1], type)
                        raise HTTPForbidden(explanation=msg)
                return True

            def _check_auto_scale(req, cluster_meta):
                if 'auto_scale' in cluster_meta and cluster_meta[
                        'auto_scale'] == '1':
                    meta = {"auto_scale": '1'}
                    params = {'filters': meta}
                    clusters = registry.get_clusters_detail(
                        req.context, **params)
                    if clusters:
                        if cluster_id:
                            temp_cluster = [
                                cluster for cluster in clusters if
                                cluster['id'] != cluster_id]
                            if temp_cluster:
                                errmsg = (
                                    _("already exist cluster "
                                      "auto_scale is true"))
                                raise HTTPBadRequest(explanation=errmsg)
                        else:
                            errmsg = (
                                _("already exist cluster auto_scale is true"))
                            raise HTTPBadRequest(explanation=errmsg)

            def _ip_into_int(ip):
                """
                Switch ip string to decimalism integer..
                :param ip: ip string
                :return: decimalism integer
                """
                return reduce(lambda x, y: (x << 8) + y,
                              map(int, ip.split('.')))

            def _is_in_network_range(ip, network):
                """
                Check ip is in range
                :param ip: Ip will be checked, like:192.168.1.2.
                :param network: Ip range,like:192.168.0.0/24.
                :return: If ip in range,return True,else return False.
                """
                network = network.split('/')
                mask = ~(2**(32 - int(network[1])) - 1)
                return (
                    _ip_into_int(ip) & mask) == (
                    _ip_into_int(
                        network[0]) & mask)

            def _check_param_nonull_and_valid(
                    values_set, keys_set, valids_set={}):
                """
                Check operation params is not null and valid.
                :param values_set: Params set.
                :param keys_set: Params will be checked.
                :param valids_set:
                :return:
                """
                for k in keys_set:
                    v = values_set.get(k, None)
                    if isinstance(v, type(True)) and v is None:
                        errmsg = (_("Segment %s can't be None." % k))
                        raise HTTPBadRequest(explanation=errmsg)
                    elif not isinstance(v, type(True)) and not v:
                        errmsg = (_("Segment %s can't be None." % k))
                        raise HTTPBadRequest(explanation=errmsg)

                for (k, v) in valids_set.items():
                    # if values_set.get(k, None) and values_set[k] not in v:
                    if values_set.get(k, None) and -1 == v.find(values_set[k]):
                        errmsg = (_("Segment %s is out of valid range." % k))
                        raise HTTPBadRequest(explanation=errmsg)

            def _get_network_detail(req, cluster_id, networks_list):
                all_network_list = []
                if cluster_id:
                    all_network_list = registry.get_networks_detail(
                        req.context, cluster_id)

                if networks_list:
                    for net_id in networks_list:
                        network_detail = registry.get_network_metadata(
                            req.context, net_id)
                        all_network_list.append(network_detail)

                all_private_network_list = [
                    network for network in all_network_list if network[
                        'network_type'] == "DATAPLANE"]
                return all_private_network_list

            def _check_cluster_add_parameters(req, cluster_meta):
                """
                By params set segment,check params is available.
                :param req: http req
                :param cluster_meta: params set
                :return:error message
                """
                if 'nodes' in cluster_meta:
                    orig_keys = list(eval(cluster_meta['nodes']))
                    for host_id in orig_keys:
                        controller._raise_404_if_host_deleted(req, host_id)

                if 'networks' in cluster_meta:
                    orig_keys = list(eval(cluster_meta['networks']))
                    network_with_same_name = []
                    for network_id in orig_keys:
                        network_name = \
                            controller._raise_404_if_network_deleted(
                                req, network_id)
                        if network_name in CLUSTER_DEFAULT_NETWORKS:
                            return (_("Network name %s of %s already exits"
                                      " in the cluster, please check." %
                                      (network_name, network_id)))
                        if network_name in network_with_same_name:
                            return (_("Network name can't be same with "
                                      "each other in 'networks[]', "
                                      "please check."))
                        network_with_same_name.append(network_name)

                # checkout network_params
                if cluster_meta.get('networking_parameters', None):
                    networking_parameters =\
                        eval(cluster_meta['networking_parameters'])

                # check logic_networks
                subnet_name_set = []  # record all subnets's name
                logic_network_name_set = []  # record all logic_network's name
                subnets_in_logic_network = {}
                external_logic_network_name = []
                if cluster_meta.get('logic_networks', None):
                    # get physnet_name list
                    all_private_cluster_networks_list = _get_network_detail(
                        req, cluster_id, cluster_meta.get(
                            'networks', None) if not isinstance(
                            cluster_meta.get(
                                'networks', None), unicode) else eval(
                            cluster_meta.get(
                                'networks', None)))
                    if not all_private_cluster_networks_list:
                        LOG.info(
                            "Private network is empty in db, it lead "
                            "logical network config invalid.")
                    physnet_name_set = [net['name']
                                        for net in
                                        all_private_cluster_networks_list]

                    logic_networks = eval(cluster_meta['logic_networks'])
                    for logic_network in logic_networks:
                        subnets_in_logic_network[logic_network['name']] = []

                        # We force setting the physnet_name of flat logical
                        # network to 'flat'.
                        if logic_network.get(
                                'segmentation_type', None) == "flat":
                            if logic_network['physnet_name'] != "physnet1" or \
                                    logic_network[
                                    'type'] != "external":
                                LOG.info(
                                    "When 'segmentation_type' is flat the "
                                    "'physnet_name' and 'type' segmentation"
                                    "must be 'physnet1'' and 'external'', "
                                    "but got '%s' and '%s'.We have changed"
                                    "it to the valid value.")
                            logic_network['physnet_name'] = "physnet1"
                            logic_network['type'] = "external"
                            physnet_name_set.append("physnet1")

                        _check_param_nonull_and_valid(
                            logic_network,
                            ['name', 'type', 'physnet_name',
                             'segmentation_type', 'shared', 'segmentation_id'],
                            {'segmentation_type': networking_parameters[
                                'segmentation_type'],
                             'physnet_name': ','.join(physnet_name_set),
                             'type': ','.join(["external", "internal"])})

                        if logic_network['type'] == "external":
                            external_logic_network_name.append(
                                logic_network['name'])

                        logic_network_name_set.append(logic_network['name'])

                        # checkout subnets params------------------------------
                        if logic_network.get('subnets', None):
                            subnet_data = logic_network['subnets']
                            for subnet in subnet_data:
                                _check_param_nonull_and_valid(
                                    subnet,
                                    ['name', 'cidr'])
                                subnet_name_set.append(subnet['name'])
                                # By cidr check floating_ranges is in range
                                # and not overlap
                                # ---------------start-----
                                if subnet['gateway'] and not \
                                        _is_in_network_range(
                                        subnet['gateway'], subnet['cidr']):
                                    return (_("Wrong gateway format."))
                                if subnet['floating_ranges']:
                                    inter_ip = lambda x: '.'.join(
                                        [str(x / (256**i) % 256) for i in
                                         range(3, -1, -1)])
                                    floating_ranges_with_int_ip = list()
                                    sorted_floating_ranges = list()
                                    sorted_floating_ranges_with_int_ip = list()
                                    for floating_ip in subnet[
                                            'floating_ranges']:
                                        if len(floating_ip) != 2:
                                            return (
                                                _("Floating ip must "
                                                  "be paris."))
                                        ip_start = _ip_into_int(floating_ip[0])
                                        ip_end = _ip_into_int(floating_ip[1])
                                        if ip_start > ip_end:
                                            return (
                                                _("Wrong floating ip format."))
                                        floating_ranges_with_int_ip.append(
                                            [ip_start, ip_end])
                                    sorted_floating_ranges_with_int_ip = \
                                        sorted(floating_ranges_with_int_ip,
                                               key=lambda x: x[0])
                                    for ip_range in \
                                            sorted_floating_ranges_with_int_ip:
                                        ip_start = inter_ip(ip_range[0])
                                        ip_end = inter_ip(ip_range[1])
                                        sorted_floating_ranges.append(
                                            [ip_start, ip_end])

                                    last_rang_ip = []
                                    for floating in sorted_floating_ranges:
                                        if not _is_in_network_range(
                                                floating[0],
                                                subnet['cidr']) or not \
                                                _is_in_network_range(
                                                floating[1], subnet['cidr']):
                                            return (
                                                _("Floating ip or gateway "
                                                  "is out of range cidr."))

                                        err_list = [
                                            err for err in last_rang_ip if
                                            _ip_into_int(
                                                floating[0]) < err]
                                        if last_rang_ip and 0 < len(err_list):
                                            return (
                                                _("Between floating ip range "
                                                  "can not be overlap."))
                                        last_rang_ip.append(
                                            _ip_into_int(floating[1]))
                                subnets_in_logic_network[logic_network[
                                    'name']].append(subnet['name'])

                    # check external logical network uniqueness
                    if len(external_logic_network_name) > 1:
                        return (_("External logical network is uniqueness "
                                  "in the cluster.Got %s." %
                                  ",".join(external_logic_network_name)))

                    # check logic_network_name uniqueness
                    if len(logic_network_name_set) != len(
                            set(logic_network_name_set)):
                        return (_("Logic network name segment "
                                  "is repetition."))

                    # check subnet_name uniqueness
                    if len(subnet_name_set) != len(set(subnet_name_set)):
                        return (_("Subnet name segment is repetition."))

                    cluster_meta['logic_networks'] = unicode(logic_networks)

                # check routers------------------------------------------------
                subnet_name_set_deepcopy = copy.deepcopy(subnet_name_set)
                router_name_set = []  # record all routers name
                if cluster_meta.get('routers', None):
                    router_data = eval(cluster_meta['routers'])
                    for router in router_data:
                        _check_param_nonull_and_valid(router, ['name'])

                        # check relevance logic_network is valid
                        external_logic_network_data = router.get(
                            'external_logic_network', None)
                        if external_logic_network_data and \
                                external_logic_network_data not in \
                                logic_network_name_set:
                            return (_("Logic_network %s is not valid range." %
                                      external_logic_network_data))
                        router_name_set.append(router['name'])

                        # check relevance subnets is valid
                        for subnet in router.get('subnets', []):
                            if subnet not in subnet_name_set:
                                return (
                                    _("Subnet %s is not valid range." %
                                      subnet))

                            # subnet cann't relate with two routers
                            if subnet not in subnet_name_set_deepcopy:
                                return (
                                    _("The subnet can't be related with "
                                      "multiple routers."))
                            subnet_name_set_deepcopy.remove(subnet)

                        if external_logic_network_data and \
                            subnets_in_logic_network[
                                external_logic_network_data] and \
                                set(subnets_in_logic_network[
                                    external_logic_network_data]). \
                                issubset(set(router['subnets'])):
                            return (
                                _("Logic network's subnets is all related"
                                  " with a router, it's not allowed."))

                # check subnet_name uniqueness
                if len(router_name_set) != len(set(router_name_set)):
                    return (_("Router name segment is repetition."))
                return (_("I'm params checker."))
            _check_auto_scale(req, cluster_meta)
            check_result = _check_cluster_add_parameters(req, cluster_meta)
            if 0 != cmp(check_result, errmsg):
                LOG.exception(
                    _("Params check for cluster-add or cluster-update "
                      "is failed!"))
                raise HTTPBadRequest(explanation=check_result)

            LOG.debug(
                _("Params check for cluster-add or cluster-update is done!"))

            return f(*args, **kwargs)
        return wrapper

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

    def _raise_404_if_host_deleted(self, req, host_id):
        host = self.get_host_meta_or_404(req, host_id)
        if host['deleted']:
            msg = _("Host with identifier %s has been deleted.") % host_id
            raise HTTPNotFound(msg)

    def _raise_404_if_network_deleted(self, req, network_id):
        network = self.get_network_meta_or_404(req, network_id)
        if network['deleted']:
            msg = _("Network with identifier %s has been deleted.") % \
                network_id
            raise HTTPNotFound(msg)
        return network.get('name', None)

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

    @utils.mutating
    @check_params
    def add_cluster(self, req, cluster_meta):
        """
        Adds a new cluster to Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about cluster

        :raises HTTPBadRequest if x-cluster-name is missing
        """
        self._enforce(req, 'add_cluster')
        cluster_name = cluster_meta["name"]
        if not cluster_name:
            raise ValueError('cluster name is null!')
        # target_systems = cluster_meta['target_systems']
        # if not target_systems:
        #     raise ValueError('target_systems is null!')
        if not cluster_meta.get('target_systems', None):
            cluster_meta['target_systems'] = "os"
        cluster_name_split = cluster_name.split('_')
        for cluster_name_info in cluster_name_split:
            if not cluster_name_info.isalnum():
                raise ValueError(
                    'cluster name must be numbers or letters or underscores !')
        try:
            params = {"filters": dict(name=cluster_name)}
            cluster_name_repeat = \
                registry.get_clusters_detail(req.context, **params)
        except Exception:
            pass
        else:
            if cluster_name_repeat:
                msg = _('cluster name [%s] is in use!') % cluster_name
                raise HTTPBadRequest(explanation=msg)

        if cluster_meta.get('nodes', None):
            orig_keys = list(eval(cluster_meta['nodes']))
            for host_id in orig_keys:
                self._raise_404_if_host_deleted(req, host_id)
                node = registry.get_host_metadata(req.context, host_id)
                if node['status'] == 'in-cluster':
                    msg = _("Forbidden to add host %s with status "
                            "'in-cluster' in another cluster") % host_id
                    raise HTTPForbidden(explanation=msg)
                if node.get('interfaces', None):
                    interfaces = node['interfaces']
                    input_host_pxe_info = [
                        interface for interface in interfaces if interface.get(
                            'is_deployment', None) == 1]
                    if not input_host_pxe_info and node.get(
                            'os_status', None) != 'active':
                        msg = _(
                            "The host %s has more than one dhcp server, "
                            "please choose one interface for deployment") % \
                            host_id
                        raise HTTPServerError(explanation=msg)
        print cluster_name
        print cluster_meta
        cluster_meta = registry.add_cluster_metadata(req.context, cluster_meta)
        return {'cluster_meta': cluster_meta}

    @utils.mutating
    def delete_cluster(self, req, id):
        """
        Deletes a cluster from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about cluster

        :raises HTTPBadRequest if x-cluster-name is missing
        """
        self._enforce(req, 'delete_cluster')

        # cluster = self.get_cluster_meta_or_404(req, id)
        print "delete_cluster:%s" % id
        try:
            registry.delete_cluster_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find cluster to delete: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete cluster: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("cluster %(id)s could not be deleted because "
                     "it is in use: "
                     "%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.warning(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            # self.notifier.info('cluster.delete', cluster)
            return Response(body='', status=200)

    @utils.mutating
    def get_cluster(self, req, id):
        """
        Returns metadata about an cluster in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque cluster identifier

        :raises HTTPNotFound if cluster metadata is not available to user
        """
        self._enforce(req, 'get_cluster')
        cluster_meta = self.get_cluster_meta_or_404(req, id)
        return {'cluster_meta': cluster_meta}

    def detail(self, req):
        """
        Returns detailed information for all available clusters

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'clusters': [
                {'id': <ID>,
                 'name': <NAME>,
                 'nodes': <NODES>,
                 'networks': <NETWORKS>,
                 'description': <DESCRIPTION>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._enforce(req, 'get_clusters')
        params = self._get_query_params(req)
        try:
            clusters = registry.get_clusters_detail(req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(clusters=clusters)

    @utils.mutating
    @check_params
    def update_cluster(self, req, id, cluster_meta):
        """
        Updates an existing cluster with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque cluster identifier

        :retval Returns the updated cluster information as a mapping
        """
        self._enforce(req, 'update_cluster')
        if 'nodes' in cluster_meta:
            orig_keys = list(eval(cluster_meta['nodes']))
            for host_id in orig_keys:
                self._raise_404_if_host_deleted(req, host_id)
                node = registry.get_host_metadata(req.context, host_id)
                if node['status'] == 'in-cluster':
                    host_cluster = registry.get_host_clusters(
                        req.context, host_id)
                    if host_cluster[0]['cluster_id'] != id:
                        msg = _("Forbidden to add host %s with status "
                                "'in-cluster' in another cluster") % host_id
                        raise HTTPForbidden(explanation=msg)
                if node.get('interfaces', None):
                    interfaces = node['interfaces']
                    input_host_pxe_info = [
                        interface for interface in interfaces if interface.get(
                            'is_deployment', None) == 1]
                    if not input_host_pxe_info and node.get(
                            'os_status', None) != 'active':
                        msg = _(
                            "The host %s has more than one dhcp server, "
                            "please choose one interface for deployment") % \
                            host_id
                        raise HTTPServerError(explanation=msg)
        if 'networks' in cluster_meta:
            orig_keys = list(eval(cluster_meta['networks']))
            for network_id in orig_keys:
                self._raise_404_if_network_deleted(req, network_id)
        orig_cluster_meta = self.get_cluster_meta_or_404(req, id)

        # Do not allow any updates on a deleted cluster.
        # Fix for LP Bug #1060930
        if orig_cluster_meta['deleted']:
            msg = _("Forbidden to update deleted cluster.")
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        try:
            cluster_meta = registry.update_cluster_metadata(req.context,
                                                            id,
                                                            cluster_meta)

        except exception.Invalid as e:
            msg = (_("Failed to update cluster metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find cluster to update: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update cluster: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.warning(utils.exception_to_str(e))
            raise HTTPConflict(body=_('Cluster operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('cluster.update', cluster_meta)

        return {'cluster_meta': cluster_meta}


class ProjectDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["cluster_meta"] = utils.get_cluster_meta(request)
        return result

    def add_cluster(self, request):
        return self._deserialize(request)

    def update_cluster(self, request):
        return self._deserialize(request)


class ProjectSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_cluster(self, response, result):
        cluster_meta = result['cluster_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(cluster=cluster_meta))
        return response

    def update_cluster(self, response, result):
        cluster_meta = result['cluster_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(cluster=cluster_meta))
        return response

    def delete_cluster(self, response, result):
        cluster_meta = result['cluster_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(cluster=cluster_meta))
        return response

    def get_cluster(self, response, result):
        cluster_meta = result['cluster_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(cluster=cluster_meta))
        return response


def create_resource():
    """Projects resource factory method"""
    deserializer = ProjectDeserializer()
    serializer = ProjectSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
