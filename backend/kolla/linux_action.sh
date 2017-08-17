#!/bin/bash
##############################################################################
# Copyright (c) 2016 ZTE Coreporation and others.
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Apache License, Version 2.0
# which accompanies this distribution, and is available at
# http://www.apache.org/licenses/LICENSE-2.0
##############################################################################

log_file='/home/os_install/shell_action.log'

function make_linux_bond
{
	bond_name=$1
	bond_eth1=$2
	bond_eth2=$3
	bond_mode=$4
	if [  -f "/etc/sysconfig/network-scripts/ifcfg-$bond_name" ];then
	    rm -rf /etc/sysconfig/network-scripts/ifcfg-$bond_name
		sed '/MASTER/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
		sed '/SLAVE/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
		sed '/MASTER/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
		sed '/SLAVE/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
	fi 
	touch /etc/sysconfig/network-scripts/ifcfg-$bond_name
	echo "DEVICE=$bond_name" >>/etc/sysconfig/network-scripts/ifcfg-$bond_name
	echo "BOOTPROTO=static" >>/etc/sysconfig/network-scripts/ifcfg-$bond_name
	echo "ONBOOT=yes" >>/etc/sysconfig/network-scripts/ifcfg-$bond_name
	echo "BONDING_OPTS=\"mode=$bond_mode miimon=100\"" >>/etc/sysconfig/network-scripts/ifcfg-$bond_name
	sed '$a\MASTER='$bond_name'' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
	sed '$a\SLAVE=yes' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
	sed '/IPADDR/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
	sed '/NETMASK/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
	sed '/GATEWAY/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
	sed '$a\MASTER='$bond_name'' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
	sed '$a\SLAVE=yes' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
	sed '/IPADDR/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
	sed '/NETMASK/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
	sed '/GATEWAY/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
	if [  -f "/etc/modprobe.d/bonding.conf" ];then
	    touch /etc/modprobe.d/bonding.conf
	fi
	echo "alias $bond_name bonding"  >>/etc/modprobe.d/bonding.conf
	echo "options $bond_name miimon=100 mode=$bond_mode" >> /etc/modprobe.d/bonding.conf
	#modprobe bonding
	#systemctl restart network
}

function add_ip
{
    eth_name=$1
	ipaddr=$2
	netmask=$3
	gateway=$4
	if [ -f /etc/sysconfig/network-scripts/ifcfg-$eth_name ];then
        sed '/IPADDR/d' -i /etc/sysconfig/network-scripts/ifcfg-$eth_name
	    sed '/NETMASK/d' -i /etc/sysconfig/network-scripts/ifcfg-$eth_name
	    sed '/GATEWAY/d' -i /etc/sysconfig/network-scripts/ifcfg-$eth_name
	else
	    touch /etc/sysconfig/network-scripts/ifcfg-$eth_name
	    echo "DEVICE=$eth_name" >>/etc/sysconfig/network-scripts/ifcfg-$eth_name
	    echo "BOOTPROTO=static" >>/etc/sysconfig/network-scripts/ifcfg-$eth_name
	    echo "ONBOOT=yes" >>/etc/sysconfig/network-scripts/ifcfg-$eth_name
	fi
	echo "IPADDR=$ipaddr" >>/etc/sysconfig/network-scripts/ifcfg-$eth_name
	echo "NETMASK=$netmask" >>/etc/sysconfig/network-scripts/ifcfg-$eth_name
	if [ "$gateway" ];then
	    echo "GATEWAY=$gateway" >>/etc/sysconfig/network-scripts/ifcfg-$eth_name
	fi
}

function vlan_eth_create
{
    eth_name=$1
	vlan_id=$2
	ipstr=$3
	ipaddr=$4
	netmask=$5
	gateway=$6
	vlan_eth_name="$eth_name.$vlan_id"
	ip link add link $eth_name name $vlan_eth_name type vlan id $vlan_id
	ifconfig $vlan_eth_name $ipstr
	if [  -f "/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name" ];then
	    rm -rf /etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
	fi 
	touch /etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
	echo "DEVICE=$vlan_eth_name" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
	echo "BOOTPROTO=static" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
	echo "ONBOOT=yes" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
	echo "IPADDR=$ipaddr" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
	echo "NETMASK=$netmask" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
	echo "VLAN=yes" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
	if [ "$gateway" ];then
	    echo "GATEWAY=$gateway" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
	fi
}

