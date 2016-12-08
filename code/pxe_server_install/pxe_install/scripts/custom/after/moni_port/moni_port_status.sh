#!/bin/bash

logfile="/var/log/monitor_port"
sriov_conf=/etc/sriov.conf
sriov_agent_conf=/etc/neutron/plugins/sriovnicagent/sriov_nic_plugin.ini
sriov_chang_vf_status=/home/opencos_install/custom/after/moni_port/nic_update

function do_logfile
{
    rm -rf $logfile
	touch $logfile
	echo "##this is monitor port logfile" >>$logfile
}

#记录日志
function do_log
{
    local logstr=$1
    LANG=en_US.ISO8859-1
    echo -n `date '+%b %d %T'` >> $logfile
    echo " $logstr" >>$logfile
}

vm_ids=""

function monitor_port
{
    check_sriov_config
    ret=`echo $?`
    do_log "check_sriov_config $ret"
    if [ $ret -ne 0 ] ; then
        #check_sriov_bond
        #ret=`echo $?`
	    #do_log "check_sriov_bond $ret"
	    #if [ $ret -ne 0 ] ; then
            #do_log "sriov_bond_check"
            #sriov_monitor_port
        #fi 
        do_log "sriov_bond_check"
	sriov_monitor_port
    else
        do_log "macvtap_check"
        macvtap_monitor_port
    fi
}

function check_sriov_config
{
    echo "check sriov config runing"    
    
    check_file_exist $sriov_conf
    [ "$exist" = "no" ] && return 0  

    check_head_str_exist $sriov_conf "sriov_vnic_type = direct"
    [ "$exist" != "" ] && return 1
	
    return 0
}

#目前就只支持主背模式
function check_sriov_bond
{
    do_log "check sriov bond runing"
    
    check_file_exist $sriov_agent_conf
    [ "$exist" = "no" ] && return 0  

    check_str_exist $sriov_agent_conf "active-backup"
    [ "$exist" != "" ] && return 1
	
    return 0
}

function check_head_str_exist
{   
    local file=$1
    local str="$2"

    exist=`cat $file | grep -w "^[[:space:]]*$str"`
}

function check_str_exist
{   
    local file=$1
    local str="$2"

    exist=`cat $file | grep -v "#" | grep $str`
}

#判断文件是否存在
function check_file_exist
{  
    exist="no"
    local file=$1
    if [ -f $file ];then
        exist="yes"
    else
        do_log "$file: file doesn't exist"
    fi
}

function sriov_monitor_port
{
    local phynic_bond_up=""
    local phynic_bond_down=""
    local phynic_bond_down_last=""
    local phynic_bond_up_last=""

    check_file_exist $sriov_agent_conf
    [ "$exist" = "no" ] && return 0 
    chmod +x $sriov_chang_vf_status
    while true
    do
        phynic_bond_up=`ovs-appctl bond/show | grep  -B 2 "active slave" | grep ":" | awk '{print $2}'| sed 's/://g'`
        if [ ! $phynic_bond_up ] ; then
            phynic_bond_down=`ovs-appctl bond/show | grep  "slave " | awk '{print $2}' | sed 's/://g'`
        else
            phynic_bond_down=`ovs-appctl bond/show | grep  "slave " | awk '{print $2}' | sed 's/://g' | grep -v $phynic_bond_up`
        fi
   
        if [[ $phynic_bond_up != $phynic_bond_up_last ]] ; then
            for i in $phynic_bond_up
            do
                do_log "$i:need to up"
                check_sriov_active $i
            done
        fi
        if [[ $phynic_bond_down != $phynic_bond_down_last ]] ; then
            for i in $phynic_bond_down
            do
                do_log "$i: need to down"
                check_sriov_down $i
            done
        fi		
        phynic_bond_down_last=$phynic_bond_down
        phynic_bond_up_last=$phynic_bond_up
        sleep 2
    done
}

