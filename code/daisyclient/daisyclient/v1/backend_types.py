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
import six

from daisyclient.common import utils
from daisyclient.openstack.common.apiclient import base

BACKEND_TYPES_PARAMS = ()
OS_REQ_ID_HDR = 'x-openstack-request-id'


class BackendTypes(base.Resource):
    def __repr__(self):
        return "<BackendTypes %s>" % self._info

    def update(self, **fields):
        self.manager.update(self, **fields)

    def delete(self, **kwargs):
        return self.manager.delete(self)

    def data(self, **kwargs):
        return self.manager.data(self, **kwargs)


class BackendTypesManager(base.ManagerWithFind):
    resource_class = BackendTypes

    def _get_meta_to_headers(self, fields):
        headers = {}
        fields_copy = copy.deepcopy(fields)

        # NOTE(flaper87): Convert to str, headers
        # that are not instance of basestring. All
        # headers will be encoded later, before the
        # request is sent.

        for key, value in six.iteritems(fields_copy):
            headers['%s' % key] = utils.to_str(value)
        return headers

    def list(self, **kwargs):
        pass

    def get(self, **kwargs):
        """
        get backend types
        """
        fields = {}
        for field in kwargs:
            if field in BACKEND_TYPES_PARAMS:
                fields[field] = kwargs[field]
            else:
                msg = 'get() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        url = '/v1/backend_types'
        hdrs = self._get_meta_to_headers(fields)
        resp, body = self.client.post(url, headers=None, data=hdrs)
        return BackendTypes(self, body)
