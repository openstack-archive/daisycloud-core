from daisy import test
from daisy.common import exception
from daisy.common import utils


class TestUtils(test.TestCase):

    def test_get_numa_node_cpus(self):
        host_cpu = {'numa_node0': '0-5,12-17',
                    'numa_node1': '6-11,18-23'}
        node0_cpus = range(0, 6) + range(12, 18)
        node1_cpus = range(6, 12) + range(18, 24)
        real_numa_cpus = utils.get_numa_node_cpus(host_cpu)
        expect_numa_cpus = {'numa_node0': node0_cpus,
                            'numa_node1': node1_cpus, }
        self.assertEqual(real_numa_cpus, expect_numa_cpus)

        host_cpu = {'numa_node0': '0-5,12-17'}
        node0_cpus = range(0, 6) + range(12, 18)
        real_numa_cpus = utils.get_numa_node_cpus(host_cpu)
        expect_numa_cpus = {'numa_node0': node0_cpus}
        self.assertEqual(real_numa_cpus, expect_numa_cpus)

        host_cpu = {'numa_node1': '6-11,18-23'}
        node1_cpus = range(6, 12) + range(18, 24)
        real_numa_cpus = utils.get_numa_node_cpus(host_cpu)
        expect_numa_cpus = {'numa_node1': node1_cpus, }
        self.assertEqual(real_numa_cpus, expect_numa_cpus)

        host_cpu = {}
        real_numa_cpus = utils.get_numa_node_cpus(host_cpu)
        expect_numa_cpus = {}
        self.assertEqual(real_numa_cpus, expect_numa_cpus)

    def test_get_numa_node_from_cpus(self):
        node0_cpus = range(0, 6) + range(12, 18)
        node1_cpus = range(6, 12) + range(18, 24)
        numa_cpus = {'numa_node0': node0_cpus,
                     'numa_node1': node1_cpus, }
        cpus_str = '1,2,12-17'
        real_numas = utils.get_numa_node_from_cpus(numa_cpus, cpus_str)
        expect_numas = [0]
        self.assertEqual(real_numas, expect_numas)

        cpus_str = '0-5,6-11,12-17,18-23'
        real_numas = utils.get_numa_node_from_cpus(numa_cpus, cpus_str)
        expect_numas = [0, 1]
        self.assertEqual(real_numas, expect_numas)

        numa_cpus = {'numa_node': node0_cpus,
                     'numa_node1': node1_cpus, }
        self.assertRaises(exception.Invalid,
                          utils.get_numa_node_from_cpus, numa_cpus, cpus_str)

    def test_get_numa_node_from_dvsc_cpus(self):
        node0_cpus = range(0, 6) + range(12, 18)
        node1_cpus = range(6, 12) + range(18, 24)
        numa_cpus = {'numa_node0': node0_cpus,
                     'numa_node1': node1_cpus, }
        dvsc_cpus = '3,4'
        real_numas = utils.get_numa_node_from_dvsc_cpus(numa_cpus, dvsc_cpus)
        expect_numas = [0]
        self.assertEqual(real_numas, expect_numas)

        dvsc_cpus = '6-7'
        real_numas = utils.get_numa_node_from_dvsc_cpus(numa_cpus, dvsc_cpus)
        expect_numas = [1]
        self.assertEqual(real_numas, expect_numas)

    def test_get_numa_node_from_dvsc_cpus_with_exception(self):
        dvsc_cpus = '6'
        node0_cpus = range(0, 6) + range(12, 18)
        node1_cpus = range(6, 12) + range(18, 24)
        numa_cpus = {'numa_node0': node0_cpus,
                     'numa_nod': node1_cpus, }
        self.assertRaises(exception.Invalid,
                          utils.get_numa_node_from_dvsc_cpus, numa_cpus, dvsc_cpus)

    def test_cidr_convert_to_ip_ranges(self):
        cidr = '192.168.1.25/31'
        ip_range = utils.cidr_convert_to_ip_ranges(cidr)
        self.assertEqual('192.168.1.24', ip_range[0])
        self.assertEqual('192.168.1.25', ip_range[1])

    def test_is_ip_ranges_overlapped(self):
        ip_ranges = [['12.1.1.1', '12.1.1.12'], ['12.1.1.9', '12.1.1.17']]
        self.assertEqual(True, utils.is_ip_ranges_overlapped(ip_ranges))

    def test_is_cidrs_overlapped_true(self):
        cidrs = ['12.1.1.1/24', '13.1.1.1/24', '13.1.1.1/23']
        self.assertEqual(True, utils.is_cidrs_overlapped(cidrs))

    def test_is_cidrs_overlapped_false(self):
        cidrs = ['12.1.1.1/24', '13.1.1.1/24', '14.1.1.1/23']
        self.assertEqual(False, utils.is_cidrs_overlapped(cidrs))
