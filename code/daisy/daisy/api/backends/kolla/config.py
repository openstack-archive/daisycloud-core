# Copyright 2013 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import re
import yaml
import subprocess
from oslo_log import log as logging
from daisy import i18n
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

kolla_file = '/home/kolla_install/'


def sort_ipv4(ip_list):
    ip_list.sort(lambda x, y: cmp(
        ''.join([i.rjust(3, '0') for i in x.split('.')]),
        ''.join([i.rjust(3, '0') for i in y.split('.')])))


# generate kolla's ansible inventory multinode file
def clean_inventory_file(file_path, filename, node_names):
    LOG.info(_("clean inventory file %s section for kolla" % node_names))
    fp = open('%s/kolla-ansible/ansible/inventory/%s' % (file_path, filename))
    txt = fp.read()
    fp.close()
    for section_name in node_names[0:len(node_names)-1]:
        next_name_index = node_names.index('%s' % section_name)
        match = re.search(r"\[%s\](.*)\[%s\]" % (
            section_name,
            node_names[next_name_index+1]),
            txt, re.S)
        txt = txt.replace(match.group(1), '\n\n')
    fp = file('%s/kolla-ansible/ansible/inventory/%s' % (
        file_path, filename), 'w')
    fp.write(txt)
    fp.close()


def update_inventory_file(file_path, filename, node_name, host_name,
                          num_of_host, connection_type):
    fp = file('%s/kolla-ansible/ansible/inventory/%s' % (file_path, filename))
    lines = []
    for line in fp:
        lines.append(line)
    fp.close()
    index_of_label = lines.index('[%s]\n' % node_name)
    lines.insert(index_of_label + num_of_host,
                 '%s\n' % host_name)
    s = ''.join(lines)
    fp = file('%s/kolla-ansible/ansible/inventory/%s' % (
        file_path, filename), 'w')
    fp.write(s)
    fp.close()


def update_inventory_file_of_ip_lines(file_path, filename, ovs_dpdk_pmd_coremask_dict):
    fp = file('%s/kolla-ansible/ansible/inventory/%s' % (file_path, filename))
    lines = []
    for line in fp:
        for mgnt_ip in ovs_dpdk_pmd_coremask_dict.keys():
            if mgnt_ip in line:
                line = line.split('\n')[0] + ' ovs_dpdk_pmd_coremask=%s' % ovs_dpdk_pmd_coremask_dict[mgnt_ip]  + '\n'
        lines.append(line)
    fp.close()
    s = ''.join(lines)
    fp = file('%s/kolla-ansible/ansible/inventory/%s' % (
        file_path, filename), 'w')
    fp.write(s)
    fp.close()


def add_role_to_inventory(file_path, config_data):
    LOG.info(_("add role to inventory file..."))
    node_names = ['control', 'network', 'compute', 'monitoring',
                  'storage', 'deployment']
    clean_inventory_file(file_path, 'multinode', node_names)
    role_names_list = {'Controller_ips': ['control'],
                       'Network_ips': ['network'],
                       'Computer_ips': ['compute', 'monitoring'],
                       'Storage_ips': ['storage']}
    for role_ips, role_sections in role_names_list.items():
        for role_section in role_sections:
            host_sequence = 1
            sort_ipv4(config_data[role_ips])
            for ips in config_data[role_ips]:
                update_inventory_file(file_path, 'multinode', role_section,
                                      ips.encode(), host_sequence, 'ssh')
                host_sequence = host_sequence + 1
    LOG.info(_("add role to inventory file has finished..."))


def update_kolla_globals_yml(data):
    with open('/etc/kolla/globals.yml', 'r') as f:
        kolla_config = yaml.load(f.read())
        kolla_config.update(data)
        f.close()
    with open('/etc/kolla/globals.yml', 'w') as f:
        f.write(yaml.dump(kolla_config, default_flow_style=False))
        f.close()


