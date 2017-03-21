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
import os
import yaml
import random
import string
import uuid
from oslo_log import log as logging
from daisy import i18n
from Crypto.PublicKey import RSA
import daisy.registry.client.v1.api as registry
import daisy.api.backends.common as daisy_cmn


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW


# generate kolla's ansible inventory multinode file
def clean_inventory_file(file_path, filename):
    LOG.info(_("begin to clean inventory file for kolla"))
    fp = open('%s/kolla/ansible/inventory/%s' % (file_path, filename))
    txt = fp.read()
    fp.close()
    node_names = ['control', 'network', 'compute', 'monitoring',
                  'storage', 'baremetal:children']
    for section_name in node_names[0:5]:
        next_name_index = node_names.index('%s' % section_name)
        match = re.search(r"\[%s\](.*)\[%s\]" % (
            section_name,
            node_names[next_name_index+1]),
            txt, re.S)
        txt = txt.replace(match.group(1), '\n\n')
    fp = file('%s/kolla/ansible/inventory/%s' % (file_path, filename), 'w')
    fp.write(txt)
    fp.close()


def update_inventory_file(file_path, filename, node_name, host_name,
                          num_of_host, connection_type):
    LOG.info(_("begin to update inventory file for kolla..."))
    fp = file('%s/kolla/ansible/inventory/%s' % (file_path, filename))
    lines = []
    for line in fp:
        lines.append(line)
    fp.close()
    index_of_label = lines.index('[%s]\n' % node_name)
    lines.insert(index_of_label + num_of_host,
                 '%s\n' % host_name)
    s = ''.join(lines)
    fp = file('%s/kolla/ansible/inventory/%s' % (file_path, filename), 'w')
    fp.write(s)
    fp.close()


def add_role_to_inventory(file_path, config_data):
    LOG.info(_("add role to inventory file..."))
    clean_inventory_file(file_path, 'multinode')
    host_sequence = 1
    for control_ip in config_data['Controller_ips']:
        update_inventory_file(file_path, 'multinode', 'control',
                              control_ip.encode(), host_sequence, 'ssh')
        host_sequence = host_sequence + 1

    host_sequence = 1
    for network_ip in config_data['Network_ips']:
        update_inventory_file(file_path, 'multinode', 'network',
                              network_ip.encode(), host_sequence, 'ssh')
        host_sequence = host_sequence + 1

    host_sequence = 1
    for compute_ip in config_data['Computer_ips']:
        update_inventory_file(file_path, 'multinode', 'compute',
                              compute_ip.encode(), host_sequence, 'ssh')
        host_sequence = host_sequence + 1

    host_sequence = 1
    for compute_ip in config_data['Computer_ips']:
        update_inventory_file(file_path, 'multinode', 'monitoring',
                              compute_ip.encode(), host_sequence, 'ssh')
        host_sequence = host_sequence + 1

    host_sequence = 1
    for storage_ip in config_data['Storage_ips']:
        update_inventory_file(file_path, 'multinode', 'storage',
                              storage_ip.encode(), host_sequence, 'ssh')
        host_sequence = host_sequence + 1


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


