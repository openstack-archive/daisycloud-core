#!/bin/bash
if [ ! "$_CREATE_BOND_FILE" ];then
_CREATE_BOND_DIR=`pwd`
cd $_CREATE_BOND_DIR
#读取配置文件参数
function get_config
{
    local file="$1"
    local key="$2"
    #配置文件不存在，错误
    [ ! -f "$file" ] && { echo -e "\n$file not exist."; return 0; }

    local key_num=`cat $file |sed '/^[[:space:]]*#/d' |sed -n "1,/\[]/p" |grep -w "$key[[:space:]]*" |grep -c "$key[[:space:]]*="`
    #模块中没有配置该key
    [ "$key_num" -eq 0 ] && return 0
    #一个key有多个值，错误
    [ "$key_num" -gt 1 ] && { echo -e "\nthere are too many \"$key\" in $file"; return 0; }
    
    local key_line=`cat $file|sed '/^[[:space:]]*#/d' |sed -n "1,/\[]/p"|grep -w "$key[[:space:]]*"|grep "$key[[:space:]]*="|tr -d ["\n"] |tr -d ["\r"]`

    if [ "$key_line" != "" ];then
        config_answer=`echo $key_line |awk -F'=' '{print $2}'`
    else
        echo -e "\nthere is no line inclued \"$key=\" in $file"
        return 0
    fi
    return 0
}


