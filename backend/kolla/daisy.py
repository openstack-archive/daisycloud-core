#!/usr/bin/python
#    Copyright 2012 OpenStack Foundation
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


# -*- coding: utf-8 -*-

import json
import os
import sys
import datetime
import time

json_path = '/home/os_install/os.json'
shell_path = '/usr/bin/bash /home/linux_action.sh'
update_network_mode = False

def analyze_json():
    f = file(json_path)
    data = json.load(f)
    f.close()
    interface_info = data['interfaces']
    if len(interface_info) == 0:
        print "%s interface information is Null" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f")
        sys.exit()
    else:
        print "%s interface_info : %s " % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f"), interface_info)
    return interface_info


def key_vlaue_check(key, dic):
    if key in dic and dic[key]:
        return True
    return False


def get_netmask_num(number):
    if number == 255:
        return 8
    if number == 254:
        return 7
    if number == 252:
        return 6
    if number == 248:
        return 5
    if number == 240:
        return 4
    if number == 224:
        return 3
    if number == 192:
        return 2
    if number == 128:
        return 1
    return 0


def get_ip_net_str(ip, netmask):
    num = 0
    for i in netmask.split('.'):
        num += get_netmask_num(int(i))
    return ip + '/' + str(num)


def ip_gateway_check(interface, plane):
    if key_vlaue_check('ip', interface):
        if key_vlaue_check('gateway', interface):
            return 'only', interface['ip'], interface['netmask'], interface['gateway']
        else:
            return 'only', interface['ip'], interface['netmask'], None
    else:
        if key_vlaue_check('ip', plane):
            if key_vlaue_check('gateway', plane):
                return 'multi', plane['ip'], plane['netmask'], plane['gateway']
            else:
                return 'multi', plane['ip'], plane['netmask'], None
        return None, None, None, None