def _del_general_params(param):
    del param['created_at']
    del param['updated_at']
    del param['deleted']
    del param['deleted_at']
    del param['id']


def _get_services_disk(req, role):
    params = {'filters': {'role_id': role['id']}}
    services_disk = registry.list_service_disk_metadata(
        req.context, **params)
    for service_disk in services_disk:
        if service_disk.get('role_id', None):
            service_disk['role_id'] = role['name']
        _del_general_params(service_disk)
    return services_disk


def config_lvm_for_cinder(config_data):
    lvm_config = {'enable_cinder': 'yes',
                  'enable_cinder_backend_lvm': 'yes',
                  'cinder_volume_group': 'cinder-volumes'}
    update_kolla_globals_yml(lvm_config)
    storage_ip_list = config_data.get('Storage_ips')
    if len(storage_ip_list) == 1:
        LOG.info(_("this is all in one environment \
                    to enable ceph backend"))
        storage_ip = storage_ip_list[0]
        fp = '/var/log/daisy/api.log'
        cmd = 'ssh -o StrictHostKeyChecking=no %s \
              "dd if=/dev/zero of=/var/lib/cinder_data.img\
               bs=1G count=20" ' % \
              (storage_ip)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'ssh -o StrictHostKeyChecking=no %s \
              "losetup --find --show /var/lib/cinder_data.img"' % \
              (storage_ip)
        obj = subprocess.Popen(cmd,
                               stdout=subprocess.PIPE,
                               shell=True)
        dev_name = obj.stdout.read().decode('utf8')
        cmd = 'ssh -o StrictHostKeyChecking=no %s \
              "pvcreate %s" ' % \
              (storage_ip, dev_name)
        daisy_cmn.subprocess_call(cmd, fp)
        cmd = 'ssh -o StrictHostKeyChecking=no %s \
              "vgcreate cinder-volumes %s" ' % \
              (storage_ip, dev_name)
        daisy_cmn.subprocess_call(cmd, fp)
        LOG.info(_("execute all four commands on \
                    storage node %s ok!" % storage_ip))


def enable_ceilometer():
    ceilometer_config = {"enable_ceilometer": "yes",
                         "enable_gnocchi": "yes",
                         "enable_aodh": "yes"}
    update_kolla_globals_yml(ceilometer_config)


def config_ceph_for_cinder(config_data, disk):
    ceph_config = {'enable_cinder': 'yes',
                   'enable_ceph': 'yes'}
    update_kolla_globals_yml(ceph_config)
    disk_name = disk.get('partition', None)
    storage_ip_list = config_data.get('Storage_ips')
    if len(storage_ip_list) > 2:
        LOG.info(_("this is CEPH backend environment \
                    with %s nodes" % len(storage_ip_list)))
        for storage_ip in storage_ip_list:
            fp = '/var/log/daisy/api.log'
            cmd = 'ssh -o StrictHostKeyChecking=no %s \
                  "parted %s -s -- mklabel gpt mkpart\
                   KOLLA_CEPH_OSD_BOOTSTRAP 1 -1" ' % \
                  (storage_ip, disk_name)
            daisy_cmn.subprocess_call(cmd, fp)
            exc_result = subprocess.check_output(
                'ssh -o StrictHostKeyChecking=no %s \
                "parted %s print" ' % (storage_ip, disk_name),
                shell=True, stderr=subprocess.STDOUT)
            LOG.info(_("parted label is %s" % exc_result))
            LOG.info(_("execute labeled command successfully\
                        on %s node" % storage_ip))


def enable_cinder_backend(req, cluster_id, config_data):
    service_disks = []
    params = {'filters': {'cluster_id': cluster_id}}
    roles = registry.get_roles_detail(req.context, **params)
    for role in roles:
        if role['name'] == 'CONTROLLER_LB':
            service_disk = _get_services_disk(req, role)
            service_disks += service_disk
    for disk in service_disks:
        if disk.get('service', None) == 'cinder' and\
                disk.get('protocol_type', None) == 'LVM':
            config_lvm_for_cinder(config_data)

        elif disk.get('service', None) == 'ceph' and\
                disk.get('protocol_type', None) == 'RAW' and\
                disk.get('partition') != None and\
                disk.get('partition') != '':
            config_ceph_for_cinder(config_data, disk)


