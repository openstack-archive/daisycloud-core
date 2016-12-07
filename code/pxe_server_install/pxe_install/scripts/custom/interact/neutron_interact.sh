#! /bin/bash

###################################################################################
#  询问与安装系统（OS/OPENCOS）相关的配置参数
#  入口：interact_setup
#
###################################################################################


#设置是否需要做控制面bond
function ask_manage_bond
{
    local CUSTOM_CFG_FILE=$1
    local install_type=$2
    echo ""
    echo -e ">>client machine manage port use bonding ,yes or no[default no]: \c"
    read parm

    [[ ! -z `echo $parm |grep -iwE "y|yes"` ]] && parm=yes
    [[ ! -z `echo $parm |grep -iwE "n|no"` ]] && parm=no	
	
	case $parm in
		"yes")
            set_config $CUSTOM_CFG_FILE "manage_port_is_using_bonding" "yes"
            ask_manage_bond_port_name $CUSTOM_CFG_FILE $install_type
            echo
			;;
		"no")
			set_config $CUSTOM_CFG_FILE "manage_port_is_using_bonding" "no"
			echo
			;;
		"")
			set_config $CUSTOM_CFG_FILE "manage_port_is_using_bonding" "no"
			echo
			;;
		*)
			echo "Please input yes or no"
			ask_manage_bond $CUSTOM_CFG_FILE
			;;		
	esac	   
}



