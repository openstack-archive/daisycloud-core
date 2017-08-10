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
from daisy_tempest import base
from fake.logical_network_fake import FakeLogicNetwork as logical_fake
from fake.logical_network_fake import FakeDiscoverHosts


class DaisyHostTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyHostTest, cls).resource_setup()
        cls.fake = logical_fake()

        cls.host_meta = copy.deepcopy(FakeDiscoverHosts().daisy_data[0])
        cls.host_meta_interfaces = {
            'type': 'ether',
            'name': 'enp129s0f0',
            'mac': '4c:09:b4:b2:78:8a',
            'ip': '99.99.1.121',
            'netmask': '255.255.255.0',
            'is_deployment': 'True',
            'slaves': 'eth1',
            'pci': '1',
            'gateway': '99.99.1.1'}

    def test_add_host(self):
        host = self.add_fake_node(0)
        self.assertEqual("init", host.status, "add-host failed")

    def tearDown(self):
        if self.host_meta.get('cluster', None):
            del self.host_meta['cluster']
        if self.host_meta.get('role', None):
            del self.host_meta['role']
        if self.host_meta.get('os_version', None):
            del self.host_meta['os_version']
        if self.host_meta.get('os_status', None):
            del self.host_meta['os_status']
        self._clean_all_host()
        self._clean_all_cluster()
        # self._clean_all_physical_node()
        super(DaisyHostTest, self).tearDown()
