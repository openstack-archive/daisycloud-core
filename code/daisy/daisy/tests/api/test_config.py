
import daisy.api.backends.tecs.config as tecs_config

import unittest
import os

compute_role = {"Compute":
                    {'services':
                        {'server1': 'component1', 'server2': 'component2'},
                     'host_interfaces':
                            [{'management': {'ip': '192.168.1.1'},
                              'deployment': {'ip': '192.168.0.1'}, },
                             {'management': {'ip': '192.168.1.2'},
                              'deployment': {'ip': '192.168.0.2'}, }, ],
                     'vip': '192.168.4.2', }, }

ha_role = {"CONTROLLER_HA":
               {'services':
                    {'nova-api': 'component3', 'mariadb': 'component4'},
                'host_interfaces':
                    [{'management': {'ip': '192.168.1.3', 'netmask': "255.255.255.0", 'name': 'eth0', },
                      'deployment': {'ip': '192.168.0.3'},
                      'storage': {'ip': '192.168.5.3'}, },
                     {'management': {'ip': '192.168.1.4', 'netmask': "255.255.255.0", 'name': 'eth0', },
                      'deployment': {'ip': '192.168.0.4'},
                      'storage': {'ip': '192.168.5.3'}, }, ],
                'vip': '192.168.4.4', }, }

lb_role = {"CONTROLLER_LB":
               {'services':
                    {'nova-api': 'component5', 'mariadb': 'component6'},
                'host_interfaces':
                    [{'management': {'ip': '192.168.1.5', 'netmask': "255.255.255.0", 'name': 'eth0', },
                      'deployment': {'ip': '192.168.0.5'},
                      'storage': {'ip': '192.168.5.5'}, },
                     {'management': {'ip': '192.168.1.6', 'netmask': "255.255.255.0", 'name': 'eth0', },
                      'deployment': {'ip': '192.168.0.6'},
                      'storage': {'ip': '192.168.5.6'}, }, ],
                'vip': '192.168.4.6', }, }

def merge_dict(*args):
    result = dict()
    for a in args:
        if isinstance(a, dict):
            result.update(a)
    return result
mix_roles = merge_dict(compute_role, ha_role, lb_role)


class TestTecsConfig(unittest.TestCase):
    def setUp(self):
        tecs_config.tecs_conf_template_path = os.path.dirname(os.path.realpath(__file__))
        print tecs_config.tecs_conf_template_path

    def tearDown(self):
        tecs_config.tecs_conf_template_path = tecs_config.default_tecs_conf_template_path

    def test_config_with_nothing(self):
        tecs, ha = tecs_config.update_tecs_conf("ab-11", {})
        self.assertTrue(True)

    def test_config_with_compute_role(self):
        tecs,ha = tecs_config.update_tecs_conf("ab-11", compute_role )
        self.assertTrue(True)
        print tecs,ha

    def test_config_with_ha_role(self):
        tecs, ha = tecs_config.update_tecs_conf("ab-11", ha_role )
        self.assertTrue(True)

    def test_config_with_lb_role(self):
        tecs, ha = tecs_config.update_tecs_conf("ab-11", lb_role )
        self.assertTrue(True)

    def test_config_with_all_role(self):
        tecs, ha = tecs_config.update_tecs_conf("ab-11", lb_role )
        self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()