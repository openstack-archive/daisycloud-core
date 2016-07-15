#!/bin/bash
# 
if [ ! "$_UPGRADE_FUNC_FILE" ];then
#头文件包含
_UPGRADE_FUNC_DIR=`pwd`
cd  $_UPGRADE_FUNC_DIR/../common/
.  daisy_common_func.sh

cd $_UPGRADE_FUNC_DIR

#输出的内容既显示在屏幕上又输出到指定文件中
function write_upgrade_log
{
    local promt="$1"
    echo -e "$promt"
    echo -e "`date -d today +"%Y-%m-%d %H:%M:%S"`  $promt" >> $logfile
}
# 获取当前安装的所有daisy相关服务的列表
function get_daisy_services
{
    all_daisy_services="
    fping
    openstack-keystone
    daisy
    python-daisy
    python-daisyclient
    openstack-ironic-api
    openstack-ironic-common
    openstack-ironic-conductor
    python-ironicclient
    openstack-ironic-discoverd
    python-ironic-discoverd
    pxe_server_install
    pxe_docker_install
    python-django-horizon
    daisy-dashboard
    " 
}

_UPGRADE_FUNC_FILE="upgrade_func.sh"

fi
