#!/bin/bash

###############################################################################################
#    功能：获取os安装进度的函数定义
###############################################################################################
function find_string_in_file
{
    local file=$1
    local string=$2
    exist=yes

    local result=`cat ${file} |grep -a "${string}"`
    [[ ${result} == "" ]] && exist=no
}

function print_progress
{
    local OS_TABLE=$1
    local MACADDR=$2
    local descript
    
    descript=`cat ${OS_TABLE} | grep -wi "${MACADDR}" |awk -F' ' '{print $2"   "$3}'`
    pxelog "${descript}" "console"
}

function modify_os_table
{
    local OS_TABLE=$1
    local MACADDR=$2
    local rate_value=$3
    local rate_descript=$4
    
    local tmp_rate=`cat $OS_TABLE | grep -wi "$MACADDR" |awk -F' ' '{print $2}'`
    
    [[ $rate_value == $tmp_rate ]] && return 0
    
    local linuxinstall_dir=`cat $OS_TABLE | grep -wi "$MACADDR" |awk -F' ' '{print $4}'`
    sed -i "s%${MACADDR}.*%${MACADDR}   ${rate_value}   ${rate_descript}   ${linuxinstall_dir}%g" ${OS_TABLE}
}

#设置完成
function set_done
{
    local INSTALL_LOG=$1
    local OS_TABLE=$2
    local MACADDR=$3
    
    modify_os_table ${OS_TABLE} ${MACADDR} "100" "done_install"
    pxelog "${MACADDR} install complete, will clean files and ${INSTALL_LOG}!"
    print_progress ${OS_TABLE} ${MACADDR}
    clean_os_files ${MACADDR} ${OS_TABLE}
    echo > ${INSTALL_LOG}
}