function change_mgt_eth_vlan_id
{
    eth_name=$1
    old_vlan_id=$2
    vlan_id=$3
    old_vlan_eth_name="$eth_name.$old_vlan_id"
    vlan_eth_name="$eth_name.$vlan_id"
    ip link del $old_vlan_eth_name
    if [  -f "/etc/sysconfig/network-scripts/ifcfg-$old_vlan_eth_name" ];then
        mv /etc/sysconfig/network-scripts/ifcfg-$old_vlan_eth_name /etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
    fi
    sed -i '/DEVICE/'d /etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
    echo "DEVICE=$vlan_eth_name" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
    ip link add link $eth_name name $vlan_eth_name type vlan id $vlan_id
    service network restart
}

function vlan_eth_delete
{
    eth_name=$1
	vlan_id=$2
	vlan_eth_name="$eth_name.$vlan_id"
	if [  -f "/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name" ];then
	    rm -rf /etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
	    ip link del $vlan_eth_name
	fi
}

function bond_change
{
    bond_name=$1
	bond_eth1=$2
	bond_eth2=$3
	bond_mode=$4
	rm -rf /etc/sysconfig/network-scripts/ifcfg-$bond_name
	sed '/MASTER/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
	sed '/SLAVE/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
	sed '/MASTER/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
	sed '/SLAVE/d' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
	sed '/'$bond_name'/d' -i /etc/modprobe.d/bonding.conf
	echo -$bond_name >/sys/class/net/bonding_masters
	#systemctl restart network.service
	ovs-vsctl add-br br-$bond_name
	if [ $bond_mode = "0" ];then
	    ovs-vsctl add-bond br-$bond_name $bond_name $bond_eth1 $bond_eth2 -- set port $bond_name bond_mode=active-backup
	elif [ $bond_mode = "1" ];then
	    ovs-vsctl add-bond br-$bond_name $bond_name $bond_eth1 $bond_eth2 -- set port $bond_name bond_mode=balance-slb lacp=off
	elif [ $bond_mode = "2" ];then
	    ovs-vsctl add-bond br-$bond_name $bond_name $bond_eth1 $bond_eth2 -- set port $bond_name bond_mode=balance-tcp lacp=active
	fi
	ovs-vsctl set interface $bond_eth1 other-config:enable-vlan-splinters=true
	ovs-vsctl set interface $bond_eth2 other-config:enable-vlan-splinters=true
}

function make_ovs_bond
{
    bond_name=$1
	bond_eth1=$2
	bond_eth2=$3
	bond_mode=$4
	ovs-vsctl add-br br-$bond_name
	if [ $bond_mode = "0" ];then
	    ovs-vsctl add-bond br-$bond_name $bond_name $bond_eth1 $bond_eth2 -- set port $bond_name bond_mode=active-backup
	elif [ $bond_mode = "1" ];then
	    ovs-vsctl add-bond br-$bond_name $bond_name $bond_eth1 $bond_eth2 -- set port $bond_name bond_mode=balance-slb lacp=off
	elif [ $bond_mode = "2" ];then
	    ovs-vsctl add-bond br-$bond_name $bond_name $bond_eth1 $bond_eth2 -- set port $bond_name bond_mode=balance-tcp lacp=active
	fi
	ovs-vsctl set interface $bond_eth1 other-config:enable-vlan-splinters=true
	ovs-vsctl set interface $bond_eth2 other-config:enable-vlan-splinters=true
}

function single_eth_ovs
{
    eth_name=$1
	if [ -f /etc/sysconfig/network-scripts/ifcfg-$eth_name ];then
        sed '/IPADDR/d' -i /etc/sysconfig/network-scripts/ifcfg-$eth_name
	    sed '/NETMASK/d' -i /etc/sysconfig/network-scripts/ifcfg-$eth_name
	    sed '/GATEWAY/d' -i /etc/sysconfig/network-scripts/ifcfg-$eth_name
	fi
	ovs-vsctl add-br br-$eth_name
	ovs-vsctl add-port br-$eth_name $eth_name
	ovs-vsctl set interface $eth_name other-config:enable-vlan-splinters=true
}

