#!/bin/bash

ISO_MOUNT_DIR_NUM=10
ISO_NFS_TAB=/var/log/iso_nfs_tab.log
PXE_OS_TAB=/var/log/pxe_os_table.log

#######################
# 记录日志到/var/log/pxe_install.log
# $1:要记录的日志
# $2:如果值为console，那么同时又在屏幕上打印此记录
# 这个函数的功能：记录一条检查日志，并在这个日志前面加上记录的时间
#######################
function pxelog
{
    local LOGFILE=/var/log/pxe_install.log
    
    if [ ! -f $LOGFILE ]; then
        touch $LOGFILE
    fi
    #记录日志
    LANG=en_US.ISO8859-1
    echo -n `date '+%b %d %T'` >> $LOGFILE
    echo -e " $1" >> $LOGFILE
    [[ $2 = "console" ]] && echo -e "$1"
    return 0
}

#######################
#从json配置文件读取参数
#######################
function get_config
{
    local file=$1
    local key=$2

    [ ! -e $file ] && { pxelog "file ${file} not exit!!" "console"; return; }
    config_answer=$(jq ".$key" $file | sed "s/\"//g" )
    pxelog "${key}=$config_answer"
    [[ "null" == ${config_answer} ]] && config_answer=""
    #config_answer=$(echo $config_answer | sed "s/\"//g")
    #忽略井号开头的注释行以及空行之后再grep过滤"key"所在的行
    #local line=`sed '/^[[:space:]]*#/d' $file | sed /^[[:space:]]*$/d | grep -w "$key"| grep "$key[[:space:]]*="`
    #if [ -z "$line" ]; then
    #    config_answer=""
    #else
        #将第一个=号替换为空格，再删除第一个单词得到value
    #    config_answer=`echo $line | sed 's/=/ /' | sed -e 's/^\w*\ *//'`
    #fi
    
}

#######################
#设置参数到conf配置文件
#######################
function set_config
{
    local file=$1
    local key=$2
    local value=$3

    [ ! -e $file ] && return

    #echo update key $key to value $value in file $file ...
    local exist=`grep "^[[:space:]]*[^#]" $file | grep -c "$key[[:space:]]*=[[:space:]]*.*"`
    #注意：如果某行是注释，开头第一个字符必须是#号!!!
    local comment=`grep -c "^[[:space:]]*#[[:space:]]*$key[[:space:]]*=[[:space:]]*.*"  $file`
    
    if [[ $value == "#" ]];then
        if [ $exist -gt 0 ];then
            sed  -i "/^[^#]/s/$key[[:space:]]*=/\#$key=/" $file       
        fi
        return
    fi

    if [ $exist -gt 0 ];then
        #如果已经存在未注释的有效配置行，直接更新value
        sed  -i "/^[^#]/s#$key[[:space:]]*=.*#$key=$value#" $file
        
    elif [ $comment -gt 0 ];then
        #如果存在已经注释掉的对应配置行，则去掉注释，更新value
        sed -i "s@^[[:space:]]*#[[:space:]]*$key[[:space:]]*=[[:space:]]*.*@$key=$value@" $file
    else
        #否则在末尾追加有效配置行
        #local timestamp=`env LANG=en_US.UTF-8 date`
        #local writer=`basename $0`
        echo "" >> $file
        #echo "# added by $writer at $timestamp" >> $file
        echo "$key=$value" >> $file
    fi
}

function convert_mac_to_ip
{
    local dhcp_mac=$1
    local lease_file=/var/lib/dhcpd/dhcpd.leases
    local line
    local ip_addr
    local log_postfix
    install_log=""
    
    #获取lease文件中最后出现这个mac地址的行号
    line=`grep -n -wi "${dhcp_mac}" ${lease_file} |tail -n 1 |awk -F':' '{print $1}'`
    
    [[ ${line} == "" ]] && { pxelog "pxe server did not assign an ip to this target machine";return 1; }
    
    #找到这个行号之前最后一次出现的ip
    ip_addr=`head -n ${line} ${lease_file} | grep -o '\<[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\>' |tail -n 1`
    
    #用ip地址得到log日志文件名
    install_log=/var/log/${ip_addr}
    log_postfix=".log"
    install_log=${install_log}${log_postfix}
    pxelog "dhcp_mac=${dhcp_mac} MACADDR=${MACADDR} install_log=${install_log}!"
    
    return 0
}


