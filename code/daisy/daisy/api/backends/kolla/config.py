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
from Crypto.PublicKey import RSA


# generate kolla's ansible inventory multinode file
def clean_inventory_file(file_path, filename):
    fp = open('%s/kolla/ansible/inventory/%s' % (file_path, filename))
    txt = fp.read()
    fp.close()
    node_names = ['control', 'network', 'compute',
                  'storage', 'kibana:children']
    for section_name in node_names[0:4]:
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
    fp = file('%s/kolla/ansible/inventory/%s' % (file_path, filename))
    lines = []
    for line in fp:
        lines.append(line)
    fp.close()
    index_of_label = lines.index('[%s]\n' % node_name)
    lines.insert(index_of_label + num_of_host,
                 '%s       ansible_connection=%s\n' %
                 (host_name, connection_type))
    s = ''.join(lines)
    fp = file('%s/kolla/ansible/inventory/%s' % (file_path, filename), 'w')
    fp.write(s)
    fp.close()


def add_role_to_inventory(file_path, config_data):
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
    for storage_ip in config_data['Storage_ips']:
        update_inventory_file(file_path, 'multinode', 'storage',
                              storage_ip.encode(), host_sequence, 'ssh')
        host_sequence = host_sequence + 1


# generate kolla's globals.yml file
def update_globals_yml(config_data):
    Version = config_data['Version']
    Namespace = config_data['Namespace']
    VIP = config_data['VIP']
    IntIfMac = config_data['IntIfMac']
    ExtIfMac = config_data['ExtIfMac']
    TulIfMac = config_data['TulIfMac']
    local_ip = config_data['LocalIP']
    # kolla_yml = yaml.load(file('/etc/kolla/globals.yml'))
    kolla_yml = {'openstack_release': '2.0.3',
                 'docker_registry': '127.0.0.1:4000',
                 'docker_namespace': 'kollaglue',
                 'kolla_internal_vip_address': '10.10.10.254',
                 'network_interface': 'eth0',
                 'tunnel_interface': 'eth0',
                 'neutron_external_interface': 'eth1'
                 }
    kolla_yml['openstack_release'] = Version.encode()
    kolla_yml['docker_registry'] = local_ip.encode()
    kolla_yml['docker_namespace'] = Namespace.encode()
    kolla_yml['kolla_internal_vip_address'] = VIP.encode()
    kolla_yml['network_interface'] = IntIfMac.encode()
    kolla_yml['tunnel_interface'] = TulIfMac.encode()
    kolla_yml['neutron_external_interface'] = ExtIfMac.encode()
    yaml.dump(kolla_yml, file('/etc/kolla/globals.yml', 'w'),
              default_flow_style=False)


# generate kolla's password.yml file
def generate_RSA(bits=2048):
    new_key = RSA.generate(bits, os.urandom)
    private_key = new_key.exportKey("PEM")
    public_key = new_key.publickey().exportKey("OpenSSH")
    return private_key, public_key


def update_password_yml():
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