def enable_neutron_backend(req, cluster_id, kolla_config):
    params = {'cluster_id': cluster_id}
    roles = registry.get_roles_detail(req.context, **params)
    all_neutron_backends = registry.list_neutron_backend_metadata(
        req.context, **params)
    for role in roles:
        for neutron_backend in all_neutron_backends:
            if role['name'] == 'CONTROLLER_LB' \
                and neutron_backend[
                    'neutron_backends_type'] == 'opendaylight' \
                    and neutron_backend['role_id'] == role['id']:
                opendaylight_config = {
                    'enable_opendaylight': "yes",
                    'neutron_plugin_agent': "opendaylight",
                    'opendaylight_mechanism_driver': "opendaylight_v2",
                    'opendaylight_l3_service_plugin': "odl-router_v2",
                    'enable_opendaylight_l3': "yes",
                    'enable_opendaylight_qos': "no",
                    'enable_opendaylight_legacy_netvirt_conntrack': "no",
                    'opendaylight_features':
                        "odl-dlux-core,odl-dluxapps-applications,"
                        "odl-mdsal-apidocs,odl-netvirt-openstack",
                    'opendaylight_restconf_port': "8088",
                    'opendaylight_restconf_port_backup': "8182",
                    'opendaylight_haproxy_restconf_port': "8087",
                    'opendaylight_haproxy_restconf_port_backup': "8181"}
                if neutron_backend['enable_l2_or_l3'] == 'l2':
                    opendaylight_config['enable_opendaylight_l3'] = 'no'
                update_kolla_globals_yml(opendaylight_config)


# generate kolla's globals.yml file
def update_globals_yml(config_data, multicast_flag):
    LOG.info(_("begin to update kolla's globals.yml file..."))
    kolla_yml = {'openstack_release': '3.0.0',
                 'openstack_logging_debug': 'True',
                 'docker_registry': '127.0.0.1:4000',
                 'docker_namespace': 'kollaglue',
                 'kolla_internal_vip_address': '10.10.10.254',
                 'network_interface': 'eth0',
                 'tunnel_interface': 'eth0',
                 'storage_interface': 'eth0',
                 'kolla_external_vip_interface': 'eth0',
                 'neutron_external_interface': 'eth1',
                 'keepalived_interface': '{{ network_interface }}'
                 }
    Version = config_data['Version'].encode()
    Namespace = config_data['Namespace'].encode()
    VIP = config_data['VIP'].encode()
    local_ip = config_data['LocalIP'].encode()
    IntIfMac = config_data['IntIfMac'].encode()
    if config_data['vlans_id'].get('MANAGEMENT'):
        IntIfMac = IntIfMac + '.' + \
            config_data['vlans_id'].get('MANAGEMENT').encode()
    ExtIfMac = config_data['ExtIfMac'].encode()
    if config_data['vlans_id'].get('EXTERNAL'):
        ExtIfMac = ExtIfMac + '.' + \
            config_data['vlans_id'].get('EXTERNAL').encode()
    TulIfMac = config_data['TulIfMac'].encode()
    if config_data['vlans_id'].get('DATAPLANE'):
        TulIfMac = TulIfMac + '.' + \
            config_data['vlans_id'].get('DATAPLANE').encode()
    PubIfMac = config_data['PubIfMac'].encode()
    if config_data['vlans_id'].get('PUBLICAPI'):
        PubIfMac = PubIfMac + '.' + \
            config_data['vlans_id'].get('PUBLICAPI').encode()
    StoIfMac = config_data['StoIfMac'].encode()
    if config_data['vlans_id'].get('STORAGE'):
        StoIfMac = StoIfMac + '.' + \
            config_data['vlans_id'].get('STORAGE').encode()
    if config_data.get('HbtIfMac') != None:
        HbtIfMac = config_data['HbtIfMac'].encode()
        if config_data['vlans_id'].get('HEARTBEAT'):
            HbtIfMac = HbtIfMac + '.' + \
                config_data['vlans_id'].get('HEARTBEAT').encode()
        kolla_yml['keepalived_interface'] = HbtIfMac
    kolla_yml['openstack_release'] = Version
    if multicast_flag == 0:
        pass
    else:
        kolla_yml['docker_registry'] = local_ip
    kolla_yml['docker_namespace'] = Namespace
    kolla_yml['kolla_internal_vip_address'] = VIP
    kolla_yml['network_interface'] = IntIfMac
    kolla_yml['tunnel_interface'] = TulIfMac
    kolla_yml['neutron_external_interface'] = ExtIfMac
    kolla_yml['kolla_external_vip_interface'] = PubIfMac
    kolla_yml['storage_interface'] = StoIfMac

    yaml.dump(kolla_yml, file('/etc/kolla/globals.yml', 'w'),
              default_flow_style=False)


