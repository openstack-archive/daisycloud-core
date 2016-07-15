#!/bin/bash
# 
if [ ! "$_UPGRADE_FUNC_FILE" ];then
#ͷ�ļ�����
_UPGRADE_FUNC_DIR=`pwd`
cd  $_UPGRADE_FUNC_DIR/../common/
.  daisy_common_func.sh

cd $_UPGRADE_FUNC_DIR

#��������ݼ���ʾ����Ļ���������ָ���ļ���
function write_upgrade_log
{
    local promt="$1"
    echo -e "$promt"
    echo -e "`date -d today +"%Y-%m-%d %H:%M:%S"`  $promt" >> $logfile
}
# ��ȡ��ǰ��װ������daisy��ط�����б�
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
