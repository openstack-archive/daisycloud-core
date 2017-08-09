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

from daisy_tempest import base
import time
from daisyclient import exc as client_exc
from fake.logical_network_fake import FakeLogicNetwork as logical_fake


class DaisyDiscoverHostTest(base.BaseDaisyTest):
    @classmethod
    def resource_setup(cls):
        super(DaisyDiscoverHostTest, cls).resource_setup()
        cls.fake = logical_fake()

        cls.host_meta = {'ip': '127.0.0.1',
                         'passwd': 'ossdbg1'}

    def test_add_dicover_host(self):
        host = self.add_discover_host(**self.host_meta)
        self.assertEqual("init", host.status, "add discover host failed")
        self.delete_discover_host(host.id)

    def test_delete_dicover_host(self):
        host = self.add_discover_host(**self.host_meta)
        self.delete_discover_host(host.id)

    def test_list_discover_host(self):
        host_meta = {'ip': '127.0.0.2', 'passwd': 'ossdbg2'}
        self.add_discover_host(**self.host_meta)
        self.add_discover_host(**host_meta)
        query_hosts = self.list_discover_host()
        hosts = [host for host in query_hosts]
        host_count = len(hosts)
        self.assertEqual(2, host_count, "list discover host failed")

    def test_update_discover_host(self):
        add_host_meta = {'ip': '127.0.0.2',
                         'passwd': 'ossdbg2',
                         'user': 'root'}
        host_1 = self.add_discover_host(**add_host_meta)
        self.assertEqual("root", host_1.user, "add discover host failed")

        update_host_meta = {'ip': '127.0.0.2',
                            'passwd': 'ossdbg1',
                            'user': 'root2'}
        update_host = self.update_discover_host(host_1.id,
                                                **update_host_meta)
        self.assertEqual("ossdbg1",
                         update_host.passwd,
                         "update discover host failed")
        self.assertEqual("root2",
                         update_host.user,
                         "update discover host failed")

    def test_get_discover_host_detail(self):
        add_host_meta = {'ip': '127.0.0.2',
                         'passwd': 'ossdbg2',
                         'user': 'root'}
        host_1 = self.add_discover_host(**add_host_meta)
        host_info = self.get_discover_host_detail(host_1.id)
        self.assertEqual("root",
                         host_info.user,
                         "get discover host failed")
        self.assertEqual("ossdbg2",
                         host_info.passwd,
                         "get discover host failed")
        self.assertEqual("127.0.0.2",
                         host_info.ip,
                         "get discover host failed")

    def test_add_discover_host_without_passwd(self):
        add_host_meta = {'ip': '127.0.0.2', 'user': 'root'}
        ex = self.assertRaises(client_exc.HTTPBadRequest,
                               self.add_discover_host,
                               **add_host_meta)
        self.assertIn("PASSWD parameter can not be None.", str(ex))

    def test_add_discover_host_with_repeat_ip(self):
        # add_host_meta = {'ip': '127.0.0.2',
        #                  'passwd': 'ossdbg2',
        #                  'user': 'root'}
        # host_1 = self.add_discover_host(**add_host_meta)
        # ex = self.assertRaises(client_exc.HTTPForbidden,
        #                        self.add_discover_host, **add_host_meta)
        # self.assertIn("403 Forbidden: ip %s already existed."
        #               % add_host_meta['ip'], str(ex))
        pass

    def test_discover_host(self):
        daisy_endpoint = "http://127.0.0.1:19292"

        def GetMiddleStr(content, startStr, endStr):
            startIndex = content.index(startStr)
            if startIndex >= 0:
                startIndex += len(startStr)
            endIndex = content.index(endStr)
            return content[startIndex:endIndex]

        local_ip = GetMiddleStr(daisy_endpoint, 'http://', ':19292')
        discover_host_meta1 = {}
        discover_host_meta1['ip'] = local_ip
        discover_host_meta1['passwd'] = 'ossdbg1'
        self.add_discover_host(**discover_host_meta1)

        discover_host = {}
        self.discover_host(**discover_host)
        time.sleep(8)
        discover_flag = 'false'
        while 1:
            print("discovring!!!!!!!!")
            if discover_flag == 'true':
                break
            discovery_host_list_generator = self.list_discover_host()
            discovery_host_list = [discover_host_tmp for discover_host_tmp
                                   in discovery_host_list_generator]
            for host in discovery_host_list:
                if host.status == 'DISCOVERY_SUCCESSFUL':
                    discover_flag = 'true'
                else:
                    discover_flag = 'false'
        self.assertEqual("true", discover_flag, "discover host failed")

    def tearDown(self):
        if self.host_meta.get('user', None):
            del self.host_meta['user']
        if self.host_meta.get('status', None):
            del self.host_meta['status']

        self._clean_all_discover_host()
        super(DaisyDiscoverHostTest, self).tearDown()
