#!/bin/bash
# 
if [ ! "$_UNINSTALL_INTERFACE_FILE" ];then
_UNINSTALL_INTERFACE_DIR=`pwd`
cd $_UNINSTALL_INTERFACE_DIR/../common
.  daisy_common_func.sh
.  daisy_global_var.sh

cd $_UNINSTALL_INTERFACE_DIR
.  uninstall_func.sh


function uninstall_daisy
{
    echo "Will uninstall daisy rpm which has been install in the machines"
    echo "clean all hosts discovery information..." 
    pxe_os_install_clean all
    
    # 先停止所有服务
    echo "stop all service..."
    stop_service_all
    remove_rpms_by_yum "openstack-keystone python-django-horizon python-keystoneclient python-keystone python-keystonemiddleware python-django-horizon daisy-dashboard"
    remove_rpms_by_yum "daisy python-daisyclient  python-daisy"
    remove_rpms_by_yum "openstack-ironic-api openstack-ironic-common openstack-ironic-conductor python-ironicclient"
    remove_rpms_by_yum "openstack-ironic-discoverd python-ironic-discoverd"
    remove_rpms_by_yum "rabbitmq-server"
    remove_rpms_by_yum "mariadb-galera-server mariadb-galera-common mariadb"
    remove_rpms_by_yum "pxe_server_install"
    remove_rpms_by_yum "fping"
    for i in `ps -elf | grep daisy-api |grep -v grep | awk -F ' ' '{print $4}'`;do kill -9 $i;done 
    for j in `ps -elf | grep daisy-registry |grep -v grep | awk -F ' ' '{print $4}'`;do kill -9 $j;done 
    for j in `ps -elf | grep rabbitmq |grep -v grep | awk -F ' ' '{print $4}'`;do kill -9 $j;done 
    for j in `ps -elf | grep ironic-api |grep -v grep | awk -F ' ' '{print $4}'`;do kill -9 $j;done
    for j in `ps -elf | grep ironic-conductor |grep -v grep | awk -F ' ' '{print $4}'`;do kill -9 $j;done
    for j in `ps -elf | grep ironic-discoverd |grep -v grep | awk -F ' ' '{print $4}'`;do kill -9 $j;done
    rm -rf /etc/daisy
    rm -rf /etc/ironic
    rm -rf /etc/ironic-discoverd
    rm -rf /etc/sudoers.d/daisy
    rm -rf /etc/rabbitmq
    rm -rf /etc/my.cnf.d
    rm -rf /var/lib/daisy
    rm -rf /var/lib/mysql/*
    rm -rf /var/lib/ironic
    rm -rf /var/lib/rabbitmq
    rm -rf /var/log/mariadb
    rm -rf /var/log/daisy
    rm -rf /var/log/ironic
    rm -rf /var/log/rabbitmq
    rm -rf /root/daisyrc_admin
    echo "Finish clean daisy!"  
}

_UNINSTALL_FUNC="uninstall_func.sh"
fi
