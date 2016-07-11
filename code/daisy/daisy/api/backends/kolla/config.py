# -*- coding: utf-8 -*-
import os
import yaml
import random
import string
import uuid
from Crypto.PublicKey import RSA


# generate kolla's ansible inventory all-in-one file
def replace_host_name(source, destination):
    all_in_one_dir = "/home/kolla/ansible/inventory/all-in-one"
    f = open(all_in_one_dir, 'r+')
    all_the_lines = f.readlines()
    f.seek(0)
    f.truncate()
    for line in all_the_lines:
        f.write(line.replace(source, destination))
    f.close()


def update_all_in_one(config_data):
    mgtip = config_data['MGTIP']
    localhost_replace = mgtip
    local_replace = 'ssh'
    template_host_name = 'localhost'
    template_connect_name = 'local'
    replace_host_name(template_host_name, localhost_replace)
    replace_host_name(template_connect_name, local_replace)


# generate kolla's ansible invenory multinode file
def update_multinode(node_name, host_name):
    fp = file('/home/zhouya/test/multinode')
    lines = []
    for line in fp:
        lines.append(line)
    fp.close()

    # print lines
    index_of_label = lines.index('[node_name]\n')
    lines.insert(index_of_label + 1, 'host_name')

    # lines.insert(1,'a new line')
    s = ''.join(lines)
    fp = file('/home/zhouya/test/multinode_test_file', 'w')
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


def test():
    print("Hello, kolla!")