#确定哪些网口需要bond处理
 function ask_manage_bond_port_name
{
    local CUSTOM_CFG_FILE=$1
	local install_type=`cat $2|grep install_type|awk -F '=' '{print $2}'`
	set_config $CUSTOM_CFG_FILE "install_type" "$install_type"
	num=""
	local net=""
    local bond_uplink_port=""
	if [ $install_type = "pxe" ];then
		get_netmask_num $2
	fi
	echo ""
	echo -e ">>Which type of node would you install,control or compute [default:compute]:\c"
	read parm5
	while true
	do
		if [[ -z $parm5 ]];then
			parm5="compute"
			break
		elif [ $parm5 = "control" -o $parm5 = "compute" ];then
		    break
		else
		    echo ""
			echo -e ">>The input is not legitimate,please re-enter [default:compute]:\c"
			read parm5
		fi
		
	done
	set_config $CUSTOM_CFG_FILE "install_mode" "$parm5"
	
    echo ""
    echo "Manage port using bonding need to set uplink nic name. More than one nic name,separated by commas."
	echo -e ">>Enter client host bonding uplink nic name[default:eth0,eth1]: \c"
    read parm
	if [[ -z $parm ]];then
		bond_uplink_port="eth0,eth1"
	else
		bond_uplink_port=$parm
	fi
	bond_eth[99]=`echo $parm|awk -F , '{print $1}'`
	bond_eth[100]=`echo $parm|awk -F , '{print $2}'`
    set_config $CUSTOM_CFG_FILE "manage_port_uplink_port" "$bond_uplink_port"
    set_config $CUSTOM_CFG_FILE "manage_port_bond_mode" "active-backup"
    set_config $CUSTOM_CFG_FILE "manage_port_dhcp_enable" "disable"
	echo ""
	echo -e ">>Enter the vlan subinterface1 ip [default: 192.168.1.0/24]: \c"
	read parm1
	if [[ -z $parm1 ]];then
	    parm1="192.168.1.X/24"
	fi
	net=`echo $parm1|awk -F '/' '{print $2}'`
	if [ $install_type = "usb" ];then
		num=$net
	fi
	while true
	do 
	   if [ $net ];then
			expr $net "+" 10 &> /dev/null
			if [ $? -eq 0 ];then
				if [ $net -eq $num ];then
					break
				else
					echo "The netmask does not belong to the initialization of dhcp server "
				fi
			else
				echo "The input is wrong"
				
			fi
	   else
			echo "The input can not be empty"
	   fi
	   echo -e ">>Please input the correct ip: \c"
	   read parm1
	   net=`echo $parm1|awk -F '/' '{print $2}'`
	   if [ $install_type = "usb" ];then
			num=$net
		fi
	done
	set_config $CUSTOM_CFG_FILE "eth_vlan_ip1" "$parm1"
	echo ""
	echo -e ">>Enter the vlan_id of the vlan subinterface1 : \c"
	read parm2
	set_config $CUSTOM_CFG_FILE "eth_vlan_id1" "$parm2"
	
	echo ""
	echo -e ">>Enter the vlan subinterface2 ip [default: 192.169.1.0/24]: \c"
	read parm1
	if [[ -z $parm1 ]];then
	    parm1="192.169.1.X/24"
	fi
	net=`echo $parm1|awk -F '/' '{print $2}'`
	if [ $install_type = "usb" ];then
		num=$net
	fi
	while true
	do 
	   if [ $net ];then
			expr $net "+" 10 &> /dev/null
			if [ $? -eq 0 ];then
				if [ $net -eq $num ];then
					break
				else
					echo "The netmask does not belong to the initialization of dhcp server "
				fi
			else
				echo "The input is wrong"
				
			fi
	   else
			echo "The input can not be empty"
	   fi
	   echo -e ">>Please input the correct ip: \c"
	   read parm1
	   net=`echo $parm1|awk -F '/' '{print $2}'`
	   if [ $install_type = "usb" ];then
			num=$net
		fi
	done
	set_config $CUSTOM_CFG_FILE "eth_vlan_ip2" "$parm1"
	echo ""
	echo -e ">>Enter the vlan_id of the vlan subinterface2 : \c"
	read parm2
	set_config $CUSTOM_CFG_FILE "eth_vlan_id2" "$parm2"
	echo ""
	echo "Would you like to make more vlan subinterface"
	echo -e ">>Please input an number[default:0]: \c"
	read parm3
	if [[ -z $parm3 ]];then
	    parm3=0
	fi
	let "parm3+=2"
	set_config $CUSTOM_CFG_FILE "manage_eth_vlan_num" "$parm3"
	local i=3
	while [ $i -le $parm3 ]
	do
	    echo "[eth_vlan$i]" >> $CUSTOM_CFG_FILE
		echo ""
		echo -e ">>Enter the vlan subinterface$i ip [example: 192.169.1.0/24]: \c"
		read parm1
		net=`echo $parm1|awk -F '/' '{print $2}'`
		if [ $install_type = "usb" ];then
			num=$net
		fi
		while true
		do 
		   if [ $net ];then
				expr $net "+" 10 &> /dev/null
				if [ $? -eq 0 ];then
					if [ $net -eq $num ];then
						break
					else
						echo "The netmask does not belong to the initialization of dhcp server "
					fi
				else
					echo "The input is wrong"
					
				fi
		   else
				echo "The input can not be empty"
		   fi
		   echo -e ">>Please input the correct ip: \c"
		   read parm1
		   net=`echo $parm1|awk -F '/' '{print $2}'`
		   if [ $install_type = "usb" ];then
				num=$net
			fi
		done
		set_config $CUSTOM_CFG_FILE "eth_vlan_ip$i" "$parm1"
		echo ""
		echo -e ">>Enter the vlan_id of the vlan subinterface$i : \c"
		read parm2
		set_config $CUSTOM_CFG_FILE "eth_vlan_id$i" "$parm2"
		let "i+=1"
	done
	
	echo ""
	echo -e ">>Which vlan subinterface would you like to choose as gateway ,please input the gateway :\c"
	read parm4
	set_config $CUSTOM_CFG_FILE "manage_bond_gateway" "$parm4"
	
}
function get_netmask_num
{
	local str=`cat $1 | grep "^[[:space:]]*[^#]"|grep net_mask_l |awk -F '=' '{print $2}'|tr -d '"'`
	local i=4
	local number=""
	while [ $i -gt 0 ]
	do
	    number=`echo $str|awk  -F '.' '{print $'$i'}'`
		if [ $number -eq 255 ];then
		    let "num+=8"
		elif [ $number -eq 0 ];then
		    let "num+=0"
		elif [ $number -eq 254 ];then
		    let "num+=7"
		elif [ $number -eq 252 ];then
		    let "num+=6"
		elif [ $number -eq 248 ];then
		    let "num+=5"
		elif [ $number -eq 240 ];then
		    let "num+=4"
		elif [ $number -eq 224 ];then
		    let "num+=3"
		elif [ $number -eq 192 ];then
		    let "num+=2"
		elif [ $number -eq 128 ];then
		    let "num+=1"
		fi
		let "i-=1"
	done	
#	echo $num
}

