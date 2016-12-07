#!/bin/bash
function update_vnc_ip
{
    local nova_config="/etc/nova/nova.conf"
    local vncip=$1
    if [ "$vncip" != "" -a -f $nova_config ];then
        tmp_ip=`openstack-config --get $nova_config DEFAULT "vncserver_proxyclient_address"`
        if [ "$tmp_ip" = "127.0.0.1" ];then
            openstack-config --set $nova_config DEFAULT "vncserver_proxyclient_address" $vncip
            systemctl restart openstack-nova-compute.service
        fi        
    fi
}
function do_matching
{
    ipaddr=""
    netmask=""
    device=""
    gateway=`grep manage_bond_gateway ../custom.conf|awk -F '=' '{print $2}'`
    local nic_gate=""
    local num=`grep manage_eth_vlan_num ../custom.conf |awk -F '=' '{print $2}'`
    local linux_bond=`grep manage_bond_name ../custom.conf|awk -F '=' '{print $2}'`
    local vlan=0
    local i=1
    while [ $i -le $num ]
    do
        vlan=`grep "eth_vlan_id$i" ../custom.conf|awk -F '=' '{print $2}'`
        device=$linux_bond"."$vlan
        nic_gate=`grep ^GATEWAY /etc/sysconfig/network-scripts/ifcfg-$device|awk -F '=' '{print $2}'`
        if [ $nic_gate -a $nic_gate = $gateway ];then
            ipaddr=`grep ^IPADDR /etc/sysconfig/network-scripts/ifcfg-$device|awk -F '=' '{print $2}'`
            netmask=`grep ^NETMASK /etc/sysconfig/network-scripts/ifcfg-$device|awk -F '=' '{print $2}'`
            break
        fi
        let "i+=1"
    done
    update_vnc_ip $ipaddr
}
do_matching