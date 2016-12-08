#!/bin/bash
if [ ! "$_CREATE_MANAGER_PORT_FILE" ];then
_CREATE_MANAGER_PORT_FILE_DIR=`pwd`

cd $_CREATE_MANAGER_PORT_FILE_DIR

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
function get_netmask
{
	local num=`echo $config_answer|awk -F '/' '{print $2}'`
	local i=0
	netma="255"
	let "num-=8"
	while [ $i -lt 3 ]
	do
	    if [ $num -ge 8 ];then
		    let "num-=8"
			netma=$netma".255"
		elif [ $num -eq 0 ];then
		    let "num-=0"
			netma=$netma".0"
		elif [ $num -eq 7 ];then
		    let "num-=7"
			netma=$netma".254"
		elif [ $num -eq 6 ];then
		    let "num-=6"
			netma=$netma".252"
		elif [ $num -eq 5 ];then
		    let "num-=5"
			netma=$netma".248"
		elif [ $num -eq 4 ];then
		    let "num-=4"
			netma=$netma".240"
		elif [ $num -eq 3 ];then
		    let "num-=3"
			netma=$netma".224"
		elif [ $num -eq 2 ];then
		    let "num-=2"
			netma=$netma".192"
		elif [ $num -eq 1 ];then
		    let "num-=1"
			netma=$netma".128"
		fi
		let "i+=1"
	done
		  
}

function get_gateway
{
   local ip1=$1
   local ip2=$2
   local ne=$3
   local gw1=""
   local gw2=""
   local a1=""
   local a2=""
   local b=""
   local i=1
   while [ $i -lt 5 ]
   do
        a1=`echo $ip1|awk -F "." '{print $'$i'}'`
		a2=`echo $ip2|awk -F "." '{print $'$i'}'`
		b=`echo $ne|awk -F "." '{print $'$i'}'`
		gw1=`echo $(( $a1 & $b))`
		gw2=`echo $(( $a2 & $b))`
		if [ $gw1 -ne $gw2 ];then
		    return 1
		fi
        let "i+=1"
   done
   return 0   
}

function constitute_bin
{
    local bin_num1=`echo ${#hci_bin}`
	local bin_num2=`echo ${#dhcp_bin}`
	local i=8
	local j=8
	while [ $i -gt $bin_num1 ]
	do
		hci_bin="0""$hci_bin"
		let "i-=1"
	done
	while [ $j -gt $bin_num2 ]
	do
		dhcp_bin="0""$dhcp_bin"
		let "j-=1"
	done
}

