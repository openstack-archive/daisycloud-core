# Copyright 2012 OpenStack Foundation.
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

import mock
from daisy import test
from daisy.api.v1 import hosts
from daisy.context import RequestContext
import webob
import json as jsonutils
#import daisy.registry.client.v1.api as registry
#import daisy.api.backends.common as daisy_cmn
from daisy.tests.api import fakes
from daisy.db.sqlalchemy import api


def set_host_meta():
    host_meta = {}
    host_meta['id'] = 'd04cfa48-c3ad-477c-b2ac-95bee7582181'
    return host_meta


def set_orig_host_meta():
    orig_host_meta = {}
    orig_host_meta['id'] = 'd04cfa48-c3ad-477c-b2ac-95bee7582181'
    return orig_host_meta


def set_discover_hosts_meta():

    fake_discover_hosts = \
        [{u'status': u'DISCOVERY_SUCCESSFUL',
          u'deleted': False,
          u'ip': u'10.43.203.132',
          u'created_at': u'2016-07-19T02:27:55.000000',
          u'updated_at': u'2016-07-19T02:28:18.000000',
          u'passwd': u'ossdbg1',
          u'mac': u'3c:da:2a:e3:23:47',
          u'cluster_id': None,
          u'user': u'root',
          u'host_id': u'f1367d9d-97f1-4d61-968c-07e6a25fb5ee',
          u'message': u'discover host for 10.43.203.132 successfully!',
          u'deleted_at': None,
          u'id': u'70a4a673-af06-4286-82b0-68a5af4dedc1'}]
    return fake_discover_hosts


def check_result(host_meta, discover_state):
    host_meta['discover_state'] = discover_state
    return host_meta


class MockLoggingHandler(object):

    """Mock logging handler to check for expected logs.

    Messages are available from an instance's ``messages`` dict, in order,
    indexed by a lowercase log level string (e.g., 'debug', 'info', etc.).
    """

    def __init__(self):
        self.messages = {'debug': [], 'info': [], 'warning': [], 'error': []}

    def debug(self, message, *args, **kwargs):
        self.messages['debug'].append(message)

    def info(self, message, *args, **kwargs):
        self.messages['info'].append(message)

    def error(self, message, *args, **kwargs):
        self.messages['error'].append(message)

    def reset(self):
        for message in self.messages:
            del self.messages[message][:]


class testLogDebug(test.TestCase):
    _log_handler = MockLoggingHandler()
    _log_messages = _log_handler.messages

    def setUp(self):
        super(testLogDebug, self).setUp()
        self.controller = hosts.Controller()
        self._log_handler.reset()

    @mock.patch('daisy.api.v1.hosts.Controller.get_network_meta_or_404')
    def test__raise_404_if_network_deleted(self,
                                           mock_get_network_meta_or_404):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        mock_get_network_meta_or_404.return_value = None
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller._raise_404_if_network_deleted,
                          req, None)

    @mock.patch('daisy.api.v1.hosts.Controller.get_cluster_meta_or_404')
    def test__raise_404_if_cluster_deleted(self,
                                           mock_get_cluster_meta_or_404):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        mock_get_cluster_meta_or_404.return_value = None
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller._raise_404_if_cluster_deleted,
                          req, None)

    @mock.patch('daisy.api.v1.hosts.Controller.get_role_meta_or_404')
    def test__raise_404_if_role_deleted(self,
                                        mock_get_role_meta_or_404):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        mock_get_role_meta_or_404.return_value = None
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller._raise_404_if_role_deleted,
                          req, None)


