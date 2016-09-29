import mock
import webob
from daisy.context import RequestContext
from daisy import test
from daisyclient.v1.client import Client
from daisy.orchestration import manager


class MockCluster():
    def __init__(self, auto_scale, id):
        self.auto_scale = auto_scale
        self.id = id

    def to_dict(self):
        dict = {'id': self.id}
        return dict


class MockHostList():
    def __init__(self, os_status, id, role="", interfaces="", role_status=""):
        self.os_status = os_status
        self.id = id
        self.role = role
        self.interfaces = interfaces
        self.role_status = role_status

    def to_dict(self):
        dict = {'status': self.os_status, 'id': self.id}
        return dict


class MockRole():
    def __init__(self, name, status):
        self.name = name
        self.status = status

    def to_dict(self):
        dict = {'name': self.name, 'status': self.status}
        return dict


class MockHostGet():
    def __init__(self):
        pass


class TestManager(test.TestCase):
    def setUp(self):
        super(TestManager, self).setUp()
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')
        self.daisy_client = mock.Mock(
            return_value=Client(
                version="1.0", endpoint="http://127.0.0.1:8080"))
        self.Orchestration = manager.OrchestrationManager()

    @mock.patch('daisyclient.v1.hosts.HostManager.list')
    @mock.patch('daisyclient.v1.clusters.ClusterManager.list')
    @mock.patch('ConfigParser.ConfigParser.get')
    @mock.patch('ConfigParser.RawConfigParser.read')
    def test_find_auto_scale_cluster_no_host(self, mock_do_read, mock_do_get,
                                             mock_do_cluster_list,
                                             mock_do_host_list):
        def do_read(filenames):
            return ['/etc/daisy/daisy-api.conf']

        def do_get(section, option):
            return '19292'

        def do_cluster_list(**kwargs):
            cluster_list1 = MockCluster(auto_scale=1, id='111111')
            cluster_list2 = MockCluster(auto_scale=0, id='222222')
            clusters_list = [cluster_list1, cluster_list2]
            for cluster_list in clusters_list:
                yield cluster_list

        def do_host_list(**kwargs):
            host1 = MockHostList(os_status='active', id='aaaa')
            host2 = MockHostList(os_status='active', id='bbbb')
            host_list = [host1, host2]
            for host in host_list:
                yield host

        mock_do_read.side_effect = do_read
        mock_do_get.side_effect = do_get
        mock_do_cluster_list.side_effect = do_cluster_list
        mock_do_host_list.side_effect = do_host_list
        result = self.Orchestration.find_auto_scale_cluster()
        self.assertEqual(result, {"status": "no init host"})

    @mock.patch('daisyclient.v1.roles.RoleManager.list')
    @mock.patch('daisyclient.v1.hosts.HostManager.list')
    @mock.patch('daisyclient.v1.clusters.ClusterManager.list')
    @mock.patch('ConfigParser.ConfigParser.get')
    @mock.patch('ConfigParser.RawConfigParser.read')
    def test_find_auto_scale_cluster_no_controller(self, mock_do_read,
                                                   mock_do_get,
                                                   mock_do_cluster_list,
                                                   mock_do_host_list,
                                                   mock_do_role_list):
        def do_read(filenames):
            return ['/etc/daisy/daisy-api.conf']

        def do_get(section, option):
            return '19292'

        def do_cluster_list(**kwargs):
            cluster_list1 = MockCluster(auto_scale=1, id='111111')
            cluster_list2 = MockCluster(auto_scale=0, id='222222')
            clusters_list = [cluster_list1, cluster_list2]
            for cluster_list in clusters_list:
                yield cluster_list

        def do_host_list(**kwargs):
            host1 = MockHostList(os_status='active', id='aaaa')
            host2 = MockHostList(os_status='init', id='bbbb')
            host_list = [host1, host2]
            for host in host_list:
                yield host

        def do_role_list(**kwargs):
            role1 = MockRole(name='COMPUTER', status="active")
            role2 = MockRole(name='CONTROLLER_HA', status="init")
            role_list = [role1, role2]
            for role in role_list:
                yield role

        mock_do_read.side_effect = do_read
        mock_do_get.side_effect = do_get
        mock_do_cluster_list.side_effect = do_cluster_list
        mock_do_host_list.side_effect = do_host_list
        mock_do_role_list.side_effect = do_role_list
        result = self.Orchestration.find_auto_scale_cluster()
        self.assertEqual(result, {"status": "no active CONTROLLER_HA role"})

    @mock.patch('daisyclient.v1.hosts.HostManager.get')
    @mock.patch('daisyclient.v1.roles.RoleManager.list')
    @mock.patch('daisyclient.v1.hosts.HostManager.list')
    @mock.patch('daisyclient.v1.clusters.ClusterManager.list')
    @mock.patch('ConfigParser.ConfigParser.get')
    @mock.patch('ConfigParser.RawConfigParser.read')
    def test_find_auto_scale_cluster_no_interfaces(self, mock_do_read,
                                                   mock_do_get,
                                                   mock_do_cluster_list,
                                                   mock_do_host_list,
                                                   mock_do_role_list,
                                                   mock_do_host_get):
        def do_read(filenames):
            return ['/etc/daisy/daisy-api.conf']

        def do_get(section, option):
            return '19292'

        def do_cluster_list(**kwargs):
            cluster_list1 = MockCluster(auto_scale=1, id='111111')
            cluster_list2 = MockCluster(auto_scale=0, id='222222')
            clusters_list = [cluster_list1, cluster_list2]
            for cluster_list in clusters_list:
                yield cluster_list

        def do_host_list(**kwargs):
            host1 = MockHostList(os_status='active', id='aaaa')
            host2 = MockHostList(os_status='init', id='bbbb')
            host_list = [host1, host2]
            for host in host_list:
                yield host

        def do_host_get(id):
            host = MockHostGet()
            return host

        def do_role_list(**kwargs):
            role1 = MockRole(name='COMPUTER', status="active")
            role2 = MockRole(name='CONTROLLER_HA', status="active")
            role_list = [role1, role2]
            for role in role_list:
                yield role

        mock_do_read.side_effect = do_read
        mock_do_get.side_effect = do_get
        mock_do_cluster_list.side_effect = do_cluster_list
        mock_do_host_list.side_effect = do_host_list
        mock_do_role_list.side_effect = do_role_list
        mock_do_host_get.side_effect = do_host_get
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.Orchestration.find_auto_scale_cluster)

    def test_get_active_compute(self):
        def do_host_list(**kwargs):
            host1 = MockHostList(os_status="active",
                                 role_status='active',
                                 id='aaaa',
                                 role=['COMPUTER'], interfaces='')
            host2 = MockHostList(os_status="active",
                                 role_status='init',
                                 id='bbbb',
                                 role=['CONTROLLER_HA'], interfaces='')
            host_list = [host1, host2]
            for host in host_list:
                yield host
        cluster_id = "123"
        host_generator = do_host_list()
        self.daisy_client.hosts.list = mock.Mock(return_value=host_generator)
        host1 = MockHostList(os_status="active",
                             role_status='active',
                             id='aaaa',
                             role=['COMPUTER'],
                             interfaces='')
        self.daisy_client.hosts.get = mock.Mock(return_value=host1)
        hosts = self.Orchestration.get_active_compute(cluster_id,
                                                      self.daisy_client)
        self.assertEqual(1, len(hosts))
