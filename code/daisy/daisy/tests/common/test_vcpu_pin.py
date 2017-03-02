from daisy import test
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

    def test_allocate_cpus(self):
        except_host_cpu_sets = {'suggest_dvs_high_cpuset': '',
                     'pci_high_cpuset': '',
                     'suggest_dvs_cpus': '',
                     'suggest_os_cpus': ''}
        host_detail = {u'cpu': {"numa_node0": "0-9,20-29",
                                "numa_node1": "10-19,30-39"},
                       u'devices': {"0000:ff:09.3": {"0000:ff:09.3": "-1"},
                                    "0000:ff:09.2": {"0000:ff:09.2": "-1"}},
                       u'disks': u'{"mpathd": {"name": "mpathd", '
                                 u' "size": " 107374182400 bytes"}}',
                       u'interfaces': [],
                       u'memory': u'{"total": " 263650268 kB", '
                                  u'"phy_memory_1": {"devices_15": {"frequency": " 2133 MHz", '
                                  u'"type": " <OUT OF SPEC>", "size": " 16384 MB"}}}',
                       u'pci': u'{"ff:0c.4": '
                               u'"ff:0c.4 System peripheral: Intel Corporation '
                               u'Haswell-E Unicast Registers (rev 02)"}',
                       u'role': [u'CONTROLLER_LB', u'CONTROLLER_HA', u'COMPUTER'],
                       u'system': u'{"product": "EC600G3", "manufacturer": "ZTE"}'
        }

        host_cpu_sets = vcpu_pin.allocate_cpus(host_detail)
        self.assertEqual(host_cpu_sets, except_host_cpu_sets)