function repir_iso_nfs_number
{
    local MACADDR=$1
    local ISOMOUNTPATH=$2
    local oper=$3
    
    pxelog "starting repair $ISOMOUNTPATH used number in $ISO_NFS_TAB!"
    (
        flock -x 200
        used_number=`cat $ISO_NFS_TAB |grep -w "${ISOMOUNTPATH}" | awk -F' ' '{print $2}' |head -n 1`
        #判断used_number是否为数字
        expr $used_number "+" 10 &> /dev/null
        if [ $? -ne 0 ];then
            pxelog "${ISOMOUNTPATH} used number is not a digital!" "console"
            return 1
        fi
        
        pxelog "befor $oper ${MACADDR}, ${ISOMOUNTPATH} is used by $used_number nfs client!"        
        if [[ $oper == "add" ]]; then
            ((used_number=$used_number+1))        
        elif [[ $oper == "dec" ]]; then
            if [[ $used_number -gt 0 ]]; then
                ((used_number=$used_number-1))
                if [[ $used_number -eq 0 ]]; then
                    local linuxinstall_mount=`basename ${ISOMOUNTPATH}`
                    linuxinstall_mount="linuxinstall-""${linuxinstall_mount}"".mount"
                    systemctl disable $linuxinstall_mount &>/dev/null
                    systemctl stop $linuxinstall_mount  &>/dev/null 
                    umount -l ${ISOMOUNTPATH} &>/dev/null
                fi
            else
                pxelog "[error]${ISOMOUNTPATH} is not mounted, cann't clean!"
                return 1
            fi
        elif [[ $oper == "clean" ]]; then
            if [[ $used_number -ne 0 ]]; then
                used_number=0
            fi        
        else
             pxelog "repir_iso_nfs_number inputpara err: oper=$oper!"
        fi
        sed -i "s%${ISOMOUNTPATH} .*%${ISOMOUNTPATH}        $used_number%g" $ISO_NFS_TAB
        pxelog "after $oper ${MACADDR}, ${ISOMOUNTPATH} is used by $used_number nfs client!"
    ) 200>/var/log/iso_nfs_tab.lock
    
    pxelog "started repair $ISOMOUNTPATH used number in $ISO_NFS_TAB!"
}

function clean_iso_nfs_number
{
    local ISOMOUNTPATH
    
    [[ ! -f $ISO_NFS_TAB ]] && return 0
    
    pxelog "starting clean $ISO_NFS_TAB!"
    (
        flock -x 200
        for (( i=1; i<=$ISO_MOUNT_DIR_NUM; i++))
        do
            ISOMOUNTPATH=/linuxinstall/linuxinstall_$i
            systemctl disable linuxinstall-linuxinstall_$i.mount &>/dev/null
            systemctl stop linuxinstall-linuxinstall_$i.mount &>/dev/null
            umount -l ${ISOMOUNTPATH} &>/dev/null
            sed -i "s%${ISOMOUNTPATH} .*%${ISOMOUNTPATH}        0%g" $ISO_NFS_TAB
        done
    ) 200>/var/log/iso_nfs_tab.lock    
    
    pxelog "started to clean $ISO_NFS_TAB!"
      
}

function clean_os_files
{
    local MACADDR=$1
    local OS_TABLE=$2
    local linuxinstall_dir=""
    
    #删除/home/install_share、/tftpboot下和目标机相关的东西
    rm /home/install_share/${MACADDR} -rf
    rm /tftpboot/${MACADDR} -rf
    rm /tftpboot/pxelinux.cfg/01-${MACADDR} -rf
    
    #将这个目标机使用的iso mount路径的使用数减一，如果减到0了，则umount
    [[ -f $OS_TABLE ]] && { linuxinstall_dir=`cat $OS_TABLE | grep -wi "$MACADDR" |awk -F' ' '{print $4}'`; }
    if [[ `echo $linuxinstall_dir |grep "/linuxinstall/linuxinstall_*"` != "" ]]; then
        repir_iso_nfs_number $MACADDR $linuxinstall_dir "dec"
        local newlog=`cat $OS_TABLE | grep -wi "$MACADDR" |sed "s%$linuxinstall_dir%null%g"`
        sed -i "s%$MACADDR.*%$newlog%g" $OS_TABLE
    else
        pxelog "[info]$MACADDR does not have a iso nfs dir or $OS_TABLE not exist!"
    fi
}