function make_bond
{
    local CUSTOM_CFG_FILE=$1
	local num
	local i=1
	local j=1
	local bri=1
	local phynic=""
	local mtu=""
	local pci=""
	first=""
	second=""
	bond_mode=""
	phyname=""
	device=""
	bond_name=""
	bridge=""
	brdata=""
	get_config $CUSTOM_CFG_FILE "ovs-port-bond_num"
	num=$config_answer
	while [ $i -le $num ]
	do
	    echo "make ovs_bond$i" >> /var/tmp/data_bond.log
		brdata=`cat /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini |grep ^bridge_mappings|awk -F ':' '{print $2}'`
		ovs-vsctl del-br $brdata
		if [ $i -eq 1 ];then
		   get_config $CUSTOM_CFG_FILE "ovs_port_uplink_port$i"
		   config_answer=${config_answer//,/ }
		   first=`echo $config_answer |awk '{print $1}'`
		   second=`echo $config_answer |awk '{print $2}'`
		   get_config $CUSTOM_CFG_FILE "ovs_port_bond_mode$i"
		   if [[ "$config_answer" = "0" ]];then
		        bond_mode="active-backup;off"
			elif [[ "$config_answer" = "1" ]];then
			    bond_mode="balance-slb;off"
			else
			    bond_mode="balance-tcp;active"
			fi		   
		   get_config $CUSTOM_CFG_FILE "ovs_phynet_name$i"
		   phyname=$config_answer
		   get_config $CUSTOM_CFG_FILE "ovs_bridge_name$i"
		   bridge="$phyname:$config_answer"
		   openstack-config --set /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini  OVS bridge_mappings  "$bridge"
		   get_config $CUSTOM_CFG_FILE "ovs_bond_name$i"
		   bond_name=$config_answer
		   phynic="$phyname:$bond_name($bond_mode;$first-$second)"
		   openstack-config --set /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini  OVS phynic_mappings  "$phynic"
		   get_config $CUSTOM_CFG_FILE "ovs_mtu_mappings$i"
		   mtu="$phyname:$config_answer"
		   openstack-config --set /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini  OVS mtu_mappings "$mtu"
		   systemctl restart neutron-openvswitch-agent.service
		#   ovs-vsctl add-port "br-data$bri" "bond$bri"
		   let "i+=1"
		   let "bri+=1"
		else
		   get_config $CUSTOM_CFG_FILE "ovs_port_uplink_port$i"
		   config_answer=${config_answer//,/ }
		   first=`echo $config_answer |awk '{print $1}'`
		   second=`echo $config_answer |awk '{print $2}'`
		   get_config $CUSTOM_CFG_FILE "ovs_port_bond_mode$i"
		   if [[ "$config_answer" = "0" ]];then
		        bond_mode="active-backup;off"
			elif [[ "$config_answer" = "1" ]];then
			    bond_mode="balance-slb;off"
			else
			    bond_mode="balance-tcp;active"
		   fi
		   get_config $CUSTOM_CFG_FILE "ovs_phynet_name$i"
		   phyname=$config_answer
		   get_config $CUSTOM_CFG_FILE "ovs_bridge_name$i"
		   bridge=$bridge",$phyname:$config_answer"
		   openstack-config --set /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini  OVS bridge_mappings  "$bridge"
		   get_config $CUSTOM_CFG_FILE "ovs_bond_name$i"
		   bond_name=$config_answer
		   phynic=$phynic",$phyname:$bond_name($bond_mode;$first-$second)"
		   openstack-config --set /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini  OVS phynic_mappings  "$phynic"
		   get_config $CUSTOM_CFG_FILE "ovs_mtu_mappings$i"
		   mtu=$mtu",$phyname:$config_answer"
		   openstack-config --set /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini  OVS mtu_mappings "$mtu"
		   systemctl restart neutron-openvswitch-agent.service
		#   ovs-vsctl add-port "br-data$bri" "bond$bri"
		   let "i+=1"
		   let "bri+=1"
		fi	
	done
	get_config $CUSTOM_CFG_FILE "sriov-port-bond_num"
	num=$config_answer
	while [ $j -le $num ]
	do
	    echo "make sriov_bond$j" >>/var/tmp/data_bond.log
		if [ $j -eq 1 ];then
		   get_config $CUSTOM_CFG_FILE "sriov_phynet_name$j"
		   phyname=$config_answer
		   get_config $CUSTOM_CFG_FILE "sriov_port_uplink_port$j"
		   config_answer=${config_answer//,/ }
		   first=`echo $config_answer |awk '{print $1}'`
		   second=`echo $config_answer |awk '{print $2}'`
		   pci="{ \"address\":\"`ethtool -i $first|grep bus-info|awk '{printf $2}'`\",\"physical_network\":\"$phyname\" }"
		   pci=$pci",{ \"address\":\"`ethtool -i $second|grep bus-info|awk '{printf $2}'`\",\"physical_network\":\"$phyname\" }"
		   openstack-config --set /etc/nova/nova.conf  DEFAULT pci_passthrough_whitelist "[$pci]"
		   get_config $CUSTOM_CFG_FILE "sriov_port_bond_mode$j"
		   if [[ "$config_answer" = "0" ]];then
		        bond_mode="active-backup;off"
			elif [[ "$config_answer" = "1" ]];then
			    bond_mode="balance-slb;off"
			else
			    bond_mode="balance-tcp;active"
			fi
		   get_config $CUSTOM_CFG_FILE "sriov_bridge_name$j"
		   bridge="$phyname:$config_answer"
		   openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC bridge_mappings  "$bridge"
		   get_config $CUSTOM_CFG_FILE "sriov_bond_name$j"
		   bond_name=$config_answer
		   phynic="$phyname:$bond_name($bond_mode;$first-$second)"
		   device="$phyname:$first-$second"
		   openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC physical_device_mappings  "$device"
		   openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC phynic_mappings  "$phynic"
		   openstack-config --set /etc/nova/nova.conf  DEFAULT phynic_mappings  "$phynic"
		   get_config $CUSTOM_CFG_FILE "sriov_mtu_mappings$j"
		   mtu="$phyname:$config_answer"
		   openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC mtu_mappings "$mtu"
		   systemctl restart openstack-nova-compute.service
		   systemctl restart neutron-sriov-nic-switch-agent.service
		#   ovs-vsctl add-port "br-data$bri" "bond$bri"
		   let "bri+=1"
		   let "j+=1"
		else
		   get_config $CUSTOM_CFG_FILE "sriov_phynet_name$j"
		   phyname=$config_answer
		   get_config $CUSTOM_CFG_FILE "sriov_port_uplink_port$j"
		   config_answer=${config_answer//,/ }
		   first=`echo $config_answer |awk '{print $1}'`
		   second=`echo $config_answer |awk '{print $2}'`
		   pci=$pci",{ \"address\":\"`ethtool -i $first|grep bus-info|awk '{printf $2}'`\",\"physical_network\":\"$phyname\" }"
		   pci=$pci",{ \"address\":\"`ethtool -i $second|grep bus-info|awk '{printf $2}'`\",\"physical_network\":\"$phyname\" }"
		   openstack-config --set /etc/nova/nova.conf  DEFAULT pci_passthrough_whitelist "[$pci]"
		   get_config $CUSTOM_CFG_FILE "sriov_port_bond_mode$j"
		   if [[ "$config_answer" = "0" ]];then
		        bond_mode="active-backup;off"
			elif [[ "$config_answer" = "1" ]];then
			    bond_mode="balance-slb;off"
			else
			    bond_mode="balance-tcp;active"
			fi
		   get_config $CUSTOM_CFG_FILE "sriov_bridge_name$j"
		   bridge=$bridge",$phyname:$config_answer"
		   openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC bridge_mappings  "$bridge"
		   get_config $CUSTOM_CFG_FILE "sriov_bond_name$j"
		   bond_name=$config_answer
		   phynic=$phynic",$phyname:$bond_name($bond_mode;$first-$second)"
		   device=$device",$phyname:$first-$second"
		   openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC physical_device_mappings  "$device"
		   openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC phynic_mappings  "$phynic"
		   openstack-config --set /etc/nova/nova.conf  DEFAULT phynic_mappings  "$phynic"
		   get_config $CUSTOM_CFG_FILE "sriov_mtu_mappings$j"
		   mtu=$mtu",$phyname:$config_answer"
		   openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC mtu_mappings "$mtu"
		   systemctl restart openstack-nova-compute.service
		   systemctl restart neutron-sriov-nic-switch-agent.service
		#   ovs-vsctl add-port "br-data$bri" "bond$bri"
		   let "j+=1"
		   let "bri+=1"
		fi	
	done
    	
		   
		   
		   
}
function do_install
{
    local CUSTOM_CFG_FILE="../custom.conf"
	config_answer=""
	get_config $CUSTOM_CFG_FILE "data_port_is_using_bonding"
	if [ $config_answer = "no" ];then
	    echo "not make_bond" >>/var/tmp/data_bond.log
		get_config $CUSTOM_CFG_FILE "data_port_phynic" 
		openstack-config --set /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini  OVS phynic_mappings "physnet1:$config_answer"
		openstack-config --set /etc/neutron/plugins/openvswitch/ovs_neutron_plugin.ini  OVS bridge_mappings  "physnet1:br-data1"
		systemctl restart neutron-openvswitch-agent.service 

		get_config $CUSTOM_CFG_FILE "data_port_phynic" 
		openstack-config --set /etc/nova/nova.conf  DEFAULT pci_passthrough_whitelist "[{ \"address\":\"`ethtool -i $config_answer|grep bus-info|awk '{printf $2}'`\",\"physical_network\":\"physnet1\" }]"
		openstack-config --set /etc/nova/nova.conf  DEFAULT phynic_mappings "physnet1:$config_answer"
		openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC bridge_mappings  "physnet1:br-data1"
		openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC physical_device_mappings "physnet1:$config_answer"
		openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC mtu_mappings "physnet1:1520"
		openstack-config --set /etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini  SRIOV_NIC phynic_mappings "physnet1:$config_answer"
		systemctl restart openstack-nova-compute.service
		systemctl restart neutron-sriov-nic-switch-agent.service

	else
	    make_bond $CUSTOM_CFG_FILE
		echo "data_bond make successful" >>/var/tmp/data_bond.log
	fi
		
	
	    
	   
	
}

touch /var/tmp/data_bond.log
echo "start do_install" >>/var/tmp/data_bond.log
do_install
_CREATE_BOND_FILE="create_bond_sh"
fi
