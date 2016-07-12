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

from six import moves

from tempest.api.daisy import base
from tempest import config
CONF = config.CONF
from nose.tools import set_trace
from daisy.common import exception

class DaisyConfigFileTest(base.BaseDaisyTest):

    @classmethod
    def resource_setup(cls):
        super(DaisyConfigFileTest, cls).resource_setup()

    def test_add_config_file(self):
        config_file={'name':'add_config_file',
                    'description':'config_file_test'}
        add_config_file=self.add_config_file(**config_file)
        self.assertEqual('add_config_file', add_config_file.name)

    def test_update_config_file(self):
        config_file_meta={'name':'add_config_file',
                         'description':'config_file_test'}
        add_config_file=self.add_config_file(**config_file_meta)

        update_config_file_meta={'name':'update_config_file'}
        update_config_file=self.update_config_file(add_config_file.id,**update_config_file_meta)

        self.assertEqual('update_config_file', update_config_file.name)

    def test_get_config_file(self):
        config_file_meta={'name':'add_config_file',
                         'description':'config_file_test'}
        add_config_file=self.add_config_file(**config_file_meta)

        get_config_file=self.get_config_file(add_config_file.id)

        self.assertEqual('add_config_file', get_config_file.name)

    def test_list_config_file(self):
        config_file_flag=False
        config_file_meta={'name':'add_config_file',
                         'description':'config_file_test'}
        add_config_set=self.add_config_file(**config_file_meta)
        list_config_file=self.list_config_file()
        config_file_list = [config_file for config_file in list_config_file]
        if config_file_list:
            config_file_flag=True
        self.assertTrue(config_file_flag, "test_list_config_file error")

    def test_delete_config_file(self):
        config_file={'name':'add_config_file',
                    'description':'config_file_test'}
        add_config_file=self.add_config_file(**config_file)
        self.delete_config_file(add_config_file.id)

    def tearDown(self):
        self._clean_all_config_file()
        super(DaisyConfigFileTest, self).tearDown()