def enable_openvswitch_dpdk(kolla_config, file_path):
    if kolla_config['enable_dvs']:
        openswitch_dpdk_config = {
            'enable_ovs_dpdk': 'yes',
            'neutron_bridge_name': 'dpdk_bridge',
            'tunnel_interface': 'dpdk_bridge',
            'enable_openvswitch': 'yes',
            'ovs_hugepage_mountpoint': '/mnt/huge_1GB'}
        isolcpus_list = kolla_config['ovs_dpdk_pmd_coremask_dict'].values()
        if len(set(isolcpus_list)) == 1:
            openswitch_dpdk_config['ovs_dpdk_pmd_coremask'] = isolcpus_list[0]
        else:
            update_inventory_file_of_ip_lines(file_path, 'multinode',
                                              kolla_config['ovs_dpdk_pmd_coremask_dict'])
        update_kolla_globals_yml(openswitch_dpdk_config)
    else:
        LOG.info(_("no need to config openvswitch dpdk"))


def update_password_yml():
    LOG.info(_("begin to update kolla's passwd.yml file..."))
    cmd = 'python '\
          '/home/kolla_install/kolla-ansible/tools/generate_passwords.py'
    fp = '/var/log/daisy/api.log'
    daisy_cmn.subprocess_call(cmd, fp)
    # generate the password of horizon
    keystone_admin_password = ['keystone_admin_password']
    opendaylight_password = ['opendaylight_password']
    with open('/etc/kolla/passwords.yml', 'r') as f:
        passwords = yaml.load(f.read())
    for k, v in passwords.items():
        if k in keystone_admin_password:
            passwords[k] = "keystone"
        elif k in opendaylight_password:
            passwords[k] = 'admin'
    f.close()
    with open('/etc/kolla/passwords.yml', 'w') as f:
        f.write(yaml.dump(passwords, default_flow_style=False))
        f.close()
    LOG.info(_("generate kolla's passwd.yml file ok..."))


def update_docker_registry_url(config_data, multicast_flag):
    mcast = {'docker_registry': '127.0.0.1:4000'}
    local_ip = config_data['LocalIP'].encode()
    ucast = {'docker_registry': local_ip}

    LOG.info(_("begin updating docker registry url"))
    if multicast_flag == 0:
        update_kolla_globals_yml(mcast)
    else:
        update_kolla_globals_yml(ucast)
    LOG.info(_("updated docker registry url"))


def update_openstack_release(config_data):
    Version = config_data['Version'].encode()
    new_version = {'openstack_release': Version}

    LOG.info(_("begin updating openstack_release"))
    update_kolla_globals_yml(new_version)
    LOG.info(_("updated openstack_release"))
