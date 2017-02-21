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

import copy

from oslo_utils import encodeutils
from oslo_utils import strutils
import six
import six.moves.urllib.parse as urlparse

from daisyclient.common import utils
from daisyclient.openstack.common.apiclient import base

PXE_ENV_CHECK_PARAMS = ('deployment_interface', 'server_ip')

DEFAULT_PAGE_SIZE = 200

SORT_DIR_VALUES = ('asc', 'desc')
SORT_KEY_VALUES = ('id', 'created_at', 'updated_at')

OS_REQ_ID_HDR = 'x-openstack-request-id'


class DeployServer(base.Resource):
    def __repr__(self):
        return "<DeployServer %s>" % self._info

    def update(self, **fields):
        self.manager.update(self, **fields)

    def delete(self, **kwargs):
        return self.manager.delete(self)

    def data(self, **kwargs):
        return self.manager.data(self, **kwargs)


class DeployServerManager(base.ManagerWithFind):
    resource_class = DeployServer

    def _deploy_server_meta_to_headers(self, fields):
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
    def _format_deploy_server_meta_for_user(meta):
        for key in ['size', 'min_ram', 'min_disk']:
            if key in meta:
                try:
                    meta[key] = int(meta[key]) if meta[key] else 0
                except ValueError:
                    pass
        return meta

    def _list(self, url, response_key, obj_class=None, body=None):
        resp, body = self.client.get(url)

        if obj_class is None:
            obj_class = self.resource_class

        data = body[response_key]
        return ([obj_class(self, res, loaded=True) for res in data if res],
                resp)

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

    def get(self, id):
        """get deploy server information by id."""
        pass

    def list(self, **kwargs):
        """Get a list of deploy server.

        :param page_size: number of items to request in each paginated request
        :param limit: maximum number of services to return
        :param marker: begin returning services that appear later in the
                       service ist than that represented by this service id
        :param filters: dict of direct comparison filters that mimics the
                        structure of an service object
        :param return_request_id: If an empty list is provided, populate this
                              list with the request ID value from the header
                              x-openstack-request-id
        :rtype: list of :class:`DeployServer`
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
            url = '/v1/deploy_server?%s' % urlparse.urlencode(qp)
            deploy_servers, resp = self._list(url, "deploy_servers")

            if return_request_id is not None:
                return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

            for deploy_server in deploy_servers:
                yield deploy_server

        return_request_id = kwargs.get('return_req_id', None)

        params = self._build_params(kwargs)

        seen = 0
        while True:
            seen_last_page = 0
            filtered = 0
            for deploy_server in paginate(params, return_request_id):
                last_deploy_server = deploy_server.id

                if (absolute_limit is not None and
                        seen + seen_last_page >= absolute_limit):
                    # Note(kragniz): we've seen enough images
                    return
                else:
                    seen_last_page += 1
                    yield deploy_server

            seen += seen_last_page

            if seen_last_page + filtered == 0:
                """
                Note(kragniz): we didn't get any deploy_servers
                in the last page
                """
                return

            if absolute_limit is not None and seen >= absolute_limit:
                # Note(kragniz): reached the limit of deploy_servers to return
                return

            if page_size and seen_last_page + filtered < page_size:
                """
                Note(kragniz): we've reached the last page
                of the deploy_servers
                """
                return

            # Note(kragniz): there are more deploy_servers to come
            params['marker'] = last_deploy_server
            seen_last_page = 0

    def add(self, **kwargs):
        """Add .

        TODO(bcwaldon): document accepted params
        """
        pass

    def delete(self, id):
        """Delete."""
        pass

    def update(self, id, **kwargs):
        """Update"""
        pass

    def pxe_env_check(self, **kwargs):
        """pxe env check

        TODO(bcwaldon): document accepted params
        """
        fields = {}

        for field in kwargs:
            if field in PXE_ENV_CHECK_PARAMS:
                fields[field] = kwargs[field]
            elif field == 'return_req_id':
                continue
            else:
                msg = "pxe_env_check() got an unexpected "\
                      "keyword argument '%s'"
                raise TypeError(msg % field)

        url = '/v1/deploy_servers/pxe_env_check'
        hdrs = self._deploy_server_meta_to_headers(fields)
        resp, body = self.client.post(url, headers=None, data=hdrs)

        return DeployServer(
            self, self._format_deploy_server_meta_for_user(
                body['deploy_server_meta']))