#选择虚拟化实现机制ovs or sriov
function ask_virtualization_mechanism
{
    local CUSTOM_CFG_FILE=$1
 #   echo ""
 #   echo -e ">>which virtualized mechanism would you like,ovs or sriov [default ovs]: \c"
 #  read parm
 #   case $parm in
 #      "ovs")
#		    set_config $CUSTOM_CFG_FILE "virtualization_mechanism" "ovs"
#            ask_data_bond $CUSTOM_CFG_FILE
#            echo
#			;;
#        "sriov")
#			set_config $CUSTOM_CFG_FILE "virtualization_mechanism" "sriov"
#			ask_data_bond $CUSTOM_CFG_FILE
#			echo
#			;;
#		"")
#			set_config $CUSTOM_CFG_FILE "virtualization_mechanism" "ovs"
			ask_data_bond $CUSTOM_CFG_FILE
#			echo
#			;;
#		*)
#			echo "Please input ovs or sriov"
#			ask_virtualization_mechanism $CUSTOM_CFG_FILE
#			;;		
#	esac	   			
}
#设置是否需要做数据面bond
function ask_data_bond
{
    local CUSTOM_CFG_FILE=$1
	eth=""
	bond_eth[97]="XXXXXX"
	num=0
	phy=0
  #  echo ""
    echo -e ">>Client machine data port use bonding ,yes or no[default no]: \c"
    read parm

    [[ ! -z `echo $parm |grep -iwE "y|yes"` ]] && parm=yes
    [[ ! -z `echo $parm |grep -iwE "n|no"` ]] && parm=no	
	
	case $parm in
		"yes")
            set_config $CUSTOM_CFG_FILE "data_port_is_using_bonding" "yes"
            ask_ovs_bond_port_name $CUSTOM_CFG_FILE
			ask_sriov_bond_port_name $CUSTOM_CFG_FILE
            echo
			;;
		"no")
			set_config $CUSTOM_CFG_FILE "data_port_is_using_bonding" "no"
			ask_data_config $CUSTOM_CFG_FILE
			echo
			;;
		"")
			set_config $CUSTOM_CFG_FILE "data_port_is_using_bonding" "no"
			ask_data_config $CUSTOM_CFG_FILE
			echo
			;;
		*)
			echo "Please input yes or no"
			ask_data_bond $CUSTOM_CFG_FILE
			;;		
	esac	   
}

