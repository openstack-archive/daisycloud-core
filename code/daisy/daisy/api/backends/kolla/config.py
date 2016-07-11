# -*- coding: utf-8 -*-
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

import os
import yaml
import random
import string
import uuid
from Crypto.PublicKey import RSA


# generate kolla's ansible inventory multinode file
def clean_inventory_file(filename):
    fp = file('/home/test/%s' % filename)
    lines = []
    for line in fp:
        lines.append(line)
    fp.close()
    node_names = ['control', 'network', 'compute', 'storage']
    for node_name in node_names:
        index_of_label = lines.index('[%s]\n' % node_name)
        line_index = index_of_label
        while 1:
            if lines[line_index + 1][0] == '[':
                break
            elif lines[line_index + 1][0] == '#':
                line_index = line_index + 1
            else:
                del lines[line_index + 1]
        lines.insert(index_of_label + 1, '\n')
    s = ''.join(lines)
    fp = file('/home/test/%s' % filename, 'w')
    fp.write(s)
    fp.close()


def update_inventory_file(filename, node_name, host_name,
                          num_of_host, connection_type):
    fp = file('/home/test/%s' % filename)
    lines = []
    for line in fp:
        lines.append(line)
    fp.close()
    index_of_label = lines.index('[%s]\n' % node_name)
    lines.insert(index_of_label + num_of_host,
                 '%s       ansible_connection=%s\n' %
                 (host_name, connection_type))
    s = ''.join(lines)
    fp = file('/home/test/%s' % filename, 'w')
    fp.write(s)
    fp.close()


# generate kolla's globals.yml file
def update_globals_yml(config_data):
    VIP = config_data['VIP']
    IntIfMac = config_data['IntIfMac']
    ExtIfMac = config_data['ExtIfMac']
    local_ip = config_data['LocalIP']
    # kolla_yml = yaml.load(file('/etc/kolla/globals.yml'))
    kolla_yml = {'openstack_release': '2.0.1',
                 'docker_registry': '127.0.0.1:4000',
                 'docker_namespace': 'kollaglue',
                 'kolla_internal_vip_address': '10.10.10.254',
                 'network_interface': 'eth0',
                 'neutron_external_interface': 'eth1'
                 }
    kolla_yml['kolla_internal_vip_address'] = VIP.encode()
    kolla_yml['network_interface'] = IntIfMac.encode()
    kolla_yml['neutron_external_interface'] = ExtIfMac.encode()
    kolla_yml['docker_registry'] = local_ip.encode()

    yaml.dump(kolla_yml, file('/etc/kolla/globals.yml', 'w'),
              default_flow_style=False)
    return


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
            if k in blank_keys and v is None:
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

    with open('/etc/kolla/passwords.yml', 'w') as f:
        f.write(yaml.dump(passwords, default_flow_style=False))