function check_sriov_active
{
    local up_port_name=$1
    check_str_exist $sriov_agent_conf $up_port_name
    [ "$exist" = "" ] && return 1
    $sriov_chang_vf_status $up_port_name UP $logfile
}

function check_sriov_down
{
    local down_port_name=$1
    check_str_exist $sriov_agent_conf $down_port_name
    [ "$exist" = "" ] && return 1
    port_stat=`ip link show efr | awk -F"state|mode" '{print $2}'`
    if [ "$port_stat" = "UP" ] ; then
        $sriov_chang_vf_status $down_port_name DOWN $logfile
    fi
}

function macvtap_monitor_port
{
    local macvtap_port_source=""
    local macvtap_port_name=""
    while true
    do
        do_logfile
        vm_ids=`virsh list | sed -e '/^$/d' -e '/^#/d' | sed '1,2d' | awk '{print $1}' |tr '\n' ' '`
        do_log "vm_ids: $vm_ids"
        for var in $vm_ids
        do
            do_log "Vm instance id:$var"
            vm_macvtap_ports=`virsh domiflist $var | sed '1,2d' | awk '{print $1":"$3}' | grep "macvtap" |tr '\n' ' '`
    
            for vm_macvtap_port in $vm_macvtap_ports
            do
                do_log "$vm_macvtap_port"
                macvtap_port_source=`echo "$vm_macvtap_port" | awk -F ':' '{print $2}'`
                macvtap_port_name=`echo "$vm_macvtap_port" | awk -F ':' '{print $1}'`
                update_macvtap_port_status $macvtap_port_source $macvtap_port_name
            done       
        done
    sleep 2
    done
}

function update_macvtap_port_status
{
    local macvtap_port_source=$1
    local macvtap_port_name=$2
    if [ "$macvtap_port_source" != "" ]; then
        macvtap_port_vf_pci=`ethtool -i $macvtap_port_source |grep 'bus-info' | awk '{print $2}'`
        do_log "macvtap_port_vf_pci:$macvtap_port_vf_pci"
    fi
    
    if [ "$macvtap_port_vf_pci" != "" ]; then
        macvtap_port_pf_name=`ls /sys/bus/pci/devices/$macvtap_port_vf_pci/physfn/net/`
        do_log "macvtap_port_pf_name:$macvtap_port_pf_name"
    fi
    
    if [ "$macvtap_port_pf_name" != "" ]; then
        macvtap_port_pf_status=`ethtool $macvtap_port_pf_name | grep 'Link detected' | awk -F ': ' '{print $2}'`
        do_log "macvtap_port_pf_status:$macvtap_port_pf_status"
    fi
    
    if [ "$macvtap_port_pf_status" != "" ]; then
        if [ $macvtap_port_pf_status = "no" ]; then
            virsh domif-setlink $var $macvtap_port_name down
        else
            set_macvtap_port_status $var $macvtap_port_pf_name $macvtap_port_name
        fi
    fi
}

function set_macvtap_port_status
{
    local var=$1
    local pf_name=$2
    local macvtap_port_name=$3
    local type=""
    local bond_name=""
    local state=""
    
    do_log "pf_name: $pf_name"
    type=`ovs-appctl bond/list |sed '1d' |grep $pf_name | awk '{print $2}'`
    bond_name=`ovs-appctl bond/list |sed '1d' |grep $pf_name | awk '{print $1}'`
    if [ "$type" != "" ]; then
        do_log "type: $type"
        if [ "$type" != "active-backup" ]; then
            virsh domif-setlink $var $macvtap_port_name up
        else        
            state=`ovs-appctl bond/show $bond_name |awk "/$pf_name/ {getline; print}" |grep active`
            do_log "state: $state"
            if [ "$state" != "" ]; then
                virsh domif-setlink $var $macvtap_port_name up
            else
                virsh domif-setlink $var $macvtap_port_name down
            fi          
        fi
    else
        virsh domif-setlink $var $macvtap_port_name up
    fi
    do_log `virsh domif-getlink $var $macvtap_port_name`
}

monitor_port