def ip_config(operation, interface, management_location):
    i = 0
    for plane in interface['assigned_networks']:
        mark, ip, netmask, gateway = ip_gateway_check(interface, plane)
        print "%s IP_CONNFIG mark:%s ip:%s netmask:%s gateway:%s" % \
              (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f"), mark, ip, netmask, gateway)
        if mark == 'only':
            if operation == '2':
                if gateway is not None:
                    os.system(shell_path+" 2 %s %s %s %s %s" %
                              ('br-'+interface['name'], 'v_'+interface['name'], ip, netmask, gateway))
                else:
                    os.system(shell_path+" 2 %s %s %s %s" %
                              ('br-'+interface['name'], 'v_'+interface['name'], ip, netmask))
            elif operation == '4':
                if gateway is not None:
                    os.system(shell_path+" 4 %s %s %s %s" %
                              (interface['name'], ip, netmask, gateway))
                else:
                    os.system(shell_path+" 4 %s %s %s" %
                              (interface['name'], ip, netmask))
            break
        elif mark == 'multi':
            if operation == '2':
                if key_vlaue_check('vlan_id', plane):
                    if gateway is not None:
                        os.system(shell_path+" 7 %s %s %s %s %s %s" %
                                  ('br-'+interface['name'], plane['network_type'].lower()[0:3] + '_' + interface['name'], plane['vlan_id'], ip, netmask, gateway))
                    else:
                        os.system(shell_path+" 7  %s %s %s %s %s" %
                                  ('br-'+interface['name'], plane['network_type'].lower()[0:3] + '_' + interface['name'], plane['vlan_id'], ip, netmask))
                else:
                    if gateway is not None:
                        os.system(shell_path+" 2 %s %s %s %s %s" %
                                  ('br-'+interface['name'], plane['network_type'].lower()[0:3] + '_' + interface['name'], ip, netmask, gateway))
                    else:
                        os.system(shell_path+" 2 %s %s %s %s" %
                                  ('br-'+interface['name'], plane['network_type'].lower()[0:3] + '_' + interface['name'], ip, netmask))
            elif operation == '4':
                if key_vlaue_check('vlan_id', plane):
                    if gateway is not None:
                        os.system(shell_path+" 8 %s %s %s %s %s %s" %
                                  (interface['name'], plane['vlan_id'], get_ip_net_str(ip, netmask), ip, netmask, gateway))
                    elif plane.has_key('old_ip') and plane['ip'] == plane['old_ip'] and plane['network_type'] == 'MANAGEMENT':
                        os.system(shell_path+" 10 %s %s %s" %
                                  (interface['name'], plane['old_vlan_id'], plane['vlan_id']))
                    else:
                        os.system(shell_path+" 8 %s %s %s %s %s" %
                                  (interface['name'], plane['vlan_id'], get_ip_net_str(ip, netmask), ip, netmask))
                else:
                    if i == 0 and management_location == -1:
                        if gateway is not None:
                            os.system(shell_path+" 4 %s %s %s %s" %
                                      (interface['name'], ip, netmask, gateway))
                        else:
                            os.system(shell_path+" 4 %s %s %s" %
                                      (interface['name'], ip, netmask))
                    else:
                        if gateway is not None:
                            os.system(shell_path+" 4 %s %s %s %s" %
                                      (interface['name']+':'+str(i), ip, netmask, gateway))
                        else:
                            os.system(shell_path+" 4 %s %s %s" %
                                      (interface['name']+':'+str(i), ip, netmask))
                    i += 1

def update_interface(interface):
    if key_vlaue_check('ip', interface):
        os.system(shell_path + " 4 %s %s %s" %
                  (interface['name'], interface['ip'], interface['netmask']))

    without_vlan_plane_list = []
    i = 0
    for plane in interface['assigned_networks']:
        if 'old_vlan_id' not in plane.keys():
            continue
        if plane['old_vlan_id'] != plane['vlan_id'] and \
                        plane['network_type'] == 'MANAGEMENT':
            continue
        if plane['old_vlan_id'] != plane['vlan_id']:
            update_interface_with_vlan(plane, interface)
        elif plane['old_ip'] != plane['ip'] or \
                        plane['old_netmask'] != plane['netmask']:
            update_interface_without_vlan(plane, interface)
            without_vlan_plane_list.insert(0, i)
        i += 1
    print "without_vlan_plane_list is %s" % without_vlan_plane_list
    for plane_index in without_vlan_plane_list:
        del interface['assigned_networks'][plane_index]
    print interface

def update_interface_with_vlan(plane, interface):
    print "old_vlan is %s" % plane['old_vlan_id']
    if plane['old_vlan_id'] != None:
        os.system(shell_path + " 9 %s %s" %
                  (interface['name'], plane['old_vlan_id']))


def update_interface_without_vlan(plane, interface):
    interface_list  = os.popen('ls /etc/sysconfig/network-scripts |grep %s'
                               % interface['name']).read().split("\n")
    print "interface_list is %s" % interface_list
    for interface_name in interface_list:
        if not interface_name:
            continue
        print interface_name
        print os.popen('cat /etc/sysconfig/network-scripts/%s |grep %s'
                       % (interface_name, plane['old_ip'])).read()
        if os.popen('cat /etc/sysconfig/network-scripts/%s |grep %s'
                            % (interface_name, plane['old_ip'])).read():
            os.system(shell_path + " 4 %s %s %s %s" %
                      (interface_name[6:], plane['ip'],  plane['netmask'], plane['gateway']))
            return

def multi_plane(interface):
    private_physnet = 0
    ovs_physnet = 0
    management_location = -1
    location = 0
    capability = []
    for plane in interface['assigned_networks']:
        if plane['network_type'] == 'DATAPLANE':
            private_physnet += 1
            #if 'ovs' in plane['ml2_type']:
            #    ovs_physnet += 1
        if private_physnet > 1:
            print "%s can not multi private plane overlapping" % \
                  datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f")
            sys.exit()
        if plane['network_type'] == 'MANAGEMENT':
            management_location = location
        if plane['capability']:
            capability.append(plane['capability'])
        location += 1
    print " %s name:%s type:%s private_physnet:%s ovs_physnet:%s management_location:%s capability:%s" % \
          (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f"),
           interface['name'],
           interface['type'],
           private_physnet,
           ovs_physnet,
           management_location,
           capability)
    if interface['type'] == 'bond':
        if management_location != -1:
            if private_physnet == 0 and len(set(capability)) == 1 and 'high' in capability:
                del interface['assigned_networks'][management_location]
                ip_config('4', interface, management_location)
            #else:
            #    os.system(shell_path+" 5 %s %s %s %s" %
            #              (interface['name'], interface['slave1'], interface['slave2'], interface['mode']))
            #    ip_config('2', interface)
        else:
            if private_physnet == 0 and len(set(capability)) == 1 and 'high' in capability:
                os.system(shell_path+" 3 %s %s %s %s" %
                          (interface['name'], interface['slave1'], interface['slave2'], interface['mode']))
                ip_config('4', interface, management_location)
            #else:
            #    os.system(shell_path+" 6 %s %s %s %s" %
            #              (interface['name'], interface['slave1'], interface['slave2'], interface['mode']))
            #    ip_config('2', interface)
    else:
        if management_location != -1:
            if ovs_physnet == 0 and len(set(capability)) < 2 and 'low' not in capability:
                if not update_network_mode:
                    del interface['assigned_networks'][management_location]
                ip_config('4', interface, management_location)
            #else:
            #    os.system(shell_path+" 1 %s" % interface['name'])
            #    ip_config('2', interface)
        else:
            if ovs_physnet == 0 and len(set(capability)) < 2 and 'low' not in capability:
                ip_config('4', interface, management_location)
            #else:
            #    os.system(shell_path+" 1 %s" % interface['name'])
            #    ip_config('2', interface)


def plane_overlapping_check(interface):
    plane_num = len(interface['assigned_networks'])
    if interface.get('vswitch_type', None) == 'dvs':
        return 
    if plane_num == 0 and not update_network_mode:
        print "%s  %s is not belong to any physnet planes" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f"),
                                                              interface['name'])
    #elif plane_num == 1:
    #    single_plane(interface)
    else:
        if update_network_mode:
            update_interface(interface)
        multi_plane(interface)

