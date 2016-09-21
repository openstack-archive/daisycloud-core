# Copyright 2014 OpenStack Foundation
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

import urllib

from tempest.common import service_client


class DatabaseFlavorsClientJSON(service_client.ServiceClient):

    def list_db_flavors(self, params=None):
        url = 'flavors'
        if params:
            url += '?%s' % urllib.urlencode(params)

        resp, body = self.get(url)
        self.expected_success(200, resp.status)
        return service_client.ResponseBodyList(resp, self._parse_resp(body))

    def get_db_flavor_details(self, db_flavor_id):
        resp, body = self.get("flavors/%s" % str(db_flavor_id))
        self.expected_success(200, resp.status)
        return service_client.ResponseBody(resp, self._parse_resp(body))