function constitute_ip
{
    local hci_ip=$1
	local dhcp_ip=$2
	local num=`echo $config_answer|awk -F '/' '{print $2}'`
	local hci_str1=`echo $hci_ip|awk -F '.' '{print $1}'`
	local hci_str2=`echo $hci_ip|awk -F '.' '{print $2}'`
	local hci_str3=`echo $hci_ip|awk -F '.' '{print $3}'`
	local hci_str4=`echo $hci_ip|awk -F '.' '{print $4}'`
	local dhcp_str1=`echo $dhcp_ip|awk -F '.' '{print $1}'`
	local dhcp_str2=`echo $dhcp_ip|awk -F '.' '{print $2}'`
	local dhcp_str3=`echo $dhcp_ip|awk -F '.' '{print $3}'`
	local dhcp_str4=`echo $dhcp_ip|awk -F '.' '{print $4}'`
	local hci_num1=`expr $num / 8`
	local hci_num2=`expr $num % 8`
	local split_num=`expr 1 + $hci_num1`
	hci_bin=""
	dhcp_bin=""
	local bin=""
	local ten=""
	if [ $split_num -eq 1 ];then
	    hci_bin=`echo "obase=2;$hci_str1"|bc`
		dhcp_bin=`echo "obase=2;$dhcp_str1"|bc`
		constitute_bin
		hci_bin=`echo ${hci_bin:0:$hci_num2}`
		dhcp_bin=`echo ${dhcp_bin:$hci_num2:8}`
		bin="$hci_bin""$dhcp_bin"
		((ten=2#$bin))
		ipadd="$ten.""$dhcp_str2.""$dhcp_str3.""$dhcp_str4"
	elif [ $split_num -eq 2 ];then
		hci_bin=`echo "obase=2;$hci_str2"|bc`
		dhcp_bin=`echo "obase=2;$dhcp_str2"|bc`
		constitute_bin
		hci_bin=`echo ${hci_bin:0:$hci_num2}`
		dhcp_bin=`echo ${dhcp_bin:$hci_num2:8}`
		bin="$hci_bin""$dhcp_bin"
		((ten=2#$bin))
		ipadd="$hci_str1.""$ten.""$dhcp_str3.""$dhcp_str4"
	elif [ $split_num -eq 3 ];then
		hci_bin=`echo "obase=2;$hci_str3"|bc`
		dhcp_bin=`echo "obase=2;$dhcp_str3"|bc`
		constitute_bin
		hci_bin=`echo ${hci_bin:0:$hci_num2}`
		dhcp_bin=`echo ${dhcp_bin:$hci_num2:8}`
		bin="$hci_bin""$dhcp_bin"
		((ten=2#$bin))
		ipadd="$hci_str1.""$hci_str2.""$ten.""$dhcp_str4"
	elif [ $split_num -eq 4 ];then
		hci_bin=`echo "obase=2;$hci_str4"|bc`
		dhcp_bin=`echo "obase=2;$dhcp_str4"|bc`
		constitute_bin
		hci_bin=`echo ${hci_bin:0:$hci_num2}`
		dhcp_bin=`echo ${dhcp_bin:$hci_num2:8}`
		bin="$hci_bin""$dhcp_bin"
		((ten=2#$bin))
		ipadd="$hci_str1.""$hci_str2.""$hci_str3.""$ten"
	fi
	
}

function vlan_eth_create
{
    local CUSTOM_CFG_FILE=$1
    local vlan_eth_name=""
	local vlan_id=""
	local gw=""
	local mode=""
	netma=""
	ipadd=""
	local num=""
	local i=1
	get_config $CUSTOM_CFG_FILE "install_mode"
	mode=$config_answer
	get_config $CUSTOM_CFG_FILE "install_type"
	typ=$config_answer
	get_config $CUSTOM_CFG_FILE "manage_bond_gateway"
	gw=$config_answer
	get_config $CUSTOM_CFG_FILE "manage_eth_vlan_num"
	num=$config_answer
	while [ $i -le $num ]
	do
		get_config $CUSTOM_CFG_FILE "eth_vlan_ip$i"
		ipadd=`echo $config_answer|awk -F '/' '{print $1}'`
		if [ $mode = "compute" -o $typ = "pxe" ];then
			#ipadd=`echo ${ipadd%.*}`"."`echo ${ipaddr##*.} `
			constitute_ip $ipadd $ipaddr
		fi
		get_netmask 
		get_config $CUSTOM_CFG_FILE "eth_vlan_id$i"
		vlan_id=$config_answer
		vlan_eth_name="$linux_bond.$vlan_id"
#		ip link add link $linux_bond name $vlan_eth_name type vlan id $vlan_id
#		ifconfig $vlan_eth_name $ipadd
		touch /etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
		echo "DEVICE=$vlan_eth_name" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
		echo "BOOTPROTO=static" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
		echo "ONBOOT=yes" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
		echo "IPADDR=$ipadd" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
		echo "NETMASK=$netma" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
		echo "VLAN=yes" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
		get_gateway $ipadd $gw $netma
		if [ $? -eq 0 ];then
		    echo "GATEWAY=$gw" >>/etc/sysconfig/network-scripts/ifcfg-$vlan_eth_name
		fi
#		sed '$a\ip link add link '$linux_bond' name '$vlan_eth_name' type vlan id '$vlan_id'' -i /etc/rc.local 
#		sed '$a\ifup '$vlan_eth_name'' -i /etc/rc.local
		let "i+=1"
    done	
}


function get_ip_eth
{
    ipaddr=`cat /etc/sysconfig/network-scripts/ifcfg-$bond_eth1 | grep "^[[:space:]]*[^#]"|grep IPADDR |awk -F '=' '{print $2}'|tr -d '"'`
	netmask=`cat /etc/sysconfig/network-scripts/ifcfg-$bond_eth1 |grep "^[[:space:]]*[^#]"|grep NETMASK |awk -F '=' '{print $2}'|tr -d '"'`
	#网卡配置文件里面读不到IP ，可能是DHCP方式获取，ifconfig获取
	if [[ -z $ipaddr ]]; then
		ipaddr=`ifconfig $bond_eth1 |grep 'inet addr' | awk '{print $2}'`
	    ipaddr=`echo $ipaddr | awk -F ':' '{print $2}'`
	fi
  
    if [[ -z $ipaddr ]]; then
		 ipaddr=`ifconfig $bond_eth1 |grep 'inet ' | awk '{print $2}'`	  
	fi
	
	if [[ -z $netmask ]]; then
		netmask=`ifconfig $bond_eth1 |grep 'Mask' | awk '{print $4}'`
		netmask=`echo $netmask | awk -F ':' '{print $2}'`
	fi
		
	if [[ -z $netmask ]]; then
		netmask=`ifconfig $bond_eth1 |grep 'netmask' | awk '{print $4}'`
	fi
	
	if [[ -z $ipaddr ]]; then
		ipaddr=`cat /etc/sysconfig/network-scripts/ifcfg-$bond_eth2 | grep "^[[:space:]]*[^#]"|grep IPADDR |awk -F '=' '{print $2}'|tr -d '"'`
		netmask=`cat /etc/sysconfig/network-scripts/ifcfg-$bond_eth2 |grep "^[[:space:]]*[^#]"|grep NETMASK |awk -F '=' '{print $2}'|tr -d '"'`
	fi
	
	if [[ -z $ipaddr ]]; then
		ipaddr=`ifconfig $bond_eth2 |grep 'inet addr' | awk '{print $2}'`
	    ipaddr=`echo $ipaddr | awk -F ':' '{print $2}'`
	fi
  
    if [[ -z $ipaddr ]]; then
		 ipaddr=`ifconfig $bond_eth2 |grep 'inet ' | awk '{print $2}'`	  
	fi
	
	if [[ -z $netmask ]]; then
		netmask=`ifconfig $bond_eth2 |grep 'Mask' | awk '{print $4}'`
		netmask=`echo $netmask | awk -F ':' '{print $2}'`
	fi
		
	if [[ -z $netmask ]]; then
		netmask=`ifconfig $bond_eth2 |grep 'netmask' | awk '{print $4}'`
	fi
	gateway=`route |grep default |awk  '{print $2}'`
}


function eth_update
{
    local str=`find /etc/sysconfig/network-scripts/ -name "ifcfg-*"`
    local eth=""
	local i=1	
	local key_num=""
	local eth_name=""
    while true
	do
	    eth=`echo $str|awk '{print $'$i'}'`
		key_num=`cat $eth |sed '/^[[:space:]]*#/d' |sed -n "1,/\[]/p" |grep -w "DEVICE[[:space:]]*" |grep -c "DEVICE[[:space:]]*="`
		if [ $key_num -eq 0 ];then
		    eth_name=`echo $eth |awk -F - '{print $3}'`
		    sed  '$i\DEVICE='$eth_name'' -i  $eth
		fi
		sed -i "/BOOTPROTO/s/dhcp/static/" $eth
        sed -i "/ONBOOT/s/no/yes/"	$eth        
        if [ $eth = `echo $str|awk '{print $NF}'` ];then
            break;
		fi
		let "i+=1" 
	done
}



function make_linux_bond
{
    local CUSTOM_CFG_FILE=$1
	get_config $CUSTOM_CFG_FILE "manage_bond_name"
	linux_bond=$config_answer
    eth_update	
#	ip link add $linux_bond type bond
    ifdown $bond_eth1
	ifdown $bond_eth2
	touch /etc/sysconfig/network-scripts/ifcfg-$linux_bond
	echo "DEVICE=$linux_bond" >>/etc/sysconfig/network-scripts/ifcfg-$linux_bond
	echo "BOOTPROTO=static" >>/etc/sysconfig/network-scripts/ifcfg-$linux_bond
	echo "ONBOOT=yes" >>/etc/sysconfig/network-scripts/ifcfg-$linux_bond
	echo "BONDING_OPTS=\"mode=1 miimon=100\"" >>/etc/sysconfig/network-scripts/ifcfg-$linux_bond
#	echo "IPADDR=$ipaddr" >>/etc/sysconfig/network-scripts/ifcfg-$linux_bond
#	echo "NETMASK=$netmask" >>/etc/sysconfig/network-scripts/ifcfg-$linux_bond
#	echo "GATEWAY=$gateway" >>/etc/sysconfig/network-scripts/ifcfg-$linux_bond
	sed '$a\MASTER='$linux_bond'' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
	sed '$a\SLAVE=yes' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
	sed -i "/BOOTPROTO/s/static/none/"  /etc/sysconfig/network-scripts/ifcfg-$bond_eth1
	sed '$a\MASTER='$linux_bond'' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
	sed '$a\SLAVE=yes' -i /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
	sed -i "/BOOTPROTO/s/static/none/"  /etc/sysconfig/network-scripts/ifcfg-$bond_eth2
#	route add default gw $gateway dev $linux_bond
	if [  -f "/etc/modprobe.d/bonding.conf" ];then
	    touch /etc/modprobe.d/bonding.conf
	fi
	echo "alias $linux_bond bonding"  >>/etc/modprobe.d/bonding.conf
	echo "options $linux_bond miimon=100 mode=1" >> /etc/modprobe.d/bonding.conf
	modprobe bonding
	echo "modprobe bonding"  >>/etc/rc.local
	ifup $bond_eth1
	ifup $bond_eth2
	ifdown $linux_bond
	ifup $linux_bond
	vlan_eth_create  $CUSTOM_CFG_FILE
	systemctl restart network

	
}

function do_install
{
    ipaddr=""
    netmask=""
    gateway=""
	local CUSTOM_CFG_FILE="../custom.conf"
	config_answer=""
	get_config $CUSTOM_CFG_FILE "manage_port_is_using_bonding"
	if [ $config_answer = "yes" ];then
	    get_config $CUSTOM_CFG_FILE "manage_port_uplink_port"
		config_answer=${config_answer//,/ }
		bond_eth1=`echo $config_answer |awk '{print $1}'`
		bond_eth2=`echo $config_answer |awk '{print $2}'`
		get_config $CUSTOM_CFG_FILE "install_type"
		if [ $config_answer = "usb" ];then
		    dhclient $bond_eth1
			sleep 10
		fi
		get_ip_eth
		make_linux_bond $CUSTOM_CFG_FILE
		sleep 30
	fi

}

do_install
	
  _CREATE_MANAGER_PORT_FILE="create_manager_port_bond.sh"
fi