def update_private_networks():
    f = file(json_path)
    data = json.load(f)
    vlan_ranges = ''
    vxlan_ranges = ''
    for plane_data in data['private_networks']:
        if plane_data['segmentation_type'] == 'vlan':
            vlan_ranges += plane_data['network_name']
            vlan_ranges += ':'
            vlan_ranges += plane_data['vlan_start']
            vlan_ranges += ':'
            vlan_ranges += plane_data['vlan_end']
            vlan_ranges += ','
        elif plane_data['segmentation_type'] == 'vxlan':
            vxlan_ranges += plane_data['vlan_start']
            vxlan_ranges += ':'
            vxlan_ranges += plane_data['vlan_end']
    vlan_ranges = vlan_ranges[:-1]

    os.system("openstack-config --set /etc/neutron/plugin.ini ml2_type_vlan network_vlan_ranges %s"
              % vlan_ranges)
    os.system("openstack-config --set /etc/neutron/plugin.ini ml2_type_vxlan vni_ranges %s"
              % vxlan_ranges)
    os.system("systemctl restart neutron-server.service")

def main(argv):
    if len(argv) > 1:
        global json_path
        global update_network_mode
        json_path = argv[1]
        update_network_mode = True

    if json_path == "/home/config_dir/config_update/private_network/private_ctrl.json":
        update_private_networks()
        return

    interface_info = analyze_json()
    for interface in interface_info:
        print "%s config: %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f"), interface)
        plane_overlapping_check(interface)
    #if not update_network_mode:
    #    os.system("systemctl restart network.service")


if __name__ == '__main__':
    main(sys.argv)