class TestHostsApiConfig(test.TestCase):
    _log_handler = MockLoggingHandler()
    _log_messages = _log_handler.messages

    def setUp(self):
        super(TestHostsApiConfig, self).setUp()
        self.controller = hosts.Controller()
        self.host_meta = {'id': '1',
                          'check_item': 'ipmi'}
        self._log_handler.reset()
        self.return_meta_of_add_host = {u'host': {
            u'os_version_id': u'42b34b9e-2ea3-428d-bf34-8cdc4cc3916a',
            u'config_set_id': None,
            u'root_disk': u'sda',
            u'os_status': u'init',
            u'isolcpus': None,
            u'updated_at': u'2016-07-17T03:33:20.000000',
            u'group_list': u'core,base',
            u'deleted_at': None,
            u'id': u'd04cfa48-c3ad-477c-b2ac-95bee7582181',
            u'description': u'default',
            u'hwm_ip': None,
            u'os_version_file': None,
            u'dmi_uuid': u'03000200-0400-0500-0006-000700080009',
            u'hwm_id': None,
            u'pci_high_cpuset': None,
            u'status': u'init',
            u'vcpu_pin_set': None,
            u'deleted': False,
            u'os_progress': 0,
            u'ipmi_passwd': u'superuser',
            u'resource_type': u'baremetal',
            u'ipmi_user': u'albert',
            u'hugepagesize': None,
            u'name': u'host-192-168-1-6',
            u'created_at': u'2016-07-15T01:40:55.000000',
            u'messages': None,
            u'hugepages': 0,
            u'os_cpus': None,
            u'ipmi_addr': u'10.43.203.230',
            u'root_pwd': u'ossdbg1',
            u'dvs_high_cpuset': None,
            u'dvs_cpus': None,
            u'swap_lv_size': 4096,
            u'root_lv_size': 102400}}

        self.orig_host_meta = {
            u'os_version_id': None,
            u'config_set_id': None,
            u'root_disk': u'sda',
            u'os_status': u'init',
            u'isolcpus': None,
            u'updated_at': u'2016-07-21T02:05:08.000000',
            u'group_list': u'core,base',
            u'cluster': u'test',
            u'deleted_at': None,
            u'id': u'4b6970c5-ef1d-4599-a1d7-70175a888e6d',
            u'description': u'default',
            u'hwm_ip': None,
            u'os_version_file': None,
            u'system': {},
            u'os_version': {u'id': None,
                            u'name': None, u'desc': u''},
            u'role': [u'COMPUTER'],
            u'memory': {u'total': u'        1850020 kB',
                        u'phy_memory_1': {u'slots': u' 2',
                                          u'devices_1': {
                                              u'frequency': u'',
                                              u'type': u' DIMM SDRAM',
                                              u'size': u' 4096 MB'},
                                          u'maximum_capacity': u' 4 GB',
                                          u'devices_2': {
                                              u'frequency': u' 3 ns',
                                              u'type': u' DIMM SDRAM',
                                              u'size': u' 8192 MB'}}},
            u'hwm_id': None,
            u'pci_high_cpuset': None,
            u'status': u'with-role',
            u'vcpu_pin_set': None,
            u'deleted': False,
            u'interfaces': [
                {u'type': u'ether',
                 u'name': u'enp132s0f2292',
                 u'is_deployment': False,
                 u'deleted': False,
                 u'ip': None,
                 u'created_at': u'2016-07-19T02:16:30.000000',
                 u'slave2': None,
                 u'updated_at': u'2016-07-19T02:16:30.000000',
                 u'id': u'542a7a9c-b9d9-4701-af69-46f23b161b57',
                 u'vswitch_type': u'ovs',
                 u'mac': u'4c:09:b4:b2:80:8c',
                 u'pci': u'0000:84:00.2',
                 u'slave1': None,
                 u'mode': None,
                 u'assigned_networks': [{u'ip': u'', u'name': u'physnet1'}],
                 u'host_id': u'4b6970c5-ef1d-4599-a1d7-70175a888e6d',
                 u'deleted_at': None,
                 u'netmask': None,
                 u'gateway': None},
                {u'type': u'ether',
                 u'name': u'enp132s0f1292',
                 u'is_deployment': False,
                 u'deleted': False,
                 u'ip': None,
                 u'created_at': u'2016-07-19T02:16:30.000000',
                 u'slave2': None,
                 u'updated_at': u'2016-07-19T02:16:30.000000',
                 u'id': u'68f9b842-41f9-4691-95e7-5cbe29c01a58',
                 u'vswitch_type': u'',
                 u'mac': u'4c:09:b4:b2:80:8b',
                 u'pci': u'0000:84:00.1',
                 u'slave1': None, u'mode': None,
                 u'assigned_networks': [
                     {u'ip': u'192.168.10.3',
                      u'name': u'PUBLICAPI'}],
                 u'host_id': u'4b6970c5-ef1d-4599-a1d7-70175a888e6d',
                 u'deleted_at': None,
                 u'netmask': None,
                 u'gateway': None},
                {u'type': u'ether',
                 u'name': u'enp132s0f3292',
                 u'is_deployment': False,
                 u'deleted': False,
                 u'ip': None,
                 u'created_at': u'2016-07-19T02:16:30.000000',
                 u'slave2': None,
                 u'updated_at': u'2016-07-19T02:16:30.000000',
                 u'id': u'fa2b0877-f34a-4fd6-bf73-1bf82491e99e',
                 u'vswitch_type': u'',
                 u'mac': u'4c:09:b4:b2:80:8d',
                 u'pci': u'0000:84:00.3',
                 u'slave1': None,
                 u'mode': None,
                 u'assigned_networks': [],
                 u'host_id': u'4b6970c5-ef1d-4599-a1d7-70175a888e6d',
                 u'deleted_at': None,
                 u'netmask': None,
                 u'gateway': None},
                {u'type': u'ether',
                 u'name': u'enp132s0f0292',
                 u'is_deployment': True,
                 u'deleted': False,
                 u'ip': u'99.99.1.102',
                 u'created_at': u'2016-07-19T02:16:30.000000',
                 u'slave2': None,
                 u'updated_at': u'2016-07-19T02:16:30.000000',
                 u'id': u'fef70adb-8001-4ec7-9790-1a38ce9a20bf',
                 u'vswitch_type': u'',
                 u'mac': u'4c:09:b4:b2:80:8a',
                 u'pci': u'0000:84:00.0',
                 u'slave1': None,
                 u'mode': None,
                 u'assigned_networks': [
                     {u'ip': u'192.168.1.6',
                      u'name': u'MANAGEMENT'}],
                 u'host_id': u'4b6970c5-ef1d-4599-a1d7-70175a888e6d',
                 u'deleted_at': None,
                 u'netmask': u'255.255.255.0',
                 u'gateway': None}],
            u'os_progress': 0,
            u'ipmi_passwd': u'keystone',
            u'resource_type': u'baremetal',
            u'position': u'',
            u'ipmi_user': u'albert',
            u'hugepagesize': None,
            u'name': u'host-192-168-1-6',
            u'dmi_uuid': u'03000200-0400-0500-0006-000700080009',
            u'created_at': u'2016-07-15T01:40:55.000000',
            u'disks': {
                u'sda': {u'name': u'sda',
                         u'extra': [u'scsi-3500003956831a6d8',
                                    u'wwn-0x500003956831a6d8'],
                         u'removable': u'',
                         u'model': u'',
                         u'disk': u'pci-0000:01:00.0-sas-'
                                  u'0x500003956831a6da-lun-0',
                         u'size': u' 200127266816 bytes'},
                u'sdb': {u'name': u'sdb', u'extra': [u'', u''],
                         u'removable': u'',
                         u'model': u'',
                         u'disk': u'ip-192.163.1.237:3260-iscsi-'
                                  u'iqn.2099-01.cn.com.'
                                  u'zte:usp.spr-4c:09:b4:b0:01:31-lun-0',
                         u'size': u' 136870912000 bytes'},
                u'sdc': {u'name': u'sdc', u'extra': [u'', u''],
                         u'removable': u'',
                         u'model': u'',
                         u'disk': u'ip-192.163.1.237:3260-'
                                  u'iscsi-iqn.2099-01.cn.com.'
                                  u'zte:usp.spr-4c:09:b4:b0:01:31-lun-1',
                         u'size': u'122122547200 bytes'}},
            u'messages': None,
            u'hugepages': 0,
            u'os_cpus': None,
            u'ipmi_addr': u'10.43.203.232',
            u'root_pwd': u'ossdbg1',
            u'dvs_high_cpuset': None,
            u'dvs_cpus': None,
            u'cpu': {u'real': 1, u'spec_1': {
                u'model': u' Pentium(R) Dual-Core CPU E5700@ 3.00GHz',
                u'frequency': 3003}, u'total': 2, u'spec_2': {
                u'model': u' Pentium(R) Dual-Core CPU E5700@ 3.00GHz',
                u'frequency': 3003}}, u'swap_lv_size': 4096,
            u'root_lv_size': 102400}

        self.return_meta_of_get_host = \
            {'host': {
                u'os_version_id': None,
                u'config_set_id': None,
                u'root_disk': u'sda',
                u'os_status': u'init',
                u'isolcpus': None,
                u'updated_at': u'2016-07-17T03:33:20.000000',
                u'group_list': u'core,base',
                u'deleted_at': None,
                u'id': u'4b6970c5-ef1d-4599-a1d7-70175a888e6d',
                u'description': u'default',
                u'os_version': {
                    u'id': None,
                    u'name': None,
                    u'desc': u''},
                u'hwm_ip': None,
                u'os_version_file': None,
                u'system': {},
                u'deleted': False,
                u'memory': {
                    u'total': u'1850020 kB',
                    u'phy_memory_1': {
                        u'slots': u' 2',
                        u'devices_1': {
                            u'frequency': u'',
                            u'type': u' DIMM SDRAM',
                            u'size': u' 4096 MB'},
                        u'maximum_capacity': u' 4 GB',
                        u'devices_2': {
                            u'frequency': u' 3 ns',
                            u'type': u' DIMM SDRAM',
                            u'size': u' 8192 MB'}}},
                u'hwm_id': None,
                u'pci_high_cpuset': None,
                u'status': u'init',
                u'vcpu_pin_set': None,
                u'dmi_uuid': u'03000200-0400-0500-0006-000700080009',
                u'interfaces': [
                    {u'type': u'ether',
                     u'name': u'enp132s0f1292',
                     u'is_deployment': False,
                     u'deleted': False,
                     u'ip': None,
                     u'created_at': u'2016-07-15T01:43:23.000000',
                     u'slave2': None,
                     u'updated_at': u'2016-07-15T01:43:23.000000',
                     u'id': u'61c5e703-247b-4882-b49b-bb5cda0b7f4e',
                     u'vswitch_type': u'',
                     u'mac': u'4c:09:b4:b2:78:8b',
                     u'pci': u'0000:84:00.1',
                     u'slave1': None,
                     u'mode': None,
                     u'assigned_networks': [],
                     u'host_id': u'd04cfa48-c3ad-477c-b2ac-95bee7582181',
                     u'deleted_at': None,
                     u'netmask': None,
                     u'gateway': None},
                    {u'type': u'ether',
                     u'name': u'enp132s0f2292',
                     u'is_deployment': False,
                     u'deleted': False,
                     u'ip': None,
                     u'created_at': u'2016-07-15T01:43:23.000000',
                     u'slave2': None,
                     u'updated_at': u'2016-07-15T01:43:23.000000',
                     u'id': u'79388234-d3f8-42cc-b93e-fd6216575bb9',
                     u'vswitch_type': u'',
                     u'mac': u'4c:09:b4:b2:78:8c',
                     u'pci': u'0000:84:00.2',
                     u'slave1': None,
                     u'mode': None,
                     u'assigned_networks': [],
                     u'host_id': u'd04cfa48-c3ad-477c-b2ac-95bee7582181',
                     u'deleted_at': None,
                     u'netmask': None,
                     u'gateway': None},
                    {u'type': u'ether',
                     u'name': u'enp132s0f3292',
                     u'is_deployment': False,
                     u'deleted': False,
                     u'ip': None,
                     u'created_at': u'2016-07-15T01:43:24.000000',
                     u'slave2': None,
                     u'updated_at': u'2016-07-15T01:43:24.000000',
                     u'id': u'a15a4c4a-4ab2-4d9d-b7ac-93bc6190406e',
                     u'vswitch_type': u'',
                     u'mac': u'4c:09:b4:b2:78:8d',
                     u'pci': u'0000:84:00.3',
                     u'slave1': None,
                     u'mode': None,
                     u'assigned_networks': [],
                     u'host_id': u'd04cfa48-c3ad-477c-b2ac-95bee7582181',
                     u'deleted_at': None,
                     u'netmask': None,
                     u'gateway': None},
                    {u'type': u'ether',
                     u'name': u'enp132s0f0292',
                     u'is_deployment': True,
                     u'deleted': False,
                     u'ip': u'99.99.1.100',
                     u'created_at': u'2016-07-15T01:43:23.000000',
                     u'slave2': None,
                     u'updated_at': u'2016-07-15T01:43:23.000000',
                     u'id': u'b596e78d-6b19-4044-9e59-a96dad0348ba',
                     u'vswitch_type': u'',
                     u'mac': u'4c:09:b4:b2:78:8a',
                     u'pci': u'0000:84:00.0',
                     u'slave1': None,
                     u'mode': None,
                     u'assigned_networks': [],
                     u'host_id': u'd04cfa48-c3ad-477c-b2ac-95bee7582181',
                     u'deleted_at': None,
                     u'netmask': u'255.255.255.0',
                     u'gateway': None}],
                u'os_progress': 0,
                u'ipmi_passwd': u'superuser',
                u'resource_type': u'baremetal',
                u'position': u'',
                u'ipmi_user': u'albert',
                u'hugepagesize': None,
                u'name': u'host-192-168-1-6',
                u'created_at': u'2016-07-15T01:40:55.000000',
                u'disks': {
                    u'sda': {u'name': u'sda',
                             u'extra': [
                                 u'scsi-3500003956831a6d8',
                                 u'wwn-0x500003956831a6d8'],
                             u'removable': u'',
                             u'model': u'',
                             u'disk': u'pci-0000:01:00.0-sas-'
                                      u'0x500003956831a6da-lun-0',
                             u'size': u' 200127266816 bytes'},
                    u'sdb': {u'name': u'sdb',
                             u'extra': [u'',
                                        u''],
                             u'removable': u'',
                             u'model': u'',
                             u'disk': u'ip-192.163.1.237:3260-iscsi-iqn.'
                                      u'2099-01.cn.com.zte:usp.spr-'
                                      u'4c:09:b4:b0:01:31-lun-0',
                             u'size': u' 136870912000 bytes'},
                    u'sdc': {u'name': u'sdc',
                             u'extra': [u'',
                                        u''],
                             u'removable': u'',
                             u'model': u'',
                             u'disk': u'ip-192.163.1.237:3260-iscsi-iqn.'
                                      u'2099-01.cn.com.zte:usp.spr-'
                                      u'4c:09:b4:b0:01:31-lun-1',
                             u'size': u'122122547200 bytes'}},
                u'messages': None,
                u'hugepages': 0,
                u'os_cpus': None,
                u'ipmi_addr': u'10.43.203.230',
                u'root_pwd': u'ossdbg1',
                u'dvs_high_cpuset': None,
                u'dvs_cpus': None,
                u'cpu': {u'real': 1,
                         u'spec_1': {
                             u'model': u' Pentium(R) Dual-Core  CPU '
                                       u'   E5700  @ 3.00GHz',
                             u'frequency': 3003},
                         u'total': 2,
                         u'spec_2': {
                             u'model': u' Pentium(R) Dual-Core  CPU'
                                       u'      E5700  @ 3.00GHz',
                             u'frequency': 3003}},
                u'swap_lv_size': 4096,
                u'root_lv_size': 102400}}

        self.return_meta_of_get_version = {
            "version": {"status": "unused",
                        "name": "redhat123.iso",
                        "checksum": "60489112c277a1816c247ba150862fbf",
                        "created_at": "2016-07-12T02:24:27.000000",
                        "size": 1089536,
                        "updated_at": "2016-07-12T02:24:27.000000",
                        "type": "redhat 7.0",
                        "id": "42b34b9e-2ea3-428d-bf34-8cdc4cc3916a",
                        "description": "azsdadsad"}}

        self.return_meta_of_list_version = {"version": [
            {u'status': u'used',
             u'name': u'redhat123.iso',
             u'deleted': False,
             u'checksum': u'ded1f72769478a74afbd339755feccf7',
             u'created_at': u'2016-07-15T09:49:36.000000',
             u'description': u'',
             u'updated_at': u'2016-07-15T09:49:36.000000',
             u'version': None,
             u'owner': None, u'deleted_at': None, u'type':
                 u'redhat 7.0',
             u'id': u'42b34b9e-2ea3-428d-bf34-8cdc4cc3916a',
             u'size': 6133760},
            {u'status': u'unused',
             u'name': u'haha',
             u'deleted': False,
             u'checksum': None,
             u'created_at': u'2016-07-16T07:10:56.000000',
             u'description': None,
             u'updated_at': u'2016-07-16T07:10:56.000000',
             u'version': None,
             u'owner': None,
             u'deleted_at': None,
             u'type': u'redhat7.0',
             u'id': u'1d6f8a93-dabc-4965-a299-df6d2e5f8558',
             u'size': None},
            {u'status': u'unused',
             u'name': u'InstallZteNotesComApp(1).exe',
             u'deleted': False,
             u'checksum': u'1c41f3cf20efd8fc0288d42ba9dd72e3',
             u'created_at': u'2016-07-18T00:54:42.000000',
             u'description': u'',
             u'updated_at': u'2016-07-18T00:54:42.000000',
             u'version': None,
             u'owner': None,
             u'deleted_at': None,
             u'type': u'tecs',
             u'id': u'4a7b2f0e-3e5f-4f3c-8ce8-1e64e1a66c68',
             u'size': 3002945},
        ]}

        self.return_meta_of_list_role = {
            "roles":
                [{u'db_vip': None,
                  u'status': u'init',
                  u'mongodb_vip': None,
                  u'vip': u'192.168.1.5',
                  u'cluster_id': u'4d3156ba-a4a5-4f41-914c-7a148170f281',
                  u'ntp_server': None,
                  u'deleted_at': None,
                  u'id': u'47da25ec-3d13-4d20-a7ad-1f29ea4cc50a',
                  u'glance_lv_size': 0,
                  u'db_lv_size': 0, u'progress': 0,
                  u'type': u'default',
                  u'nova_lv_size': 0,
                  u'glance_vip': None,
                  u'config_set_id': u'9b3d7d4c-d007-4903-addf-03c7f531c784',
                  u'description': u'Controller role,'
                                  u'backup type is loadbalance',
                  u'deleted': False,
                  u'updated_at': u'2016-07-19T02:16:04.000000',
                  u'role_type': u'CONTROLLER_LB',
                  u'deployment_backend': u'tecs',
                  u'name': u'CONTROLLER_LB',
                  u'created_at': u'2016-07-18T02:34:52.000000',
                  u'messages': None,
                  u'public_vip': None,
                  u'disk_location': u'local',
                  u'config_set_update_progress': 0},
                 {u'db_vip': u'192.168.1.4',
                  u'status': u'init',
                  u'mongodb_vip': None,
                  u'vip': u'192.168.1.2',
                  u'cluster_id': u'4d3156ba-a4a5-4f41-914c-7a148170f281',
                  u'ntp_server': u'',
                  u'deleted_at': None,
                  u'id': u'3f3e72e4-194d-4caa-ba34-9b3eb16e4cda',
                  u'glance_lv_size': 51200,
                  u'db_lv_size': 0, u'progress': 0,
                  u'type': u'default',
                  u'nova_lv_size': 0,
                  u'glance_vip': u'192.168.1.3',
                  u'config_set_id': u'99519270-1ff7-45bb-b255-d2af17c85cf1',
                  u'description': u'Controller role,backup type is'
                                  u' HA,active/standby',
                  u'deleted': False,
                  u'updated_at': u'2016-07-19T02:16:05.000000',
                  u'role_type': u'CONTROLLER_HA',
                  u'deployment_backend': u'tecs',
                  u'name': u'CONTROLLER_HA',
                  u'created_at': u'2016-07-18T02:34:52.000000',
                  u'messages': None,
                  u'public_vip': u'192.168.1.4',
                  u'disk_location': u'local',
                  u'config_set_update_progress': 0},
                 {u'db_vip': None,
                  u'status': u'init',
                  u'mongodb_vip': None,
                  u'vip': None,
                  u'cluster_id': u'4d3156ba-a4a5-4f41-914c-7a148170f281',
                  u'ntp_server': None,
                  u'deleted_at': None,
                  u'id': u'06ba4992-e665-42d4-b6c0-617e068adbc0',
                  u'glance_lv_size': 0,
                  u'db_lv_size': 0, u'progress': 0,
                  u'type': u'default',
                  u'nova_lv_size': 0,
                  u'glance_vip': None,
                  u'config_set_id': u'e9834102-e430-44f9-9376-7161cb0eab6b',
                  u'description': u'Compute role',
                  u'deleted': False,
                  u'updated_at': u'2016-07-18T02:34:52.000000',
                  u'role_type': u'COMPUTER',
                  u'deployment_backend': u'tecs',
                  u'name': u'COMPUTER',
                  u'created_at': u'2016-07-18T02:34:52.000000',
                  u'messages': None,
                  u'public_vip': None,
                  u'disk_location': u'local',
                  u'config_set_update_progress': 0},
                 {u'db_vip': None,
                  u'status': u'init',
                  u'mongodb_vip': None,
                  u'vip': None,
                  u'cluster_id': None,
                  u'ntp_server': None,
                  u'deleted_at': None,
                  u'id': u'225bb223-ea33-4f78-bb53-111deb8fb856',
                  u'glance_lv_size': 0,
                  u'db_lv_size': 0, u'progress': 0,
                  u'type': u'template',
                  u'nova_lv_size': 0,
                  u'glance_vip': None,
                  u'config_set_id': None,
                  u'description': u'Role for zenic nfmanager.',
                  u'deleted': False,
                  u'updated_at': u'2014-10-18T06:59:00.000000',
                  u'role_type': u'ZENIC_NFM',
                  u'deployment_backend': u'zenic',
                  u'name': u'ZENIC_NFM',
                  u'created_at': u'2014-10-18T06:59:00.000000',
                  u'messages': None,
                  u'public_vip': None,
                  u'disk_location': u'local',
                  u'config_set_update_progress': 0},
                 {u'db_vip': None,
                  u'status': u'init',
                  u'mongodb_vip': None,
                  u'vip': None,
                  u'cluster_id': None,
                  u'ntp_server': None,
                  u'deleted_at': None,
                  u'id': u'afb4e0ff-434f-4f49-aa0c-4998350bf028',
                  u'glance_lv_size': 0,
                  u'db_lv_size': 0, u'progress': 0,
                  u'type': u'template',
                  u'nova_lv_size': 0,
                  u'glance_vip': None,
                  u'config_set_id': None,
                  u'description': u'Role for zenic controller.',
                  u'deleted': False,
                  u'updated_at': u'2014-10-18T06:58:06.000000',
                  u'role_type': u'ZENIC_CTL',
                  u'deployment_backend': u'zenic',
                  u'name': u'ZENIC_CTL',
                  u'created_at': u'2014-10-18T06:58:06.000000',
                  u'messages': None,
                  u'public_vip': None,
                  u'disk_location': u'local',
                  u'config_set_update_progress': 0},
                 {u'db_vip': None,
                  u'status': u'init',
                  u'mongodb_vip': None,
                  u'vip': None,
                  u'cluster_id': None,
                  u'ntp_server': None,
                  u'deleted_at': None,
                  u'id': u'13ee2c6d-5cec-484e-bd39-20a8f17c8a79',
                  u'glance_lv_size': 0,
                  u'db_lv_size': 0, u'progress': 0,
                  u'type': u'template',
                  u'nova_lv_size': 0,
                  u'glance_vip': None,
                  u'config_set_id': None,
                  u'description': u'Role for proton.',
                  u'deleted': False,
                  u'updated_at': u'2014-10-15T07:48:57.000000',
                  u'role_type': u'PROTON',
                  u'deployment_backend': u'proton',
                  u'name': u'PROTON',
                  u'created_at': u'2014-10-15T07:48:57.000000',
                  u'messages': None,
                  u'public_vip': None,
                  u'disk_location': u'local',
                  u'config_set_update_progress': 0},
                 {u'db_vip': None,
                  u'status': u'init',
                  u'mongodb_vip': None,
                  u'vip': None,
                  u'cluster_id': None,
                  u'ntp_server': None,
                  u'deleted_at': None,
                  u'id': u'c38b1e59-c5e7-4e84-8876-ae2f2bdcf09b',
                  u'glance_lv_size': 0,
                  u'db_lv_size': 0, u'progress': 0,
                  u'type': u'template',
                  u'nova_lv_size': 0,
                  u'glance_vip': None,
                  u'config_set_id': None,
                  u'description': u'Compute role',
                  u'deleted': False,
                  u'updated_at': u'2014-10-15T07:48:55.000000',
                  u'role_type': u'COMPUTER',
                  u'deployment_backend': u'tecs',
                  u'name': u'COMPUTER',
                  u'created_at': u'2014-10-15T07:48:55.000000',
                  u'messages': None,
                  u'public_vip': None,
                  u'disk_location': u'local',
                  u'config_set_update_progress': 0},
                 {u'db_vip': None,
                  u'status': u'init',
                  u'mongodb_vip': None,
                  u'vip': None,
                  u'cluster_id': None,
                  u'ntp_server': u'',
                  u'deleted_at': None,
                  u'id': u'508afb41-f301-4bbb-9043-7aa618097caf',
                  u'glance_lv_size': 51200,
                  u'db_lv_size': 0, u'progress': 0,
                  u'type': u'template',
                  u'nova_lv_size': 0,
                  u'glance_vip': None,
                  u'config_set_id': None,
                  u'description': u'Controller role,backup type is'
                                  u' HA,active/standby',
                  u'deleted': False,
                  u'updated_at': u'2014-10-17T08:19:36.000000',
                  u'role_type': u'CONTROLLER_HA',
                  u'deployment_backend': u'tecs',
                  u'name': u'CONTROLLER_HA',
                  u'created_at': u'2014-10-15T07:48:54.000000',
                  u'messages': None,
                  u'public_vip': u'',
                  u'disk_location': u'local',
                  u'config_set_update_progress': 0},
                 {u'db_vip': None,
                  u'status': u'init',
                  u'mongodb_vip': None,
                  u'vip': None,
                  u'cluster_id': None,
                  u'ntp_server': None,
                  u'deleted_at': None,
                  u'id': u'1ba53c70-94b1-4301-a9d3-a9ba0ed373b7',
                  u'glance_lv_size': 0,
                  u'db_lv_size': 0, u'progress': 0,
                  u'type': u'template',
                  u'nova_lv_size': 0,
                  u'glance_vip': None,
                  u'config_set_id': None,
                  u'description': u'Controller role,'
                                  u'backup type is loadbalance',
                  u'deleted': False,
                  u'updated_at': u'2014-10-15T07:48:53.000000',
                  u'role_type': u'CONTROLLER_LB',
                  u'deployment_backend': u'tecs',
                  u'name': u'CONTROLLER_LB',
                  u'created_at': u'2014-10-15T07:48:53.000000',
                  u'messages': None,
                  u'public_vip': None,
                  u'disk_location': u'local',
                  u'config_set_update_progress': 0}]
        }
        self.return_meta_of_get_cluster = {
            u'vlan_end': None,
            u'updated_at': u'2016-07-19T02:16:05.000000',
            u'owner': None,
            u'networking_parameters': {
                u'vni_range': [None, None],
                u'public_vip': u'192.168.1.4',
                u'net_l23_provider': None,
                u'base_mac': u'',
                u'gre_id_range': [None,
                                  None],
                u'vlan_range': [None, None],
                u'segmentation_type': None},
            u'gre_id_start': None,
            u'deleted_at': None,
            u'networks': [
                u'd3d60abf-c8d1-49ec-9731-d500b1ef4acb',
                u'bc99206e-0ac2-4b6e-9cd3-d4cdd11c208e',
                u'8518a8a5-e5fb-41ba-877f-eef386e3376f',
                u'8048a7d7-7b85-4621-837c-adea08acdbbd',
                u'6aacb625-99f2-4a95-b98f-ec0af256eb55',
                u'4ad601b0-19e2-4feb-b41a-6e3af5153e2a'],
            u'hwm_ip': u'',
            u'id': u'4d3156ba-a4a5-4f41-914c-7a148170f281',
            u'base_mac': u'',
            u'auto_scale': 0,
            u'target_systems': u'os+tecs',
            u'vni_end': None,
            u'gre_id_end': None,
            u'nodes': [
                u'6e3a0ab9-fff6-459b-8bf1-9b6681efbfb0',
                u'd25666c1-651a-4cd7-875a-41a52fddaf6b',
                u'd04cfa48-c3ad-477c-b2ac-95bee7582181',
                u'4b6970c5-ef1d-4599-a1d7-70175a888e6d'],
            u'description': u'',
            u'deleted': False,
            u'routers': [],
            u'logic_networks': [],
            u'net_l23_provider': None,
            u'vlan_start': None,
            u'name': u'test',
            u'created_at': u'2016-07-18T02:34:52.000000',
            u'public_vip': u'192.168.1.4',
            u'use_dns': 1,
            u'vni_start': None,
            u'segmentation_type': None}
        self.return_meta_of_list_cluster = {
            "clusters":
                [{u'vlan_end': None,
                  u'updated_at': u'2016-07-19T02:16:05.000000',
                  u'owner': None,
                  u'gre_id_start': None,
                  u'deleted_at': None,
                  u'networks': [
                      u'd3d60abf-c8d1-49ec-9731-d500b1ef4acb',
                      u'bc99206e-0ac2-4b6e-9cd3-d4cdd11c208e',
                      u'8518a8a5-e5fb-41ba-877f-eef386e3376f',
                      u'8048a7d7-7b85-4621-837c-adea08acdbbd',
                      u'6aacb625-99f2-4a95-b98f-ec0af256eb55',
                      u'4ad601b0-19e2-4feb-b41a-6e3af5153e2a',
                      u'6abc03db-1103-403d-881c-6f8991be5f72',
                      u'6296c21b-ee82-41ea-a679-f96284c76f3f',
                      u'4adf8372-e994-48e6-a352-dd534d428ace',
                      u'31e5f873-dd08-4860-a160-8c0136ceef6f',
                      u'08599e05-0938-4749-aed0-0b860715dbdc',
                      u'071e6df6-8ed4-4e44-aff2-4f76661f8c4b'],
                  u'hwm_ip': u'',
                  u'id': u'4d3156ba-a4a5-4f41-914c-7a148170f281',
                  u'base_mac': u'',
                  u'gre_id_end': None,
                  u'target_systems': u'os+tecs',
                  u'vni_end': None,
                  u'auto_scale': 0, u'nodes': [
                      u'6e3a0ab9-fff6-459b-8bf1-9b6681efbfb0',
                      u'd25666c1-651a-4cd7-875a-41a52fddaf6b',
                      u'd04cfa48-c3ad-477c-b2ac-95bee7582181',
                      u'4b6970c5-ef1d-4599-a1d7-70175a888e6d'],
                  u'status': u'init',
                  u'description': u'',
                  u'deleted': False,
                  u'net_l23_provider': None,
                  u'vlan_start': None,
                  u'name': u'test',
                  u'created_at': u'2016-07-18T02:34:52.000000',
                  u'public_vip': u'192.168.1.4',
                  u'use_dns': 1,
                  u'vni_start': None,
                  u'segmentation_type': None},
                 {u'vlan_end': None,
                  u'updated_at': u'2016-07-21T02:58:32.000000',
                  u'owner': None,
                  u'gre_id_start': None,
                  u'deleted_at': None,
                  u'networks': [
                      u'd3d60abf-c8d1-49ec-9731-d500b1ef4acb',
                      u'bc99206e-0ac2-4b6e-9cd3-d4cdd11c208e',
                      u'8518a8a5-e5fb-41ba-877f-eef386e3376f',
                      u'8048a7d7-7b85-4621-837c-adea08acdbbd',
                      u'6aacb625-99f2-4a95-b98f-ec0af256eb55',
                      u'4ad601b0-19e2-4feb-b41a-6e3af5153e2a',
                      u'6abc03db-1103-403d-881c-6f8991be5f72',
                      u'6296c21b-ee82-41ea-a679-f96284c76f3f',
                      u'4adf8372-e994-48e6-a352-dd534d428ace',
                      u'31e5f873-dd08-4860-a160-8c0136ceef6f',
                      u'08599e05-0938-4749-aed0-0b860715dbdc',
                      u'071e6df6-8ed4-4e44-aff2-4f76661f8c4b'],
                  u'hwm_ip': u'',
                  u'id': u'46703334-27f4-4837-8eef-e82000af2cb7',
                  u'base_mac': u'',
                  u'gre_id_end': None,
                  u'target_systems': u'os+tecs',
                  u'vni_end': None,
                  u'auto_scale': 0,
                  u'status': u'init',
                  u'description': u'',
                  u'deleted': False,
                  u'net_l23_provider': None,
                  u'vlan_start': None,
                  u'name': u'whl123',
                  u'created_at': u'2016-07-21T02:58:31.000000',
                  u'public_vip': u'1.1.1.1',
                  u'use_dns': 1,
                  u'vni_start': None,
                  u'segmentation_type': None}]
        }
        self.return_meta_of_update_host = {
            u'host':
                {
                    u'os_version_id': u'42b34b9e-2ea3-428d-bf34-8cdc4cc3916a',
                    u'config_set_id': None,
                    u'root_disk': u'sda',
                    u'os_status': u'init',
                    u'isolcpus': None,
                    u'updated_at': u'2016-07-21T03:21:33.000000',
                    u'group_list': u'core,base',
                    u'deleted_at': None,
                    u'id': u'4b6970c5-ef1d-4599-a1d7-70175a888e6d',
                    u'description': u'default',
                    u'hwm_ip': None,
                    u'os_version_file': "/var/lib/daisy/versionfile"
                                        "/os/redhat123.iso",
                    u'dmi_uuid': u'03000200-0400-0500-0006-000700080009',
                    u'hwm_id': None,
                    u'pci_high_cpuset': None,
                    u'status': u'with-role',
                    u'vcpu_pin_set': None,
                    u'deleted': False,
                    u'os_progress': 0,
                    u'ipmi_passwd': u'keystone',
                    u'resource_type': u'baremetal',
                    u'ipmi_user': u'albert',
                    u'hugepagesize': None,
                    u'name': u'host-192-168-1-6',
                    u'created_at': u'2016-07-15T01:40:55.000000',
                    u'messages': None,
                    u'hugepages': 0,
                    u'os_cpus': None,
                    u'ipmi_addr': u'10.43.203.232',
                    u'root_pwd': u'ossdbg1',
                    u'dvs_high_cpuset': None,
                    u'dvs_cpus': None,
                    u'swap_lv_size': 4096,
                    u'root_lv_size': 102400}}

        self.hwm_host_meta = [{u'links': [{u'uri': u'/api/v1.0/hardware/nodes/'
                                                   u'26LXND2/allocation',
                                           u'rel': u'allocation'}],
                               u'interfaces': [{u'mac': u'14:9E:CF:FE:62:21',
                                                u'description': u'Ethernet',
                                                u'bandwidth': u'',
                                                u'name': u'NIC.Integrated.1',
                                                u'adapterName': u''}],
                               u'hardwareType': u'BladeServer: DELL-M1000E',
                               u'cpuCore': 28,
                               u'disk': 557,
                               u'id': u'26LXND2',
                               u'cpuFrequency': u'2400MHz',
                               u'serialNo': u'26LXND2',
                               u'self': u'/api/v1.0/hardware/nodes/26LXND2',
                               u'hardwareStatus': u'normal', u'memory': 160.0},
                              {u'links': [{u'uri': u'/api/v1.0/hardware/nodes/'
                                                   u'26MXND2/allocation',
                                           u'rel': u'allocation'}],
                               u'interfaces': [{u'mac': u'14:9E:CF:FE:62:E4',
                                                u'description': u'Ethernet',
                                                u'bandwidth': u'',
                                                u'name': u'NIC.Integrated.1',
                                                u'adapterName': u''}],
                               u'hardwareType': u'BladeServer: DELL-M1000E',
                               u'cpuCore': 28,
                               u'disk': 557,
                               u'id': u'26MXND2',
                               u'cpuFrequency': u'2400MHz',
                               u'serialNo': u'26MXND2',
                               u'self': u'/api/v1.0/hardware/nodes/26MXND2',
                               u'hardwareStatus': u'normal',
                               u'memory': 160.0}]
        self.return_meta_of_host_role = {
            "role": {
                u'db_vip': None,
                u'status': u'init',
                u'mongodb_vip': None,
                u'vip': u'192.168.1.5',
                u'cluster_id': u'4d3156ba-a4a5-4f41-914c-7a148170f281',
                u'ntp_server': None,
                u'deleted_at': None,
                u'id': u'47da25ec-3d13-4d20-a7ad-1f29ea4cc50a',
                u'glance_lv_size': 0,
                u'db_lv_size': 0, u'progress': 0,
                u'type': u'default',
                u'nova_lv_size': 0,
                u'glance_vip': None,
                u'config_set_id': u'9b3d7d4c-d007-4903-addf-03c7f531c784',
                u'description': u'Controller role,backup type is loadbalance',
                u'deleted': False,
                u'updated_at': u'2016-07-19T02:16:04.000000',
                u'role_type': u'CONTROLLER_LB',
                u'deployment_backend': u'tecs',
                u'name': u'CONTROLLER_LB',
                u'created_at': u'2016-07-18T02:34:52.000000',
                u'messages': None,
                u'public_vip': None,
                u'disk_location': u'local',
                u'config_set_update_progress': 0}}

    def fake_do_request(self, method, path, **params):
        res = mock.Mock()
        host_id = "4b6970c5-ef1d-4599-a1d7-70175a888e6d"
        version_id = "42b34b9e-2ea3-428d-bf34-8cdc4cc3916a"
        cluster_id = "4d3156ba-a4a5-4f41-914c-7a148170f281"
        if method == "GET" and path == "/versions/%s" % version_id:
            get_result = self.return_meta_of_get_version
            res.read.return_value = jsonutils.dumps(get_result)
            return res
        if method == "GET" and path == "/versions/list":
            list_result = self.return_meta_of_list_version
            res.read.return_value = jsonutils.dumps(list_result)
            return res
        if method == "GET" and path == "/roles/detail":
            list_result = self.return_meta_of_list_role
            res.read.return_value = jsonutils.dumps(list_result)
            return res
        if method == "GET" and path == "/clusters/%s" % cluster_id:
            get_result = self.return_meta_of_get_cluster
            res.read.return_value = jsonutils.dumps(get_result)
            return res
        if method == "GET" and path == "/clusters":
            list_result = self.return_meta_of_list_cluster
            res.read.return_value = jsonutils.dumps(list_result)
            return res

        if method == "PUT" and path == "/nodes/%s" % host_id:
            update_result = self.return_meta_of_update_host
            res.read.return_value = jsonutils.dumps(update_result)
            return res
        if method == "GET" and path == "/nodes/%s" % host_id:
            get_result = self.return_meta_of_get_host
            res.read.return_value = jsonutils.dumps(get_result)
            return res
        role_ids = ["47da25ec-3d13-4d20-a7ad-1f29ea4cc50a",
                    "3f3e72e4-194d-4caa-ba34-9b3eb16e4cda",
                    "06ba4992-e665-42d4-b6c0-617e068adbc0",
                    "225bb223-ea33-4f78-bb53-111deb8fb856",
                    "afb4e0ff-434f-4f49-aa0c-4998350bf028",
                    "13ee2c6d-5cec-484e-bd39-20a8f17c8a79",
                    "c38b1e59-c5e7-4e84-8876-ae2f2bdcf09b",
                    "508afb41-f301-4bbb-9043-7aa618097caf",
                    "1ba53c70-94b1-4301-a9d3-a9ba0ed373b7"]
        role_paths = ["/roles/%s/hosts" % role_id for role_id in role_ids]
        if method == "GET" and path in role_paths:
            get_result = self.return_meta_of_host_role
            res.read.return_value = jsonutils.dumps(get_result)
            return res

    def test_get_group_list_when_has_input(self):
        host_meta = set_host_meta()
        host_meta['group_list'] = 'core'
        orig_host_meta = set_orig_host_meta()
        orig_host_meta['group_list'] = 'core,base'
        os_version_type = 'redhat 7.0'
        host_meta, group_list = self.controller. \
            _get_group_list(host_meta, orig_host_meta, os_version_type)
        self.assertEqual(host_meta['group_list'], 'core')
        self.assertEqual(group_list, 'core')

    def test_get_group_list_when_has_no_input(self):
        host_meta = set_host_meta()
        orig_host_meta = set_orig_host_meta()
        orig_host_meta['group_list'] = 'core,base'
        os_version_type = 'redhat 7.0'
        host_meta, group_list = self.controller. \
            _get_group_list(host_meta, orig_host_meta, os_version_type)
        self.assertEqual(group_list, 'core,base')

    def test_get_group_list_when_has_input_and_origin(self):
        host_meta = set_host_meta()
        orig_host_meta = set_orig_host_meta()
        os_version_type = 'redhat 7.0'
        host_meta, group_list = self.controller. \
            _get_group_list(host_meta, orig_host_meta, os_version_type)
        self.assertEqual(host_meta['group_list'], 'core,base')
        self.assertEqual(group_list, 'core,base')

    def test_get_group_list_when_has_input_and_origin_centos(self):
        host_meta = set_host_meta()
        orig_host_meta = set_orig_host_meta()
        os_version_type = 'centos 7.0'
        host_meta, group_list = self.controller. \
            _get_group_list(host_meta, orig_host_meta, os_version_type)
        self.assertEqual(host_meta['group_list'], 'core,base')
        self.assertEqual(group_list, 'core,base')

    def test_get_os_version_when_host_meta_has_os_version_id(self):
        host_meta = set_host_meta()
        host_meta['os_version'] = '42b34b9e-2ea3-428d-bf34-8cdc4cc3916a'
        orig_host_meta = set_orig_host_meta()
        os_version = self.controller._get_os_version(host_meta,
                                                     orig_host_meta)
        self.assertEqual(host_meta['os_version'], os_version)

    def test_get_os_version_when_host_meta_has_no_os_version_id(self):
        host_meta = set_host_meta()
        orig_host_meta = set_orig_host_meta()
        orig_host_meta['os_version_id'] = '42b34b9e-2ea3-428d-' \
                                          'bf34-8cdc4cc3916b'
        orig_host_meta['os_version_file'] = None
        os_version = self.controller._get_os_version(host_meta,
                                                     orig_host_meta)
        self.assertEqual(orig_host_meta['os_version_id'], os_version)

    def test_get_os_version_when_host_and_orig_host_has_os_version_id(self):
        host_meta = set_host_meta()
        host_meta['os_version'] = '42b34b9e-2ea3-428d-bf34-8cdc4cc3916a'
        orig_host_meta = set_orig_host_meta()
        orig_host_meta['os_version_id'] = '42b34b9e-2ea3-428d-' \
                                          'bf34-8cdc4cc3916b'
        os_version = self.controller._get_os_version(host_meta,
                                                     orig_host_meta)
        self.assertEqual(host_meta['os_version'], os_version)

    def test_get_os_version_when_host_meta_has_os_version_file(self):
        host_meta = set_host_meta()
        host_meta['os_version'] = '/var/lib/daisy/versionfile/os/redhat123.iso'
        orig_host_meta = set_orig_host_meta()
        os_version = self.controller._get_os_version(host_meta,
                                                     orig_host_meta)
        self.assertEqual(host_meta['os_version'], os_version)

    def test_get_os_version_when_host_meta_has_no_os_version_file(self):
        host_meta = set_host_meta()
        orig_host_meta = set_orig_host_meta()
        orig_host_meta['os_version_id'] = None
        orig_host_meta['os_version_file'] = '/var/lib/daisy/' \
                                            'versionfile/os/redhat321.iso'
        os_version = self.controller._get_os_version(host_meta,
                                                     orig_host_meta)
        self.assertEqual(orig_host_meta['os_version_file'], os_version)

    def test_get_os_version_when_host_and_orig_host_has_os_version_file(self):
        host_meta = set_host_meta()
        host_meta['os_version'] = '/var/lib/daisy/versionfile/os' \
                                  '/redhat123.iso'
        orig_host_meta = set_orig_host_meta()
        orig_host_meta['os_version_id'] = '/var/lib/daisy/versionfile' \
                                          '/os/redhat321.iso'
        os_version = self.controller._get_os_version(host_meta,
                                                     orig_host_meta)
        self.assertEqual(host_meta['os_version'], os_version)

    @mock.patch('daisy.registry.client.v1.client.RegistryClient.do_request')
    def test_get_os_version_type_when_input_os_version_id(self,
                                                          mock_do_request):
        os_version = '42b34b9e-2ea3-428d-bf34-8cdc4cc3916a'
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        mock_do_request.side_effect = self.fake_do_request
        os_version_type = self.controller._get_os_version_type(req,
                                                               os_version)
        self.assertEqual("redhat 7.0", os_version_type)

    def test_check_group_list_without_core_redhat(self):
        os_version_type = "redhat 7.0"
        group_list = 'base'
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller._check_group_list,
                          os_version_type, group_list)

    def test_check_group_list_without_base_redhat(self):
        os_version_type = "redhat 7.0"
        group_list = 'core'
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller._check_group_list,
                          os_version_type, group_list)

    def test_check_group_list_without_core_centos(self):
        os_version_type = "centos 7.0"
        group_list = 'base'
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller._check_group_list,
                          os_version_type, group_list)

    @mock.patch('daisy.registry.client.v1.client.RegistryClient.do_request')
    def test_check_os_version_when_input_id(self, mock_do_request):
        os_version = '12334b9e-2ea3-428d-bf34-8cdc4cc39123'
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        mock_do_request.side_effect = self.fake_do_request
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller._check_os_version, req,
                          os_version)

    # @mock.patch('daisy.registry.client.v1.client.RegistryClient.do_request')
    # def test_check_os_version_when_input_file(self, mock_do_request):
    #     os_version = '/var/lib/daisy/redhat1234.iso'
    #     req = webob.Request.blank('/')
    #     req.context = RequestContext(is_admin=True,
    #                                  user='fake user',
    #                                  tenant='fake tenant')
    #     mock_do_request.side_effect = self.fake_do_request
    #     self.assertRaises(webob.exc.HTTPForbidden,
    #                       self.controller._check_os_version, req,
    #                       os_version)

    @mock.patch("daisy.api.v1.hosts.Controller._check_os_version")
    @mock.patch("daisy.api.v1.hosts.Controller._get_os_version")
    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    @mock.patch('daisy.registry.client.v1.client.RegistryClient.do_request')
    def test_update_host_with_os_version_id(self, mock_do_request,
                                            mock_get_host_meta_or_404,
                                            mock_get_os_version,
                                            mock_check_os_version):
        host_meta = set_host_meta()
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_meta['os_version'] = '42b34b9e-2ea3-428d-bf34-8cdc4cc3916a'
        id = "4b6970c5-ef1d-4599-a1d7-70175a888e6d"
        mock_get_host_meta_or_404.return_value = self.orig_host_meta
        #self.controller.get_host_meta_or_404 = mock.Mock(
        #    return_value=self.orig_host_meta)
        mock_get_os_version.return_value = \
            "42b34b9e-2ea3-428d-bf34-8cdc4cc3916a"
        #self.controller._get_os_version = mock.Mock(
        #    return_value="42b34b9e-2ea3-428d-bf34-8cdc4cc3916a")
        mock_check_os_version.return_value = None
        #self.controller._check_os_version = mock.Mock(return_value=None)
        mock_do_request.side_effect = self.fake_do_request
        update_host = self.controller.update_host(req, id, host_meta)
        self.assertEqual('42b34b9e-2ea3-428d-bf34-8cdc4cc3916a',
                         update_host['host_meta']['os_version_id'])

    @mock.patch("daisy.api.v1.hosts.Controller._check_os_version")
    @mock.patch("daisy.api.v1.hosts.Controller._get_os_version")
    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    @mock.patch('daisy.registry.client.v1.client.RegistryClient.do_request')
    def test_update_host_with_os_version_file(self, mock_do_request,
                                              mock_get_host_meta_or_404,
                                              mock_get_os_version,
                                              mock_check_os_version):
        host_meta = set_host_meta()
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_meta['os_version'] = "/var/lib/daisy/redhat123.iso"
        id = "4b6970c5-ef1d-4599-a1d7-70175a888e6d"
        mock_get_host_meta_or_404.return_value = self.orig_host_meta
        #self.controller.get_host_meta_or_404 = mock.Mock(
        #    return_value=self.orig_host_meta)
        mock_get_os_version.return_value = "/var/lib/daisy/redhat123.iso"
        #self.controller._get_os_version = mock.Mock(
        #    return_value="/var/lib/daisy/redhat123.iso")
        mock_check_os_version.return_value = None
        #self.controller._check_os_version = mock.Mock(return_value=None)
        mock_do_request.side_effect = self.fake_do_request
        update_host = self.controller.update_host(req, id, host_meta)
        self.assertEqual('/var/lib/daisy/versionfile/os/redhat123.iso',
                         update_host['host_meta']['os_version_file'])

    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    def test_update_host_with_dvs_sriov_and_bond_no_VF(
            self, mock_get_host_meta_or_404):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        id = "4b6970c5-ef1d-4599-a1d7-70175a888e6d"
        orig_host_meta = {'id': '4b6970c5-ef1d-4599-a1d7-70175a888e6d',
                          "deleted": None}
        host_meta = {
            "cluster": "111111111111-22222222222-3333333333333",
            "interfaces": [
                {u'type': u'bond',
                 u'name': u'bond0',
                 u'slave2': u'enp_slave2',
                 u'vswitch_type': u'dvs,sriov(direct)',
                 u'slave1': u'enp_slave1',
                 u'assigned_networks': [{u'ip': u'', u'name': u'physnet1'}],
                 u'slaves': {u'enp_slave1', u'enp_slave2'}
                 },
                {u'type': u'ether',
                 u'name': u'enp_slave1',
                 u'vswitch_type': u'',
                 u'pci': u'0000:84:00.1',
                 u'is_support_vf': False},
                {u'type': u'ether',
                 u'name': u'enp_slave2',
                 u'vswitch_type': u'',
                 u'pci': u'0000:84:00.2',
                 u'is_support_vf': False}]}
        mock_get_host_meta_or_404.return_value = orig_host_meta
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update_host,
                          req, id, host_meta)

    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    def test_update_host_with_dvs_sriov_and_inf_no_VF(
            self, mock_get_host_meta_or_404):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        id = "4b6970c5-ef1d-4599-a1d7-70175a888e6d"
        orig_host_meta = {'id': '4b6970c5-ef1d-4599-a1d7-70175a888e6d',
                          "deleted": None}
        host_meta = {
            "cluster": "111111111111-22222222222-3333333333333",
            "interfaces": [
                {u'type': u'ether',
                 u'name': u'enp_slave1',
                 u'vswitch_type': u'dvs,sriov(direct)',
                 u'pci': u'0000:84:00.1',
                 u'is_support_vf': False},
                {u'type': u'ether',
                 u'name': u'enp_slave2',
                 u'vswitch_type': u'',
                 u'pci': u'0000:84:00.2',
                 u'is_support_vf': False}]}
        mock_get_host_meta_or_404.return_value = orig_host_meta
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update_host,
                          req, id, host_meta)

    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    def test_update_host_with_wrong_type(
            self, mock_get_host_meta_or_404):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        id = "4b6970c5-ef1d-4599-a1d7-70175a888e6d"
        orig_host_meta = {'id': '4b6970c5-ef1d-4599-a1d7-70175a888e6d',
                          "deleted": None}
        host_meta = {
            "cluster": "111111111111-22222222222-3333333333333",
            "interfaces": [
                {u'type': u'ether',
                 u'name': u'enp_slave1',
                 u'vswitch_type': u'dvs,sriov(macvtap)',
                 u'pci': u'0000:84:00.1',
                 u'is_support_vf': False},
                {u'type': u'ether',
                 u'name': u'enp_slave2',
                 u'vswitch_type': u'',
                 u'pci': u'0000:84:00.2',
                 u'is_support_vf': False}]}
        mock_get_host_meta_or_404.return_value = orig_host_meta
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update_host,
                          req, id, host_meta)

    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    def test_update_host_with_no_pci(
            self, mock_get_host_meta_or_404):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        id = "4b6970c5-ef1d-4599-a1d7-70175a888e6d"
        orig_host_meta = {'id': '4b6970c5-ef1d-4599-a1d7-70175a888e6d',
                          "deleted": None}
        host_meta = {
            "cluster": "111111111111-22222222222-3333333333333",
            "interfaces": [
                {u'type': u'ether',
                 u'name': u'enp_slave1',
                 u'vswitch_type': u'dvs,sriov(direct)',
                 u'pci': u'0000:84:00.1',
                 u'is_support_vf': False},
                {u'type': u'ether',
                 u'name': u'enp_slave2',
                 u'vswitch_type': u'',
                 u'is_support_vf': False}]}
        mock_get_host_meta_or_404.return_value = orig_host_meta
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.update_host,
                          req, id, host_meta)

    def test_check_interface_on_update_host_no_bond_slave(self):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        id = "4b6970c5-ef1d-4599-a1d7-70175a888e6d"
        orig_host_meta = {'id': '4b6970c5-ef1d-4599-a1d7-70175a888e6d',
                          "deleted": None}
        host_meta = {
            "cluster": "111111111111-22222222222-3333333333333",
            "interfaces": [
                {u'type': u'bond',
                 u'name': u'enp_slave1',
                 u'vswitch_type': u'dvs,sriov(direct)',
                 u'pci': u'0000:84:00.1',
                 u'is_support_vf': False},
                {u'type': u'ether',
                 u'name': u'enp_slave2',
                 u'vswitch_type': u'',
                 u'pci': u'0000:84:00.2',
                 u'is_support_vf': False}]}
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller._check_interface_on_update_host,
                          req, host_meta, orig_host_meta)

    @mock.patch("daisy.api.backends.common.check_discover_state_with_no_hwm")
    @mock.patch("daisy.registry.client.v1.api.get_host_clusters")
    @mock.patch("daisy.api.v1.hosts.Controller.get_cluster_meta_or_404")
    def test_verify_host_cluster_with_no_discover(
            self, mock_get_cluster_meta_or_404,
            mock_get_host_clusters, mock_check_discover_state_with_no_hwm):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            'hwm_id': '1',
            "cluster": "66e57b5c-fc4f-4c09-a550-b057ff4f5452",
            "name": "abcddd"}
        orig_host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "status": "in-cluster",
            "name": "host-1"}
        host_cluster = [{
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "cluster_id": "66e57b5c-fc4f-4c09-a550-b057ff4f5452",
            "status": "in-cluster",
            "name": "host-1"}]
        mock_get_cluster_meta_or_404.return_value =\
            {"id": "66e57b5c-fc4f-4c09-a550-b057ff4f5452"}
        mock_get_host_clusters.return_value = host_cluster
        mock_check_discover_state_with_no_hwm.return_value = \
            check_result(orig_host_meta, '')
        #registry.get_host_clusters = mock.Mock(return_value=host_cluster)
        #self.controller.get_cluster_meta_or_404 = \
        #    mock.Mock(return_value={"id": "66e57b5c-fc4f"
        #                                 "-4c09-a550-b057ff4f5452"})
        #daisy_cmn.check_discover_state_with_no_hwm = \
        #    mock.Mock(return_value=check_result(orig_host_meta, ''))
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller._verify_host_cluster, req,
                          "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
                          orig_host_meta, host_meta)

    @mock.patch('logging.Logger')
    def test_host_check_ipmi_with_active_host(self, mock_log):
        host_id = '1'
        host = {'os_status': 'active',
                'id': '1',
                'name': 'host_1'}
        mock_log.side_effect = self._log_handler
        self.assertEqual({
            'ipmi_check_result': 'active host do not need ipmi check'},
            self.controller._host_ipmi_check(host_id, host))

    @mock.patch('logging.Logger')
    def test_host_check_ipmi_with_no_ipmi_addr(self, mock_log):
        host_id = '1'
        host = {'id': '1',
                'name': 'test',
                'os_status': 'init',
                'ipmi_addr': None,
                'ipmi_user': 'zteroot',
                'ipmi_passwd': 'superuser'}
        mock_log.side_effect = self._log_handler
        self.assertEqual({'ipmi_check_result': "No ipmi address "
                                               "configed for host 1, "
                                               "please check"},
                         self.controller._host_ipmi_check(host_id, host))

    @mock.patch('logging.Logger')
    def test_host_check_ipmi_with_no_ipmi_user(self, mock_log):
        host_id = '1'
        host = {'id': '1',
                'name': 'test',
                'os_status': 'init',
                'ipmi_addr': '192.168.1.2',
                'ipmi_user': None,
                'ipmi_passwd': 'superuser'}
        mock_log.side_effect = self._log_handler
        self.assertEqual({'ipmi_check_result': "No ipmi user configed "
                                               "for host 1, please check"},
                         self.controller._host_ipmi_check(host_id, host))

    @mock.patch('logging.Logger')
    @mock.patch('subprocess.Popen.communicate')
    def test_host_check_ipmi_with_no_ipmi_passwd(self,
                                                 mock_communicate,
                                                 mock_log):
        host_id = '1'
        host = {'id': '1',
                'name': 'test',
                'os_status': 'init',
                'ipmi_addr': '192.168.1.2',
                'ipmi_user': 'zteroot',
                'ipmi_passwd': None}
        mock_log.side_effect = self._log_handler
        mock_communicate.return_value = \
            ('', 'Unable to get Chassis Power Status')
        self.assertEqual({'ipmi_check_result': 'ipmi check failed'},
                         self.controller._host_ipmi_check(host_id, host))

    @mock.patch('logging.Logger')
    @mock.patch('subprocess.Popen.communicate')
    def test_host_check_ipmi_with_correct_ipmi_parameters(self,
                                                          mock_communicate,
                                                          mock_log):
        host_id = '1'
        host = {'id': '1',
                'name': 'host_1',
                'os_status': 'init',
                'ipmi_addr': '192.168.1.2',
                'ipmi_user': 'zteroot',
                'ipmi_passwd': 'superuser'}
        mock_log.side_effect = self._log_handler
        mock_communicate.return_value = ('Chassis Power is on', '')
        self.assertEqual({'ipmi_check_result': 'ipmi check successfully'},
                         self.controller._host_ipmi_check(host_id, host))

    @mock.patch('logging.Logger')
    @mock.patch('subprocess.Popen.communicate')
    def test_host_check_ipmi_with_error_ipmi_parameters(self,
                                                        mock_communicate,
                                                        mock_log):
        host_id = '1'
        host = {'id': '1',
                'os_status': 'init',
                'name': 'host_1',
                'ipmi_addr': '192.168.1.2',
                'ipmi_user': 'zteroot',
                'ipmi_passwd': 'superuser'}
        mock_log.side_effect = self._log_handler
        mock_communicate.return_value = \
            ('', 'Unable to get Chassis Power Status')
        self.assertEqual({'ipmi_check_result': 'ipmi check failed'},
                         self.controller._host_ipmi_check(host_id, host))

    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    @mock.patch('daisy.registry.client.v1.api.update_host_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_roles_detail')
    @mock.patch('daisy.registry.client.v1.api.get_clusters_detail')
    def test_host_update_with_removable_disk(self,
                                             mock_get_clusters,
                                             mock_get_roles,
                                             mock_update_host,
                                             mock_get_host_meta_or_404):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_id = '1'
        host_meta = {'os_status': 'active'}
        host = {
            'deleted': 0,
            'os_status': 'init',
            'disks': {
                "sr0": {
                    "name": "sr0",
                    "extra": ["ata-Slimtype_DVD_A_DS8ACSH_426603507668", ""],
                    "removable": "removable",
                    "model": "Slimtype DVD A  DS8ACSH",
                    "disk": "",
                    "size": ""},
                "sda": {
                    "name": "sda",
                    "extra": ["scsi-SASR7805_456_A32D532E", ""],
                    "removable": "non-removable",
                    "model": "",
                    "disk": "pci-0000:09:00.0-scsi-0:0:0:0",
                    "size": " 999643152384 bytes"}},
            'root_disk': 'sda',
            'root_lv_size': 102400,
            'memory': {"total": "65551468 kB",
                       "phy_memory_1": {"slots": " 24",
                                        "devices_20":
                                            {"frequency": " Unknown",
                                             "type": " <OUT OF SPEC>",
                                             "size": " No Module "
                                                     "Installed"},
                                        "maximum_capacity": " 768 GB"}},
            'cpu': {"numa_node0": "0-9,20-29",
                    "total": 40,
                    "numa_node1": "10-19,30-39",
                    "real": 2,
                    "spec_35": {"model": " Intel(R) Xeon(R) CPU E"
                                         "5-2650 v3 @ 2.30GHz",
                                "frequency": 2822.621}},
            'ipmi_addr': '10.43.2.3',
            'ipmi_user': 'aaa',
            'ipmi_passwd': 'aaa',
            'os_version_file': None,
            'os_version_id': None}
        host_return = {'deleted': '0',
                       'os_status': 'init',
                       'disks': {
                           "sda":
                               {"name": "sda",
                                "extra": ["scsi-SASR7805_456_A32D532E",
                                          ""],
                                "removable": "non-removable",
                                "model": "",
                                "disk": "pci-0000:09:00.0-scsi-0:0:0:0",
                                "size": " 999643152384 bytes"}},
                       'root_disk': 'sda',
                       'root_lv_size': 102400,
                       'memory': {"total": "65551468 kB",
                                  "phy_memory_1": {"slots": " 24",
                                                   "devices_20":
                                                       {"frequency":
                                                            " Unknown",
                                                        "type":
                                                            " <OUT OF SPEC>",
                                                        "size": " No Module "
                                                                "Installed"},
                                                   "maximum_capacity":
                                                       " 768 GB"}}
                       }
        clusters = [{'id': '1',
                     'name': 'test'}]
        roles = [{'id': '1'}]
        versions = [{'id': 'fe604c80-b5a0-4454-bbfd-2295ad8f1e5d'}]
        mock_get_host_meta_or_404.return_value = host
        #self.controller.get_host_meta_or_404 = mock.Mock(return_value=host)
        mock_get_clusters.return_value = clusters
        mock_get_roles.return_value = roles
        mock_update_host.return_value = host_return
        host_detail = self.controller.update_host(req, host_id, host_meta)
        self.assertEqual(1, len(host_detail['host_meta']['disks']))

    def test_check_interface_on_update_host(self):
        host_id = "fe604c80-b5a0-4454-bbfd-2295ad8f1e5d"
        req = fakes.HTTPRequest.blank('/nodes/%s' % host_id)

        host_meta = {
            "cluster": "111111-222222-333333",
            "interfaces": [
                {
                    "name": "enp3s0f0",
                    "is_deployment": False,
                    "deleted": False,
                    "ip": "192.168.1.8",
                    "is_vf": False,
                    "mac": "4c:09:b4:b0:ac:4b",
                    "netmask": "255.255.255.0",
                    "vswitch_type": "",
                    "state": "up",
                    "pci": "0000: 03: 00.0",
                    "current_speed": "100Mb/s",
                    "assigned_networks": [],
                    "max_speed": "1000baseT/Full",
                    "host_id": "f2af88bf-a336-4e90-9c2b-cbb11638e580",
                    "type": "ether",
                    "is_support_vf": False
                },
                {
                    "name": "enp3s0f1",
                    "is_deployment": False,
                    "deleted": False,
                    "ip": "10.43.203.224",
                    "is_vf": False,
                    "mac": "4c:09:b4:b0:ac:4c",
                    "netmask": "255.255.254.0",
                    "vswitch_type": "",
                    "state": "up",
                    "pci": "0000: 03: 00.1",
                    "current_speed": "100Mb/s",
                    "assigned_networks": [],
                    "max_speed": "1000baseT/Full",
                    "host_id": "f2af88bf-a336-4e90-9c2b-cbb11638e580",
                    "type": "ether",
                    "is_support_vf": False
                },
                {
                    "mode": "active-backup;off",
                    "type": "bond",
                    "name": "bond0",
                    "slave1": "enp3s0f0",
                    "slave2": "enp3s0f1",
                    "bond_type": "dvs/sr-iov/ovs"
                }
            ]}

        orig_host_meta = {
            "cluster": "test_host",
            "interfaces":
                [{
                    "name": "enp3s0f0",
                    "is_deployment": False,
                    "deleted": False,
                    "ip": "192.168.1.8",
                    "is_vf": False,
                    "mac": "4c:09:b4:b0:ac:4b",
                    "netmask": "255.255.255.0",
                    "vswitch_type": "",
                    "state": "up",
                    "pci": "0000: 03: 00.0",
                    "current_speed": "100Mb/s",
                    "assigned_networks": [],
                    "max_speed": "1000baseT/Full",
                    "host_id": "f2af88bf-a336-4e90-9c2b-cbb11638e580",
                    "type": "ether",
                    "is_support_vf": False
                }, {
                    "name": "enp3s0f1",
                    "is_deployment": False,
                    "deleted": False,
                    "ip": "10.43.203.224",
                    "is_vf": False,
                    "mac": "4c:09:b4:b0:ac:4c",
                    "netmask": "255.255.254.0",
                    "vswitch_type": "",
                    "state": "up",
                    "pci": "0000: 03: 00.1",
                    "current_speed": "100Mb/s",
                    "assigned_networks": [],
                    "max_speed": "1000baseT/Full",
                    "host_id": "f2af88bf-a336-4e90-9c2b-cbb11638e580",
                    "type": "ether",
                    "is_support_vf": False
                }
            ]}

        mac_list = ["4c:09:b4:b0:ac:4c", "4c:09:b4:b0:ac:4b"]
        result = self.controller.\
            _check_interface_on_update_host(req, host_meta, orig_host_meta)
        self.assertEqual(len(mac_list), len(result))

    @mock.patch('daisy.registry.client.v1.api.'
                'update_phyname_of_network')
    @mock.patch('daisy.registry.client.v1.api.get_all_networks')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_clusters_detail')
    def test_check_interface_on_update_host_without_bond_type(
            self, mock_get_clusters_detail, mock_get_cluster_network,
            mock_get_all_networks, mock_update_network):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        def update_network(req, networks):
            pass

        host_meta = {
            'cluster': '1',
            'interfaces':
                [{'name': 'enp3s2','ip': '192.168.1.2',
                'mac': '00:23:cd:96:53:96','pci': '0000:03:02.0',
                'assigned_networks': [],
                'host_id': '1','type': 'ether'},
                {'name': 'bond0','bond_type': '',
                'mode': 'active-backup;off',
                'slaves': ['enp2s0', 'enp3s2'],
                'assigned_networks':[{'ip': '192.168.1.5',
                'name': 'PUBLICAPI'}],'host_id': '1','type': 'bond'},
                {'name': 'enp2s0','ip': '10.43.178.21',
                'mac': '00:24:21:74:8a:56','pci': '0000:02:00.0',
                'assigned_networks': [],'host_id': '1',
                'type': 'ether'}, {'name': 'enp3s1',
                'mac': '00:23:cd:96:53:97', 'pci': '0000:03:02.1',
                'type': 'ether'}]}
        orig_host_meta = {'status': 'in-cluster',
                          'discover_mode': 'PXE',
                          'cluster_name': 'cluster_1',
                          'os_status': 'active',
                          'root_disk': 'sda',
                          'root_lv_size': 102400,
                          'swap_lv_size': 51200,
                          'root_pwd': 'ossdbg1',
                          'isolcpus': '',
                          'deleted': 0,
                          'interfaces': [{'name': 'enp3s2',
                                          'mac': '00:23:cd:96:53:96',
                                          'pci': '0000:03:02.0',
                                          'is_deployment': ''},
                                         {'name': 'bond0',
                                          'mac': '',
                                          'pci': '',
                                          'is_deployment': ''},
                                         {'mac': '00:24:21:74:8a:56',
                                          'pci': '0000:02:00.0',
                                          'is_deployment': ''},
                                         {'mac': '00:24:21:74:8a:57',
                                          'pci': '0000:02:00.1',
                                          'is_deployment': True}]}
        mock_get_clusters_detail.return_value = [{'id': '1',
                                                  'name': 'cluster_1'}]
        mock_get_cluster_network.return_value = [{'name': 'PUBLICAPI',
                                                  'id': '1'}]
        mock_get_all_networks.return_value = [{'name': 'PUBLICAPI',
                                               'id': '1',
                                               'cidr': '192.168.1.1/24',
                                               'network_type': 'PUBLICAPI'
                                               }]
        mock_update_network.side_effect = update_network
        mac_list = self.controller._check_interface_on_update_host(
            req, host_meta, orig_host_meta)
        self.assertIn('00:23:cd:96:53:96', mac_list)

    @mock.patch('daisy.registry.client.v1.client.RegistryClient.do_request')
    @mock.patch('daisy.registry.client.v1.api.get_all_networks')
    @mock.patch('daisy.registry.client.v1.api.get_networks_detail')
    @mock.patch('daisy.registry.client.v1.api.get_clusters_detail')
    def test_check_interface_on_update_host_with_bond_type(
            self, mock_get_clusters_detail, mock_get_cluster_network,
            mock_get_all_networks, mock_do_request):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_meta = {
            'cluster': '1',
            'interfaces':
                [{'name': 'enp3s2','ip': '192.168.1.2',
                'mac': '00:23:cd:96:53:96','pci': '0000:03:02.0',
                'assigned_networks': [],
                'host_id': '1','type': 'ether'},
                {'name': 'bond0','bond_type': 'linux',
                'mode': 'active-backup;off',
                'slaves': ['enp2s0', 'enp3s2'],
                'assigned_networks':[{'name': 'physnet1'}],
                'host_id': '1','type': 'bond'},
                {'name': 'enp2s0','ip': '10.43.178.21',
                'mac': '00:24:21:74:8a:56','pci': '0000:02:00.0',
                'assigned_networks': [],'host_id': '1',
                'type': 'ether'}, {'name': 'enp3s1',
                'mac': '00:23:cd:96:53:97', 'pci': '0000:03:02.1',
                'type': 'ether'}]}
        orig_host_meta = {'status': 'in-cluster',
                          'discover_mode': 'PXE',
                          'cluster_name': 'cluster_1',
                          'os_status': 'active',
                          'root_disk': 'sda',
                          'root_lv_size': 102400,
                          'swap_lv_size': 51200,
                          'root_pwd': 'ossdbg1',
                          'isolcpus': '',
                          'deleted': 0,
                          'interfaces': [{'name': 'enp3s2',
                                          'mac': '00:23:cd:96:53:96',
                                          'pci': '0000:03:02.0',
                                          'is_deployment': ''},
                                         {'name': 'bond0',
                                          'mac': '',
                                          'pci': '',
                                          'is_deployment': ''},
                                         {'mac': '00:24:21:74:8a:56',
                                          'pci': '0000:02:00.0',
                                          'is_deployment': ''},
                                         {'mac': '00:24:21:74:8a:57',
                                          'pci': '0000:02:00.1',
                                          'is_deployment': True}]}
        mock_get_clusters_detail.return_value = [{'id': '1',
                                                  'name': 'cluster_1'}]
        mock_get_cluster_network.return_value = [{'name': 'DATAPLANE',
                                                  'id': '1'}]
        mock_get_all_networks.return_value = [{'name': 'physnet1',
                                               'id': '1',
                                               'cidr': '',
                                               'network_type': 'DATAPLANE'
                                               }]
        mock_do_request.side_effect = self.fake_do_request
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller._check_interface_on_update_host,
                          req, host_meta, orig_host_meta)

    @mock.patch('logging.Logger')
    @mock.patch('daisy.registry.client.v1.api.'
                'update_discover_host_metadata')
    @mock.patch('daisy.registry.client.v1.api.'
                'get_all_host_interfaces')
    @mock.patch('daisy.registry.client.v1.api.'
                'get_discover_hosts_detail')
    def test_add_discover_host_with_exist_host_with_mac(
            self, mock_get_discovered_hosts,
            mock_get_all_host_interfaces,
            mock_update_discover_host, mock_log):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        def update_discover_host(context, host_id, host_info):
            discover_host_meta = {'ip': '1.2.3.4',
                                  'status': 'init',
                                  'user': 'root',
                                  'passwd': 'ossdbg1'
                                  }
            discover_host = api.discover_host_add(context, discover_host_meta)
            discover_host_id = discover_host['id']
            api.discover_host_update(context, discover_host_id, host_info)
            discover_hosts = api.discover_host_get_all(context)
            discover_host_id = discover_hosts[0]['id']
            discover_host_info = api.discover_host_get(context,
                                                       discover_host_id)
            api.discover_host_destroy(context, discover_host_id)
            return discover_host_info

        host_meta = {'ip': '1.2.3.4',
                     'passwd': 'ossdbg1',
                     'user': 'root',
                     'mac': '4c:09:b4:b1:c1:f0'}
        mock_get_discovered_hosts.return_value = [{'ip': '1.2.3.4',
                                                   'status': 'init',
                                                   'id': '1'}]
        mock_get_all_host_interfaces.return_value = [{'host_id': '1'}]
        mock_update_discover_host.side_effect = update_discover_host
        mock_log.side_effect = self._log_handler
        update_discover_host = self.controller.add_discover_host(req,
                                                                 host_meta)
        self.assertEqual('1', update_discover_host['host_meta']['host_id'])

    @mock.patch('daisy.api.v1.hosts.Controller.'
                '_get_discover_host_filter_by_ip')
    @mock.patch('daisy.api.v1.hosts.Controller._get_discover_host_ip')
    @mock.patch('logging.Logger')
    def test_add_discover_host_with_exist_host(self, mock_log,
                                               mock_get_discover_host_ip,
                                               mock_get_discover_host):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        mock_get_discover_host_ip.return_value = ['1.2.3.4']
        mock_get_discover_host.return_value = {
            'ip': '1.2.3.4', 'status': 'DISCOVERY_SUCCESSFUL'}
        host_meta = {'ip': '1.2.3.4',
                     'passwd': 'ossdbg1',
                     'user': 'root'}
        mock_log.side_effect = self._log_handler
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller.add_discover_host, req, host_meta)

    @mock.patch('daisy.api.v1.hosts.Controller._get_discover_host_ip')
    @mock.patch('logging.Logger')
    def test_add_discover_host_with_not_exist_host_without_password(
            self, mock_log, mock_get_discover_host_ip):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        mock_get_discover_host_ip.return_value = []
        mock_log.side_effect = self._log_handler
        host_meta = {'ip': '1.2.3.4'}
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller.add_discover_host, req, host_meta)

    @mock.patch('logging.Logger')
    @mock.patch('daisy.registry.client.v1.api.'
                'add_discover_host_metadata')
    @mock.patch('daisy.registry.client.v1.api.'
                'get_all_host_interfaces')
    @mock.patch('daisy.registry.client.v1.api.'
                'get_discover_hosts_detail')
    def test_add_discover_host_with_not_exist_host_with_mac(
            self, mock_get_discovered_hosts,
            mock_get_all_host_interfaces,
            mock_add_discover_host, mock_log):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        def add_new_discover_host(context, host_info):
            return api.discover_host_add(context, host_info)

        host_meta = {'ip': '1.2.3.4',
                     'passwd': 'ossdbg1',
                     'user': 'root',
                     'mac': '4c:09:b4:b1:c1:f0'}
        mock_get_discovered_hosts.return_value = [{'ip': '1.2.3.6',
                                                   'status': 'init',
                                                   'id': '1'}]
        mock_get_all_host_interfaces.return_value = [{'host_id': '2'}]
        mock_add_discover_host.side_effect = add_new_discover_host
        mock_log.side_effect = self._log_handler
        add_host_info = self.controller.add_discover_host(req, host_meta)
        self.assertEqual('2', add_host_info['host_meta']['host_id'])

    @mock.patch('logging.Logger')
    @mock.patch('daisy.registry.client.v1.api.'
                'update_discover_host_metadata')
    @mock.patch('daisy.registry.client.v1.api.'
                'get_all_host_interfaces')
    @mock.patch('daisy.registry.client.v1.api.'
                'get_discover_hosts_detail')
    def test_discover_host_bin_with_discovered_host(
            self, mock_get_discover_hosts_detail,
            mock_get_all_host_interfaces, mock_update_discover_host, mock_log):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_meta = {}

        def get_discover_hosts(context, **params):
            discover_host_meta1 = {'ip': '1.2.3.4',
                                   'user': 'root',
                                   'passwd': 'ossdbg1'}
            api.discover_host_add(context, discover_host_meta1)
            return api.discover_host_get_all(context)

        def update_discover_host(context, host_id, host_info):
            api.discover_host_update(context, host_id, host_info)
            api.discover_host_destroy(context, host_id)

        mock_get_discover_hosts_detail.side_effect = get_discover_hosts
        mock_get_all_host_interfaces.return_value = [{'ip': '1.2.3.4',
                                                      'host_id': '3'}]
        mock_update_discover_host.side_effect = update_discover_host
        mock_log.side_effect = self._log_handler
        self.controller.discover_host_bin(req, host_meta)
        self.assertTrue(mock_update_discover_host.called)

    @mock.patch("daisy.registry.client.v1.api.get_hosts_detail")
    @mock.patch("daisy.registry.client.v1.api.get_host_metadata")
    @mock.patch("daisy.api.v1.hosts.Controller.get_host")
    @mock.patch("daisy.api.v1.hosts.Controller._verify_interface_in_same_host")
    def test__verify_interface_among_hosts(
            self, mock_verify_interface_in_same_host, mock_get_host,
            mock_get_host_metadata, mock_get_hosts_detail):
        host_meta = {
            'cluster': '1',
            'dmi_uuid': '03000200-0400-0500-0006-000700080009',
            'interfaces':
                [{'name': 'enp132s0f2292', 'ip': '192.168.1.2',
                  'mac': '4c:09:b4:b2:80:8c', 'pci': '0000:03:02.0',
                  'assigned_networks': [],
                  'host_id': '1', 'type': 'ether'},
                 {'name': 'bond0', 'bond_type': '',
                  'mode': 'active-backup;off',
                  'slaves': ['enp2s0', 'enp132s0f2292'],
                  'assigned_networks':[{'ip': '192.168.1.5',
                  'name': 'PUBLICAPI'}], 'host_id': '1', 'type': 'bond'},
                 {'name': 'enp2s0', 'ip': '10.43.178.21',
                  'mac': '00:24:21:74:8a:56','pci': '0000:02:00.0',
                  'assigned_networks': [], 'host_id': '1',
                  'type': 'ether'}, {'name': 'enp3s1',
                  'mac': '00:23:cd:96:53:97', 'pci': '0000:03:02.1',
                  'type': 'ether'}]}
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        mock_verify_interface_in_same_host.return_value = {}
        mock_get_host.return_value = {'host_meta': self.orig_host_meta}
        mock_get_host_metadata.return_value = self.orig_host_meta
        mock_get_hosts_detail.return_value = [self.orig_host_meta]
        #self.controller._verify_interface_in_same_host = \
        #    mock.Mock(return_value={})
        #registry.get_hosts_detail = \
        #    mock.Mock(return_value=[self.orig_host_meta])
        #registry.get_host_metadata = \
        #    mock.Mock(return_value=self.orig_host_meta)
        #self.controller.get_host = \
        #    mock.Mock(return_value={'host_meta': self.orig_host_meta})
        id = ""
        os_status = ""
        (id, status) = self.controller._verify_interface_among_hosts(
            req, host_meta)
        self.assertEqual("4b6970c5-ef1d-4599-a1d7-70175a888e6d", id)

    @mock.patch("daisy.api.v1.hosts.Controller._check_add_host_interfaces")
    def test_add_host_with_same_host(self, mock_check_add_host_interfaces):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        mock_check_add_host_interfaces.return_value = "samehost"
        #self.controller._check_add_host_interfaces = \
        #    mock.Mock(return_value="samehost")
        result = self.controller.add_host(req, self.host_meta)
        self.assertEqual('samehost', result)

    @mock.patch("daisy.registry.client.v1.api.update_host_metadata")
    @mock.patch("daisy.registry.client.v1.api.get_discover_hosts_detail")
    @mock.patch("daisy.registry.client.v1.api.get_clusters_detail")
    @mock.patch("daisy.registry.client.v1.api.get_roles_detail")
    @mock.patch("daisy.api.v1.hosts.Controller._verify_host_cluster")
    @mock.patch("daisy.api.v1.hosts.Controller."
                "_check_interface_on_update_host")
    @mock.patch("daisy.api.v1.hosts.Controller.get_host_meta_or_404")
    def test_update_host_with_same_host(
            self, mock_get_host_meta_or_404,
            mock_check_interface_on_update_host, mock_verify_host_cluster,
            mock_get_roles_detail, mock_get_clusters_detail,
            mock_get_discover_hosts_detail, mock_update_host_metadata):
        host_meta = {
            'id': '4b6970c5-ef1d-4599-a1d7-70175a888e6d',
            'cluster': '1',
            'dmi_uuid': '03000200-0400-0500-0006-000700080009',
            'root_disk': 'sda',
            'os_status': 'init',
            'interfaces':
                [{'name': 'enp132s0f2292','ip': '192.168.1.2',
                'mac': '4c:09:b4:b2:80:8c','pci': '0000:03:02.0',
                'assigned_networks': [],
                'host_id': '1','type': 'ether'},
                {'name': 'bond0','bond_type': '',
                'mode': 'active-backup;off',
                'slaves': ['enp2s0', 'enp132s0f2292'],
                'assigned_networks':[{'ip': '192.168.1.5',
                'name': 'PUBLICAPI'}],'host_id': '1',
                'type': 'bond'},
                {'name': 'enp2s0','ip': '10.43.178.21',
                'mac': '00:24:21:74:8a:56','pci': '0000:02:00.0',
                'assigned_networks': [],'host_id': '1',
                'type': 'ether'}, {'name': 'enp3s1',
                'mac': '00:23:cd:96:53:97', 'pci': '0000:03:02.1',
                'type': 'ether'}],
            'disks':
                "{u'sda': {u'name': u'sda',"
                "u'extra': [u'scsi-3500003956831a6d8',"
                "u'wwn-0x500003956831a6d8'],"
                "u'removable': u'',"
                "u'model': u'',"
                "u'disk': u'pci-0000:01:00.0-sas-'"
                "u'0x500003956831a6da-lun-0',"
                "u'size': u' 200127266816 bytes'}}",
            'cpu': "{'real': 1, 'spec_1': {}, 'total': 1}"
        }
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenamet')
        mock_get_host_meta_or_404.return_value = self.orig_host_meta
        mock_check_interface_on_update_host.return_value = \
            ['4c:09:b4:b2:80:8c', '00:24:21:74:8a:56']
        mock_verify_host_cluster.return_value = {}
        #self.controller.get_host_meta_or_404 = mock.Mock(
        #    return_value=self.orig_host_meta)
        #self.controller._check_interface_on_update_host = mock.Mock(
        #    return_value=['4c:09:b4:b2:80:8c', '00:24:21:74:8a:56'])
        #self.controller._verify_host_cluster = mock.Mock(return_value={})
        #hw_info = {'disks': {'sda': {'name': 'sda',
        #                             'size': '200127266816',
        #                             'disk': u'pci-0000:01:00.0',
        #                             'removable': u''}},
        #           'cpu': {'real': 1, 'spec_1': {}, 'total': 1}}
        #mock_get_host_hw_info.return_value = hw_info
        #utils.get_host_hw_info = mock.Mock(return_value=hw_info)
        id = '4b6970c5-ef1d-4599-a1d7-70175a888e6d'
        mock_get_roles_detail.return_value = {}
        mock_get_clusters_detail.return_value = {}
        mock_get_discover_hosts_detail.return_value = {}
        mock_update_host_metadata.return_value = host_meta
        #registry.get_roles_detail = mock.Mock(return_value={})
        #registry.get_clusters_detail = mock.Mock(return_value={})
        #registry.get_discover_hosts_detail = mock.Mock(return_value={})
        #registry.update_host_metadata = mock.Mock(return_value=host_meta)
        result = self.controller.update_host(req, id, host_meta)
        self.assertEqual(host_meta, result['host_meta'])