function add_ovs_port
{
    bridge=$1
	name=$2
	ipaddr=$3
	netmask=$4
	gateway=$5
	ovs-vsctl add-port $bridge $name -- set interface $name type=internal
	touch /etc/sysconfig/network-scripts/ifcfg-$name
	echo "DEVICE=$name" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "DEVICETYPE=ovs" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "TYPE=OVSIntPort" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "OVS_BRIDGE=$bridge" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "BOOTPROTO=static" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "ONBOOT=yes" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "IPADDR=$ipaddr" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "NETMASK=$netmask" >>/etc/sysconfig/network-scripts/ifcfg-$name
	if [ "$gateway" ];then
	    echo "GATEWAY=$gateway" >>/etc/sysconfig/network-scripts/ifcfg-$name
	fi
}

function ovs_tag_port_create
{
    bridge=$1
	name=$2
	tag=$3
	ipaddr=$4
	netmask=$5
	gateway=$6
	ovs-vsctl add-port $bridge $name tag=$tag -- set interface $name type=internal
	touch /etc/sysconfig/network-scripts/ifcfg-$name
	echo "DEVICE=$name" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "DEVICETYPE=ovs" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "TYPE=OVSIntPort" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "OVS_BRIDGE=$bridge" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "BOOTPROTO=static" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "ONBOOT=yes" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "OVS_OPTIONS=\"tag=$tag\"" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "IPADDR=$ipaddr" >>/etc/sysconfig/network-scripts/ifcfg-$name
	echo "NETMASK=$netmask" >>/etc/sysconfig/network-scripts/ifcfg-$name
	if [ "$gateway" ];then
	    echo "GATEWAY=$gateway" >>/etc/sysconfig/network-scripts/ifcfg-$name
	fi
}

function operation
{
    local options=$1
	case $options in
		"1")
            single_eth_ovs $2
			echo "$(date +%Y-%m-%d' '%k:%M:%S:%N)  single_eth_ovs $2" >>$log_file
			;;
		"2")
            add_ovs_port $2 $3 $4 $5 $6
			echo "$(date +%Y-%m-%d' '%k:%M:%S:%N)  add_ovs_port $2 $3 $4 $5 $6" >>$log_file
			;;
		"3")
            make_linux_bond $2 $3 $4 $5
			echo "$(date +%Y-%m-%d' '%k:%M:%S:%N)  make_linux_bond $2 $3 $4 $5" >>$log_file
			;;
		"4")
			add_ip $2 $3 $4 $5
			echo "$(date +%Y-%m-%d' '%k:%M:%S:%N)  add_ip $2 $3 $4 $5" >>$log_file
			;;
		"5")
			bond_change $2 $3 $4 $5
			echo "$(date +%Y-%m-%d' '%k:%M:%S:%N)  bond_change $2 $3 $4" >>$log_file
			;;
        "6")
			make_ovs_bond $2 $3 $4 $5
			echo "$(date +%Y-%m-%d' '%k:%M:%S:%N)  make_ovs_bond $2 $3 $4 $5" >>$log_file
			;;
		"7")
            ovs_tag_port_create $2 $3 $4 $5 $6 $7
			echo "$(date +%Y-%m-%d' '%k:%M:%S:%N)  ovs_tag_port_create $2 $3 $4 $5 $6 $7" >>$log_file
			;;
        "8")
			vlan_eth_create $2 $3 $4 $5 $6 $7
			echo "$(date +%Y-%m-%d' '%k:%M:%S:%N)  vlan_eth_create $2 $3 $4 $5 $6 $7" >>$log_file
			;;
        "9")
			vlan_eth_delete $2 $3
			echo "$(date +%Y-%m-%d' '%k:%M:%S:%N)  vlan_eth_delete $2 $3" >>$log_file
			;;
        "10")
                        change_mgt_eth_vlan_id $2 $3 $4
                        echo "$(date +%Y-%m-%d' '%k:%M:%S:%N)  change_mgt_eth_vlan_id $2 $3 $4" >>$log_file
                        ;;				
	esac	   
}


operation $1 $2 $3 $4 $5 $6 $7 