function bond_eth_check
{
    local i=""
    local mark=0   
    eth=$1
	while true
	do
		#while [ ! -f "/etc/sysconfig/network-scripts/ifcfg-$eth" ]
		#do
			#echo -e ">>the network card which name is $eth is not exist ,please input a new one: \c"
			#read eth
		#done
		#echo "OK"
		for i in ${bond_eth[@]}
		do   
		    #echo "i $i" 
			if [ $i = $eth ];then
				echo -e ">>The network card which name is $eth is Inused ,please input a new one: \c"
				read eth
				mark=0
				break
			fi
			mark=1
		done
		if [ $mark -eq 1 ];then
			mark=0
			break
		fi					
	done
}
#确定哪些网口需要ovs_bond处理
function ask_ovs_bond_port_name
{
    local CUSTOM_CFG_FILE=$1
	local i=1
	ovs_first=""
    ovs_second=""
	echo ""
	echo -e ">>Please input the number of the ovs_bond which you wan to make [default:1]: \c"
	read bond_num
	if [[ -z $bond_num ]]; then 
	     bond_num=1
	fi
	expr $bond_num "+" 10 &> /dev/null
	while [ $? -ne 0 ]
	do 
	   echo ""
	   echo -e ">>Please input an number[default:1]: \c"
	   read bond_num
	   if [[ -z $bond_num ]];then
	       bond_num=1
		fi
	   expr $bond_num "+" 10 &> /dev/null
	done
	set_config $CUSTOM_CFG_FILE "ovs-port-bond_num" "$bond_num"
	num=$bond_num
	phy=$bond_num
	while [ $i -le $bond_num ]
	do
	   if [ $bond_num -eq 1 ];then
	        echo ""
			echo "Data port using bonding need to set uplink nic name. More than one nic name,separated by commas."
			echo -e ">>Enter client host bonding uplink nic name with bond1 [default:eth0,eth1]: \c"
			read parm1
			if [[ -z $parm1 ]];then
			    parm1="eth0,eth1"
			fi
			ovs_first=`echo $parm1|awk -F , '{print $1}'`
            bond_eth_check $ovs_first
			ovs_first=$eth
			bond_eth[i*2-1]=$ovs_first
			ovs_second=`echo $parm1|awk -F , '{print $2}'`
			bond_eth_check $ovs_second
			ovs_second=$eth
			parm1="$ovs_first,$ovs_second"
			bond_ovs[i*2-1]=$parm1	
            bond_ovs[i*2]="$ovs_second,$ovs_first"			
			bond_eth[i*2]=$ovs_second
			set_config $CUSTOM_CFG_FILE "ovs_port_uplink_port1" "$parm1"
			while true; do
                bond_mode="0"
                echo "Please select bond mode:"
                echo "  0  --  backup"
                echo "  1  --  on"
                echo "  2  --  lacp"
                echo -e "input bond mode:\c"
				read bond_mode
                if ( [ "$bond_mode" = "0" ] || [ "$bond_mode" = "1" ] || [ "$bond_mode" = "2" ] ); then
                    break
                fi
            done
			ovs_bond_mode[i]=$bond_mode
			set_config $CUSTOM_CFG_FILE "ovs_port_bond_mode$i" "$bond_mode"
			echo ""
			echo -e ">>Set the number of mtu_mappings[default:1520]: \c"
			read parm2
			if [[ -z $parm2 ]];then
			    parm2=1520
			fi
			set_config $CUSTOM_CFG_FILE "ovs_mtu_mappings$i" "$parm2"
			set_config $CUSTOM_CFG_FILE "ovs_phynet_name$i" "physnet$i"
			set_config $CUSTOM_CFG_FILE "ovs_bridge_name$i" "br-bond$i"
			set_config $CUSTOM_CFG_FILE "ovs_bond_name$i" "bond$i"
		else
		    if [ $i -ge 4 ];then
			    echo "[ovs-port-bond$i]" >> $CUSTOM_CFG_FILE
			fi
			echo ""
			echo "Data port using bonding need to set uplink nic name. More than one nic name,separated by commas."
			echo -e ">>Enter client host bonding uplink nic name with bond$i,the input can not be empty: \c"
			read parm1
            ovs_first=`echo $parm1|awk -F , '{print $1}'`
			bond_eth_check $ovs_first
			ovs_first=$eth
			bond_eth[i*2-1]=$ovs_first
			ovs_second=`echo $parm1|awk -F , '{print $2}'`
			bond_eth_check $ovs_second
			ovs_second=$eth
			parm1="$ovs_first,$ovs_second"
			bond_ovs[i*2-1]=$parm1	
            bond_ovs[i*2]="$ovs_second,$ovs_first"	
			bond_eth[i*2]=$ovs_second			
			set_config $CUSTOM_CFG_FILE "ovs_port_uplink_port$i" "$parm1"
			while true; do
				echo "Please select bond mode:"
				echo "  0  --  backup"
				echo "  1  --  on"
				echo "  2  --  lacp"
				echo -e "Input bond mode:\c"
				read bond_mode
				if ( [ "$bond_mode" = "0" ] || [ "$bond_mode" = "1" ] || [ "$bond_mode" = "2" ] ); then
					break
				fi
			done
			ovs_bond_mode[i]=$bond_mode
			set_config $CUSTOM_CFG_FILE "ovs_port_bond_mode$i" "$bond_mode"
			echo ""
			echo -e ">>set the number of mtu_mappings: \c"
			read parm2
			set_config $CUSTOM_CFG_FILE "ovs_mtu_mappings$i" "$parm2" 
			set_config $CUSTOM_CFG_FILE "ovs_phynet_name$i" "physnet$i"
			set_config $CUSTOM_CFG_FILE "ovs_bridge_name$i" "br-bond$i"
			set_config $CUSTOM_CFG_FILE "ovs_bond_name$i" "bond$i"
		fi
		let "i+=1"
	done
}
function sriov_check_with_ovs
{
    local i=""
	local j=1
	for i in ${bond_ovs[@]}
	do
    	let "j+=1"
		if [ $i = $parm ];then
		    if [ ${ovs_bond_mode[j/2]} = $sriov_mode ];then
			    mark=1
				flag=1
				flag_num=`expr $j / 2`
				break
			else
			    echo "This bond has been made in ovs , but the bond_mode is not same ,please try again"
				echo "Data port using bonding need to set uplink nic name. More than one nic name,separated by commas."
				echo -e ">>Enter client host bonding uplink nic name with bond,the input can not be empty: \c"
				read parm			
				while true; do
					echo "Please select bond mode:"
					echo "  0  --  backup"
					echo "  1  --  on"
					echo "  2  --  lacp"
					echo -e "Input bond mode:\c"
					read mode
					if ( [ "$mode" = "0" ] || [ "$mode" = "1" ] || [ "$mode" = "2" ] ); then
						break
					fi
				done
				sriov_mode=$mode
				sriov_check_with_ovs
				break
			fi
		fi
	done
}
function sriov_check_bond
{
    mark=0
	local j=0
	local n=0
	parm=$1
	sriov_mode=$2
	sriov_check_with_ovs
	if [ $mark -eq 1 ];then
	    mark=0
		sriov_first=`echo $parm|awk -F , '{print $1}'`
		sriov_second=`echo $parm|awk -F , '{print $2}'`
	else
		sriov_first=`echo $parm|awk -F , '{print $1}'`
		sriov_second=`echo $parm|awk -F , '{print $2}'`
		bond_eth_check $sriov_first
		sriov_first=$eth
		bond_eth[num*2-1]=$sriov_first
		bond_eth_check $sriov_second
		sriov_second=$eth
		bond_eth[num*2]=$sriov_second
		let "num+=1"
	fi
}