class TestGetClusterNetworkInfo(test.TestCase):
    _log_handler = MockLoggingHandler()
    _log_messages = _log_handler.messages

    def setUp(self):
        super(TestGetClusterNetworkInfo, self).setUp()
        self.controller = hosts.Controller()
        self._log_handler.reset()

    @mock.patch('logging.Logger.error')
    def test_get_cluster_networks_info_with_None(self, mock_log):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        mock_log.side_effect = self._log_handler.error
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller.get_cluster_networks_info,
                          req)
        self.assertIn('error, the type and cluster_id '
                      'can not be empty at the same time',
                      self._log_messages['error'])

    @mock.patch('daisy.registry.client.v1.api.get_all_networks')
    def test_get_cluster_networks_info_with_type_and_cluster_id(
            self, mock_get_all_networks):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        def fake_get_all_networks(context, **params):
            if params == {'filters': {'cluster_id': 'cluster_1111',
                                      'type': 'default'}}:
                get_result = {"cluster_1111 , default"}
                return get_result

        mock_get_all_networks.side_effect = fake_get_all_networks
        return_all_networks = self.controller.get_cluster_networks_info(
            req, cluster_id='cluster_1111', type='default')
        self.assertEqual({"cluster_1111 , default"}, return_all_networks)

    @mock.patch('daisy.registry.client.v1.api.get_all_networks')
    def test_get_cluster_networks_info_with_type(self, mock_get_all_networks):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        def fake_get_all_networks(context, **params):
            if params == {'filters': {'cluster_id': 'cluster_1111'}}:
                get_result = {"cluster_1111"}
                return get_result
            elif params == {'filters': {'type': 'default'}}:
                get_result = {"default"}
                return get_result

        mock_get_all_networks.side_effect = fake_get_all_networks
        return_all_networks = self.controller.get_cluster_networks_info(
            req, type='default')
        self.assertEqual({"default"}, return_all_networks)

    @mock.patch('daisy.registry.client.v1.api.get_all_networks')
    def test_get_cluster_networks_info_with_cluter_id(self,
                                                      mock_get_all_networks):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        def fake_get_all_networks(context, **params):
            if params == {'filters': {'cluster_id': 'cluster_1111'}}:
                get_result = {"cluster_1111"}
                return get_result
            elif params == {'filters': {'type': 'default'}}:
                get_result = {"default"}
                return get_result

        mock_get_all_networks.side_effect = fake_get_all_networks
        return_all_networks = self.controller.get_cluster_networks_info(
            req, cluster_id='cluster_1111')
        self.assertEqual({"cluster_1111"}, return_all_networks)

    @mock.patch('daisy.api.backends.common.update_role_host')
    @mock.patch('daisy.api.backends.common.get_roles_of_host')
    @mock.patch('subprocess.call')
    def test_ready_to_discover_host(self, mock_do_call, mock_do_get_roles,
                                    mock_do_update_role):
        def mock_call(*args, **kwargs):
            pass

        def mock_get_roles(*args, **kwargs):
            pass

        def mock_update_role(*args, **kwargs):
            pass

        req = webob.Request.blank('/')
        host_meta = {'os_status': 'init'}
        mock_do_call.side_effect = mock_call
        mock_do_get_roles.side_effect = mock_get_roles
        mock_do_update_role.side_effect = mock_update_role
        self.controller._ready_to_discover_host(req, host_meta,
                                                set_host_meta())
        self.assertEqual(None, host_meta.get('role'))

    def test_ready_to_discover_host_with_tecs_version(self):
        req = webob.Request.blank('/')
        orig_host_meta = {'tecs_version_id': '1',
                          'tecs_patch_id': '1'}
        host_meta = {}
        self.controller._ready_to_discover_host(req, host_meta,
                                                orig_host_meta)
        self.assertEqual('', host_meta.get('tecs_version_id'))
        self.assertEqual('', host_meta.get('tecs_patch_id'))

    def test_check_add_host_interfaces(self):
        req = webob.Request.blank('/')
        host_info = set_host_meta()
        self.assertRaises(webob.exc.HTTPBadRequest,
                          self.controller._check_add_host_interfaces,
                          req, host_info)

    @mock.patch('daisy.registry.client.v1.api.get_hosts_detail')
    def test_verify_host_name_with_os_active(self, mock_do_get_hosts_detail):

        def mock_get_hosts_detail(*args, **kwargs):
            return []

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        mock_do_get_hosts_detail.side_effect = mock_get_hosts_detail
        host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "os_status": "active",
            "name": "host-1"}
        orig_host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "os_status": "active",
            "name": "host-2"}
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller._verify_host_name, req,
                          "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
                          orig_host_meta, host_meta)

    @mock.patch('daisy.registry.client.v1.api.get_hosts_detail')
    def test_verify_host_name_with_empty(self, mock_do_get_hosts_detail):

        def mock_get_hosts_detail(*args, **kwargs):
            return []

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        mock_do_get_hosts_detail.side_effect = mock_get_hosts_detail
        host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "os_status": "init",
            "name": ""}
        orig_host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "os_status": "init",
            "name": "host-1"}
        self.assertEqual(None, self.controller._verify_host_name(
            req, "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            orig_host_meta, host_meta))

    @mock.patch('daisy.registry.client.v1.api.get_hosts_detail')
    def test_verify_host_name_with_format_no_valid(
            self, mock_do_get_hosts_detail):

        def mock_get_hosts_detail(*args, **kwargs):
            return []

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        mock_do_get_hosts_detail.side_effect = mock_get_hosts_detail
        host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "os_status": "init",
            "name": "~~~~"}
        orig_host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "os_status": "init",
            "name": "host-1"}
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller._verify_host_name, req,
                          "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
                          orig_host_meta, host_meta)

    @mock.patch('daisy.registry.client.v1.api.get_hosts_detail')
    def test_verify_host_name_with_out_length(
            self, mock_do_get_hosts_detail):

        def mock_get_hosts_detail(*args, **kwargs):
            return []

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        mock_do_get_hosts_detail.side_effect = mock_get_hosts_detail
        host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "os_status": "init",
            "name": "a123456789a123456789a123456789a123456789"}
        orig_host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "os_status": "init",
            "name": "host-1"}
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller._verify_host_name, req,
                          "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
                          orig_host_meta, host_meta)

    @mock.patch('daisy.registry.client.v1.api.get_hosts_detail')
    def test_check_host_name_with_conflict(self, mock_do_get_hosts_detail):

        def mock_get_hosts_detail(*args, **kwargs):
            return [
                {
                    'id': u'f9b3aa0b-43c6-437a-9243-e7d141d22114',
                    'name': u'abcddd'
                },
                {
                    'id': u'bad3f85a-aa2a-429e-b941-7f2d8312dc2a',
                    'name': u'abcd'
                },
                {
                    'id': u'b3ea6edc-8758-41e6-9b5b-ebfea2622c06',
                    'name': u'abcdddd'
                },
                {
                    'id': u'840b92ab-7e79-4a7d-be0a-5e735e0a836e',
                    'name': u''
                }
            ]

        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        mock_do_get_hosts_detail.side_effect = mock_get_hosts_detail
        host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "os_status": "init",
            "name": "abcddd"}
        orig_host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "os_status": "init",
            "name": "host-1"}
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller._verify_host_name, req,
                          "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
                          orig_host_meta, host_meta)

    @mock.patch("daisy.api.v1.hosts.Controller.get_cluster_meta_or_404")
    @mock.patch("daisy.api.backends.common.check_discover_state_with_hwm")
    @mock.patch("daisy.registry.client.v1.api.get_host_clusters")
    def test_verify_host_cluster_with_in_cluster(
            self, mock_get_host_clusters,
            mock_check_discover_state_with_hwm, mock_get_cluster_meta_or_404):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')
        host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            'hwm_id': '1',
            "cluster": "66e57b5c-fc4f-4c09-a550-b057ff4f5452",
            "name": "abcddd"}
        orig_host_meta = {
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "status": "in-cluster",
            "name": "host-1"}
        host_cluster = [{
            "id": "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
            "cluster_id": "66e57b5c-fc4f-4c09-a550-b057ff4f5453",
            "status": "in-cluster",
            "name": "host-1"}]
        mock_get_host_clusters.return_value = host_cluster
        #registry.get_host_clusters = \
        #    mock.Mock(return_value=host_cluster)
        mock_get_cluster_meta_or_404.return_value = \
            {"id": "66e57b5c-fc4f-4c09-a550-b057ff4f5452"}
        #self.controller.get_cluster_meta_or_404 = \
        #    mock.Mock(return_value={"id": "66e57b5c-fc4f-"
        #                                  "4c09-a550-b057ff4f5452"})
        mock_check_discover_state_with_hwm.return_value = \
            check_result(host_meta, 'SSH:DISCOVERY_SUCCESSFUL')
        #daisy_cmn.check_discover_state_with_hwm = \
        #   mock.Mock(return_value=check_result(host_meta,
        #                                       'SSH:DISCOVERY_SUCCESSFUL'))
        self.assertRaises(webob.exc.HTTPForbidden,
                          self.controller._verify_host_cluster, req,
                          "840b92ab-7e79-4a7d-be0a-5e735e0a836e",
                          orig_host_meta, host_meta)

    @mock.patch('daisy.registry.client.v1.api.delete_host_metadata')
    @mock.patch('subprocess.call')
    @mock.patch('daisy.registry.client.v1.api.get_host_metadata')
    def test_delete_install_unfinished_host(self, mock_get_host,
                                            mock_call,
                                            mock_delete_host):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True,
                                     user='fake user',
                                     tenant='fake tenant')

        def del_mac(cmd, shell, stdout, stderr):
            pass
        host_id = '1'
        mock_get_host.return_value = {'interfaces': [{'mac': '1'}]}
        mock_call.side_effect = del_mac
        mock_delete_host.return_value = {}
        self.controller.delete_host(req, host_id)
        response = self.controller.delete_host(req, host_id)
        self.assertEqual(200, response.status_code)

    def test_interface_has_vf(self):
        interface = {"name": "eth0", "is_support_vf": True}
        ret = self.controller._interface_has_vf(interface)
        self.assertTrue(ret)

    def test_get_interface_by_name(self):
        name = "eth0"
        ret = self.controller._get_interface_by_name(name, None)
        self.assertIsNone(ret)

        interfaces = [{'name': 'eth1'}]
        ret = self.controller._get_interface_by_name(name, interfaces)
        self.assertIsNone(ret)
