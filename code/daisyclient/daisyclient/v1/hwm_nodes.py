# Copyright 2012 OpenStack Foundation
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

import sys
import copy

from oslo_utils import encodeutils
from oslo_utils import strutils
import six

from daisyclient.common import utils
from daisyclient.openstack.common.apiclient import base
from daisyclient.common.http import HTTPClient

reload(sys)
sys.setdefaultencoding('utf-8')

DEFAULT_PAGE_SIZE = 200

SORT_DIR_VALUES = ('asc', 'desc')
SORT_KEY_VALUES = ('serialNo', 'created_at', 'updated_at', 'status')

OS_REQ_ID_HDR = 'x-openstack-request-id'


class Node(base.Resource):
    def __repr__(self):
        return "<Node %s>" % self._info

    def update(self, **fields):
        self.manager.update(self, **fields)

    def delete(self, **kwargs):
        return self.manager.delete(self)

    def data(self, **kwargs):
        return self.manager.data(self, **kwargs)


class NodeManager(base.ManagerWithFind):
    resource_class = Node

    def get_hwm_client(self, hwm_ip):
        if hwm_ip:
            endpoint = "http://" + hwm_ip + ":8089"
            client = HTTPClient(endpoint)
        else:
            client = self.client

        return client

    def _list(self, url, hwm_ip, response_key, obj_class=None, body=None):
        hwm_client = self.get_hwm_client(hwm_ip)
        resp, body = hwm_client.get(url)

        if obj_class is None:
            obj_class = self.resource_class

        data = body[response_key]
        return ([obj_class(self, res, loaded=True) for res in data if res],
                resp)

    def _host_meta_from_headers(self, headers):
        meta = {'properties': {}}
        safe_decode = encodeutils.safe_decode
        for key, value in six.iteritems(headers):
            value = safe_decode(value, incoming='utf-8')
            if key.startswith('x-image-meta-property-'):
                _key = safe_decode(key[22:], incoming='utf-8')
                meta['properties'][_key] = value
            elif key.startswith('x-image-meta-'):
                _key = safe_decode(key[13:], incoming='utf-8')
                meta[_key] = value

        for key in ['is_public', 'protected', 'deleted']:
            if key in meta:
                meta[key] = strutils.bool_from_string(meta[key])

        return self._format_host_meta_for_user(meta)

    def _host_meta_to_headers(self, fields):
        headers = {}
        fields_copy = copy.deepcopy(fields)

        # NOTE(flaper87): Convert to str, headers
        # that are not instance of basestring. All
        # headers will be encoded later, before the
        # request is sent.

        for key, value in six.iteritems(fields_copy):
            headers['%s' % key] = utils.to_str(value)
        return headers

    @staticmethod
    def _format_host_meta_for_user(meta):
        for key in ['size', 'min_ram', 'min_disk']:
            if key in meta:
                try:
                    meta[key] = int(meta[key]) if meta[key] else 0
                except ValueError:
                    pass
        return meta

    def _build_params(self, parameters):
        params = {'limit': parameters.get('page_size', DEFAULT_PAGE_SIZE)}

        if 'marker' in parameters:
            params['marker'] = parameters['marker']

        sort_key = parameters.get('sort_key')
        if sort_key is not None:
            if sort_key in SORT_KEY_VALUES:
                params['sort_key'] = sort_key
            else:
                raise ValueError('sort_key must be one of the following: %s.'
                                 % ', '.join(SORT_KEY_VALUES))

        sort_dir = parameters.get('sort_dir')
        if sort_dir is not None:
            if sort_dir in SORT_DIR_VALUES:
                params['sort_dir'] = sort_dir
            else:
                raise ValueError('sort_dir must be one of the following: %s.'
                                 % ', '.join(SORT_DIR_VALUES))

        filters = parameters.get('filters', {})
        params.update(filters)

        return params

    def list(self, **kwargs):
        """Get a list of nodes.
        :param page_size: number of items to request in each paginated request
        :param limit: maximum number of hosts to return
        :param marker: begin returning hosts that appear later in the host
                       list than that represented by this host id
        :param filters: dict of direct comparison filters that mimics the
                        structure of an host object
        :param return_request_id: If an empty list is provided, populate this
                              list with the request ID value from the header
                              x-openstack-request-id
        :rtype: list of :class:`Host`
        """
        absolute_limit = kwargs.get('limit')
        page_size = kwargs.get('page_size', DEFAULT_PAGE_SIZE)

        def paginate(qp, return_request_id=None):
            for param, value in six.iteritems(qp):
                if isinstance(value, six.string_types):
                    # Note(flaper87) Url encoding should
                    # be moved inside http utils, at least
                    # shouldn't be here.
                    #
                    # Making sure all params are str before
                    # trying to encode them
                    qp[param] = encodeutils.safe_decode(value)

            hwm_ip = kwargs.get('hwm_ip')
            url = '/api/v1.0/hardware/nodes'
            nodes, resp = self._list(url, hwm_ip, "nodes")

            if return_request_id is not None:
                return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

            for node in nodes:
                yield node

        return_request_id = kwargs.get('return_req_id', None)

        params = self._build_params(kwargs)

        seen = 0
        while True:
            seen_last_page = 0
            filtered = 0
            for host in paginate(params, return_request_id):
                last_host = host.serialNo

                if (absolute_limit is not None and
                        seen + seen_last_page >= absolute_limit):
                    # Note(kragniz): we've seen enough images
                    return
                else:
                    seen_last_page += 1
                    yield host

            seen += seen_last_page

            if seen_last_page + filtered == 0:
                # Note(kragniz): we didn't get any hosts in the last page
                return

            if absolute_limit is not None and seen >= absolute_limit:
                # Note(kragniz): reached the limit of hosts to return
                return

            if page_size and seen_last_page + filtered < page_size:
                # Note(kragniz): we've reached the last page of the hosts
                return

            # Note(kragniz): there are more hosts to come
            params['marker'] = last_host
            seen_last_page = 0

    def location(self, **kwargs):
        """Get location of node."""
        hwm_ip = kwargs.get('hwm_ip')
        hwm_id = kwargs.get('hwm_id')
        hwm_client = self.get_hwm_client(hwm_ip)
        url = '/api/v1.0/hardware/nodes/%s/location' % hwm_id
        resp, body = hwm_client.get(url)
        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

        return Node(self, self._format_host_meta_for_user(body))

    def restart(self, **kwargs):
        """Restart node."""
        hdrs = {}
        hwm_ip = kwargs.get('hwm_ip')
        hwm_id = kwargs.get('hwm_id')
        hwm_client = self.get_hwm_client(hwm_ip)
        url = '/api/v1.0/hardware/nodes/%s/restart_actions' % hwm_id
        resp, body = hwm_client.post(url, headers=hdrs, data=hdrs)
        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

        return Node(self, self._format_host_meta_for_user(body))

    def restart_state(self, **kwargs):
        """Get restart state of node."""
        hwm_ip = kwargs.get('hwm_ip')
        action_id = kwargs.get('action_id')
        hwm_client = self.get_hwm_client(hwm_ip)
        url = '/api/v1.0/hardware/nodes/restart_actions/%s' % action_id
        resp, body = hwm_client.get(url)
        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

        return Node(self, self._format_host_meta_for_user(body))

    def set_boot(self, **kwargs):
        """Set boot type of node."""
        hdrs = {}
        hwm_ip = kwargs.get('hwm_ip')
        hwm_id = kwargs.get('hwm_id')
        boot_type = kwargs.get('boot_type')
        hwm_client = self.get_hwm_client(hwm_ip)
        url = '/api/v1.0/hardware/nodes/%s/one_time_boot?from=%s' % \
              (hwm_id, boot_type)
        resp, body = hwm_client.post(url, headers=hdrs, data=hdrs)
        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

        return Node(self, self._format_host_meta_for_user(body))

    def update(self, **kwargs):
        """Update hosts."""
        absolute_limit = kwargs.get('limit')
        page_size = kwargs.get('page_size', DEFAULT_PAGE_SIZE)

        hwm_ip = kwargs.get('hwm_ip')
        hwm_client = self.get_hwm_client(hwm_ip)
        hwm_url = '/api/v1.0/hardware/nodes'
        hwm_resp, hwm_body = hwm_client.get(hwm_url)
        hwm_body['hwm_ip'] = hwm_ip

        def paginate(qp, return_request_id=None):
            for param, value in six.iteritems(qp):
                if isinstance(value, six.string_types):
                    # Note(flaper87) Url encoding should
                    # be moved inside http utils, at least
                    # shouldn't be here.
                    #
                    # Making sure all params are str before
                    # trying to encode them
                    qp[param] = encodeutils.safe_decode(value)

            hdrs = self._host_meta_to_headers(hwm_body)
            url = '/v1/hwm_nodes'
            resp, body = self.client.post(url, headers={}, data=hdrs)
            obj_class = self.resource_class
            hosts = [obj_class(self, res, loaded=True) for res in body['nodes']
                     if res]

            if return_request_id is not None:
                return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

            for host in hosts:
                yield host

        return_request_id = kwargs.get('return_req_id', None)

        params = self._build_params(kwargs)

        seen = 0
        while True:
            seen_last_page = 0
            filtered = 0
            for host in paginate(params, return_request_id):
                last_host = host.id

                if (absolute_limit is not None and
                        seen + seen_last_page >= absolute_limit):
                    # Note(kragniz): we've seen enough images
                    return
                else:
                    seen_last_page += 1
                    yield host

            seen += seen_last_page

            if seen_last_page + filtered == 0:
                # Note(kragniz): we didn't get any hosts in the last page
                return

            if absolute_limit is not None and seen >= absolute_limit:
                # Note(kragniz): reached the limit of hosts to return
                return

            if page_size and seen_last_page + filtered < page_size:
                # Note(kragniz): we've reached the last page of the hosts
                return

            # Note(kragniz): there are more hosts to come
            params['marker'] = last_host
            seen_last_page = 0

    def cloud_state(self, **kwargs):
        """To inform provider the cloud state."""
        hdrs = dict()
        fields = dict()
        provider_ip = kwargs.pop('provider_ip')
        operation = kwargs.get('operation')
        fields["envName"] = kwargs.get('name')
        fields["envUrl"] = kwargs.get('url')
        hwm_url = '/v1/hwm'
        resp, hwm_body = self.client.get(hwm_url)
        hwms_ip = [hwm['hwm_ip'] for hwm in hwm_body['hwm']]
        if provider_ip in hwms_ip:
            url = '/api/envChangeNotification'
            provider_client = self.get_hwm_client(provider_ip)
            if operation == "add":
                hdrs = {"add_environment": fields}
            if operation == "delete":
                hdrs = {"delete_environment": fields}

            resp, body = provider_client.post(url, data=hdrs)
        else:
            return

    def get_min_mac(self, hwm_id):
        params = dict()
        resp, body = self.client.get('/v1/nodes')
        hosts = body.get('nodes')
        if hosts:
            for host in hosts:
                if hwm_id == host.get('hwm_id'):
                    params['host_id'] = host['id']
                    resp, host_body = self.client.get('/v1/nodes/%s' %
                                                      host['id'])
                    interfaces = host_body['host'].get('interfaces')
                    if interfaces:
                        mac_list = [interface['mac'] for interface in
                                    interfaces if interface.get('mac')]
                        if mac_list:
                            params['mac'] = min(mac_list)
        return params

    def pxe_host_discover(self, **kwargs):
        """Pxe host discover."""
        hdrs = dict()
        hwm_ip = kwargs.get('hwm_ip')
        hwm_id = kwargs.get('hwm_id')
        hwm_client = self.get_hwm_client(hwm_ip)
        pxe_url = '/api/v1.0/hardware/nodes/%s/one_time_boot?from=pxe' % \
                  hwm_id
        resp, pxe_body = hwm_client.post(pxe_url, headers=hdrs, data=hdrs)
        params = self.get_min_mac(hwm_id)
        params['status'] = "DISCOVERING"
        resp, body = self.client.post(
            '/v1/pxe_discover/nodes', headers=params, data=params)
        restart_url = '/api/v1.0/hardware/nodes/%s/restart_actions' % \
                      hwm_id
        resp, restart_body = hwm_client.post(restart_url, headers=hdrs,
                                             data=hdrs)
        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

        return Node(self, self._format_host_meta_for_user(restart_body))
