import mock
import webob
from daisy.context import RequestContext
from daisy.common import exception
from daisy import test
from daisyclient.v1.client import Client
from daisy.orchestration import manager
from daisy.common import utils


class MockCluster():
    def __init__(self, auto_scale, id):
        self.auto_scale = auto_scale
        self.id = id

    def to_dict(self):
        dict = {'id': self.id}
        return dict


class MockHostList():
    def __init__(self, os_status, id, role = "", interfaces="",
                 role_status="", hwm_id="", discover_mode=""):
        self.os_status = os_status
        self.id = id
        self.role = role
        self.interfaces = interfaces
        self.role_status = role_status
        self.hwm_id = hwm_id
        self.discover_mode = discover_mode
        self.memory = {"total": " 65941828 kB"}
        self.cpu = {"total": 24}
        self.name = "test"
        self.os_version_id = "1"
        self.os_version_file = ""
        self.root_lv_size = ""
        self.swap_lv_size = ""
        self.hwm_ip = ""
        self.hugepagesize = ""
        self.hugepages = ""
        self.isolcpus = ""
        self.ipmi_user = ""
        self.ipmi_passwd = ""
        self.vcpu_pin_set = ""
        self.dvs_high_cpuset = ""
        self.pci_high_cpuset = ""
        self.os_cpus = ""
        self.dvs_cpus = ""
        self.root_disk = ""
        self.config_set_id = ""
        self.group_list = ""
        self.dvsc_cpus = ""
        self.dvsp_cpus = ""
        self.dvsv_cpus = ""
        self.dvsblank_cpus = ""
        self.flow_mode = ""
        self.virtio_queue_size = ""
        self.dvs_config_type = ""
        self.tecs_patch_id = ""

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
            return_value=Client(version="1.0",
                                endpoint="http://127.0.0.1:8080"))
        self.Orchestration = manager.OrchestrationManager()

    def tearDown(self):
        super(TestManager, self).tearDown()


    def test_get_active_compute(self):
        interfaces = [
            {"ip": "",
             "updated_at": "2016-12-14T05:56:48.000000",
             "current_speed": "10000Mb/s",
             "assigned_networks": [],
             "id": "55ab07c5-8dbf-43b4-b80f-97e041475b11",
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:81:00.0",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "",
             "max_speed": "10000baseT/Full",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens44f0",
             "is_deployment": False,
             "created_at": "2016-12-14T05:56:48.000000",
             "mac": "74:4a:a4:01:86:8f",
             "mode": ""
             },
            {"name": "bond1",
             "is_deployment": False,
             "deleted": False,
             "ip": "",
             "created_at": "2016-12-14T05:56:48.000000",
             "slave2": "ens44f1",
             "updated_at": "2016-12-14T05:56:48.000000",
             "id": "6d3b6ffa-5737-43fb-8c02-a45ac137b090",
             "mac": "",
             "vswitch_type": "",
             "netmask": "",
             "pci": "",
             "slave1": "ens44f0",
             "mode": "balance-tcp;active",
             "assigned_networks": [],
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "type": "bond",
             "gateway": ""
             },
            {"ip": "",
             "updated_at": "2016-12-14T05:56:48.000000",
             "current_speed": "10000Mb/s",
             "assigned_networks": [],
             "id": "7d0bfbff-1588-40b3-9450-3244b71b3c3c",
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:81:00.1",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "",
             "max_speed": "10000baseT/Full",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens44f1",
             "is_deployment": False,
             "created_at": "2016-12-14T05:56:48.000000",
             "mac": "74:4a:a4:01:86:90",
             "mode": ""
             },
            {"ip": "",
             "updated_at": "2016-12-14T05:56:48.000000",
             "current_speed": "1000Mb/s",
             "assigned_networks": [],
             "id": "869db3df-7581-49d0-b89e-c56cf5488c10",
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:01:00.0",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "",
             "max_speed": "  Not reported",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens4f0",
             "is_deployment": False,
             "created_at": "2016-12-14T05:56:48.000000",
             "mac": "74:4a:a4:01:5f:33",
             "mode": ""
             },
            {"name": "bond0",
             "is_deployment": False,
             "deleted": False,
             "ip": "",
             "created_at": "2016-12-14T05:56:48.000000",
             "slave2": "ens12f1",
             "updated_at": "2016-12-14T05:56:48.000000",
             "id": "bcc694b5-e3c3-43ba-acfe-c58f1ae92ee4",
             "mac": "",
             "vswitch_type": "",
             "netmask": "",
             "pci": "",
             "slave1": "ens12f0",
             "mode": "active-backup",
             "assigned_networks": [],
             "host_id": "",
             "type": "bond",
             "gateway": ""
             },
            {"ip": "",
             "updated_at": "2016-12-14T05:56:48.000000",
             "current_speed": "1000Mb/s",
             "assigned_networks": [],
             "id": "c237c4cd-840e-433f-b71f-06c537444f06",
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:01:00.1",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "",
             "max_speed": "  Not reported",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens4f1",
             "is_deployment": False,
             "created_at": "2016-12-14T05:56:48.000000",
             "mac": "74:4a:a4:01:5f:34",
             "mode": ""
             },
            {"ip": "",
             "updated_at": "2016-12-14T05:56:48.000000",
             "current_speed": "Unknown!",
             "assigned_networks": [],
             "id": "f0fd2f53-d952-40bb-973e-83bddddd57a7",
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:08:00.0",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "",
             "max_speed": "10000baseT/Full",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens12f0",
             "is_deployment": False,
             "created_at": "2016-12-14T05:56:48.000000",
             "mac": "74:4a:a4:01:86:77",
             "mode": ""
             },
            {"ip": "",
             "updated_at": "2016-12-14T05:56:48.000000",
             "current_speed": "10000Mb/s",
             "assigned_networks": [],
             "id": "f9312bb6-6849-49af-a5fc-2c887f69b907",
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:08:00.1",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "255.255.255.0",
             "max_speed": "10000baseT/Full",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens12f1",
             "is_deployment": True,
             "created_at": "2016-12-14T05:56:48.000000",
             "mac": "74:4a:a4:01:86:78",
             "mode": ""}]
        def do_host_list(**kwargs):
            
            host1 = MockHostList(os_status="active",role_status='active',
                                 id='aaaa', role=['COMPUTER'],
                                 interfaces=interfaces, discover_mode="PXE")
            host2 = MockHostList(os_status="active",role_status='init',
                                 id='bbbb', role=['CONTROLLER_HA'],
                                 interfaces=interfaces, discover_mode="PXE")
            host_list = [host1, host2]
            for host in host_list:
                yield host
        cluster_id = "123"
        host_generator = do_host_list()
        self.daisy_client.hosts.list = mock.Mock(return_value=host_generator)
        host1 = MockHostList(os_status="active",role_status='active',
                             id='aaaa', role=['COMPUTER'],
                             interfaces=interfaces)
        self.daisy_client.hosts.get = mock.Mock(return_value=host1)
        hosts = self.Orchestration.get_active_compute(
            cluster_id, self.daisy_client)
        self.assertEqual(1, len(hosts))

    def test_check_isomorphic_host(self):
        active_host1 = MockHostList(os_status='active', id='aaaa')
        active_host2 = MockHostList(os_status='active', id='bbbb')
        compute_host_list = [active_host1, active_host2]
        host_info = MockHostList(os_status='active', id='cccc')
        host_hw_info = {'cpu':{"total": 24},
                        'memory':{"total": " 65941828 kB"}}
        utils.get_host_hw_info = mock.Mock(return_value=host_hw_info)
        utils.get_numa_node_cpus = mock.Mock(return_value=3)
        result = self.Orchestration.check_isomorphic_host(
            compute_host_list, host_info)
        self.assertEqual(False, result)

    def test_check_interface_isomorphic_nomal(self):
        new_interfaces = [
            {"current_speed": "10000Mb/s",
             "assigned_networks": [],
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:81:00.0",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "",
             "max_speed": "10000baseT/Full",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens44f0",
             "mac": "74:4a:a4:01:86:8f",
             "mode": ""}]
        active_host = MockHostList(os_status='active', id='aaaa',
                                   interfaces=new_interfaces)
        result = self.Orchestration._check_interface_isomorphic(
            new_interfaces, active_host)
        self.assertEqual(True, result)

    def test_check_interface_different_pci(self):
        new_interfaces = [
            {"current_speed": "10000Mb/s",
             "assigned_networks": [],
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:81:00.0",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "",
             "max_speed": "10000baseT/Full",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens44f0",
             "mac": "74:4a:a4:01:86:8f",
             "mode": ""}]
        active_interface = [
            {"current_speed": "10000Mb/s",
             "assigned_networks": [],
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:81:00.1",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "",
             "max_speed": "10000baseT/Full",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens44f0",
             "mac": "74:4a:a4:01:86:8f",
             "mode": ""}]
        active_host = MockHostList(os_status='active', id='aaaa',
                                   interfaces=active_interface)
        result = self.Orchestration._check_interface_isomorphic(
            new_interfaces, active_host)
        self.assertEqual(False, result)

    def test_check_interface_active_host_with_bond(self):
        new_interfaces = [
            {"current_speed": "10000Mb/s",
             "assigned_networks": [],
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:81:00.0",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "",
             "max_speed": "10000baseT/Full",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens44f0",
             "mac": "74:4a:a4:01:86:8f",
             "mode": ""}]
        active_interface = [
            {"current_speed": "10000Mb/s",
             "assigned_networks": [],
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:81:00.0",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "",
             "max_speed": "10000baseT/Full",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens44f0",
             "mac": "74:4a:a4:01:86:8f",
             "mode": ""},
            {"current_speed": "10000Mb/s",
             "assigned_networks": [],
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "",
             "slave1": "",
             "slave2": "",
             "type": "bond",
             "deleted": False,
             "netmask": "",
             "max_speed": "10000baseT/Full",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "bond0",
             "mac": "74:4a:a4:01:86:8f",
             "mode": ""}]
        active_host = MockHostList(os_status='active', id='aaaa',
                                   interfaces=active_interface)
        result = self.Orchestration._check_interface_isomorphic(
            new_interfaces, active_host)
        self.assertEqual(True, result)

    def test_check_interface_different_maxspeed(self):
        new_interfaces = [
            {"current_speed": "10000Mb/s", "assigned_networks": [],
             "gateway": "", "vswitch_type": "", "state": "up",
             "pci": "0000:81:00.0", "slave1": "", "slave2": "",
             "type": "ether", "deleted": False, "netmask": "",
             "max_speed": "10000baseT/Full",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens44f0", "mac": "74:4a:a4:01:86:8f", "mode": ""}
        ]
        active_interface = [
            {"current_speed": "10000Mb/s", "assigned_networks": [],
             "gateway": "", "vswitch_type": "", "state": "up",
             "pci": "0000:81:00.0", "slave1": "", "slave2": "",
             "type": "ether", "deleted": False, "netmask": "",
             "max_speed": "1",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens44f0", "mac": "74:4a:a4:01:86:8f",
             "mode": ""}]
        active_host = MockHostList(os_status='active', id='aaaa',
                                   interfaces=active_interface)
        result = self.Orchestration._check_interface_isomorphic(
            new_interfaces, active_host)
        self.assertEqual(False, result)

    def test_set_scale_host_interface(self):
        cluster_id = "123"
        active_interface = [
            {"current_speed": "10000Mb/s", "assigned_networks": [],
             "gateway": "", "vswitch_type": "", "state": "up",
             "pci": "0000:81:00.0", "slave1": "", "slave2": "",
             "type": "ether", "deleted": False, "netmask": "",
             "max_speed": "1",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens44f0",
             "mac": "74:4a:a4:01:86:8f",
             "mode": ""}]
        host_info = MockHostList(os_status='active', id='aaaa',
                                 interfaces=active_interface)
        self.Orchestration.get_active_compute = mock.Mock(
            return_value=[host_info])
        result = self.Orchestration.set_scale_host_interface(
            cluster_id, host_info, self.daisy_client)
        self.assertEqual(host_info, result)

    def test_set_scale_host_interface_no_active_host(self):
        cluster_id = "123"
        active_interface = [
            {"current_speed": "10000Mb/s",
             "assigned_networks": [],
             "gateway": "",
             "vswitch_type": "",
             "state": "up",
             "pci": "0000:81:00.0",
             "slave1": "",
             "slave2": "",
             "type": "ether",
             "deleted": False,
             "netmask": "",
             "max_speed": "1",
             "host_id": "5e33d072-328b-4e7c-a672-0edffb1158b9",
             "name": "ens44f0",
             "mac": "74:4a:a4:01:86:8f",
             "mode": ""}]
        host_info = MockHostList(os_status='active', id='aaaa',
                                 interfaces=active_interface)
        self.Orchestration.get_active_compute = mock.Mock(
            return_value=[host_info])
        self.Orchestration.check_isomorphic_host = mock.Mock(return_value=[])
        result = self.Orchestration.set_scale_host_interface(
            cluster_id, host_info, self.daisy_client)
        self.assertEqual(None, result)
