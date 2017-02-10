import mock
import webob
from daisy.context import RequestContext
from daisy.api.backends import common
from daisy import test


class MockLoggingHandler(object):

    """Mock logging handler to check for expected logs.

    Messages are available from an instance's ``messages`` dict, in order,
    indexed by a lowercase log level string (e.g., 'debug', 'info', etc.).
    """

    def __init__(self):
        self.messages = {'debug': [], 'info': [], 'warning': [], 'error': []}

    def info(self, message, *args, **kwargs):
        self.messages['info'].append(message)

    def error(self, message, *args, **kwargs):
        self.messages['error'].append(message)

    def reset(self):
        for message in self.messages:
            del self.messages[message][:]


class TestCommon(test.TestCase):
    _log_handler = MockLoggingHandler()

    def setUp(self):
        super(TestCommon, self).setUp()
        self._log_handler.reset()
        self._log_messages = self._log_handler.messages
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')

    @mock.patch('logging.Logger.info')
    @mock.patch('daisy.api.backends.common.subprocess_call')
    def test_trust_me(self, mock_do_subprocess_call, mock_log):
        def mock_subprocess_call(*args, **kwargs):
            pass
        ip = ['127.0.0.1']
        passwd = 'ossdbg1'
        mock_do_subprocess_call.side_effect = mock_subprocess_call
        mock_log.side_effect = self._log_handler.info
        common.trust_me(ip, passwd)
        self.assertIn("Setup trust to '127.0.0.1' successfully",
                      self._log_messages['info'])

    @mock.patch('daisy.api.backends.common.if_used_shared_storage')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_host_metadata')
    def test_check_vlan_nic_and_join_vlan_network_without_provider(
            self, mock_get_host, mock_get_cluster_metadata, mock_use_storage):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        cluster_id = '4d3156ba-a4a5-4f41-914c-7a148170f281'
        host_list = ['fd3156ba-a4a5-4f41-914c-7a148170f28d', ]
        networks = [{'network_type': 'DATAPLANE'},
                    {'network_type': 'OUTBAND',
                     'cidr': '10.43.178.1/24',
                     'vlan_id': '100',
                     'name': 'OUTBAND'}]
        return_host_detail = {'interfaces': [{'ip': '10.43.178.129',
                                              'type': 'vlan',
                                              'name': 'eth0.100',
                                              'assigned_networks': []}]}
        mock_get_host.return_value = return_host_detail
        mock_get_cluster_metadata.return_value = {'use_provider_ha': 0}
        mock_use_storage.return_value = (True, None)
        vlan_interface_list = common.check_vlan_nic_and_join_vlan_network(
            self.req, cluster_id, host_list, networks)

        self.assertEqual([], vlan_interface_list)

    @mock.patch('daisy.api.backends.common.if_used_shared_storage')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('daisy.registry.client.v1.api.get_host_metadata')
    def test_check_vlan_nic_and_join_vlan_network_with_outband(
            self, mock_get_host, mock_get_cluster_metadata, mock_use_storage):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        cluster_id = '4d3156ba-a4a5-4f41-914c-7a148170f281'
        host_list = ['fd3156ba-a4a5-4f41-914c-7a148170f28d', ]
        networks = [{'network_type': 'DATAPLANE'},
                    {'network_type': 'OUTBAND',
                     'cidr': '10.43.178.1/24',
                     'vlan_id': '100',
                     'name': 'OUTBAND'}]
        return_host_detail = {'interfaces': [{'ip': '10.43.178.129',
                                              'type': 'vlan',
                                              'name': 'eth0.100',
                                              'assigned_networks': []}]}
        mock_get_host.return_value = return_host_detail
        mock_get_cluster_metadata.return_value = {'use_provider_ha': 1}
        mock_use_storage.return_value = (True, None)
        vlan_interface_list = common.check_vlan_nic_and_join_vlan_network(
            self.req, cluster_id, host_list, networks)

        self.assertEqual('OUTBAND', vlan_interface_list[0]['eth0']['name'])

    @mock.patch('daisy.api.backends.common.if_used_shared_storage')
    @mock.patch('daisy.registry.client.v1.api.get_cluster_metadata')
    @mock.patch('logging.Logger.info')
    @mock.patch('daisy.registry.client.v1.api.get_host_metadata')
    def test_check_bond_or_ether_nic_and_join_network_without_provider(
            self, mock_get_host, mock_log, mock_get_cluster_metadata,
            mock_use_storage):
        req = webob.Request.blank('/')
        req.context = RequestContext(is_admin=True, user='fake user',
                                     tenant='fake tenant')
        cluster_id = '4d3156ba-a4a5-4f41-914c-7a148170f281'
        host_list = ['fd3156ba-a4a5-4f41-914c-7a148170f28d', ]
        networks = [{'network_type': 'DATAPLANE'},
                    {'network_type': 'OUTBAND',
                     'cidr': '10.43.178.1/24',
                     'vlan_id': '100',
                     'name': 'OUTBAND'}]
        father_vlan_list = []
        return_host_detail = {'interfaces': [{'ip': '10.43.178.129',
                                              'type': 'ether',
                                              'name': 'eth0.100',
                                              'assigned_networks': []}]}
        mock_get_host.return_value = return_host_detail
        mock_get_cluster_metadata.return_value = {'use_provider_ha': 0}
        mock_use_storage.return_value = (True, None)
        common.check_bond_or_ether_nic_and_join_network(
            self.req, cluster_id, host_list, networks, father_vlan_list)
        self.assertTrue(mock_use_storage.called)
        self.assertTrue(mock_get_cluster_metadata.called)
