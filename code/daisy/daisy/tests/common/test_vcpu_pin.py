import unittest
import mock
from daisy.common import vcpu_pin


class TestVcpuPin(unittest.TestCase):

    def test_allocate_cpus_with_dvs_and_pci_on_same_node(self):
        host_cpu = {'numa_node0': '0-5,12-17',
                    'numa_node1': '6-11,18-23'}
        roles = ['CONTROLLER_LB', 'CONTROLLER_HA', 'COMPUTER']
        #interfaces = [{'switch_type': 'dvs', 'name': 'ens33'}]
        host_detail = {'id': "host_test_id",
                       'name': "host_test_name",
                       'cpu': host_cpu,
                       'role': roles}
        dvs_cpus = [14, 15, 16, 17]
        high_cpusets = range(12, 18) + range(0, 6)
        low_cpusets = range(18, 24) + range(6, 12)
        dvs_cpu_sets = mock.Mock(return_value={'high': high_cpusets,
                                               'low': low_cpusets,
                                               'dvs': dvs_cpus})
        vcpu_pin.allocate_dvs_cpus = dvs_cpu_sets
        pci_cpu_sets = mock.Mock(return_value={'high': high_cpusets,
                                               'low': low_cpusets})
        vcpu_pin.allocate_clc_cpus = pci_cpu_sets
        real_cpu_sets = vcpu_pin.allocate_cpus(host_detail)
        expect_cpu_sets = {'dvs_high_cpuset': '0-5,12-17',
                           'pci_high_cpuset': '0-5,12-17',
                           'suggest_dvs_cpus': '14-17',
                           'suggest_os_cpus': '0,6-8'}
        self.assertEqual(expect_cpu_sets, real_cpu_sets)
