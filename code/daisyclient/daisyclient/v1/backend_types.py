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


class BackendTypesManager(base.ManagerWithFind):
    resource_class = BackendTypes

    def list(self, **kwargs):
        pass

    def get(self):
        """
        get backend types
        """
        url = '/v1/backend_types'
        resp, body = self.client.post(url, headers=None, data=None)
        return BackendTypes(self, body)