#此函数就是从日志文件中找anaconda程序各个阶段的关键字来确认安装进度，每个阶段对应的安装进度是固定的
#从最后的阶段往前开始搜索，除了给出进度值，还需要更新服务器上的一个目标机安装统计表
#出现anaconda: Thread Done: AnaConfigurationThread----100% done_install
#出现anaconda: Running Thread: AnaConfigurationThread----62%-100%   post_config
#出现anaconda: Running Thread: AnaInstallThread----2%-62%   package_install，期间需要再细化
#出现anaconda: Running Thread: AnaStorageThread----1%   storage_config
#其余0%  plan_install
#$1: 目标机安装日志文件
#$2: 目标机安装统计表
#$3: 目标机mac地址
function get_progress_rh70_base
{
    local INSTALL_LOG=$1
    local OS_TABLE=$2
    local MACADDR=$3
    local descript
    local rate_value 
    
    
    #查看日志，搜索anaconda: Thread Done: AnaConfigurationThread,搜到了，表示安装完成，进度是100%
    descript="anaconda: Thread Done: AnaConfigurationThread"
    find_string_in_file ${INSTALL_LOG} "${descript}"
    if [ ${exist} == yes ]; then
        set_done $INSTALL_LOG $OS_TABLE $MACADDR
        return 0
    fi       
    
        
    #查看日志，搜索anaconda: Running Thread: AnaConfigurationThread，搜到了，表示在执行post阶段的配置，进度是62%-100%，这里又分好几个阶段
    descript="anaconda: Running Thread: AnaConfigurationThread"
    find_string_in_file ${INSTALL_LOG} "${descript}"
    if [ ${exist} == yes ]; then
        #查看日志，搜索yum.*Installed的个数，总共28个，期间百分比是79-96%
        number=`cat ${INSTALL_LOG} |grep "yum.*Installed" | wc -l`
        if [ ${number} -gt 0 ]; then
            ((rate_value=${number}*17/28+79)) 
            [[ $rate_value -gt 99 ]] && rate_value=99
            modify_os_table ${OS_TABLE} ${MACADDR} "${rate_value}" "post_config"
            print_progress ${OS_TABLE} ${MACADDR}
            return 0
        fi
    
        #查看日志，搜索anaconda: Running post-installation scripts,搜到了，表示已经执行了66%
        descript="anaconda: Running post-installation scripts"
        find_string_in_file ${INSTALL_LOG} "${descript}"
        if [ ${exist} == yes ]; then
            modify_os_table ${OS_TABLE} ${MACADDR} "66" "post_config"
            print_progress ${OS_TABLE} ${MACADDR}            
            return 0
        fi         
        
        modify_os_table ${OS_TABLE} ${MACADDR} "62" "post_config"
        print_progress ${OS_TABLE} ${MACADDR}
        return 0
    fi       
        
    #查看日志，搜索anaconda: Running Thread: AnaInstallThread，搜到了，表示在执行package的安装，2%-62%，这里又分好几个阶段
    descript="anaconda: Running Thread: AnaInstallThread"
    find_string_in_file ${INSTALL_LOG} "${descript}"
    if [ ${exist} == yes ]; then
        #查看日志，搜索packaging:  transaction complete，搜到了，表示已经执行完61%
        descript="packaging:  transaction complete"
        find_string_in_file ${INSTALL_LOG} "${descript}"
        if [ ${exist} == yes ]; then
            modify_os_table ${OS_TABLE} ${MACADDR} "61" "package_install"
            print_progress ${OS_TABLE} ${MACADDR}
            return 0
        fi
    
        #查看日志，搜索packaging: Installed products updated，搜到了，表示已经执行完54%
        descript="packaging: Installed products updated"
        find_string_in_file ${INSTALL_LOG} "${descript}"
        if [ ${exist} == yes ]; then
            modify_os_table ${OS_TABLE} ${MACADDR} "54" "package_install"
            print_progress ${OS_TABLE} ${MACADDR}
            return 0
        fi
        
        #查看日志，搜索packaging: Performing post-installation setup tasks，搜到了，表示已经执行完43%
        descript="packaging: Performing post-installation setup tasks"
        find_string_in_file ${INSTALL_LOG} "${descript}"
        if [ ${exist} == yes ]; then
            modify_os_table ${OS_TABLE} ${MACADDR} "43" "package_install"
            print_progress ${OS_TABLE} ${MACADDR}
            return 0
        fi
        
        #查看日志，搜索packaging: Preparing transaction from installation source，搜到了，表示在5%-43%之间，需要根据安装的包数再细化
        descript="packaging: Preparing transaction from installation source"
        find_string_in_file ${INSTALL_LOG} "${descript}"
        if [ ${exist} == yes ]; then
            descript="packaging: Installing"
            find_string_in_file ${INSTALL_LOG} "${descript}"
            if [ ${exist} == yes ]; then
                #根据安装包数计算进度
                #获取到日志中安装的最后一条记录packaging: Installing **** (**/***) 
                descript=`cat ${INSTALL_LOG} |grep "packaging: Installing" | tail -n 1`
                #截取出安装的包数和总包数**/***
                descript=${descript%\)*}
                descript=${descript##*\(}
                local total_pachages=${descript#*/}
                local installed_packages=${descript%/*}
                pxelog "total_pachages=$total_pachages installed_packages=$installed_packages"
                ((rate_value=${installed_packages}*38/${total_pachages}+5))
                modify_os_table ${OS_TABLE} ${MACADDR} "${rate_value}" "package_install"
                print_progress ${OS_TABLE} ${MACADDR}
                return 0
            fi
        
            modify_os_table ${OS_TABLE} ${MACADDR} "5" "package_install"
            print_progress ${OS_TABLE} ${MACADDR}
            return 0
        fi
        
        
        modify_os_table ${OS_TABLE} ${MACADDR} "2" "package_install"
        print_progress ${OS_TABLE} ${MACADDR}
        return 0
    fi
    
    #查看日志，搜索anaconda: Running Thread: AnaStorageThread，搜到了，表示在执行存储设备的配置，进度是1%
    descript="anaconda: Running Thread: AnaStorageThread"
    find_string_in_file ${INSTALL_LOG} "${descript}"
    if [ ${exist} == yes ]; then
        modify_os_table ${OS_TABLE} ${MACADDR} "1" "storage_config"
        print_progress ${OS_TABLE} ${MACADDR}
        return 0
    fi    
    
    modify_os_table ${OS_TABLE} ${MACADDR} "0" "plan_install"
    print_progress ${OS_TABLE} ${MACADDR}
    return 0 
}

function get_progress_rh65_base
{
    local INSTALL_LOG=$1
    local OS_TABLE=$2
    local MACADDR=$3
    local tmp_process=""
    local tmp_rate=""
    
    
    local array_process=("complete" "dopostaction" "postscripts" "methodcomplete" "copylogs" "setfilecon" 
                     "writeksconfig" "reipl" "instbootloader" "firstboot" "writeconfig" "postinstallconfig"
                     "installpackages" "preinstallconfig" "install" "postselection" "basepkgsel" "reposetup"
                     "bootloadersetup" "enablefilesystems" "storagedone" "autopartitionexecute" "setuptime")
    local array_rate=("100" "95" "90" "85" "80" "75"\
                      "70" "65" "60" "55" "50" "45"\
                      "40" "35" "30" "25" "20" "15"\
                      "10" "7" "3" "2" "1")                      
    local array_process_num=${#array_process[@]}                
    local array_rate_num=${#array_rate[@]} 
     
    [[ $array_process_num != $array_rate_num ]] && { pxelog "array_process_num != array_rate_num"; return 1; }
    
    for (( i=0; i<$array_process_num; i++ ))
    do
        tmp_process=${array_process[$i]}
        tmp_rate=${array_rate[$i]}
        #redhat6.5日志的特点是，一个阶段开始的标志moving (1) to step *****，阶段结束的标志leaving (1) step *****，这里用开始的标志里的“to step *****”作为查询关键字
        if [[ `cat $INSTALL_LOG | grep -w "to step $tmp_process"` != "" ]]; then
            if [[ $tmp_rate == 100 ]]; then            
               set_done $INSTALL_LOG $OS_TABLE $MACADDR                  
            else
               modify_os_table ${OS_TABLE} ${MACADDR} "$tmp_rate" "$tmp_process"
               print_progress ${OS_TABLE} ${MACADDR}
            fi
            break       
        fi
    done 
    
    if [[ $i == $array_process_num ]]; then
        modify_os_table ${OS_TABLE} ${MACADDR} "0" "plan_install"
        print_progress ${OS_TABLE} ${MACADDR}
    fi
}



function get_progress
{
    local INSTALL_LOG=$1
    local OS_TABLE=$2
    local MACADDR=$3
    local descript
    local keywords="to step setuptime"
    
    #日志不存在的情况下，到目标机安装统计表上面去查一下相应的安装情况，如果不是0%也不是100%，那么报错
    if [ ! -f ${INSTALL_LOG} ]; then
        descript=`cat ${OS_TABLE} | grep -wi "${MACADDR}" |awk -F' ' '{print $2}'`
        if [[ ${descript} != "0" && ${descript} != "100" ]];then
            modify_os_table ${OS_TABLE} ${MACADDR} "0" "error"            
            pxelog "log file ${INSTALL_LOG} not exist,can not get progress!"     
        fi
        print_progress ${OS_TABLE} ${MACADDR}
        return 0
    fi    
    
    #到日志中查找关键字：to step setuptime，如果找到了，则按redhat6.5的规则定进度，否则按redhat7.0的方式
    if [[ `cat $INSTALL_LOG |grep "$keywords"` != "" ]]; then
        get_progress_rh65_base $@; return $?
    else
        get_progress_rh70_base $@; return $?
    fi
}
