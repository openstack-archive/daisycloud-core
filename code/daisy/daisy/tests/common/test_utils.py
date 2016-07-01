import unittest
from daisy.common import utils


class TestUtils(unittest.TestCase):

    def test_get_numa_node_cpus(self):
        host_cpu = {'numa_node0': '0-5,12-17',
                    'numa_node1': '6-11,18-23'}
        node0_cpus = range(0, 6) + range(12, 18)
        node1_cpus = range(6, 12) + range(18, 24)
        real_numa_cpus = utils.get_numa_node_cpus(host_cpu)
        expect_numa_cpus = {'numa_node0': node0_cpus,
                            'numa_node1': node1_cpus, }
        self.assertEqual(expect_numa_cpus, real_numa_cpus)

        host_cpu = {'numa_node0': '0-5,12-17'}
        node0_cpus = range(0, 6) + range(12, 18)
        real_numa_cpus = utils.get_numa_node_cpus(host_cpu)
        expect_numa_cpus = {'numa_node0': node0_cpus}
        self.assertEqual(expect_numa_cpus, real_numa_cpus)

        host_cpu = {'numa_node1': '6-11,18-23'}
        node1_cpus = range(6, 12) + range(18, 24)
        real_numa_cpus = utils.get_numa_node_cpus(host_cpu)
        expect_numa_cpus = {'numa_node1': node1_cpus, }
        self.assertEqual(expect_numa_cpus, real_numa_cpus)

        host_cpu = {}
        real_numa_cpus = utils.get_numa_node_cpus(host_cpu)
        expect_numa_cpus = {}
        self.assertEqual(expect_numa_cpus, real_numa_cpus)

    def test_get_numa_node_from_cpus(self):
        node0_cpus = range(0, 6) + range(12, 18)
        node1_cpus = range(6, 12) + range(18, 24)
        numa_cpus = {'numa_node0': node0_cpus,
                     'numa_node1': node1_cpus, }
        cpus_str = '1,2,12-17'
        real_numas = utils.get_numa_node_from_cpus(numa_cpus, cpus_str)
        expect_numas = [0]
        self.assertEqual(expect_numas, real_numas)

        cpus_str = '0-5,6-11,12-17,18-23'
        real_numas = utils.get_numa_node_from_cpus(numa_cpus, cpus_str)
        expect_numas = [0, 1]
        self.assertEqual(expect_numas, real_numas)
