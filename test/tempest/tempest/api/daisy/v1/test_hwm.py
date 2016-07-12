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

from tempest.api.daisy import base
from tempest import config
from fake.logical_network_fake import FakeLogicNetwork as logical_fake
CONF = config.CONF


class DaisyHwmTest(base.BaseDaisyTest):
    @classmethod
    def resource_setup(cls):
        super(DaisyHwmTest, cls).resource_setup()
        cls.fake = logical_fake()

        cls.hwm_meta = {'hwm_ip': '10.43.211.63',
                        'description': 'the first hwm'}

    def test_add_hwm(self):
        hwm = self.add_hwm(**self.hwm_meta)
        self.assertEqual("10.43.211.63", hwm.hwm_ip, "add-hwm failed")

    def test_update_hwm(self):
        update_hwm_meta = {'hwm_ip': '10.43.174.11'}
        add_hwm = self.add_hwm(**self.hwm_meta)
        update_hwm = self.update_hwm(add_hwm.id, **update_hwm_meta)

        self.assertEqual("10.43.174.11", update_hwm.hwm_ip,
                         "update-hwm failed")

    def test_hwm_detail_info(self):
        add_hwm = self.add_hwm(**self.hwm_meta)
        hwm_detail = self.get_hwm_detail(add_hwm.id)
        self.assertEqual("10.43.211.63", hwm_detail.hwm_ip,
                         "test_hwm_detail_info failed")

    def test_hwm_list(self):
        self.add_hwm(**self.hwm_meta)
        hwms = self.list_hwm()
        for hwm in hwms:
            self.assertTrue(hwm != None)

    def test_hwm_delete(self):
        hwm = self.add_hwm(**self.hwm_meta)
        self.delete_hwm(hwm.id)

    def tearDown(self):
        self._clean_all_hwm()
        super(DaisyHwmTest, self).tearDown()
