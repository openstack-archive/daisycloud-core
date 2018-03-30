#!/bin/bash
# 
if [ ! "$_UPGRADE_FUNC_FILE" ];then

_UPGRADE_FUNC_DIR=`pwd`
cd  $_UPGRADE_FUNC_DIR/../common/
.  daisy_common_func.sh

cd $_UPGRADE_FUNC_DIR

function write_upgrade_log
{
    local promt="$1"
    echo -e "$promt"
    echo -e "`date -d today +"%Y-%m-%d %H:%M:%S"`  $promt" >> $logfile
}

function get_daisy_services
{
    all_daisy_services="
    fping
    openstack-keystone
    daisy
    python-daisy
    python-daisyclient
    daisy-discoverd
    python-daisy-discoverd
    pxe_server_install
    " 
}

_UPGRADE_FUNC_FILE="upgrade_func.sh"

fi
