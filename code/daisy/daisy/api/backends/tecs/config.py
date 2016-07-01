# -*- coding: utf-8 -*-
import os
import re
import commands
import types
import subprocess
import socket
import netaddr
from oslo_log import log as logging
from ConfigParser import ConfigParser
from daisy.common import exception
from daisy import i18n

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

service_map = {
    'lb': 'haproxy',
    'mongodb': 'mongod',
    'ha': '',
    'mariadb': 'mariadb',
    'amqp': 'rabbitmq-server',
    'ceilometer-api': 'openstack-ceilometer-api',
    'ceilometer-collector': 'openstack-ceilometer-collector,\
                                openstack-ceilometer-mend',
    'ceilometer-central': 'openstack-ceilometer-central',
    'ceilometer-notification': 'openstack-ceilometer-notification',
    'ceilometer-alarm': 'openstack-ceilometer-alarm-evaluator,\
                        openstack-ceilometer-alarm-notifier',
    'heat-api': 'openstack-heat-api',
    'heat-api-cfn': 'openstack-heat-api-cfn',
    'heat-engine': 'openstack-heat-engine',
    'ironic': 'openstack-ironic-api,openstack-ironic-conductor',
    'horizon': 'httpd,opencos-alarmmanager',
    'keystone': 'openstack-keystone',
    'glance': 'openstack-glance-api,openstack-glance-registry',
    'cinder-volume': 'openstack-cinder-volume',
    'cinder-scheduler': 'openstack-cinder-scheduler',
    'cinder-api': 'openstack-cinder-api',
    'neutron-metadata': 'neutron-metadata-agent',
    'neutron-lbaas': 'neutron-lbaas-agent',
    'neutron-dhcp': 'neutron-dhcp-agent',
    'neutron-server': 'neutron-server',
    'neutron-l3': 'neutron-l3-agent',
    'compute': 'openstack-nova-compute',
    'nova-cert': 'openstack-nova-cert',
    'nova-sched': 'openstack-nova-scheduler',
    'nova-vncproxy': 'openstack-nova-novncproxy,openstack-nova-consoleauth',
    'nova-conductor': 'openstack-nova-conductor',
    'nova-api': 'openstack-nova-api',
    'nova-cells': 'openstack-nova-cells',
    'camellia-api': 'camellia-api'
}


def add_service_with_host(services, name, host):
    if name not in services:
        services[name] = []
    services[name].append(host)


def add_service_with_hosts(services, name, hosts):
    if name not in services:
        services[name] = []
    for h in hosts:
        services[name].append(h['management']['ip'])


