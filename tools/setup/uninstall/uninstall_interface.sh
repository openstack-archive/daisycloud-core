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
    echo "stop all service..."
    stop_service_all
    remove_rpms_by_yum "daisy python-daisyclient  python-daisy"
    remove_rpms_by_yum "daisy-discoverd python-daisy-discoverd"
    remove_rpms_by_yum "daisy4nfv-jasmine"
    rpm -e  pxe_server_install
    for i in `ps -elf | grep daisy-api |grep -v grep | awk -F ' ' '{print $4}'`;do kill -9 $i;done
    for j in `ps -elf | grep daisy-registry |grep -v grep | awk -F ' ' '{print $4}'`;do kill -9 $j;done
    for j in `ps -elf | grep daisy-orchestration |grep -v grep | awk -F ' ' '{print $4}'`;do kill -9 $j;done
    for j in `ps -elf | grep daisy-discoverd |grep -v grep | awk -F ' ' '{print $4}'`;do kill -9 $j;done
    # delect keystone database
    delete_keystone_sql="drop database IF EXISTS keystone"
    write_install_log "delect keystone database in mariadb"
    echo ${delete_keystone_sql} | mysql
    if [ $? -ne 0 ];then
        echo "Error:delete keystone database failed..."
    fi
    # delect daisy database
    delete_daisy_sql="drop database IF EXISTS daisy"
    write_install_log "delect daisy database in mariadb"
    echo ${delete_daisy_sql} | mysql
    if [ $? -ne 0 ];then
        echo "Error:delete daisy database failed..."
    fi
    echo "remove container and image..."
    container_id=`docker ps -a |grep "registry"|awk -F' ' '{print $1}'`
    if [ -n "$container_id" ];then
        docker stop $container_id
        docker rm $container_id
    fi
    image_id=`docker images |grep "registry"|awk -F' ' '{print $3}'`
    if [ -n "$image_id" ];then
        docker rmi $image_id
    fi
    rm -rf /etc/daisy
    rm -rf /etc/daisy-discoverd
    rm -rf /etc/sudoers.d/daisy
    rm -rf /var/lib/daisy
    rm -rf /var/log/daisy
    rm -rf /var/lib/daisy-discoverd
    rm -rf /var/log/daisy-discoverd
    rm -rf /root/daisyrc_admin
    echo "Finish clean daisy!"
}

_UNINSTALL_FUNC="uninstall_func.sh"
fi
