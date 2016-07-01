#!/bin/bash
# 提供和yum安装相关的公共函数和变量
if [ ! "$_UPGRADE_INTERFACE_FILE" ];then
_UPGRADE_INTERFACE_DIR=`pwd`
cd $_UPGRADE_INTERFACE_DIR/../common/
.  daisy_common_func.sh
.  daisy_global_var.sh

cd $_UPGRADE_INTERFACE_DIR/../install/
.  install_func.sh

cd $_UPGRADE_INTERFACE_DIR
.  upgrade_func.sh

daisy_upgrade="/var/log/daisy/daisy_upgrade"
upgradedatefile=`date -d "today" +"%Y%m%d-%H%M%S"`
logfile=$daisy_upgrade/daisyupgrade_$upgradedatefile.log

function upgrade_daisy
{
    if [ ! -d "$daisy_upgrade" ];then
        mkdir -p $daisy_upgrade
    fi
 
    if [ ! -f "$logfile" ];then
        touch $logfile
    fi 

    write_upgrade_log "wait to stop daisy services..."
    stop_service_all 

    #获取当前所有daisy服务包
    get_daisy_services
    
    # 升级daisy服务包
    upgrade_rpms_by_yum "$all_daisy_services"

    
    #同步daisy数据库
    which daisy-manage >> $logfile 2>&1
    if [ "$?" == 0 ];then
        write_upgrade_log  "start daisy-manage db_sync..." 
        daisy-manage db_sync
        [ "$?" -ne 0 ] && { write_upgrade_log "Error:daisy-manage db_sync command faild"; exit 1; } 
    fi

    #同步ironic数据库
    which ironic-dbsync >> $logfile 2>&1
    if [ "$?" == 0 ];then
        write_upgrade_log "start ironic-dbsync ..." 
        ironic-dbsync --config-file /etc/ironic/ironic.conf
        [ "$?" -ne 0 ] && { write_upgrade_log "Error:ironic-dbsync --config-file /etc/ironic/ironic.conf faild"; exit 1; } 
    fi

    #同步keystone数据库
    which keystone-manage >> $logfile 2>&1
    if [ "$?" == 0 ];then
        write_upgrade_log  "start keystone-manage db_sync..." 
        keystone-manage db_sync
        [ "$?" -ne 0 ] && { write_upgrade_log "Error:keystone-manage db_sync command faild"; exit 1; } 
    fi

    write_upgrade_log  "wait to start daisy service..."
    start_service_all >> $logfile 2>&1

    mysql_cmd="mysql"
    local mariadb_result=`systemctl is-active mariadb.service`
    if [ $? -eq 0 ];then
        #update type=private,name=private to type=dataplane,name=physnet1
        local update_private_to_physnet1_sql="use daisy;update networks set name='physnet1',network_type='DATAPLANE' where network_type='PRIVATE' and name='PRIVATE' and deleted=0;"
        write_upgrade_log "update private name to physnet1 and private to dataplane in daisy database"
        echo ${update_private_to_physnet1_sql} | ${mysql_cmd}
        if [ $? -ne 0 ];then
            write_upgrade_log "Error:update private name to physnet1 and private to dataplane in daisy database failed..."
            exit 1
        fi
        #update type=private to type=dataplane
        local update_private_to_dataplane_sql="use daisy;update networks set network_type='DATAPLANE' where network_type='PRIVATE' and deleted=0;"
        write_upgrade_log "update private to dataplane in daisy database"
        echo ${update_private_to_dataplane_sql} | ${mysql_cmd}
        if [ $? -ne 0 ];then
            write_upgrade_log "Error:update private to dataplane in daisy database failed..."
            exit 1
        fi
        #update public to publicapi
        local update_public_to_publicapi_sql="use daisy;update networks set network_type='PUBLICAPI',name='PUBLICAPI' where network_type='PUBLIC' and deleted=0;"
        write_upgrade_log "update public to publicapi in daisy database"
        echo ${update_public_to_publicapi_sql} | ${mysql_cmd}
        if [ $? -ne 0 ];then
            write_upgrade_log "Error:update public to publicapi in daisy database failed..."
            exit 1
        fi

        local cluster_list_sql="use daisy;select clusters.id from clusters where deleted=0;"
        local cluster_list_id=`echo ${cluster_list_sql} | ${mysql_cmd}|grep -v id`
        for cluster_id in ${cluster_list_id}
        do
            local cluster_segmentation_sql="use daisy;select clusters.segmentation_type from clusters where id='"$cluster_id"' and deleted=0;"
            local cluster_segmentation=`echo ${cluster_segmentation_sql} | ${mysql_cmd}|grep -v segmentation_type`
            if [ ${cluster_segmentation} == "vlan" ];then
                #update public to publicapi
                local update_segmentation_type_vlan_sql="use daisy;update networks set segmentation_type='vlan' where cluster_id='"$cluster_id"' and network_type='DATAPLANE' and deleted=0;"
                write_upgrade_log "update segmentation_type to vlan in daisy database"
                echo ${update_segmentation_type_vlan_sql} | ${mysql_cmd}
                if [ $? -ne 0 ];then
                    write_upgrade_log "Error:update segmentation_type to vlan in daisy database failed..."
                    exit 1
                fi
            fi
            if [ ${cluster_segmentation} == "vxlan" ];then
                local update_segmentation_type_vxlan_sql="use daisy;update networks set segmentation_type='vxlan' where cluster_id='"$cluster_id"' and network_type='DATAPLANE' and deleted=0;"
                write_upgrade_log "update segmentation_type to vxlan in daisy database"
                echo ${update_segmentation_type_vxlan_sql} | ${mysql_cmd}
                if [ $? -ne 0 ];then
                    write_upgrade_log "Error:update segmentation_type to vxlan in daisy database failed..."
                    exit 1
                fi
                local vni_start_sql="use daisy;select clusters.vni_start from clusters where id='"$cluster_id"' and deleted=0;"
                local vni_start=`echo ${vni_start_sql} | ${mysql_cmd}|grep -v vni_start`
                if [ "$vni_start" != "NULL" ];then
                    local update_segmentation_type_vxlan_sql="use daisy;update networks set vni_start='"$vni_start"' where cluster_id='"$cluster_id"' and network_type='DATAPLANE' and deleted=0;"
                    echo ${update_segmentation_type_vxlan_sql} | ${mysql_cmd}
                    if [ $? -ne 0 ];then
                        write_upgrade_log "Error:update vni_start in daisy database failed..."
                        exit 1
                    fi
                fi

                local vni_end_sql="use daisy;select clusters.vni_end from clusters where id='"$cluster_id"' and deleted=0;"
                local vni_end=`echo ${vni_end_sql} | ${mysql_cmd}|grep -v vni_end`
                if [ "$vni_end" != "NULL" ];then
                    local update_segmentation_type_vxlan_sql="use daisy;update networks set vni_end='"$vni_end"' where cluster_id='"$cluster_id"' and network_type='DATAPLANE' and deleted=0;"
                    echo ${update_segmentation_type_vxlan_sql} | ${mysql_cmd}
                    if [ $? -ne 0 ];then
                        write_upgrade_log "Error:update vni_end in daisy database failed..."
                        exit 1
                    fi
                fi

                local vxlan_cidr_sql="use daisy;select networks.cidr from networks where cluster_id='"$cluster_id"' and network_type='VXLAN'and deleted=0;"
                local vxlan_cidr=`echo ${vxlan_cidr_sql} | ${mysql_cmd}|awk 'NR==2{print}'`
                if [ "$vxlan_cidr" != "NULL" ];then
                    local update_vxlan_cidr_sql="use daisy;update networks set cidr='"$vxlan_cidr"' where cluster_id='"$cluster_id"' and network_type='DATAPLANE' and name='physnet1' and deleted=0;"
                    echo ${update_vxlan_cidr_sql} | ${mysql_cmd}
                    if [ $? -ne 0 ];then
                        write_upgrade_log "Error:update cidr from vxlan to physnet1 in daisy database failed..."
                        exit 1
                    fi
                fi
            fi

            local update_segmentation_type_and_vni_null_sql="use daisy;update clusters set segmentation_type='NULL',vni_start=NULL,vni_end=NULL where id='"$cluster_id"' and deleted=0;"
            echo ${update_segmentation_type_and_vni_null_sql} | ${mysql_cmd}
            if [ $? -ne 0 ];then
                write_upgrade_log "Error:update segmentation_type and vni for blank in daisy database failed..."
                exit 1
            fi

            local vxlan_id_sql="use daisy;select networks.id from networks where cluster_id='"$cluster_id"' and network_type='VXLAN'and deleted=0;"
            local vxlan_id=`echo ${vxlan_id_sql} | ${mysql_cmd} | awk 'NR==2{print}'`
            local physnet1_id_sql="use daisy;select networks.id from networks where cluster_id='"$cluster_id"' and network_type='DATAPLANE' and name='physnet1' and deleted=0;"
            local physnet1_id=`echo ${physnet1_id_sql} | ${mysql_cmd}|awk 'NR==2{print}'`
            local update_vxlan_ip_ranges_sql="use daisy;update ip_ranges set network_id='"$physnet1_id"' where network_id='"$vxlan_id"' and deleted=0;"
            write_upgrade_log "update ip_ranges from vxlan to physnet1 in daisy database"
            echo ${update_vxlan_ip_ranges_sql} | ${mysql_cmd}
            if [ $? -ne 0 ];then
                write_upgrade_log "Error:update ip_ranges from vxlan to physnet1 in daisy database failed..."
                exit 1
            fi
        done

        #delete vxlan
        local delete_vxlan_sql="use daisy;delete from networks where network_type='VXLAN' and deleted=0;"
        write_upgrade_log "delete vxlan in daisy database"
        echo ${delete_vxlan_sql} | ${mysql_cmd}
        if [ $? -ne 0 ];then
            write_upgrade_log "Error:delete vxlan in daisy database failed..."
            exit 1
        fi
        #update capability=high
        local update_capability_sql="use daisy;update networks set capability='high';"
        write_upgrade_log "update networks tables capability=high daisy database"
        echo ${update_capability_sql} | ${mysql_cmd}
        if [ $? -ne 0 ];then
            write_upgrade_log "Error:update networks capability=high in daisy database failed..."
            exit 1
        fi
    else 
        write_upgrade_log "Error:mariadb service is not active"
        exit 1
    fi

    write_upgrade_log  "Daisy upgrade successful..."
}

_UPGRADE_INTERFACE_FILE="upgrade_interface.sh"
fi
