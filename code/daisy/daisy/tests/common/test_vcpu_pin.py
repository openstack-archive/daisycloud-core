import mock
from daisy import test
from daisy.common import utils
from daisy.common import vcpu_pin


class TestVcpuPin(test.TestCase):

    def test_pci_get_cpu_sets(self):
        numa_node0 = range(0, 6) + range(12, 18)
        numa_node1 = range(6, 12) + range(18, 24)
        numa_cpus = {'numa_node0': numa_node0,
                     'numa_node1': numa_node1}
        device_numa_node = {'0000:7f:0f.1': 1}
        clc_pci_list = ["7f:0f.1"]

        (status, pci_cpusets) = vcpu_pin.pci_get_cpu_sets(numa_cpus,
                                                          device_numa_node,
                                                          clc_pci_list)
        self.assertEqual(status['rc'], 0)
        self.assertEqual(set(pci_cpusets['high']), set(numa_node1))

        numa_cpus = {}
        (status, pci_cpusets) = vcpu_pin.pci_get_cpu_sets(numa_cpus,
                                                          device_numa_node,
                                                          clc_pci_list)
        self.assertEqual(status['rc'], 4)
        self.assertEqual(set(pci_cpusets['high']), set([-4]))
        numa_cpus = {'numa_node0': '',
                     'numa_node1': ''}
        (status, pci_cpusets) = vcpu_pin.pci_get_cpu_sets(numa_cpus,
                                                          device_numa_node,
                                                          clc_pci_list)
        self.assertEqual(status['rc'], 4)
        self.assertEqual(set(pci_cpusets['high']), set([-4]))

        numa_cpus = {'numa_node0': numa_node0,
                     'numa_node1': numa_node1}
        device_numa_node = {'0000:7f:0f.1': -1}
        (status, pci_cpusets) = vcpu_pin.pci_get_cpu_sets(numa_cpus,
                                                          device_numa_node,
                                                          clc_pci_list)
        self.assertEqual(status['rc'], 1)
        self.assertEqual(set(pci_cpusets['high']), set([-1]))

        device_numa_node = {'0000:7f:0f.1': 2}
        (status, pci_cpusets) = vcpu_pin.pci_get_cpu_sets(numa_cpus,
                                                          device_numa_node,
                                                          clc_pci_list)
        self.assertEqual(status['rc'], 5)
        self.assertEqual(set(pci_cpusets['high']), set([-5]))

    def test_dvs_get_cpu_sets(self):
        numa_node0 = range(0, 6) + range(12, 18)
        numa_node1 = range(6, 12) + range(18, 24)
        numa_cpus = {'numa_node0': numa_node0,
                     'numa_node1': numa_node1}
        nics_info = [{'name': 'eth0', 'bus': '0000:7f:0f.2'}]
        device_numa_node = {'0000:7f:0f.2': 0}

        (status, dvs_cpusets) = vcpu_pin.dvs_get_cpu_sets(numa_cpus,
                                                          nics_info,
                                                          device_numa_node)
        self.assertEqual(status['rc'], 0)
        expect_dvs_high = numa_node0
        self.assertEqual(dvs_cpusets['dvs']['dvsp'], [14, 15])
        self.assertEqual(dvs_cpusets['dvs']['dvsv'], [2, 3])
        self.assertEqual(dvs_cpusets['dvs']['dvsc'], [1, 13])
        self.assertEqual(set(dvs_cpusets['high']),
                         (set(numa_node0) - set(dvs_cpusets['dvs']['dvsp']) -
                          set(dvs_cpusets['dvs']['dvsv']) -
                          set(dvs_cpusets['dvs']['dvsc'])))

        numa_cpus = {}
        (status, dvs_cpusets) = vcpu_pin.dvs_get_cpu_sets(numa_cpus,
                                                          nics_info,
                                                          device_numa_node)
        self.assertEqual(status['rc'], 4)
        self.assertEqual(set(dvs_cpusets['high']), set([-4]))
        self.assertEqual(dvs_cpusets['dvs']['dvsc'], [-4])
        self.assertEqual(dvs_cpusets['dvs']['dvsp'], [-4])
        self.assertEqual(dvs_cpusets['dvs']['dvsv'], [-4])
        numa_cpus = {'numa_node0': '',
                     'numa_node1': ''}
        (status, dvs_cpusets) = vcpu_pin.dvs_get_cpu_sets(numa_cpus,
                                                          nics_info,
                                                          device_numa_node)
        self.assertEqual(status['rc'], 4)
        self.assertEqual(set(dvs_cpusets['high']), set([-4]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsp']), set([-4]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsv']), set([-4]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsc']), set([-4]))

        numa_cpus = {'numa_node0': numa_node0,
                     'numa_node1': numa_node1}
        device_numa_node = {'0000:7f:0f.2': -1}
        (status, dvs_cpusets) = vcpu_pin.dvs_get_cpu_sets(numa_cpus,
                                                          nics_info,
                                                          device_numa_node)
        self.assertEqual(status['rc'], 1)
        self.assertEqual(set(dvs_cpusets['high']), set([-1]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsp']), set([-1]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsc']), set([-1]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsv']), set([-1]))

        device_numa_node = {'0000:7f:0f.2': 0, '0000:7f:0f.3': 1}
        nics_info = [{'name': 'eth0', 'bus': '0000:7f:0f.2'},
                     {'name': 'eth1', 'bus': '0000:7f:0f.3'}]
        (status, dvs_cpusets) = vcpu_pin.dvs_get_cpu_sets(numa_cpus,
                                                          nics_info,
                                                          device_numa_node)
        self.assertEqual(status['rc'], 2)
        self.assertEqual(set(dvs_cpusets['high']), set([-2]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsp']), set([-2]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsv']), set([-2]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsc']), set([-2]))

        nics_info = [{'name': 'eth0', 'bus': '0000:7f:0f.2'}]
        device_numa_node = {'0000:7f:0f.3': 0}
        (status, dvs_cpusets) = vcpu_pin.dvs_get_cpu_sets(numa_cpus,
                                                          nics_info,
                                                          device_numa_node)
        self.assertEqual(status['rc'], 3)
        self.assertEqual(set(dvs_cpusets['high']), set([-3]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsp']), set([-3]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsc']), set([-3]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsv']), set([-3]))

        nics_info = [{'name': 'eth0', 'bus': '0000:7f:0f.2'}]
        device_numa_node = {'0000:7f:0f.2': 2}
        (status, dvs_cpusets) = vcpu_pin.dvs_get_cpu_sets(numa_cpus,
                                                          nics_info,
                                                          device_numa_node)
        self.assertEqual(status['rc'], 5)
        self.assertEqual(set(dvs_cpusets['high']), set([-5]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsc']), set([-5]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsp']), set([-5]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsv']), set([-5]))

        numa_node0 = range(0, 4)
        numa_node1 = range(6, 10)
        numa_cpus = {'numa_node0': numa_node0,
                     'numa_node1': numa_node1}
        nics_info = [{'name': 'eth0', 'bus': '0000:7f:0f.2'}]
        device_numa_node = {'0000:7f:0f.2': 0}
        (status, dvs_cpusets) = vcpu_pin.dvs_get_cpu_sets(numa_cpus,
                                                          nics_info,
                                                          device_numa_node, 4)
        print dvs_cpusets
        self.assertEqual(status['rc'], 6)
        self.assertEqual(set(dvs_cpusets['high']), set([-6]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsc']), set([-6]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsp']), set([-6]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsv']), set([-6]))

    def test_get_dvs_cpusets(self):
        numa_node0 = range(0, 6) + range(12, 18)
        numa_node1 = range(6, 12) + range(18, 24)
        numa_cpus = {'numa_node0': numa_node0,
                     'numa_node1': numa_node1}
        host_detail = {'id': 'host_id_123',
                       'interfaces': [{'name': 'eth0', 'type': 'ether',
                                       'vswitch_type': 'dvs'}],
                       'devices': {'7f-0f-1': {'0000:7f:0f.1': 0}}}
        host_hw_info = {'interfaces': {'eth0': {'name': 'eth0',
                                                'pci': '0000:7f:0f.1'}}}

        dvs_cpusets = vcpu_pin.get_dvs_cpusets(
            numa_cpus, host_detail, host_hw_info)
        self.assertEqual(set(dvs_cpusets['high']), set([0, 4, 5, 12, 16, 17]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsc']), set([1, 13]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsp']), set([14, 15]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsv']), set([2, 3]))

        host_detail = {'id': 'host_id_123',
                       'interfaces': [{'name': 'eth0', 'type': 'ether',
                                       'vswitch_type': ''}]}
        host_hw_info = {'devices': {'7f-0f-1': {'0000:7f:0f.1': 0}},
                        'interfaces': {'eth0': {'name': 'eth0',
                                                'pci': '0000:7f:0f.1'}}}

        dvs_cpusets = vcpu_pin.get_dvs_cpusets(
            numa_cpus, host_detail, host_hw_info)
        self.assertEqual(set(dvs_cpusets['high']), set([-7]))
        self.assertEqual(set(dvs_cpusets['low']), set([-7]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsp']), set([-7]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsv']), set([-7]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsc']), set([-7]))

        host_detail = {'id': 'host_id_123',
                       'interfaces': [{'slave1': 'eth0',
                                       'slave2': 'eth1', 'type': 'bond',
                                       'vswitch_type': 'dvs'}]}
        host_hw_info = {'devices': {'7f-0f-1': {'0000:7f:0f.1': 0},
                                    '7f-0f-2': {'0000:7f:0f.2': 0}},
                        'interfaces': {'eth0': {'name': 'eth0',
                                                'pci': '0000:7f:0f.1'},
                                       'eth1': {'name': 'eth1',
                                                'pci': '0000:7f:0f.2'}}}
        dvs_cpusets = vcpu_pin.get_dvs_cpusets(
            numa_cpus, host_detail, host_hw_info)
        self.assertEqual(set(dvs_cpusets['high']), set([0, 4, 5, 12, 16, 17]))
        self.assertEqual(set(dvs_cpusets['low']), set(numa_node1))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsc']), set([1, 13]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsp']), set([14, 15]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsv']), set([2, 3]))

        host_detail = {'id': 'host_id_123',
                       'interfaces': [{'slave1': 'eth0',
                                       'slave2': 'eth1', 'type': 'bond',
                                       'vswitch_type': 'dvs'}]}
        host_hw_info = {'devices': {'7f-0f-1': {'0000:7f:0f.1': 0},
                                    '7f-0f-2': {'0000:7f:0f.2': 1}},
                        'interfaces': {'eth0': {'name': 'eth0',
                                                'pci': '0000:7f:0f.1'},
                                       'eth1': {'name': 'eth1',
                                                'pci': '0000:7f:0f.2'}}}
        dvs_cpusets = vcpu_pin.get_dvs_cpusets(
            numa_cpus, host_detail, host_hw_info)
        self.assertEqual(set(dvs_cpusets['high']), set([-2]))
        self.assertEqual(set(dvs_cpusets['low']), set([-2]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsc']), set([-2]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsp']), set([-2]))
        self.assertEqual(set(dvs_cpusets['dvs']['dvsv']), set([-2]))

    def test_allocate_os_cpus(self):
        numa_node0 = range(0, 6) + range(12, 18)
        numa_node1 = range(6, 12) + range(18, 24)

        # pci_cpusets = {'high': numa_node0 + numa_node1, 'low': []}
        # dvs_cpusets = {'high': numa_node0 + numa_node1, 'low': [],
        # 'dvs': [20, 21, 22, 23]}
        # roles_name = ['COMPUTER']
        # os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
        # pci_cpusets, dvs_cpusets)
        # self.assertEqual(set(os_cpus), set([0, 1]))
        dvs_high = list(set(numa_node0) - set([13, 14, 15, 16, 17, 12]))
        pci_cpusets = {'high': numa_node0, 'low': numa_node1}
        dvs_cpusets = {'high': dvs_high, 'low': numa_node1,
                       'dvs': {'dvsc': [12, 13], 'dvsp': [14, 15],
                               'dvsv': [16, 17]}}

        roles_name = ['CONTROLLER_LB', 'CONTROLLER_HA']
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([]))

        roles_name = []
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([]))

        roles_name = []
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([]))

        roles_name = ['COMPUTER']
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([0, 12]))

        roles_name = ['COMPUTER', 'CONTROLLER_HA']
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([0, 12, 18, 6]))

        roles_name = ['COMPUTER', 'CONTROLLER_LB']
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([0, 12, 18, 6]))

        roles_name = ['COMPUTER', 'CONTROLLER_LB', 'CONTROLLER_HA']
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([0, 12, 18, 6]))

        pci_cpusets = {}
        dvs_high = list(set(numa_node1) - set([18, 19, 20, 21, 22, 23]))
        dvs_cpusets = {'high': numa_node1, 'low': numa_node0,
                       'dvs': {'dvsc': [20, 21], 'dvsp': [22, 23],
                               'dvsc': [18, 19]}}

        roles_name = ['COMPUTER']
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([0, 18]))

        pci_cpusets = {'high': numa_node0, 'low': numa_node1}
        dvs_cpusets = {}
        roles_name = ['COMPUTER', 'CONTROLLER_LB', 'CONTROLLER_HA']
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([0, 6, 12, 18]))

        pci_cpusets = {'high': [-4], 'low': [-4]}
        dvs_cpusets = {'high': numa_node0, 'low': numa_node1,
                       'dvs': [14, 15, 16, 17]}
        roles_name = ['COMPUTER']
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([]))

        pci_cpusets = {'high': numa_node0, 'low': numa_node1}
        dvs_cpusets = {'high': [-2], 'low': [-2],
                       'dvs': [-2]}
        roles_name = ['COMPUTER']
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([]))

        pci_cpusets = {'high': [-4], 'low': [-4]}
        dvs_cpusets = {'high': [-2], 'low': [-2],
                       'dvs': [-2]}
        roles_name = ['COMPUTER']
        os_cpus = vcpu_pin.allocate_os_cpus(roles_name,
                                            pci_cpusets, dvs_cpusets)
        self.assertEqual(set(os_cpus), set([]))

    def test_allocate_clc_cpus(self):
        host_detail = {'id': 'host_id_123',
                       'interfaces': []}
        clc_cpu_sets = vcpu_pin.allocate_clc_cpus(host_detail)
        self.assertEqual(clc_cpu_sets, {})
        numa_nodes = {'numa_node0': "0-5,12-17",
                      'numa_node1': "6-11,18-23"}
        host_detail = {'id': 'host_id_123',
                       'interfaces': [{'mac': '123'}],
                       'role': ['COMPUTER'],
                       'devices': {'7f-0f-1': {'0000:7f:0f.1': 0}},
                       'cpu': numa_nodes,
                       'pci': {'0000:7f:0f.1': '8086:0a48'}}
        host_hw_info = {}
        utils.get_host_hw_info = mock.Mock(return_value=host_hw_info)
        clc_cpu_sets = vcpu_pin.allocate_clc_cpus(host_detail)
        self.assertEqual(clc_cpu_sets, {})

        host_hw_info = {'devices': {'7f-0f-1': {'0000:7f:0f.1': 0}},
                        'cpu': numa_nodes,
                        'pci': {'7f-0f-1': '7f:0f.1 8086:0435'}}
        utils.get_host_hw_info = mock.Mock(return_value=host_hw_info)
        clc_cpu_sets = vcpu_pin.allocate_clc_cpus(host_detail)
        numa_node0 = range(0, 6) + range(12, 18)
        numa_node1 = range(6, 12) + range(18, 24)
        self.assertEqual(set(clc_cpu_sets['high']), set(numa_node0))
        self.assertEqual(set(clc_cpu_sets['low']), set(numa_node1))

        host_hw_info = {'devices': {'7f-0f-1': {'0000:7f:0f.1': 0},
                                    '7f-0f-2': {'0000:7f:0f.2': 1}},
                        'cpu': numa_nodes,
                        'pci': {'7f-0f-1': '7f:0f.1 8086:0435',
                                '7f-0f-2': '7f:0f.2 8086:0435'}}
        utils.get_host_hw_info = mock.Mock(return_value=host_hw_info)
        clc_cpu_sets = vcpu_pin.allocate_clc_cpus(host_detail)
        self.assertEqual(set(clc_cpu_sets['high']),
                         set(numa_node0+numa_node1))
        self.assertEqual(set(clc_cpu_sets['low']), set([]))

        host_hw_info = {'devices': {'7f-0f-1': {'0000:7f:0f.1': -1}},
                        'cpu': numa_nodes,
                        'pci': {'7f-0f-1': '7f:0f.1 8086:0435'}}
        utils.get_host_hw_info = mock.Mock(return_value=host_hw_info)
        clc_cpu_sets = vcpu_pin.allocate_clc_cpus(host_detail)
        self.assertEqual(set(clc_cpu_sets['high']), set([-1]))
        self.assertEqual(set(clc_cpu_sets['low']), set([-1]))

    def test_allocate_dvs_cpus(self):
        host_detail = {'id': 'host_id_123',
                       'interfaces': []}
        dvs_cpu_sets = vcpu_pin.allocate_dvs_cpus(host_detail)
        self.assertEqual(dvs_cpu_sets, {})

        host_detail = {'id': 'host_id_123',
                       'interfaces': [{'name': 'eth0', 'type': 'ether',
                                       'vswitch_type': 'ovs'}]}

        dvs_cpu_sets = vcpu_pin.allocate_dvs_cpus(host_detail)
        self.assertEqual(dvs_cpu_sets, {})
        numa_nodes = {'numa_node0': "0-5,12-17",
                      'numa_node1': "6-11,18-23"}
        host_detail = {'id': 'host_id_123',
                       'interfaces': [{'name': 'eth0', 'type': 'ether',
                                       'vswitch_type': 'dvs'}],
                       'cpu': numa_nodes,
                       'devices': {'7f-0f-1': {'0000:7f:0f.1': 0}}
                       }
        host_hw_info = {'interfaces': {'eth0': {'name': 'eth0',
                                                'pci': '0000:7f:0f.1'}}}
        utils.get_host_hw_info = mock.Mock(return_value=host_hw_info)
        dvs_cpu_sets = vcpu_pin.allocate_dvs_cpus(host_detail)
        numa_node0 = range(0, 6) + range(12, 18)
        numa_node1 = range(6, 12) + range(18, 24)
        self.assertEqual(set(dvs_cpu_sets['dvs']['dvsc']), set([1, 13]))
        self.assertEqual(set(dvs_cpu_sets['dvs']['dvsp']), set([14, 15]))
        self.assertEqual(set(dvs_cpu_sets['dvs']['dvsv']), set([2, 3]))
        self.assertEqual(set(dvs_cpu_sets['high']), set([0, 4, 5, 12, 16, 17]))
        self.assertEqual(set(dvs_cpu_sets['low']), set(numa_node1))

    def test_allocate_cpus(self):
        numa_nodes = {'numa_node0': '0-5,12-17',
                      'numa_node1': '6-11,18-23'}
        roles = ['CONTROLLER_LB', 'CONTROLLER_HA', 'COMPUTER']
        host_detail = {'id': "host_test_id",
                       'name': "host_test_name",
                       'role': roles,
                       'interfaces': [{'name': 'eth0', 'type': 'ether',
                                       'vswitch_type': 'ovs'}],
                       'cpu': numa_nodes,
                       'devices': {'7f-0f-1': {'0000:7f:0f.1': 0}},
                       'pci': {'7f-0f-1': '7f:0f.1 8086:0a48'}}
        host_hw_info = {'interfaces': {'eth0': {'name': 'eth0',
                                                'pci': '0000:7f:0f.1'}}}
        utils.get_host_hw_info = mock.Mock(return_value=host_hw_info)
        cpu_sets = vcpu_pin.allocate_cpus(host_detail)
        expect_cpu_sets = {'suggest_dvs_high_cpuset': '',
                           'pci_high_cpuset': '',
                           'suggest_dvs_cpus': '',
                           'suggest_os_cpus': ''}
        self.assertEqual(cpu_sets, expect_cpu_sets)

        host_detail = {'id': "host_test_id",
                       'name': "host_test_name",
                       'role': roles,
                       'interfaces': [{'name': 'eth0', 'type': 'ether',
                                       'vswitch_type': 'dvs'}]}
        cpu_sets = vcpu_pin.allocate_cpus(host_detail)
        expect_cpu_sets = {'suggest_dvs_cpus': '1-3,13-15',
                           'suggest_dvsp_cpus': '14,15',
                           'numa_node': 0,
                           'suggest_dvsc_cpus': '1,13',
                           'suggest_dvsv_cpus': '2,3',
                           'suggest_os_cpus': '0,6,12,18',
                           'suggest_dvs_high_cpuset': '0,4,5,12,16,17',
                           'pci_high_cpuset': ''}
        self.assertEqual(cpu_sets, expect_cpu_sets)

        host_detail = {'id': "host_test_id",
                       'name': "host_test_name",
                       'role': roles,
                       'interfaces': [{'name': 'eth0', 'type': 'ether',
                                       'vswitch_type': 'ovs'}]}
        host_hw_info = {'cpu': numa_nodes,
                        'devices': {'7f-0f-1': {'0000:7f:0f.1': 0}},
                        'interfaces': {'eth0': {'name': 'eth0',
                                                'pci': '0000:7f:0f.1'}},
                        'pci': {'7f-0f-1': '7f:0f.1 8086:0435'}}
        utils.get_host_hw_info = mock.Mock(return_value=host_hw_info)
        cpu_sets = vcpu_pin.allocate_cpus(host_detail)
        expect_cpu_sets = {'suggest_dvs_high_cpuset': '',
                           'pci_high_cpuset': '0-5,12-17',
                           'suggest_dvs_cpus': '',
                           'numa_node': [],
                           'suggest_os_cpus': '0,6,12,18'}
        self.assertEqual(cpu_sets, expect_cpu_sets)

        host_detail = {'id': "host_test_id",
                       'name': "host_test_name",
                       'role': roles,
                       'interfaces': [{'name': 'eth0', 'type': 'ether',
                                       'vswitch_type': 'dvs'}]}
        host_hw_info = {'cpu': numa_nodes,
                        'devices': {'7f-0f-1': {'0000:7f:0f.1': 0}},
                        'interfaces': {'eth0': {'name': 'eth0',
                                                'pci': '0000:7f:0f.1'}},
                        'pci': {'7f-0f-1': '7f:0f.1 8086:0435'}}
        utils.get_host_hw_info = mock.Mock(return_value=host_hw_info)
        cpu_sets = vcpu_pin.allocate_cpus(host_detail)
        expect_cpu_sets = {'suggest_dvs_high_cpuset': '0,4,5,12,16,17',
                           'pci_high_cpuset': '0-5,12-17',
                           'suggest_dvs_cpus': '1-3,13-15',
                           'suggest_dvsc_cpus': '1,13',
                           'suggest_dvsp_cpus': '14,15',
                           'suggest_dvsv_cpus': '2,3',
                           'suggest_os_cpus': '0,6,12,18',
                           'numa_node': 0}
        self.assertEqual(cpu_sets, expect_cpu_sets)

        host_detail = {'id': "host_test_id",
                       'name': "host_test_name",
                       'role': roles,
                       'interfaces': [{'name': 'eth0', 'type': 'ether',
                                       'vswitch_type': 'dvs'}]}
        host_hw_info = {'cpu': numa_nodes,
                        'devices': {'7f-0f-1': {'0000:7f:0f.1': 0},
                                    '7f-0f-2': {'0000:7f:0f.2': 1}},
                        'interfaces': {'eth0': {'name': 'eth0',
                                                'pci': '0000:7f:0f.2'}},
                        'pci': {'7f-0f-1': '7f:0f.1 8086:0435'}}
        utils.get_host_hw_info = mock.Mock(return_value=host_hw_info)
        cpu_sets = vcpu_pin.allocate_cpus(host_detail)
        expect_cpu_sets = {'suggest_dvs_high_cpuset': '6,10,11,18,22,23',
                           'pci_high_cpuset': '0-5,12-17',
                           'suggest_dvs_cpus': '7-9,19-21',
                           'suggest_dvsc_cpus': '7,19',
                           'suggest_dvsp_cpus': '20,21',
                           'suggest_dvsv_cpus': '8,9',
                           'suggest_os_cpus': '0,6,12,18',
                           'numa_node': 1}
        self.assertEqual(cpu_sets, expect_cpu_sets)