function clean_all_os_files
{
    #删除/home/install_share、/tftpboot下所有目标机相关的东西
    rm /home/install_share/* -rf
    
    if [[ -d /tftpboot ]]; then
        mkdir -p /tftpboot_bak
        cp -rf /tftpboot/* /tftpboot_bak/
        rm -rf /tftpboot/*
        cp /tftpboot_bak/initrd.img /tftpboot/
        cp /tftpboot_bak/pxelinux.0 /tftpboot/
        cp /tftpboot_bak/vmlinuz /tftpboot/
        cp -rf /tftpboot_bak/pxelinux.cfg /tftpboot/
        rm -rf /tftpboot/pxelinux.cfg/01-*
        rm -rf /tftpboot_bak 
    fi   
    
    #将所有/linuxinstall/linuxinstall_n的路径umount，使用数也清0
    clean_iso_nfs_number
}

function clean_os_table
{
    local MACADDR=$1
    local OS_TABLE=$2
    
    if [ -f ${OS_TABLE} ]; then
        [[ `cat ${OS_TABLE} |grep "${MACADDR}"` != "" ]] &&  sed -i "/${MACADDR}/d" ${OS_TABLE}
    fi    
}

#清除某个目标机使用过的所有ip的日志
function clean_mac_all_log
{
    local dhcp_mac=$1
    local lease_file=/var/lib/dhcpd/dhcpd.leases
    local line_mac
    local ip_addr
    local log_postfix
    install_log_tmp=""
    
    #获取lease文件中是否出现这个mac地址
    list=`grep -n -wi "${dhcp_mac}" ${lease_file} |awk -F':' '{print $1}'`
    
    [[ ${list} == "" ]] && { pxelog "pxe server did not assign an ip to this target machine";return 1; }
        
    #如果lease文件中是否出现这个mac地址则删除这一项
    for i in $list
    do
        #找到出现这个mac地址所在的行号
        line_mac=$i
        
        #找到这个行号之前最后一次出现的ip
        line=`head -n ${line_mac} ${lease_file} | grep -n -o '\<[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\>' |tail -n 1`
               
        ip_addr=`echo $line |awk -F':' '{print $2}'`
                        
        #用ip地址得到log日志文件名并且清除日志
        install_log_tmp=/var/log/${ip_addr}
        log_postfix=".log"
        install_log_tmp=${install_log_tmp}${log_postfix}
                
        if [[ ${install_log_tmp} != "" ]]; then
            INSTALL_LOG_TMP=${install_log_tmp}
            if [ -f ${INSTALL_LOG_TMP} ]; then
              echo > ${INSTALL_LOG_TMP}
              pxelog "clean_mac_all_log dhcp_mac=${dhcp_mac} MACADDR=${MACADDR} install_log_tmp=${install_log_tmp} clean ${install_log_tmp}!"
            else
                pxelog "clean_mac_all_log dhcp_mac=${dhcp_mac} MACADDR=${MACADDR} install_log_tmp=${install_log_tmp} not exist!"
            fi
        fi
    done
    return 0    
}

#清除所有目标机使用过的所有ip的日志
function clean_all_log
{
    local lease_file=/var/lib/dhcpd/dhcpd.leases
    local ip_addr
    local log_postfix
    install_log_tmp=""
    
    [[ ! -f $lease_file ]] && return 0
    
    #获取lease文件中所有分配出去的ip
    list=`cat $lease_file |grep -o '\<[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\>'`
    
    [[ ${list} == "" ]] && { pxelog "pxe server did not assign an ip to any target machine";return 1; }
        
    #如果lease文件中是否出现这个mac地址则删除这一项
    for i in $list
    do
        ip_addr=$i
                        
        #用ip地址得到log日志文件名并且清除日志
        install_log_tmp=/var/log/${ip_addr}
        log_postfix=".log"
        install_log_tmp=${install_log_tmp}${log_postfix}
                
        if [[ ${install_log_tmp} != "" ]]; then
            INSTALL_LOG_TMP=${install_log_tmp}
            if [ -f ${INSTALL_LOG_TMP} ]; then
                echo > ${INSTALL_LOG_TMP}
                pxelog "clean_all_log install_log_tmp=${install_log_tmp} clean ${install_log_tmp}!"
            else
                pxelog "clean_all_log install_log_tmp=${install_log_tmp} not exist!"
            fi
        fi
    done
    return 0    
}

#清除某个目标机最后使用的ip的日志
function clean_mac_last_log
{
    local dhcp_mac=$1
    
    convert_mac_to_ip ${dhcp_mac} || { return 1; }
    INSTALL_LOG=${install_log}
                        
    if [ -f ${INSTALL_LOG} ]; then
        echo > $INSTALL_LOG
        pxelog "clean_mac_last_log dhcp_mac=${dhcp_mac} MACADDR=${MACADDR} install_last_log=${INSTALL_LOG} clean ${INSTALL_LOG}!"
    else
        pxelog "clean_mac_last_log dhcp_mac=${dhcp_mac} MACADDR=${MACADDR} install_last_log=${INSTALL_LOG} not exist!"
    fi
    return 0    
}