def test_ping(ping_src_nic, ping_desc_ips):
    ping_cmd = 'fping'
    for ip in set(ping_desc_ips):
        ping_cmd = ping_cmd + ' -I ' + ping_src_nic + ' ' + ip
    obj = subprocess.Popen(
        ping_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    _returncode = obj.returncode
    if _returncode == 0 or _returncode == 1:
        ping_result = stdoutput.split('\n')
        if "No such device" in erroutput:
            return []
        reachable_hosts = [result.split(
        )[0] for result in ping_result if result and
            result.split()[2] == 'alive']
    else:
        msg = "ping failed beaceuse there is invlid ip in %s" % ping_desc_ips
        raise exception.InvalidIP(msg)
    return reachable_hosts


def get_local_deployment_ip(tecs_deployment_ips):
    (status, output) = commands.getstatusoutput('ifconfig')
    netcard_pattern = re.compile('\S*: ')
    ip_str = '([0-9]{1,3}\.){3}[0-9]{1,3}'
    # ip_pattern = re.compile('(inet %s)' % ip_str)
    pattern = re.compile(ip_str)
    nic_ip = {}
    for netcard in re.finditer(netcard_pattern, str(output)):
        nic_name = netcard.group().split(': ')[0]
        if nic_name == "lo":
            continue
        ifconfig_nic_cmd = "ifconfig %s" % nic_name
        (status, output) = commands.getstatusoutput(ifconfig_nic_cmd)
        if status:
            continue
        ip = pattern.search(str(output))
        if ip and ip.group() != "127.0.0.1":
            nic_ip[nic_name] = ip.group()

    deployment_ip = ''
    for nic in nic_ip.keys():
        if nic_ip[nic] in tecs_deployment_ips:
            deployment_ip = nic_ip[nic]
            break
    if not deployment_ip:
        for nic, ip in nic_ip.items():
            if test_ping(nic, tecs_deployment_ips):
                deployment_ip = nic_ip[nic]
                break
    return deployment_ip


class AnalsyConfig(object):

    def __init__(self, all_configs):
        self.all_configs = all_configs

        self.services = {}
        self.components = []
        self.modes = {}
        # self.ha_conf = {}
        self.services_in_component = {}
        # self.heartbeat = {}
        self.lb_components = []
        self.heartbeats = [[], [], []]
        self.lb_vip = ''
        self.ha_vip = ''
        self.db_vip = ''
        self.glance_vip = ''
        self.public_vip = ''
        self.share_disk_services = []
        self.share_cluster_disk_services = []
        self.ha_conf = {}
        self.child_cell_dict = {}
        self.ha_master_host = {}

    def get_heartbeats(self, host_interfaces):
        for network in host_interfaces:
            self.heartbeats[0].append(network["management"]["ip"])
            # if network.has_key("heartbeat1") and network["heartbeat1"]["ip"]:
            if "heartbeat1" in network and network["heartbeat1"]["ip"]:
                self.heartbeats[1].append(network["heartbeat1"]["ip"])

            # if network.has_key("heartbeat2") and network["heartbeat2"]["ip"]:
            if "heartbeat2" in network and network["heartbeat2"]["ip"]:
                self.heartbeats[2].append(network["heartbeat2"]["ip"])

            # if network.has_key("storage") and network["storage"]["ip"]:
            if "storage" in network and network["storage"]["ip"]:
                # if not network.has_key("heartbeat1"):
                if "heartbeat1" not in network:
                    self.heartbeats[1].append(network["storage"]["ip"])
                # if network.has_key("heartbeat1") and not \
                # network.has_key("heartbeat2"):
                if "heartbeat1" in network and \
                        "heartbeat2" not in network:
                    self.heartbeats[2].append(network["storage"]["ip"])

        # delete empty heartbeat line
        if not self.heartbeats[0]:
            self.heartbeats[0] = self.heartbeats[1]
            self.heartbeats[1] = self.heartbeats[2]
        if not self.heartbeats[1]:
            self.heartbeats[1] = self.heartbeats[2]

        # remove repeated ip
        if set(self.heartbeats[1]) == set(self.heartbeats[0]):
            self.heartbeats[1] = []
            if set(self.heartbeats[2]) != set(self.heartbeats[0]):
                self.heartbeats[1] = self.heartbeats[2]
                self.heartbeats[2] = []
        if set(self.heartbeats[2]) == set(self.heartbeats[0]) or \
                set(self.heartbeats[2]) == set(self.heartbeats[1]):
            self.heartbeats[2] = []

    def prepare_child_cell(self, child_cell_name, configs):
        cell_compute_hosts = str()
        cell_compute_name = child_cell_name[11:] + '_COMPUTER'
        for role_name, role_configs in self.all_configs.items():
            if role_name == cell_compute_name:
                cell_compute_host = [
                    host_interface['management']['ip']
                    for host_interface in role_configs['host_interfaces']]
                cell_compute_hosts = ",".join(cell_compute_host)
                self.all_configs.pop(role_name)

        child_cell_host = configs['host_interfaces'][0]['management']['ip']
        self.child_cell_dict[repr(child_cell_host).strip("u'")] \
            = repr(cell_compute_hosts).strip("u'")

    def prepare_ha_lb(self, role_configs, is_ha, is_lb):
        if is_lb:
            self.ha_master_host['ip'] = role_configs[
                'host_interfaces'][0]['management']['ip']
            self.ha_master_host['hostname'] = role_configs[
                'host_interfaces'][0]['name']
            self.components.append('CONFIG_LB_INSTALL')
            add_service_with_hosts(self.services,
                                   'CONFIG_LB_BACKEND_HOSTS',
                                   role_configs['host_interfaces'])
            self.lb_vip = role_configs['vip']
        if is_ha:
            # convert dns to ip
            manage_ips = []
            for host_interface in role_configs['host_interfaces']:
                manage_ip = ''
                management_addr =\
                    host_interface['management']['ip']
                try:
                    ip_lists = socket.gethostbyname_ex(management_addr)
                    manage_ip = ip_lists[2][0]
                except Exception:
                    if netaddr.IPAddress(management_addr).version == 6:
                        manage_ip = management_addr
                    else:
                        raise exception.InvalidNetworkConfig(
                            "manage ip is not valid %s" % management_addr)
                finally:
                    manage_ips.append(manage_ip)

            self.ha_vip = role_configs['vip']
            self.share_disk_services += role_configs['share_disk_services']
            self.share_cluster_disk_services += \
                role_configs['share_cluster_disk_services']
            local_deployment_ip = get_local_deployment_ip(manage_ips)
            filename = r'/etc/zte-docker'
            if local_deployment_ip:
                if os.path.exists(filename):
                    add_service_with_host(
                        self.services, 'CONFIG_REPO',
                        'http://' + local_deployment_ip +
                        ':18080' + '/tecs_install/')
                else:
                    add_service_with_host(
                        self.services, 'CONFIG_REPO',
                        'http://' + local_deployment_ip + '/tecs_install/')
            else:
                msg = "can't find ip for yum repo"
                raise exception.InvalidNetworkConfig(msg)
            self.components.append('CONFIG_HA_INSTALL')
            add_service_with_host(
                self.services, 'CONFIG_HA_HOST',
                role_configs['host_interfaces'][0]['management']['ip'])
            add_service_with_hosts(self.services, 'CONFIG_HA_HOSTS',
                                   role_configs['host_interfaces'])
            ntp_host = role_configs['ntp_server'] \
                if role_configs['ntp_server'] else role_configs['vip']
            add_service_with_host(self.services, 'CONFIG_NTP_SERVERS',
                                  ntp_host)

            if role_configs['db_vip']:
                self.db_vip = role_configs['db_vip']
                add_service_with_host(
                    self.services, 'CONFIG_MARIADB_HOST',
                    role_configs['db_vip'])
            else:
                self.db_vip = role_configs['vip']
                add_service_with_host(
                    self.services, 'CONFIG_MARIADB_HOST', role_configs['vip'])

            if role_configs['glance_vip']:
                self.glance_vip = role_configs['glance_vip']
                add_service_with_host(
                    self.services, 'CONFIG_GLANCE_HOST',
                    role_configs['glance_vip'])
            else:
                self.glance_vip = role_configs['vip']
                add_service_with_host(
                    self.services, 'CONFIG_GLANCE_HOST', role_configs['vip'])

            if role_configs['public_vip']:
                self.public_vip = role_configs['public_vip']
            else:
                self.public_vip = role_configs['vip']

            add_service_with_host(self.services,
                                  'CONFIG_NOVA_VNCPROXY_HOST',
                                  self.public_vip)
            add_service_with_host(self.services, 'CONFIG_PUBLIC_IP',
                                  self.public_vip)
            add_service_with_host(self.services, 'CONFIG_HORIZON_HOST',
                                  self.public_vip)
            '''
            add_service_with_host(self.services, 'CONFIG_ADMIN_IP',
                                  role_configs['vip'])
            add_service_with_host(self.services, 'CONFIG_INTERNAL_IP',
                                  role_configs['vip'])
            '''

    def prepare_role_service(self, is_ha, service, role_configs):
        host_key_name = "CONFIG_%s_HOST" % service
        hosts_key_name = "CONFIG_%s_HOSTS" % service

        add_service_with_hosts(self.services, hosts_key_name,
                               role_configs['host_interfaces'])
        if service != 'LB' and service not in ['NOVA_VNCPROXY', 'MARIADB',
                                               'GLANCE', 'HORIZON']:
            add_service_with_host(self.services, host_key_name,
                                  role_configs['vip'])

        if is_ha and service == 'LB':
            add_service_with_hosts(
                self.services, 'CONFIG_LB_FRONTEND_HOSTS',
                role_configs['host_interfaces'])

    def prepare_mode(self, is_ha, is_lb, service):
        mode_key = "CONFIG_%s_INSTALL_MODE" % service
        if is_ha:
            self.modes.update({mode_key: 'HA'})
        elif is_lb:
            self.modes.update({mode_key: 'LB'})
            # special process
            if service == 'GLANCE':
                self.modes.update(
                    {'CONFIG_GLANCE_API_INSTALL_MODE': 'LB'})
                self.modes.update(
                    {'CONFIG_GLANCE_REGISTRY_INSTALL_MODE': 'LB'})
            # if s == 'HEAT':
            #    self.modes.update({'CONFIG_HEAT_API_INSTALL_MODE': 'LB'})
            #    self.modes.update({'CONFIG_HEAT_API_CFN_INSTALL_MODE': 'LB'})
            # if s == 'CEILOMETER':
            #    self.modes.update({
            #                     'CONFIG_CEILOMETER_API_INSTALL_MODE': 'LB'})
            if service == 'IRONIC':
                self.modes.update(
                    {'CONFIG_IRONIC_API_INSTALL_MODE': 'LB'})
        else:
            self.modes.update({mode_key: 'None'})

    def prepare_services_in_component(self, component, service, role_configs):
        if component not in self.services_in_component.keys():
            self.services_in_component[component] = {}
            self.services_in_component[component]["service"] = []
        self.services_in_component[component][
            "service"].append(service_map[service])

        if component == "horizon":
            self.services_in_component[component]["fip"] = self.public_vip
        elif component == "database":
            self.services_in_component[component]["fip"] = self.db_vip
        elif component == "glance":
            self.services_in_component[component]["fip"] = self.glance_vip
        else:
            self.services_in_component[component]["fip"] = role_configs["vip"]

        network_name = ''
        if component in ['horizon'] and\
                'publicapi' in role_configs["host_interfaces"][0]:
            network_name = 'publicapi'
        else:
            network_name = 'management'

        self.services_in_component[component]["netmask"] = \
            role_configs["host_interfaces"][0][network_name]["netmask"]
        self.services_in_component[component]["nic_name"] = \
            role_configs["host_interfaces"][0][network_name]["name"]
        if component == 'loadbalance' and \
           'CONTROLLER_LB' in self.all_configs and \
           self.all_configs['CONTROLLER_LB']['vip']:
            self.services_in_component[component]["fip"] = \
                self.all_configs['CONTROLLER_LB']['vip']

    def prepare_amqp_mariadb(self):
        if self.lb_vip:
            amqp_vip = ''
            if self.modes['CONFIG_AMQP_INSTALL_MODE'] == 'LB':
                amqp_vip = self.lb_vip
                add_service_with_host(
                    self.services,
                    'CONFIG_AMQP_CLUSTER_MASTER_NODE_IP',
                    self.ha_master_host['ip'])
                add_service_with_host(
                    self.services, 'CONFIG_AMQP_CLUSTER_MASTER_NODE_HOSTNAME',
                    self.ha_master_host['hostname'])
            else:
                amqp_vip = self.ha_vip
            amqp_dict = "{'%s':'%s,%s,%s,%s'}" % (amqp_vip, self.ha_vip,
                                                  self.lb_vip, self.glance_vip,
                                                  self.public_vip)
            mariadb_dict = "{'%s':'%s,%s,%s,%s'}" % (self.db_vip, self.ha_vip,
                                                     self.lb_vip,
                                                     self.glance_vip,
                                                     self.public_vip)
            add_service_with_host(self.services, 'CONFIG_LB_HOST', self.lb_vip)
        elif self.ha_vip:
            amqp_dict = "{'%s':'%s,%s,%s'}" % (self.ha_vip, self.ha_vip,
                                               self.glance_vip,
                                               self.public_vip)
            mariadb_dict = "{'%s':'%s,%s,%s'}" % (self.db_vip, self.ha_vip,
                                                  self.glance_vip,
                                                  self.public_vip)
        else:
            amqp_dict = "{}"
            mariadb_dict = "{}"
        if self.lb_vip or self.ha_vip:
            add_service_with_host(self.services, 'CONFIG_MARIADB_DICT',
                                  mariadb_dict)
            add_service_with_host(self.services, 'CONFIG_AMQP_DICT', amqp_dict)

    def prepare(self):
        for role_name, role_configs in self.all_configs.items():
            if role_name == "OTHER":
                continue

            is_ha = re.match(".*_HA$", role_name) is not None
            is_lb = re.match(".*_LB$", role_name) is not None
            is_child_cell = re.match(".*_CHILD_CELL.*", role_name) is not None
            if is_child_cell:
                self.prepare_child_cell(role_name, role_configs)
                continue
            self.prepare_ha_lb(role_configs, is_ha, is_lb)

            for service, component in role_configs['services'].items():
                s = service.strip().upper().replace('-', '_')
                self.prepare_role_service(is_ha, s, role_configs)
                self.prepare_mode(is_ha, is_lb, s)

                if is_lb:
                    self.lb_components.append(component)
                c = "CONFIG_%s_INSTALL" % \
                    component.strip().upper().replace('-', '_')
                self.components.append(c)

                if is_ha:
                    if component == 'log':
                        continue
                    self.prepare_services_in_component(component, service,
                                                       role_configs)
            if is_ha:
                self.get_heartbeats(role_configs['host_interfaces'])

        self.prepare_amqp_mariadb()

        if self.child_cell_dict:
            add_service_with_host(self.services, 'CONFIG_CHILD_CELL_DICT',
                                  str(self.child_cell_dict))

    def update_conf_with_services(self, tecs):
        for s in self.services:
            if tecs.has_option("general", s):
                # if type(self.services[s]) is types.ListType:
                if isinstance(self.services[s], types.ListType):
                    if self.services[s] and not self.services[s][0]:
                        return
                tecs.set("general", s, ','.join(self.services[s]))
            else:
                msg = "service %s is not exit in conf file" % s
                LOG.info(msg)

    def update_conf_with_components(self, tecs):
        for s in self.components:
            if tecs.has_option("general", s):
                tecs.set("general", s, 'y')
            else:
                msg = "component %s is not exit in conf file" % s
                LOG.info(msg)

    def update_conf_with_modes(self, tecs):
        for k, v in self.modes.items():
            if tecs.has_option("general", k):
                tecs.set("general", k, v)
            else:
                msg = "mode %s is not exit in conf file" % k
                LOG.info(msg)

    def update_tecs_conf(self, tecs):
        self.update_conf_with_services(tecs)
        self.update_conf_with_components(tecs)
        self.update_conf_with_modes(tecs)

    def update_ha_conf(self, ha, ha_nic_name, tecs=None):
        if self.all_configs['OTHER'].get('dns_config'):
            for heartbeat in self.heartbeats:
                for name_ip in self.all_configs['OTHER']['dns_config']:
                    for tmp in heartbeat:
                        if tmp == name_ip.keys()[0]:
                            heartbeat.remove(tmp)
                            heartbeat.append(name_ip.values()[0])

            for k, v in self.services_in_component.items():
                for name_ip in self.all_configs['OTHER']['dns_config']:
                    if v['fip'] == name_ip.keys()[0]:
                        v['fip'] = name_ip.values()[0]
        ha.set('DEFAULT', 'heartbeat_link1', ','.join(self.heartbeats[0]))
        ha.set('DEFAULT', 'heartbeat_link2', ','.join(self.heartbeats[1]))
        ha.set('DEFAULT', 'heartbeat_link3', ','.join(self.heartbeats[2]))

        ha.set('DEFAULT', 'components', ','.join(
            self.services_in_component.keys()))

        for k, v in self.services_in_component.items():
            ha.set('DEFAULT', k, ','.join(v['service']))
            if k == 'glance':
                if 'glance' in self.share_disk_services:
                    ha.set('DEFAULT', 'glance_device_type', 'iscsi')
                    ha.set(
                        'DEFAULT', 'glance_device',
                        '/dev/mapper/vg_glance-lv_glance')
                    ha.set('DEFAULT', 'glance_fs_type', 'ext4')
                else:
                    ha.set('DEFAULT', 'glance_device_type', 'drbd')
                    ha.set(
                        'DEFAULT', 'glance_device', '/dev/vg_data/lv_glance')
                    ha.set('DEFAULT', 'glance_fs_type', 'ext4')
            # mariadb now not support db cluster, don't support share disk.
            if k == "database":
                if 'db' in self.share_disk_services:
                    ha.set(
                        'DEFAULT', 'database_device',
                        '/dev/mapper/vg_db-lv_db')
                    ha.set('DEFAULT', 'database_fs_type', 'ext4')
                    ha.set('DEFAULT', 'database_device_type', 'share')
                    if tecs:
                        tecs.set(
                            "general",
                            'CONFIG_HA_INSTALL_MARIADB_LOCAL',
                            'n')
                elif 'db' in self.share_cluster_disk_services:
                    ha.set(
                        'DEFAULT', 'database_device',
                        '/dev/mapper/vg_db-lv_db')
                    ha.set('DEFAULT', 'database_fs_type', 'ext4')
                    ha.set('DEFAULT', 'database_device_type', 'share_cluster')
                    if tecs:
                        tecs.set(
                            "general",
                            'CONFIG_HA_INSTALL_MARIADB_LOCAL',
                            'y')
                else:
                    ha.set('DEFAULT', 'database_device_type', 'local_cluster')
                    if tecs:
                        tecs.set(
                            "general",
                            'CONFIG_HA_INSTALL_MARIADB_LOCAL',
                            'y')

                if 'db_backup' in self.share_disk_services:
                    ha.set(
                        'DEFAULT',
                        'backup_database_device',
                        '/dev/mapper/vg_db_backup-lv_db_backup')
                    ha.set('DEFAULT', 'backup_database_fs_type', 'ext4')

                if "mongod" in v['service']:
                    if 'mongodb' in self.share_disk_services:
                        ha.set(
                            'DEFAULT', 'mongod_device',
                            '/dev/mapper/vg_mongodb-lv_mongodb')
                        ha.set('DEFAULT', 'mongod_fs_type', 'ext4')
                        ha.set('DEFAULT', 'mongod_local', '')
                        if tecs:
                            tecs.set(
                                "general",
                                'CONFIG_HA_INSTALL_MONGODB_LOCAL', 'n')
                    else:
                        ha.set('DEFAULT', 'mongod_fs_type', 'ext4')
                        ha.set('DEFAULT', 'mongod_local', 'yes')
                        if tecs:
                            tecs.set(
                                "general",
                                'CONFIG_HA_INSTALL_MONGODB_LOCAL', 'y')

            if k not in self.lb_components:
                # if "bond" in v['nic_name']:
                    # v['nic_name'] = "vport"
                ha.set('DEFAULT', k + '_fip', v['fip'])
                if ha_nic_name and k not in ['horizon']:
                    nic_name = ha_nic_name
                else:
                    nic_name = v['nic_name']
                ha.set('DEFAULT', k + '_nic', nic_name)
                cidr_netmask = reduce(lambda x, y: x + y,
                                      [bin(int(i)).count('1')
                                       for i in v['netmask'].split('.')])
                ha.set('DEFAULT', k + '_netmask', cidr_netmask)


def update_conf(tecs, key, value):
    tecs.set("general", key, value)


def get_conf(tecs_conf_file, **kwargs):
    result = {}
    if not kwargs:
        return result

    tecs = ConfigParser()
    tecs.optionxform = str
    tecs.read(tecs_conf_file)

    result = {key: tecs.get("general", kwargs.get(key, None))
              for key in kwargs.keys()
              if tecs.has_option("general", kwargs.get(key, None))}
    return result


def _get_physnics_info(network_type, phynics):
    # bond1(active-backup;lacp;eth1-eth2)
    # eth0
    # phynet1:eth0
    # phynet1:bond1(active-backup;lacp;eth1-eth2), phynet2:eth3
    phynics_info = []
    if not phynics:
        return

    phynic_info = phynics.split("(")
    if 2 == len(phynic_info):
        phynic_info = phynic_info[1][0:-1].split(";")
        phynics_info.extend(phynic_info[-1].split('-'))
    else:
        phynic_info = phynic_info[0].split(":")
        if network_type == 'vlan':
            phynics_info.append(phynic_info[1])
        else:
            phynics_info.append(phynic_info[0])
    return phynics_info


def get_physnics_info(network_type, phynics):
    # bond1(active-backup;lacp;eth1-eth2)
    # phynet1:eth0
    # phynet1:bond1(active-backup;lacp;eth1-eth2), phynet1:eth3
    phynics_info = []
    if network_type == 'vxlan':
        phynics_info.extend(_get_physnics_info(network_type, phynics))
    elif network_type == 'vlan':
        phynics = phynics.split(',')
        for phynic_info in phynics:
            phynics_info.extend(_get_physnics_info(network_type, phynic_info))
    return phynics_info


def update_conf_with_zenic(tecs, zenic_configs):
    zenic_vip = zenic_configs.get('vip')
    if not zenic_vip:
        return

    auth = zenic_configs.get('auth')
    if not auth:
        auth = 'restconf:LkfhRDGIPyGzbWGM2uAaNQ=='

    update_conf(tecs, 'CONFIG_ZENIC_USER_AND_PW', auth)
    update_conf(tecs, 'CONFIG_ZENIC_API_NODE', '%s:8181' % zenic_vip)

    ml2_drivers = tecs.get(
        "general", 'CONFIG_NEUTRON_ML2_MECHANISM_DRIVERS').split(',')
    ml2_drivers.extend(['proxydriver'])
    update_conf(
        tecs, 'CONFIG_NEUTRON_ML2_MECHANISM_DRIVERS', ','.join(ml2_drivers))


class DvsDaisyConfig(object):

    def __init__(self, tecs, networks_config):
        self.tecs = tecs
        self.networks_config = networks_config

        # common
        self.dvs_network_type = []
        self.dvs_vswitch_type = {}
        self.dvs_cpu_sets = []
        self.dvs_physnics = []
        self.enable_sdn = False

        # for vlan
        self.dvs_physical_mappings = []
        self.dvs_bridge_mappings = []

        # for vxlan
        self.dvs_vtep_ip_ranges = []
        self.dvs_vxlan_info = ''
        self.dvs_domain_id = {}

    def config_tecs_for_dvs(self):
        self._get_dvs_config()
        self._set_dvs_config()

    def _get_dvs_config(self):
        network = self.networks_config
        vswitch_type = network.get('vswitch_type')
        if not vswitch_type:
            return
        self.dvs_vswitch_type.update(vswitch_type)

        dvs_cpu_sets = network.get('dvs_cpu_sets')
        self.dvs_cpu_sets.extend(dvs_cpu_sets)

        network_type = network['network_config'].get('network_type')

        if network_type in ['vlan']:
            self.dvs_network_type.extend(['vlan'])
            self._private_network_conf_for_dvs(network)

        elif network_type in ['vxlan']:
            self.dvs_network_type.extend(['vxlan'])
            self._bearing_network_conf_for_dvs(network)

    def _set_dvs_config(self):
        if not self.networks_config.get('enable_sdn') and (
            self.dvs_vswitch_type.get('ovs_agent_patch')) and (
                len(self.dvs_vswitch_type.get('ovs_agent_patch')) > 0):
            return

        if not self.dvs_vswitch_type.get('ovs_agent_patch') and not\
                self.dvs_vswitch_type.get('ovdk'):
            return

        update_conf(self.tecs, 'CONFIG_DVS_TYPE', self.dvs_vswitch_type)
        update_conf(self.tecs, 'CONFIG_DVS_PHYSICAL_NICS',
                    ",".join(set(self.dvs_physnics)))
        # cpu sets for dvs, add CONFIG_DVS_CPU_SETS to tecs.conf firstly
        update_conf(self.tecs, 'CONFIG_DVS_CPU_SETS', self.dvs_cpu_sets)

        if 'vlan' in self.dvs_network_type:
            update_conf(self.tecs, 'CONFIG_NEUTRON_OVS_BRIDGE_MAPPINGS',
                        self.dvs_bridge_mappings)
            update_conf(self.tecs, 'CONFIG_NEUTRON_OVS_PHYSNET_IFACES',
                        self.dvs_physical_mappings)

        elif 'vxlan' in self.dvs_network_type:
            update_conf(self.tecs, 'CONFIG_DVS_VXLAN_INFO',
                        self.dvs_vxlan_info)
            update_conf(self.tecs, 'CONFIG_DVS_NODE_DOMAIN_ID',
                        self.dvs_domain_id)
            update_conf(self.tecs, 'CONFIG_NEUTRON_ML2_VTEP_IP_RANGES',
                        self.dvs_vtep_ip_ranges)

    '''
    private_networks_config_for_dvs
    {
        network_config = {
             enable_sdn = ''
             network_type = ['vlan']
        }

        vswitch_type = { ===============> such as vxlan
            'ovdk': ['192.168.0.2', '192.168.0.20'] ,
            'ovs_agent_patch': ['192.168.0.21', '192.168.0.30']
        }

        physnics_config = {
            physical_mappings = eth0 ===============> such as ovs vlan
            bridge_mappings =  ==========> private->name & physical_name
        }
    }
    '''

    def _private_network_conf_for_dvs(self, private_network):
        self.dvs_vswitch_type.update(private_network.get('vswitch_type'))
        self.dvs_bridge_mappings = \
            private_network['physnics_config'].get('bridge_mappings')
        self.dvs_physical_mappings = \
            private_network['physnics_config'].get('physical_mappings')
        self.dvs_physical_mappings = self.dvs_physical_mappings.encode('utf8')

        self.dvs_physnics.extend(
            get_physnics_info('vlan', self.dvs_physical_mappings))

    '''
    bearing_networks_config
    {
        network_config = {
             enable_sdn = ''
             network_type = ['vxlan']
             vtep_ip_ranges=[['192.168.0.2','192.168.0.200']]==>bearing->ip_range
        }

        vswitch_type = {  ==========> bearing->assigned_network
            'ovdk': ['192.168.0.2', '192.168.0.20'] ,
            'ovs_agent_patch': ['192.168.0.21', '192.168.0.30']
        }

        physnics_config = {
            vxlan_info = eth0  ======>bearing->assigned_network->host_interface
            domain_id = {              ==========> bearing->assigned_network
                '0': ['192.168.0.2', '192.168.0.20'] ,
                '1': ['192.168.0.21', '192.168.0.30']
            }
        }
    }
    '''

    def _bearing_network_conf_for_dvs(self, bearing_network):
        self.dvs_vtep_ip_ranges.extend(
            bearing_network['network_config'].get('vtep_ip_ranges'))
        self.dvs_vswitch_type.update(bearing_network.get('vswitch_type'))
        self.dvs_domain_id.update(
            bearing_network['physnics_config'].get('dvs_domain_id'))
        self.dvs_vxlan_info = \
            bearing_network['physnics_config'].get('vxlan_info')
        self.dvs_physnics.extend(
            get_physnics_info('vxlan', self.dvs_vxlan_info))


default_tecs_conf_template_path = "/var/lib/daisy/tecs/"
tecs_conf_template_path = default_tecs_conf_template_path


def private_network_conf(tecs, private_networks_config):
    if private_networks_config:
        mode_str = {
            '0': '(active-backup;off;"%s-%s")',
            '1': '(balance-slb;off;"%s-%s")',
            '2': '(balance-tcp;active;"%s-%s")'
        }

        config_neutron_sriov_bridge_mappings = []
        config_neutron_sriov_physnet_ifaces = []
        config_neutron_ovs_bridge_mappings = []
        config_neutron_ovs_physnet_ifaces = []
        for private_network in private_networks_config:
            type = private_network.get('type', None)
            name = private_network.get('name', None)
            assign_networks = private_network.get('assigned_networks', None)
            slave1 = private_network.get('slave1', None)
            slave2 = private_network.get('slave2', None)
            mode = private_network.get('mode', None)
            if not type or not name or not assign_networks or not\
                    slave1 or not slave2 or not mode:
                break

            for assign_network in assign_networks:
                network_type = assign_network.get('network_type', None)
                # TODO:why ml2_type & physnet_name is null
                ml2_type = assign_network.get('ml2_type', None)
                physnet_name = assign_network.get('physnet_name', None)
                if not network_type or not ml2_type or not physnet_name:
                    break

                # ether
                if 0 == cmp(type, 'ether') and\
                   0 == cmp(network_type, 'DATAPLANE'):
                    if 0 == cmp(ml2_type, 'sriov'):
                        config_neutron_sriov_bridge_mappings.append(
                            "%s:%s" % (physnet_name, "br-" + name))
                        config_neutron_sriov_physnet_ifaces.append(
                            "%s:%s" % (physnet_name, name))
                    elif 0 == cmp(ml2_type, 'ovs'):
                        config_neutron_ovs_bridge_mappings.append(
                            "%s:%s" % (physnet_name, "br-" + name))
                        config_neutron_ovs_physnet_ifaces.append(
                            "%s:%s" % (physnet_name, name))
                # bond
                elif 0 == cmp(type, 'bond') and\
                        0 == cmp(network_type, 'DATAPLANE'):
                    if 0 == cmp(ml2_type, 'sriov'):
                        config_neutron_sriov_bridge_mappings.append(
                            "%s:%s" % (physnet_name, "br-" + name))
                        config_neutron_sriov_physnet_ifaces.append(
                            "%s:%s" % (physnet_name, name + mode_str[mode]
                                       % (slave1, slave2)))
                    elif 0 == cmp(ml2_type, 'ovs'):
                        config_neutron_ovs_bridge_mappings.append(
                            "%s:%s" % (physnet_name, "br-" + name))
                        config_neutron_ovs_physnet_ifaces.append(
                            "%s:%s" % (physnet_name, name + mode_str[mode]
                                       % (slave1, slave2)))

        if config_neutron_sriov_bridge_mappings:
            update_conf(tecs,
                        'CONFIG_NEUTRON_SRIOV_BRIDGE_MAPPINGS',
                        ",".join(config_neutron_sriov_bridge_mappings))
        if config_neutron_sriov_physnet_ifaces:
            update_conf(tecs,
                        'CONFIG_NEUTRON_SRIOV_PHYSNET_IFACES',
                        ",".join(config_neutron_sriov_physnet_ifaces))
        if config_neutron_ovs_bridge_mappings:
            update_conf(tecs, 'CONFIG_NEUTRON_OVS_BRIDGE_MAPPINGS',
                        ",".join(config_neutron_ovs_bridge_mappings))
        if config_neutron_ovs_physnet_ifaces:
            update_conf(tecs, 'CONFIG_NEUTRON_OVS_PHYSNET_IFACES',
                        ",".join(config_neutron_ovs_physnet_ifaces))


def update_tecs_config(config_data, cluster_conf_path):
    msg = "tecs config data is: %s" % config_data
    LOG.info(msg)

    daisy_tecs_path = tecs_conf_template_path
    tecs_conf_template_file = os.path.join(daisy_tecs_path, "tecs.conf")
    ha_conf_template_file = os.path.join(daisy_tecs_path, "HA.conf")
    if not os.path.exists(cluster_conf_path):
        os.makedirs(cluster_conf_path)
    tecs_conf_out = os.path.join(cluster_conf_path, "tecs.conf")
    ha_config_out = os.path.join(cluster_conf_path, "HA_1.conf")

    tecs = ConfigParser()
    tecs.optionxform = str
    tecs.read(tecs_conf_template_file)

    cluster_data = config_data['OTHER']['cluster_data']
    update_conf(tecs, 'CLUSTER_ID', cluster_data['id'])
    # if cluster_data.has_key('networking_parameters'):
    if 'networking_parameters' in cluster_data:
        networking_parameters = cluster_data['networking_parameters']
        # if networking_parameters.has_key('base_mac') and\
        if 'base_mac'in networking_parameters and\
                networking_parameters['base_mac']:
            update_conf(
                tecs, 'CONFIG_NEUTRON_BASE_MAC',
                networking_parameters['base_mac'])
        # if networking_parameters.has_key('gre_id_range') and\
        if 'gre_id_range' in networking_parameters and\
            len(networking_parameters['gre_id_range']) > 1 \
                and networking_parameters['gre_id_range'][0] and\
                networking_parameters['gre_id_range'][1]:
            update_conf(tecs, 'CONFIG_NEUTRON_ML2_TUNNEL_ID_RANGES',
                        ("%s:%s" % (networking_parameters['gre_id_range'][0],
                                    networking_parameters['gre_id_range'][1])))
    if 'vxlan' in config_data['OTHER'].get('segmentation_type', {}):
        update_conf(
            tecs, 'CONFIG_NEUTRON_ML2_VNI_RANGES',
            config_data['OTHER']['segmentation_type']['vxlan']['vni_range'])
        update_conf(tecs, 'CONFIG_NEUTRON_ML2_TENANT_NETWORK_TYPES', 'vxlan')
        update_conf(tecs, 'CONFIG_NEUTRON_ML2_TYPE_DRIVERS', 'vxlan')
    else:
        update_conf(tecs, 'CONFIG_NEUTRON_ML2_TENANT_NETWORK_TYPES', 'vlan')
        update_conf(tecs, 'CONFIG_NEUTRON_ML2_TYPE_DRIVERS', 'vlan')

    physic_network_cfg = config_data['OTHER']['physic_network_config']
    if physic_network_cfg.get('json_path', None):
        update_conf(
            tecs, 'CONFIG_NEUTRON_ML2_JSON_PATH',
            physic_network_cfg['json_path'])
    if physic_network_cfg.get('vlan_ranges', None):
        update_conf(tecs, 'CONFIG_NEUTRON_ML2_VLAN_RANGES',
                    physic_network_cfg['vlan_ranges'])
    if config_data['OTHER']['tecs_installed_hosts']:
        update_conf(tecs, 'EXCLUDE_SERVERS', ",".join(
            config_data['OTHER']['tecs_installed_hosts']))

    ha = ConfigParser()
    ha.optionxform = str
    ha.read(ha_conf_template_file)

    config = AnalsyConfig(config_data)
    # if config_data['OTHER'].has_key('ha_nic_name'):
    if 'ha_nic_name'in config_data['OTHER']:
        ha_nic_name = config_data['OTHER']['ha_nic_name']
    else:
        ha_nic_name = ""

    config.prepare()

    config.update_tecs_conf(tecs)
    config.update_ha_conf(ha, ha_nic_name, tecs)

    update_conf_with_zenic(tecs, config_data['OTHER']['zenic_config'])
    # if config_data['OTHER']['dvs_config'].has_key('network_config'):
    if 'network_config' in config_data['OTHER']['dvs_config']:
        config_data['OTHER']['dvs_config']['network_config']['enable_sdn'] = \
            config_data['OTHER']['zenic_config'].get('vip', False)
        dvs_config = DvsDaisyConfig(tecs, config_data['OTHER']['dvs_config'])

        dvs_config.config_tecs_for_dvs()

    tecs.write(open(tecs_conf_out, "w+"))
    ha.write(open(ha_config_out, "w+"))

    return


def test():
    print("Hello, world!")