#确定哪些网口需要sriov_bond处理
function ask_sriov_bond_port_name
{
    flag=0
	flag_num=0
    local CUSTOM_CFG_FILE=$1
	local i=1
	sriov_first=""
	sriov_second=""
	sriov_mode=""
	let "phy+=1"
	let "num+=1"
	echo ""
	echo -e ">>Please input the number of the sriov_bond which you wan to make [default:1]: \c"
	read bond_num
	if [[ -z $bond_num ]] ;then 
	     bond_num=1
	fi
	expr $bond_num "+" 10 &> /dev/null
	while [ $? -ne 0 ]
	do 
	   echo ""
	   echo -e ">>Please input an number[default:1]: \c"
	   read bond_num
	   if [[ -z $bond_num ]];then
	       bond_num=1
		fi
	   expr $bond_num "+" 10 &> /dev/null
	done
	set_config $CUSTOM_CFG_FILE "sriov-port-bond_num" "$bond_num"
	while [ $i -le $bond_num ]
	do
	   if [ $bond_num -eq 1 ];then
	        echo ""
			echo "Data port using bonding need to set uplink nic name. More than one nic name,separated by commas."
			echo -e ">>Enter client host bonding uplink nic name with bond1 [default:eth0,eth1]: \c"
			read parm1
			if [[ -z $parm1 ]];then
			    parm1="eth0,eth1"
			fi
			while true; do
                echo "Please select bond mode:"
                echo "  0  --  backup"
                echo "  1  --  on"
                echo "  2  --  lacp"
                echo  -e "Input bond mode:\c"
				read bond_mode
                if ( [ "$bond_mode" = "0" ] || [ "$bond_mode" = "1" ] || [ "$bond_mode" = "2" ] ); then
                    break
                fi
            done
			sriov_check_bond $parm1 $bond_mode
			if [ $flag -eq 1 ];then
			    set_config $CUSTOM_CFG_FILE "sriov_phynet_name$i" "physnet$flag_num"
			    set_config $CUSTOM_CFG_FILE "sriov_bridge_name$i" "br-bond$flag_num"
			    set_config $CUSTOM_CFG_FILE "sriov_bond_name$i" "bond$flag_num"
				flag=0
				flag_num=0
			else
				set_config $CUSTOM_CFG_FILE "sriov_phynet_name$i" "physnet$phy"
				set_config $CUSTOM_CFG_FILE "sriov_bridge_name$i" "br-bond$phy"
				set_config $CUSTOM_CFG_FILE "sriov_bond_name$i" "bond$phy"
			fi
			set_config $CUSTOM_CFG_FILE "sriov_port_uplink_port$i" "$sriov_first,$sriov_second"
			set_config $CUSTOM_CFG_FILE "sriov_port_bond_mode$i" "$sriov_mode"
			
			echo ""
			echo -e ">>Set the number of mtu_mappings[default:1520]: \c"
			read parm2
			if [[ -z $parm2 ]];then
			    parm2=1520
			fi
			set_config $CUSTOM_CFG_FILE "sriov_mtu_mappings1" "$parm2"
			
			
		else
		    if [ $i -ge 4 ];then
			    echo "[sriov-port-bond$i]" >> $CUSTOM_CFG_FILE
			fi
		    echo ""
			echo "Data port using bonding need to set uplink nic name. More than one nic name,separated by commas."
			echo -e ">>Enter client host bonding uplink nic name with bond$i,the input can not be empty: \c"
			read parm1			
			while true; do
                echo "Please select bond mode:"
                echo "  0  --  backup"
                echo "  1  --  on"
                echo "  2  --  lacp"
                echo -e "Input bond mode:\c"
				read bond_mode
                if ( [ "$bond_mode" = "0" ] || [ "$bond_mode" = "1" ] || [ "$bond_mode" = "2" ] ); then
                    break
                fi
            done
			sriov_check_bond $parm1 $bond_mode
			if [ $flag -eq 1 ];then
			    set_config $CUSTOM_CFG_FILE "sriov_phynet_name$i" "physnet$flag_num"
			    set_config $CUSTOM_CFG_FILE "sriov_bridge_name$i" "br-bond$flag_num"
			    set_config $CUSTOM_CFG_FILE "sriov_bond_name$i" "bond$flag_num"
				flag=0
				flag_num=0
			else
				set_config $CUSTOM_CFG_FILE "sriov_phynet_name$i" "physnet$phy"
				set_config $CUSTOM_CFG_FILE "sriov_bridge_name$i" "br-bond$phy"
				set_config $CUSTOM_CFG_FILE "sriov_bond_name$i" "bond$phy"
			fi
			set_config $CUSTOM_CFG_FILE "sriov_port_uplink_port$i" "$sriov_first,$sriov_second"
			set_config $CUSTOM_CFG_FILE "sriov_port_bond_mode$i" "$sriov_mode"
			echo ""
			echo -e ">>Set the number of mtu_mappings: \c"
			read parm2
			set_config $CUSTOM_CFG_FILE "sriov_mtu_mappings$i" "$parm2"
		fi
		let "i+=1"
		let "phy+=1"
	done
}

#不做bond处理需要配置的物理口
function ask_data_config
{
    local CUSTOM_CFG_FILE=$1
	local phynic_port
	local pci_net_phy
	echo ""
    echo -e ">>Please input  bridge interface.The interface will be added to the associated bridge.It must be different from Private interface and Public interface. (default: er0): \c"
    read parm1
	if [[ -z $parm1 ]];then
		phynic_port="er0"
	else
		phynic_port=$parm1
	fi
	set_config $CUSTOM_CFG_FILE "data_port_phynic" "$phynic_port"
}