def enable_ceph_backend(req, cluster_id, config_data):
    service_disks = []
    params = {'filters': {'cluster_id': cluster_id}}
    roles = registry.get_roles_detail(req.context, **params)
    for role in roles:
        if role['name'] == 'COMTROLLER_LB':
            service_disk = _get_services_disk(req, role)
            service_disks.append(service_disk)
    for disk in service_disks:
        if disk.get('service', None) == 'cinder' and\
                disk.get('protocol_type', None) == 'LVM':

            with open('/etc/kolla/globals.yml', 'r') as f:
                kolla_config = yaml.load(f.read())
            kolla_config.update({'enable_cinder': 'yes',
                                 'enable_cinder_backend_lvm': 'yes',
                                 'cinder_volume_group': 'cinder-volumes'})
            f.close()
            with open('/etc/kolla/globals.yml', 'w') as f:
                f.write(yaml.dump(kolla_config, default_flow_style=False))
                f.close()
            storage_ip_list = config_data.get('Storage_ips')
            if len(storage_ip_list) == 1:
                LOG.info(_("this is all in one environment \
                            to enable ceph backend"))
                for storage_ip in storage_ip_list:
                    fp = '/var/log/daisy/api.log'
                    cmd = 'ssh -o StrictHostKeyChecking=no %s \
                          "mknod /dev/loop2 b 7 2" ' % \
                          (storage_ip)
                    daisy_cmn.subprocess_call(cmd, fp)
                    cmd = 'ssh -o StrictHostKeyChecking=no %s \
                          "dd if=/dev/zero of=/var/lib/cinder_data.img\
                           bs=1G count=20" ' % \
                          (storage_ip)
                    daisy_cmn.subprocess_call(cmd, fp)
                    cmd = 'ssh -o StrictHostKeyChecking=no %s \
                          "losetup /dev/loop2 /var/lib/cinder_data.img" ' % \
                          (storage_ip)
                    daisy_cmn.subprocess_call(cmd, fp)
                    cmd = 'ssh -o StrictHostKeyChecking=no %s \
                          "pvcreate /dev/loop2" ' % \
                          (storage_ip)
                    daisy_cmn.subprocess_call(cmd, fp)
                    cmd = 'ssh -o StrictHostKeyChecking=no %s \
                          "vgcreate cinder-volumes /dev/loop2" ' % \
                          (storage_ip)
                    daisy_cmn.subprocess_call(cmd, fp)
                LOG.info(_("execute all five commands on \
                            storage node %s ok!" % storage_ip))

        elif disk.get('service', None) == 'cinder' and\
                disk.get('protocol_type', None) == 'CEPH':
            with open('/etc/kolla/globals.yml', 'r') as f:
                kolla_config = yaml.load(f.read())
            kolla_config.update({'enable_cinder': 'yes',
                                 'enable_ceph': 'yes'})
            f.close()
            with open('/etc/kolla/globals.yml', 'w') as f:
                f.write(yaml.dump(kolla_config, default_flow_style=False))
                f.close()
            disk_name = disk.get('partition', None)
            storage_ip_list = config_data.get('Storage_ips')
            if len(storage_ip_list) not in [1, 2]:
                LOG.info(_("this is CEPH backend environment \
                            with %s nodes" % len(storage_ip_list)))
                for storage_ip in storage_ip_list:
                    fp = '/var/log/daisy/api.log'
                    cmd = 'ssh -o StrictHostKeyChecking=no %s \
                          "parted %s -s -- mklabel gpt mkpart\
                           KOLLA_CEPH_OSD_BOOTSTRAP 1 -1" ' % \
                          (storage_ip, disk_name)
                    daisy_cmn.subprocess_call(cmd, fp)
                    LOG.info(_("execute labeled command successfully\
                                on %s node" % storage_ip))


# generate kolla's globals.yml file
def update_globals_yml(config_data):
    LOG.info(_("begin to update kolla's globals.yml file..."))
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

    kolla_yml = {'openstack_release': '3.0.0',
                 'docker_registry': '127.0.0.1:4000',
                 'docker_namespace': 'kollaglue',
                 'kolla_internal_vip_address': '10.10.10.254',
                 'network_interface': 'eth0',
                 'tunnel_interface': 'eth0',
                 'storage_interface': 'eth0',
                 'kolla_external_vip_interface': 'eth0',
                 'neutron_external_interface': 'eth1',
                 }
    kolla_yml['openstack_release'] = Version
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


# generate kolla's password.yml file
def generate_RSA(bits=2048):
    new_key = RSA.generate(bits, os.urandom)
    private_key = new_key.exportKey("PEM")
    public_key = new_key.publickey().exportKey("OpenSSH")
    return private_key, public_key


def update_password_yml():
    LOG.info(_("begin to update kolla's passwd.yml file..."))
    # These keys should be random uuids
    uuid_keys = ['ceph_cluster_fsid', 'rbd_secret_uuid']

    # SSH key pair
    ssh_keys = ['nova_ssh_key']

    # If these keys are None, leave them as None
    blank_keys = ['docker_registry_password']

    # generate the password of horizon
    keystone_admin_password = ['keystone_admin_password']

    # length of password
    length = 40

    with open('/etc/kolla/passwords.yml', 'r') as f:
        passwords = yaml.load(f.read())

    for k, v in passwords.items():
        if (k in ssh_keys and
                (v is None or
                 v.get('public_key') is None and
                 v.get('private_key') is None)):
            private_key, public_key = generate_RSA()
            passwords[k] = {
                'private_key': private_key,
                'public_key': public_key
            }
            continue
        if v is None:
            if k in blank_keys:
                continue
            if k in uuid_keys:
                passwords[k] = str(uuid.uuid4())
            if k in keystone_admin_password:
                passwords[k] = "keystone"
            else:
                passwords[k] = ''.join([
                    random.SystemRandom().choice(
                        string.ascii_letters + string.digits)
                    for n in range(length)
                ])
    f.close()
    with open('/etc/kolla/passwords.yml', 'w') as f:
        f.write(yaml.dump(passwords, default_flow_style=False))
        f.close()
