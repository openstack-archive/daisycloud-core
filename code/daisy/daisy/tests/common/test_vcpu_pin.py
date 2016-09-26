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
                         (set(numa_node0) - set(
                             dvs_cpusets['dvs']['dvsp']) - set(
                             dvs_cpusets['dvs']['dvsv']) - set(
                             dvs_cpusets['dvs']['dvsc'])))

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
                                       'vswitch_type': 'dvs'}]}
        host_hw_info = {'devices': {'7f-0f-1': {'0000:7f:0f.1': 0}},
                        'interfaces': {'eth0': {'name': 'eth0',
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

        host_detail = {'id': 'host_id_123',
                       'interfaces': [{'name': 'eth0', 'type': 'ether',
                                       'vswitch_type': 'dvs'}]}
        numa_nodes = {'numa_node0': "0-5,12-17",
                      'numa_node1': "6-11,18-23"}
        host_hw_info = {'cpu': numa_nodes,
                        'devices': {'7f-0f-1': {'0000:7f:0f.1': 0}},
                        'interfaces': {'eth0': {'name': 'eth0',
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
