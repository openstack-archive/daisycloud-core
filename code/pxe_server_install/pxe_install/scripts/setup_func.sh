#! /bin/bash

###############################################################################################
#    功能：安装目标机配置的一些函数定义
###############################################################################################
# 定制root用户口令
function custom_ks_rootpwd
{
    local CFG_FILE=$1
    local KS_FILE=$2

    pxelog "starting custom_ks_rootpwd!"

    get_config $CFG_FILE "root_pwd"
    rootpwd=$config_answer
    sed -i "s/rootpw.*$/rootpw  $rootpwd/g" $KS_FILE

    pxelog "started custom_ks_rootpwd!\n"
}

function custom_swap_size
{
    local CFG_FILE=$1
    local swap_from_json=$2

    get_config $CFG_FILE "memory_size"
    memsize=$config_answer
    [[ -z $memsize || 0 -eq ${memsize} ]] && { pxelog "[error]memory_size is invalid: $memsize!\n" "console"; return 1; }
    if [[ $memsize -le 4 ]];then
        swapsize=4000
    elif [[ $memsize -le 16 ]];then
        swapsize=8000
    elif [[ $memsize -le 64 ]];then
        swapsize=32000
    elif [[ $memsize -gt 64 ]];then
        swapsize=64000
    else
        swapsize=4000
    fi
    pxelog "swap size refer to memory_size: $swapsize M, and swap size from json: $swap_from_json M "

    return 0
}

# 定制ks中的vg
# 修改ks中根盘盘符以及格式化磁盘的列表
# 支持多磁盘，但是要指定根盘，比如sda,sdb,sdc，其中sda是根盘。sda包括boot区、cinder、root卷、机动的600M(用于biosboot、vg_sys卷组信息、根盘剩余空间grow方式分区最小要500M)、剩余空间。
# part: boot区（400M）、biosboot区（1M）、pv.01(大小是root卷+4M)、pv.02（cinder大小）、pv.03（根盘剩余的空间）、pv.04（sdb）、pv.05（sdc）....依次类推
# vg: vg_sys(pv.01)、cinder-volumes(pv.02)、vg_data(pv.03，pv.04，pv.05.....)_
# 下面按上面vg的顺序介绍上面各个逻辑卷的分配
# root逻辑卷，vg_sys组，无默认值，一定要传入一个非0和非空的值，daisy判断这个分区的大小，至少50G
# cinder卷组，名字cinder-volumes组，默认为0，如果指定，则按实际大小分配，属于pv.02分区，cindervolumes组
# swap逻辑卷，vg_data组，无默认值，一定要有传值，且不能为0，daisy会根据memory大小计算
# db逻辑卷，vg_data组，默认为0，如果指定，则按实际大小分配，如果-1，将vg_data剩余的空间都分配给db
# mongodb逻辑卷，vg_data组，默认为0，如果指定，则按实际大小分配，如果-1，将vg_data剩余的空间都分配给mongodb
# nova逻辑卷，vg_data组，默认为0，如果指定，则按实际大小分配，如果-1，将vg_data剩余的空间都分配给nova
# glance逻辑卷，vg_data组，默认为0，如果指定，则按实际大小分配，如果-1，将vg_data剩余的空间都分配给nova
# provider逻辑卷，vg_data组，默认为0，如果指定，则按实际大小分配，如果-1，将vg_data剩余的空间都分配给nova，这个卷有个特殊的，是安装的时候不指定挂载路径，所以需要在post阶段创建逻辑卷
function custom_ks_vg_tfg
{
    local CFG_FILE=$1
    local KS_FILE=$2
    local free_storage
    local pv_01=4
    local pv_no=0
    local free_lv_name=""
    local vg_data_part_list=""
    local boot_size=400
    #机动的600M目前使用的地方是：biosboot 1M，系统会划出1M，vg_sys除了root卷大小，还需要多出4M，要不然创建root卷失败，另外根盘剩余空间用grow方式创建一个分区的时候，最少要500M
    local flexible_size=600
    local vg_data_free=1024

    pxelog "starting custom_ks_vg_tfg!"

    #获取根盘盘符
    get_config $CFG_FILE "root_disk"
    root_disk=$config_answer
    #修改ks文件中根盘盘符
    sed -i "s/bootloader --location=mbr --boot-drive=sda --driveorder=sda/bootloader --location=mbr --boot-drive=${root_disk} --driveorder=${root_disk}/g" $KS_FILE
    sed -i "s/part \/boot --fstype ext3 --size=400 --ondisk=sda/part \/boot --fstype ext3 --size=400 --ondisk=${root_disk}/g" $KS_FILE
    sed -i "s/part biosboot --fstype=biosboot --size=1 --ondisk=sda/part biosboot --fstype=biosboot --size=1 --ondisk=${root_disk}/g" $KS_FILE

    #获取盘符列表
    get_config $CFG_FILE "disk_list"
    disk_list=$config_answer
    #修改ks文件中盘符列表
    sed -i "s/--drives=sda/--drives=${disk_list}/g" $KS_FILE
    sed -i "s/disknamelist=sda/disknamelist=${disk_list}/g" $KS_FILE

    #获取总的硬盘大小（所有扫到的盘总和），单位是M
    get_config $CFG_FILE "storage_size"
    storage_size=$config_answer
    [[ -z ${storage_size} || 0 = ${storage_size} ]] && { pxelog "[error]storage_size is invalid: ${storage_size} M!\n" "console"; return 1; }
    free_storage=${storage_size}
    pxelog "storage_size=${storage_size} M, free_storage=$free_storage M"

    #boot分区固定写死了400M，另外600M作为冗余
    ((free_storage=${free_storage}-${boot_size}-${flexible_size}))
    pxelog "boot_size=${boot_size} M, flexible_size=${flexible_size} M, free_storage=$free_storage M"

    #获取root大小，创建在根盘上，无默认值，一定要传入一个非0和非空的值，daisy判断这个分区的大小，至少50G
    get_config $CFG_FILE "root_lv_size"
    root_lv_size=$config_answer
    #如果没有配置或者配置为0，则返回失败
    [[ -z ${root_lv_size} || 0 = ${root_lv_size} ]] && { pxelog "[error]root_lv_size is invalid: ${root_lv_size} M!\n" "console"; return 1; }
    sed -i '/^logvol \/ --fstype ext4/d' $KS_FILE
    [ $root_lv_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for root size($root_lv_size M)!\n" "console"; return 1; }
    #root大小小于50G就告警
    [ $root_lv_size -lt 51200 ] && { pxelog "[error]root size is $root_lv_size M, less than 50G, not enough for system working!\n" "console"; return 1; }
    sed -i "/\#lv_root/a\logvol \/ --fstype ext4 --vgname=vg_sys --size=$root_lv_size --name=lv_root" $KS_FILE
    ((pv_01=$root_lv_size+$pv_01))
    ((free_storage=$free_storage-$root_lv_size))
    pxelog "root_lv_size=${root_lv_size} M, free_storage=$free_storage M, pv_01=$pv_01 M"

    #获取swap分区的大小，无默认值，一定要有传值，且不能为0，daisy会根据memory大小计算
    get_config $CFG_FILE "swap_lv_size"
    swap_lv_size=$config_answer
    custom_swap_size $CFG_FILE $swap_lv_size || return 1
    [[ -z ${swap_lv_size} || 0 = ${swap_lv_size} ]] && { pxelog "[error]swap_lv_size is invalid: ${swap_lv_size} M!\n" "console"; return 1; }
    [ $swap_lv_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for swap size($swap_lv_size M)!\n" "console"; return 1; }
     sed -i "s/logvol swap.*/logvol swap  --fstype swap  --vgname=vg_data    --size=$swap_lv_size    --name=lv_swap/" $KS_FILE
    ((free_storage=$free_storage-$swap_lv_size))
    pxelog "swap_lv_size=${swap_lv_size} M, free_storage=$free_storage M"

    #获取db的大小，默认为0，如果指定，则按实际大小分配，如果为-1，则暂时先设置为-1，最后再根据剩余空间修改
    get_config $CFG_FILE "db_lv_size"
    db_lv_size=$config_answer
    if [[ ${db_lv_size} == "-1" ]];then
         [[ ${free_lv_name} != "" ]] && { pxelog "[error]${free_lv_name} is already -1, db_lv_size can not be set -1!\n" "console"; return 1; }
         free_lv_name="db"
         ((free_storage=$free_storage-1))
    fi
    if [[ ! -z $db_lv_size && 0 -ne $db_lv_size ]]; then
        sed -i '/^logvol \/var\/lib\/mysql/d' $KS_FILE
        [ $db_lv_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for db size($db_lv_size M)!\n" "console"; return 1; }
        sed -i "/\#lv_db/a\logvol \/var\/lib\/mysql --fstype ext4 --vgname=vg_data --size=$db_lv_size --name=lv_db" $KS_FILE
        ((free_storage=$free_storage-$db_lv_size))
    fi
    pxelog "db_lv_size=${db_lv_size} M, free_storage=$free_storage M"

    #获取mongodb的大小，默认为0，如果指定，则按实际大小分配，如果为-1，则暂时先设置为-1，最后再根据剩余空间修改
    get_config $CFG_FILE "mongodb_lv_size"
    mongodb_lv_size=$config_answer
    if [[ ${mongodb_lv_size} == "-1" ]];then
         [[ ${free_lv_name} != "" ]] && { pxelog "[error]${free_lv_name} is already -1, mongodb_lv_size can not be set -1!\n" "console"; return 1; }
         free_lv_name="mongodb"
         ((free_storage=$free_storage-1))
    fi
    if [[ ! -z $mongodb_lv_size && 0 -ne $mongodb_lv_size ]]; then
        sed -i '/^logvol \/var\/lib\/mongodb/d' $KS_FILE
        [ $mongodb_lv_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for mongodb size($mongodb_lv_size M)!\n" "console"; return 1; }
        sed -i "/\#lv_mongodb/a\logvol \/var\/lib\/mongodb --fstype ext4 --vgname=vg_data --size=$mongodb_lv_size --name=lv_mongodb" $KS_FILE
        ((free_storage=$free_storage-$mongodb_lv_size))
    fi
    pxelog "mongodb_lv_size=${mongodb_lv_size} M, free_storage=$free_storage M"

    #获取nova大小，默认为0，如果指定，则按实际大小分配，如果为-1，则暂时先设置为-1，最后再根据剩余空间修改
    get_config $CFG_FILE "nova_lv_size"
    nova_lv_size=$config_answer
    if [[ ${nova_lv_size} == "-1" ]];then
         [[ ${free_lv_name} != "" ]] && { pxelog "[error]${free_lv_name} is already -1, nova_lv_size can not be set -1!\n" "console"; return 1; }
         free_lv_name="nova"
         ((free_storage=$free_storage-1))
    fi
    if [[ ! -z $nova_lv_size && 0 -ne $nova_lv_size ]]; then
        sed -i '/^logvol \/var\/lib\/nova/d' $KS_FILE
        [ $nova_lv_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for nova size($nova_lv_size M)!\n" "console"; return 1; }
        sed -i "/\#lv_nova/a\logvol \/var\/lib\/nova --fstype ext4 --vgname=vg_data --size=$nova_lv_size --name=lv_nova" $KS_FILE
        ((free_storage=$free_storage-$nova_lv_size))
    fi
    pxelog "nova_lv_size=${nova_lv_size} M, free_storage=$free_storage M"

    #获取glance大小，默认为0，如果指定，则按实际大小分配，如果为-1，则暂时先设置为-1，最后再根据剩余空间修改
    get_config $CFG_FILE "glance_lv_size"
    glance_lv_size=$config_answer
    if [[ ${glance_lv_size} == "-1" ]];then
         [[ ${free_lv_name} != "" ]] && { pxelog "[error]${free_lv_name} is already -1, glance_lv_size can not be set -1!\n" "console"; return 1; }
         free_lv_name="glance"
         ((free_storage=$free_storage-1))
    fi
    if [[ ! -z $glance_lv_size && 0 -ne $glance_lv_size ]]; then
        sed -i '/^logvol \/var\/lib\/glance/d' $KS_FILE
        get_config $CFG_FILE "mount_glance"
        mount_glance=$config_answer
        #如果mount_glance为yes，表示安装后自动挂载到/var/lig/glance，创建逻辑卷用anaconda的logvol，否则安装只创建卷，不挂载，这个操作在post阶段执行
        if [[ $mount_glance != "yes" ]]; then
            [ $glance_lv_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for glance size($glance_lv_size M)!\n" "console"; return 1; }
            sed -i "/\#lv_glance_nomount/a\udevadm settle --timeout=300" $KS_FILE
            sed -i "/\#lv_glance_nomount/a\udevadm settle --timeout=300" $KS_FILE
            sed -i "/\#lv_glance_nomount/a\e2label \/dev\/mapper\/vg_data-lv_glance" $KS_FILE
            sed -i "/\#lv_glance_nomount/a\mke2fs -t ext4 \/dev\/mapper\/vg_data-lv_glance" $KS_FILE
            sed -i "/\#lv_glance_nomount/a\udevadm settle --timeout=300" $KS_FILE
            sed -i "/\#lv_glance_nomount/a\udevadm settle --timeout=300" $KS_FILE
            sed -i "/\#lv_glance_nomount/a\echo \"lvcreate -n lv_glance -L ${glance_lv_size}M -y vg_data\" >>  /home/os_install/usrdata/pxe_install.log" $KS_FILE
            sed -i "/\#lv_glance_nomount/a\lvcreate -n lv_glance -L ${glance_lv_size}M -y vg_data" $KS_FILE
            ((free_storage=$free_storage-$glance_lv_size))
        else
            [ $glance_lv_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for glance size($glance_lv_size M)!\n" "console"; return 1; }
            sed -i "/\#lv_glance_mount/a\logvol \/var\/lib\/glance --fstype ext4 --vgname=vg_data --size=$glance_lv_size --name=lv_glance" $KS_FILE
            ((free_storage=$free_storage-$glance_lv_size))
        fi
    fi
    pxelog "glance_lv_size=${glance_lv_size} M, free_storage=$free_storage M"

    #获取provider大小，默认为0，如果指定，则按实际大小分配，如果为-1，则暂时先设置为-1，最后再根据剩余空间修改
    get_config $CFG_FILE "provider_lv_size"
    provider_lv_size=$config_answer
    if [[ ${provider_lv_size} == "-1" ]];then
         [[ ${free_lv_name} != "" ]] && { pxelog "[error]${free_lv_name} is already -1, provider_lv_size can not be set -1!\n" "console"; return 1; }
         free_lv_name="provider"
         ((free_storage=$free_storage-1))
    fi
    if [[ ! -z $provider_lv_size && 0 -ne $provider_lv_size ]]; then
        #安装只创建卷，不挂载，这个操作在post阶段执行
        [ $provider_lv_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for provider size($provider_lv_size M)!\n" "console"; return 1; }
        sed -i "/\#lv_provider_nomount/a\udevadm settle --timeout=300" $KS_FILE
        sed -i "/\#lv_provider_nomount/a\udevadm settle --timeout=300" $KS_FILE
        sed -i "/\#lv_provider_nomount/a\e2label \/dev\/mapper\/vg_data-lv_provider" $KS_FILE
        sed -i "/\#lv_provider_nomount/a\mke2fs -t ext4 \/dev\/mapper\/vg_data-lv_provider" $KS_FILE
        sed -i "/\#lv_provider_nomount/a\udevadm settle --timeout=300" $KS_FILE
        sed -i "/\#lv_provider_nomount/a\udevadm settle --timeout=300" $KS_FILE
        sed -i "/\#lv_provider_nomount/a\echo \"lvcreate -n lv_provider -L ${provider_lv_size}M -y vg_data\" >>  /home/os_install/usrdata/pxe_install.log" $KS_FILE
        sed -i "/\#lv_provider_nomount/a\lvcreate -n lv_provider -L ${provider_lv_size}M -y vg_data" $KS_FILE
        ((free_storage=$free_storage-$provider_lv_size))
    fi
    pxelog "provider_lv_size=${provider_lv_size} M, free_storage=$free_storage M"

    #设置pv.01，包括root_lv_size、swap_lv_size的冗余空间
    sed -i "/\#end_part/i\part pv.01 --size=$pv_01 --ondisk=${root_disk}" $KS_FILE
    pxelog "vg_sys_size equal to $pv_01 M"
    pv_no=1

    #获取cinder分区的大小，默认为0，如果指定，则按实际大小分配
    get_config $CFG_FILE "cinder_vg_size"
    cinder_vg_size=$config_answer
    if [[ ! -z $cinder_vg_size && 0 -ne $cinder_vg_size ]]; then
        #创建物理卷
        ((pv_no=${pv_no}+1))
        [ $cinder_vg_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for cinder size($cinder_vg_size M)!\n" "console"; return 1; }
        sed -i "/\#end_part/i\part pv.0${pv_no} --size=$cinder_vg_size --ondisk=${root_disk}" $KS_FILE
        sed -i "s/volgroup cindervolumes pv.02 --pesize=4096/volgroup cindervolumes pv.0${pv_no} --pesize=4096/g" $KS_FILE
        ((free_storage=$free_storage-$cinder_vg_size))
    else
        #删除pv.2物理卷以及cinder vg
        sed -i "/cindervolumes/d" $KS_FILE
    fi
    pxelog "cinder_vg_size=${cinder_vg_size} M, free_storage=$free_storage M"

    #获取docker分区的大小，默认为0，如果指定，则按实际大小分配
    get_config $CFG_FILE "docker_vg_size"
    docker_vg_size=$config_answer
    if [[ ! -z $docker_vg_size && 0 -ne $docker_vg_size ]]; then
        #创建物理卷
        ((pv_no=${pv_no}+1))
        [ $docker_vg_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for docker size($docker_vg_size M)!\n" "console"; return 1; }
        sed -i "/\#end_part/i\part pv.0${pv_no} --size=$docker_vg_size --ondisk=${root_disk}" $KS_FILE
        sed -i "s/volgroup vg_docker pv.03 --pesize=4096/volgroup vg_docker pv.0${pv_no} --pesize=4096/g" $KS_FILE
        ((free_storage=$free_storage-$docker_vg_size))
    else
        #删除docker vg
        sed -i "/vg_docker/d" $KS_FILE
    fi
    pxelog "docker_vg_size=${docker_vg_size} M, free_storage=$free_storage M"

    #设置根盘剩余空间的分区
    ((pv_no=pv_no+1))
    sed -i "/\#end_part/i\part pv.0${pv_no} --grow --ondisk=${root_disk}" $KS_FILE
    vg_data_part_list="${vg_data_part_list}"" ""pv.0""${pv_no}"
    pxelog "vg_data_part_list=${vg_data_part_list}"

    #对其他的盘，每个盘都设置一个分区
    disk_list_array=`echo ${disk_list} | sed "s/,/ /g"`
    pxelog "disk_list_array=${disk_list_array}"
    for i in ${disk_list_array};
    do
        if [[ $i != ${root_disk} ]];then
            ((pv_no=pv_no+1))
            sed -i "/\#end_part/i\part pv.0${pv_no} --grow --ondisk=${i}" $KS_FILE
            vg_data_part_list="${vg_data_part_list}"" ""pv.0""${pv_no}"
            pxelog "vg_data_part_list=${vg_data_part_list}"
        fi
    done

    #设置vg_data组
    sed -i "s/volgroup vg_data.*/volgroup vg_data ${vg_data_part_list} --pesize=4096/g" $KS_FILE
    ((vg_data_size=${storage_size}-${boot_size}-${flexible_size}-${cinder_vg_size}-${pv_01}))
    pxelog "vg_data_size About equal to ${vg_data_size} M"

    #修改ks文件中size=-1的地方，大小改成free_storage-vg_data_free(1G)
    if [[ ${free_lv_name} != "" ]]; then
        if [[ ${free_storage} -gt ${vg_data_free} ]]; then
            ((grow_size=${free_storage}-${vg_data_free}))
        else
            pxelog "[error]free_storage=${free_storage} M is less than to ${vg_data_free} M, insufficient for ${free_lv_name} lv" "console"
            return 1
        fi

        sed -i "s/--size=-1/--size=${grow_size}/g" $KS_FILE
        sed -i "s/-1M/${grow_size}M/g" $KS_FILE
        pxelog "${free_lv_name} lv size is set to ${grow_size} M"
    fi

    pxelog "started custom_ks_vg_tfg!\n"

    return 0
}


# 定制ks中的vg
# 修改ks中根盘盘符以及格式化磁盘的列表
# 只支持安装系统到根盘
# part: boot区（400M）、biosboot区（1M）、pv.01(大小是root卷+swap+8M)
# vg: vg_sys(pv.01)
# root逻辑卷，vg_sys组，无默认值，一定要传入一个非0和非空的值，daisy判断这个分区的大小，至少50G
# swap逻辑卷，vg_sys组，无默认值，一定要有传值，且不能为0，daisy会根据memory大小计算
function custom_ks_vg_else
{
    local CFG_FILE=$1
    local KS_FILE=$2
    local free_storage
    local pv_01=8
    local pv_no=0
    local free_lv_name=""
    local vg_data_part_list=""
    local boot_size=400
    #机动的600M目前使用的地方是：biosboot 1M，系统会划出1M，vg_sys除了root卷大小，还需要多出4M，要不然创建root卷失败
    local flexible_size=600
    local vg_data_free=1024

    pxelog "starting custom_ks_vg_else!"

    #获取根盘盘符
    get_config $CFG_FILE "root_disk"
    root_disk=$config_answer
    #修改ks文件中根盘盘符
    sed -i "s/bootloader --location=mbr --boot-drive=sda --driveorder=sda/bootloader --location=mbr --driveorder=${root_disk}/g" $KS_FILE
    sed -i "s/part \/boot --fstype ext3 --size=400 --ondisk=sda/part \/boot --fstype ext3 --size=400 --ondisk=${root_disk}/g" $KS_FILE
    sed -i "s/part biosboot --fstype=biosboot --size=1 --ondisk=sda/part biosboot --fstype=biosboot --size=1 --ondisk=${root_disk}/g" $KS_FILE

    #获取盘符列表
    get_config $CFG_FILE "disk_list"
    disk_list=$config_answer
    #修改ks文件中盘符列表
    sed -i "s/--drives=sda/--drives=${disk_list}/g" $KS_FILE
    sed -i "s/disknamelist=sda/disknamelist=${disk_list}/g" $KS_FILE

    #获取总的硬盘大小（所有扫到的盘总和），单位是M
    get_config $CFG_FILE "storage_size"
    storage_size=$config_answer
    [[ -z ${storage_size} || 0 = ${storage_size} ]] && { pxelog "[error]storage_size is invalid: ${storage_size} M!\n" "console"; return 1; }
    free_storage=${storage_size}
    pxelog "storage_size=${storage_size} M, free_storage=$free_storage M"

    #boot分区固定写死了400M，另外600M作为冗余
    ((free_storage=${free_storage}-${boot_size}-${flexible_size}))
    pxelog "boot_size=${boot_size} M, flexible_size=${flexible_size} M, free_storage=$free_storage M"

    #获取root大小，创建在根盘上，无默认值，一定要传入一个非0和非空的值，daisy判断这个分区的大小，至少50G
    get_config $CFG_FILE "root_lv_size"
    root_lv_size=$config_answer
    #如果没有配置或者配置为0，则返回失败
    [[ -z ${root_lv_size} || 0 = ${root_lv_size} ]] && { pxelog "[error]root_lv_size is invalid: ${root_lv_size} M!\n" "console"; return 1; }
    sed -i '/^logvol \/ --fstype ext4/d' $KS_FILE
    [ $root_lv_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for root size($root_lv_size M)!\n" "console"; return 1; }
    #root大小小于50G就告警
    [ $root_lv_size -lt 51200 ] && { pxelog "[error]root size is $root_lv_size M, less than 50G, not enough for system working!\n" "console"; return 1; }
    sed -i "/\#lv_root/a\logvol \/ --fstype ext4 --vgname=vg_sys --size=$root_lv_size --name=lv_root" $KS_FILE
    ((pv_01=$root_lv_size+$pv_01))
    ((free_storage=$free_storage-$root_lv_size))
    pxelog "root_lv_size=${root_lv_size} M, free_storage=$free_storage M, pv_01=$pv_01 M"

    #获取swap分区的大小，无默认值，一定要有传值，且不能为0，daisy会根据memory大小计算
    get_config $CFG_FILE "swap_lv_size"
    swap_lv_size=$config_answer
    custom_swap_size $CFG_FILE $swap_lv_size || return 1
    [[ -z ${swap_lv_size} || 0 = ${swap_lv_size} ]] && { pxelog "[error]swap_lv_size is invalid: ${swap_lv_size} M!\n" "console"; return 1; }
    [ $swap_lv_size -gt $free_storage ] && { pxelog "[error]free storage is $free_storage M, not enough for swap size($swap_lv_size M)!\n" "console"; return 1; }
     sed -i "s/logvol swap.*/logvol swap  --fstype swap  --vgname=vg_sys    --size=$swap_lv_size    --name=lv_swap/" $KS_FILE
    ((pv_01=$swap_lv_size+$pv_01))
    ((free_storage=$free_storage-$swap_lv_size))
    pxelog "swap_lv_size=${swap_lv_size} M, free_storage=$free_storage M"

    #设置pv.01，包括root_lv_size、swap_lv_size的冗余空间
    sed -i "/\#end_part/i\part pv.01 --size=$pv_01 --ondisk=${root_disk}" $KS_FILE
    pxelog "vg_sys_size equal to $pv_01 M"

    sed -i "/cindervolumes/d" $KS_FILE
    sed -i "/pv.02/d" $KS_FILE
    sed -i "/pv.03/d" $KS_FILE
    sed -i "/pv.04/d" $KS_FILE
    pxelog "started custom_ks_vg_else!\n"

    return 0
}

function custom_ks_vg
{
    pxelog "starting custom_ks_vg!\n"

    #对于我们自己的系统，需要定制vg_data，而对于其他的系统，只要能将系统安装上就可以
    if [[ $IS_TFG_ISO == "yes" ]]; then
        custom_ks_vg_tfg $@ || return 1
    else
        custom_ks_vg_else $@ || return 1
    fi
    pxelog "started custom_ks_vg!\n"

    return 0
}

# 定制ks中的绑核信息
function custom_ks_vmm
{
    local CFG_FILE=$1
    local KS_FILE=$2

    pxelog "starting custom_ks_vmm!"

    get_config $CFG_FILE "vmm_type"
    vmtype=$config_answer

    #liushn 目前vmm类型没有提供接口给上层进行配置，都默认用kvm
    if [ ! $vmtype = "xen" ];then
        sed -i "s/dom0_mem=1024M dom0_max_vcpus=2//g" $KS_FILE
    else
        get_config $CFG_FILE "cpus"
        xcpus=$config_answer
        get_config $CFG_FILE "memsize"
        xmemsize=$config_answer

        sed -i "s/dom0_mem=1024M/dom0_mem=${xmemsize}M/g" $KS_FILE
        sed -i "s/dom0_max_vcpus=2/dom0_max_vcpus=$xcpus/g" $KS_FILE
        #sed -i "s/^RPCNFSDCOUNT=[0-9]*/RPCNFSDCOUNT=32/"  $nfs_conf
    fi

    pxelog "started custom_ks_vmm!\n"
}

#定制安装完成后是否reboot
function custom_ks_reboot
{
    local CFG_FILE=$1
    local KS_FILE=$2

    pxelog "starting custom_ks_reboot!"

    get_config $CFG_FILE "reboot"
    client_reboot=$config_answer
    if [[ $client_reboot == "yes" ]] ;then
        sed -i "s/^#*reboot/reboot/g" $KS_FILE
    else
        sed -i "s/^reboot/#reboot/g" $KS_FILE
    fi

    pxelog "started custom_ks_reboot!\n"
}

function custom_ks_hugepages
{
    local CFG_FILE=$1
    local KS_FILE=$2

    pxelog "starting custom_ks_hugepages!"

    get_config $CFG_FILE "hugepages"
    pages=$config_answer
    [[ $pages == "" ]] && pages=0
    sed -i "s/pagevalue2/${pages}/g" $KS_FILE

    get_config $CFG_FILE "hugepagesize"
    sizes=$config_answer
    [[ $sizes == "" ]] && sizes="1G"
    [[ $sizes != "1G" && $sizes != "2M" ]] && { pxelog "[error]hugepagesize value error($sizes)" "console"; return 1; }
    sed -i "s/pagevalue1/${sizes}/g" $KS_FILE

    pxelog "started custom_ks_hugepages!\n"
}

function custom_ks_isolcpus
{
    local CFG_FILE=$1
    local KS_FILE=$2

    pxelog "starting custom_ks_isolcpus!"

    get_config $CFG_FILE "isolcpus"
    isolcpus=$config_answer
    if [[ $isolcpus != "" ]]; then
        sed -i "s/isolvalue/${isolcpus}/g" $KS_FILE
    else
        sed -i "/isolvalue/d" $KS_FILE
    fi

    pxelog "started custom_ks_isolcpus!\n"
}


function custom_ks_hostname
{
    local CFG_FILE=$1
    local KS_FILE=$2

    pxelog "starting custom_ks_hostname!"

    get_config $CFG_FILE "hostname"
    hostname=$config_answer
    sed -i  "/hostname/s/.*/echo \"${hostname}\"> \/etc\/hostname/"  $KS_FILE

    pxelog "started custom_ks_hostname!\n"
}

#检查nfs服务器的文件夹是否存在
function check_nfs_exports
{
    local result=0

    pxelog "starting check_nfs_exports!"

    [ `cat /etc/exports | grep -c /home/install_share` -eq 0 ] && { pxelog "/home/install_share is not exported !" "console"; result=1; }
    [ `cat /etc/exports | grep -c /tftpboot` -eq 0 ]           && { pxelog "/tftpboot is not exported !" "console"; result=1; }
    for (( i=1; i<=$ISO_MOUNT_DIR_NUM; i++))
    do
        [ `cat /etc/exports | grep -c -w "/linuxinstall/linuxinstall_$i"` -eq 0 ] && { pxelog "/linuxinstall/linuxinstall_$i is not exported !" "console"; result=1; }
    done
    pxelog "started check_nfs_exports!\n"

    return $result
}

#创建以目标安装机mac地址命名的共享文件夹，用于mount iso、存放引导程序和ks文件等
#$1:json格式的配置文件
function custom_share_folder
{
    local CFG_FILE=$1
    local dhcp_mac

    pxelog "starting custom_share_folder!"

    #获取mac地址
    get_config $CFG_FILE "dhcp_mac"
    dhcp_mac=$config_answer
    [[ -z $dhcp_mac || "0" = ${dhcp_mac} ]] && { pxelog "[error]dhcp_mac is null or 0" "console"; return 1; }
    #将mac地址的:换成-
    MACADDR=`echo $config_answer | sed "s/:/-/g"`

    #/home/install_share下创建以mac地址命名的文件夹
    INSTALLSHAREPATH=/home/install_share/${MACADDR}
    rm -rf ${INSTALLSHAREPATH} 2>/dev/null
    mkdir ${INSTALLSHAREPATH}

    #/tftpboot下创建以mac地址命名的文件夹
    rm -rf /tftpboot/pxelinux.cfg/01-${MACADDR}
    rm -rf /tftpboot/${MACADDR} 2>/dev/null
    mkdir /tftpboot/${MACADDR}

    pxelog "started custom_share_folder!\n"
    return 0
}

function repair_rsyslog_line
{
    local file=$1
    local string=$2
    local result
    local lineflag
    local is_modify=0

    result=`cat ${file} |grep "${string}"`
    if [[ ${result} == "" ]]; then
        lineflag=`grep -n "GLOBAL DIRECTIVES" ${file} | head -n 1 |awk -F':' '{print $1}'`
        sed -i "${lineflag}i ${string}" ${file}
        is_modify=1
    else
        result=`cat ${file} |grep "^[[:space:]]*${string}"`
        if [[ ${result} == "" ]]; then
           sed -i "s/.*${string}.*/${string}/g" ${file}
           is_modify=1
        fi
    fi

    return ${is_modify}
}

#设置/etc/rsyslog.conf,允许接收远程日志，并且日志文件名以ip命名，用以区分各个不同机器的日志
function custom_rsyslog
{
    local rsyslog_cfg=/etc/rsyslog.conf
    local is_modify=0

    #判断UDP相关的配置是否打开
    repair_rsyslog_line ${rsyslog_cfg} "\$ModLoad imudp" || is_modify=1
    repair_rsyslog_line ${rsyslog_cfg} "\$UDPServerRun 514" || is_modify=1
    repair_rsyslog_line ${rsyslog_cfg} "\$ModLoad imtcp" || is_modify=1
    repair_rsyslog_line ${rsyslog_cfg} "\$InputTCPServerRun 514" || is_modify=1
    repair_rsyslog_line ${rsyslog_cfg} "\$template IpTemplate,\"\/var\/log\/\%FROMHOST-IP\%.log\"" || is_modify=1
    repair_rsyslog_line ${rsyslog_cfg} "*.* \?IpTemplate" || is_modify=1
    repair_rsyslog_line ${rsyslog_cfg} "\\& ~" || is_modify=1

    [[ ${is_modify} -eq 1 ]] && { systemctl restart rsyslog.service; pxelog "rsyslog.conf repaired"; }
}


#判断是否tfg系统
function get_iso_type
{
    IS_TFG_ISO="no";

    #iso+bin形式，表示是tfg系统
    get_config $CFG_FILE "tfg_bin"
    local TFG_BIN=$config_answer
    [[ "${TFG_BIN}" != ""  &&  -e "${TFG_BIN}" ]] && IS_TFG_ISO="yes"


    #在ISOMOUNTPATH路径下判断是否有bin。
    if [[ -d ${ISOMOUNTPATH} ]];then
        local  OS_TFG_BIN=${ISOMOUNTPATH}/*.bin
        [ -e ${OS_TFG_BIN} ] && IS_TFG_ISO="yes"
    fi
}

#处理os安装的一些预处理工作:包括创建和目标机mac地址相关的文件夹，mount iso；拷贝ISO中的引导程序到根目录；拷贝ks文件、网口固化脚本文
#$1:json格式的配置文件
#$2:安装配置文件的路径
function custom_pre_cfg
{
    local CFG_FILE=$1
    local ISOPATH
    local WORKDIR=$2
    local dhcp_mac
    local INSTALL_LOG

    pxelog "starting custom_pre_cfg!"

    #创建以目标安装机mac地址命名的共享文件夹，用于mount iso、存放引导程序和ks文件等
    custom_share_folder ${CFG_FILE} || return 1

    pxelog "MACADDR=${MACADDR}"
    pxelog "INSTALLSHAREPATH=${INSTALLSHAREPATH}"

    #获取iso文件
    get_config $CFG_FILE "iso_path"
    ISOPATH=${config_answer}

    [[ -z ${ISOPATH} ]] && { pxelog "[error]iso_path is null !" "console"; return 1; }
    [[ ! -e ${ISOPATH} ]] && { pxelog "[error]iso_path ${ISOPATH} not exist !" "console"; return 1; }

    #确认iso的挂载点
    rm -rf /usr/lib/systemd/system/linuxinstall.mount 2>/dev/nul
    ISOMOUNTPATH=`mount |grep -w $ISOPATH | grep -w "/linuxinstall/linuxinstall_[0-9]*" |head -n 1| awk -F' ' '{print $3}'`
    #如果没有找到iso的挂载点那么需要选择一个未用的/linuxinstall/linuxinstall_n进行挂载
    if [[ ${ISOMOUNTPATH} == "" ]]; then
        for (( i=1; i<=$ISO_MOUNT_DIR_NUM; i++))
        do
            if [[ `mount |grep -w "/linuxinstall/linuxinstall_$i"` == "" ]]; then
                ISOMOUNTPATH=/linuxinstall/linuxinstall_$i
                #mount iso
                mount -t iso9660 ${ISOPATH} ${ISOMOUNTPATH} -o loop

                repir_iso_nfs_number $MACADDR ${ISOMOUNTPATH} "clean"   ||  return 1

                break
            fi
        done
    fi

    #所有的/linuxinstall/linuxinstall_*用完了，就报错，否则将ISOMOUNTPATH的使用数加1
    if [[ ${ISOMOUNTPATH} == "" ]]; then
        pxelog "[error]all /linuxinstall/linuxinstall_n are used, iso can't be mounted !" "console"
        return 1
    else
        pxelog "ISOMOUNTPATH=${ISOMOUNTPATH}!"

        #生成linuxinstall-linuxinstall_$i.mount并且使能
        local linuxinstall_mount=`basename ${ISOMOUNTPATH}`
        linuxinstall_mount="linuxinstall-""${linuxinstall_mount}"".mount"
        linuxinstall_mount_unit=/lib/systemd/system/$linuxinstall_mount
        pxelog "linuxinstall mount unit file=$linuxinstall_mount_unit !"
        cp -rf ${WORKDIR}/pxe/linuxinstall.mount $linuxinstall_mount_unit
        sed -i "s:What.*:What=${ISOPATH}:g" $linuxinstall_mount_unit
        sed -i "s:Where.*:Where=${ISOMOUNTPATH}:g" $linuxinstall_mount_unit
        systemctl enable $linuxinstall_mount &>/dev/null

        #修改ISOMOUNTPATH的使用数
        repir_iso_nfs_number $MACADDR ${ISOMOUNTPATH} "add"   ||  return 1
    fi

    #判断是否tfg系统
    get_iso_type

    # 拷贝内核和启动程序到为目标机创建的根目录,拷贝完需要umount
    \cp -f /${ISOMOUNTPATH}/isolinux/initrd.img        /tftpboot/${MACADDR}/
    \cp -f /${ISOMOUNTPATH}/isolinux/vmlinuz           /tftpboot/${MACADDR}/


    # 拷贝pxe的引导程序到根目录
    [ ! -e /tftpboot/pxelinux.0 ] && { \cp -f /usr/share/syslinux/pxelinux.0             /tftpboot; }

    #kickstart 拷贝出来，方便以后可不更换ISO，修改kickstart
    rm -rf ${INSTALLSHAREPATH}/*
    \cp -f ${WORKDIR}/pxe/pxe_kickstart.cfg  ${INSTALLSHAREPATH}/
    \cp -rf ${WORKDIR}/usrdata ${INSTALLSHAREPATH}/  &>/dev/null
    \cp -rf ${WORKDIR}/scripts/custom  ${INSTALLSHAREPATH}/ &>/dev/null
    rm -rf ${INSTALLSHAREPATH}/custom/interact* &>/dev/null
    \cp -f ${CFG_FILE}  ${INSTALLSHAREPATH}/os.json

    #拷贝tfg的bin文件到INSTALLSHAREPATH下面
    get_config $CFG_FILE "tfg_bin"
    tfg_bin=$config_answer
    [[ ! -z ${tfg_bin} && -e ${tfg_bin} ]] && { pxelog "tfg_bin exist!\n"; \cp -f ${tfg_bin}  ${INSTALLSHAREPATH}/; }

    #在/var/log/pxe_os_table.log下记录这个目标机
    [ ! -f $PXE_OS_TAB ] && { touch $PXE_OS_TAB; }
    [[ `cat $PXE_OS_TAB |grep "${MACADDR}"` == "" ]] && { echo "${MACADDR}    0    plan_install   ${ISOMOUNTPATH}" >>$PXE_OS_TAB; } \
                                                                || { sed -i "s%${MACADDR} .*%${MACADDR}    0    plan_install   ${ISOMOUNTPATH}%g" $PXE_OS_TAB; }

    #网口固化和网络配置的脚本拷贝出来，用于后续根据jason文件定制固化规则以及网口配置
    \cp -f ${WORKDIR}/scripts/nic_net_cfg.sh  ${INSTALLSHAREPATH}/usrdata/

    #服务器启动接收远程日志的功能，用于接收目标机安装过程中的日志
    custom_rsyslog

    #清空目标机所有的历史日志记录
    get_config $CFG_FILE "dhcp_mac"
    dhcp_mac=$config_answer
    clean_mac_all_log ${dhcp_mac}

    pxelog "started custom_pre_cfg!\n"

    return 0
}

#生成default文件
function custom_default_cfg
{
    local CFG_FILE=$1
    local WORKDIR=$2
    local DEFAULT_CFG=/tftpboot/pxelinux.cfg/01-${MACADDR}
    local KS_FILE=${INSTALLSHAREPATH}/pxe_kickstart.cfg

    pxelog "starting custom_default_cfg!"

    #拷贝default文件到/tftpboot/pxelinux.cfg文件夹，并且改成以mac地址命名的文件
    [ ! -d /tftpboot/pxelinux.cfg ] && { mkdir -p /tftpboot/pxelinux.cfg; }
    cp -rf ${WORKDIR}/pxe/default ${DEFAULT_CFG}


    #获取pxe服务器的监听地址
    local svrip=`cat /etc/dhcp/dhcpd.conf | grep next-server |awk -F' ' '{print $2}' |sed "s/;//"`

    #修改defult文件，涉及kernel文件和initrd相对于/tftpboot的存放位置，ks文件存放位置
    sed -i "s%kernel vmlinuz%kernel ${MACADDR}/vmlinuz%g" ${DEFAULT_CFG}
    sed -i "s%initrd=initrd.img%initrd=${MACADDR}/initrd.img%g" ${DEFAULT_CFG}
    sed -i "s%nfs:.*:.*pxe_kickstart.cfg%nfs:$svrip:${KS_FILE}%g" ${DEFAULT_CFG}

    pxelog "started custom_default_cfg!\n"
    return 0
}

function custom_ks_server_ip
{
    local KS_FILE=$1

    pxelog "starting custom_ks_server_ip!"

    #获取pxe服务器的监听地址
    local svrip=`cat /etc/dhcp/dhcpd.conf | grep next-server |awk -F' ' '{print $2}' |sed "s/;//"`

    #修改ks文件中nfs服务器ip
    sed -i "s/ntpdate -s.*/ntpdate -s $svrip\" >> \/var\/spool\/cron\/root/g"  $KS_FILE
    sed -i "s%nfs --server=.*--dir=%nfs --server=$svrip --dir=%g" 	$KS_FILE
    sed -i "s/NFS_SERVER_ADDRESS=.*/NFS_SERVER_ADDRESS=$svrip/g"    $KS_FILE

    #修改ks文件中logging主机ip
    sed -i "s/logging --host=.*--level=/logging --host=$svrip --port=514 --level=/g"    $KS_FILE

    pxelog "started custom_ks_server_ip!\n"

    return 0
}

function custom_ks_nfs_dir
{
    local KS_FILE=$1

    pxelog "starting custom_ks_nfs_dir!"

    #修改ks文件中和目标机mac地址相关的文件夹或者目录
    sed -i "s%macaddr%${MACADDR}%g"  $KS_FILE


    #修改ks文件中iso挂载点
    sed -i "s%iso_nfs_dir%${ISOMOUNTPATH}%g"  $KS_FILE

    pxelog "started custom_ks_nfs_dir!\n"
    return 0
}


#######################
#从json配置文件读取网口相关参数，并且修改网口固化和网口配置脚本NET_FILE，改写ks文件，在post阶段执行NET_FILE
#######################
function custom_ks_net_config
{
    local CFG_FILE=$1
    local KS_FILE=$2
    local NET_FILE=$3

    pxelog "starting custom_ks_net_config!"

    [ ! -e $CFG_FILE ] && { pxelog "[error]file ${CFG_FILE} not exist!" "console"; return 1; }
    [ ! -e $KS_FILE ] && { pxelog "[error]file ${KS_FILE} not exist!" "console"; return 1; }
    [ ! -e $NET_FILE ] && { pxelog "[error]file ${NET_FILE} not exist!" "console"; return 1; }

    local length=$(cat $CFG_FILE | jq '.interfaces[].name' | wc -l)
    pxelog "interfaces length=$length"
    for (( i=0; i<length; i++))
    do
        pxelog "interface[$i]"
        get_config $CFG_FILE "interfaces[$i].name"
        local eth_name=$config_answer
        get_config $CFG_FILE "interfaces[$i].type"
        local eth_type=$config_answer
        get_config $CFG_FILE "interfaces[$i].pci"
        local eth_pci=$config_answer
        local eth_gateway=""
        local eth_ip=""
        local eth_netmask=""
        local management_gateway=""
        local management_ip=""
        local management_netmask=""
        local network_type=""
        local vlan_id=""
        #从interfaces[$i]中获取管理面的ip、netmask、gateway
        local length2=$(cat $CFG_FILE | jq ".interfaces[$i].assigned_networks[].network_type" | wc -l)
        pxelog "assigned_networks length=$length2"
        if [ $length2 -eq 0 ];then
            network_type="MANAGEMENT"
        else
            for (( j=0; j<length2; j++))
            do
                get_config $CFG_FILE "interfaces[$i].assigned_networks[$j].network_type"
                network_type=$config_answer
                if [[ $network_type = "MANAGEMENT" ]]; then
                    get_config $CFG_FILE "interfaces[$i].assigned_networks[$j].ip"
                    management_ip=$config_answer
                    get_config $CFG_FILE "interfaces[$i].assigned_networks[$j].netmask"
                    management_netmask=$config_answer
                    get_config $CFG_FILE "interfaces[$i].assigned_networks[$j].gateway"
                    management_gateway=$config_answer
                    get_config $CFG_FILE "interfaces[$i].assigned_networks[$j].vlan_id"
                    vlan_id=$config_answer
                    break 1
                fi
            done
        fi
        #只对管理口配置ip、netmask、gateway
        if [[ $network_type = "MANAGEMENT" ]]; then
            get_config $CFG_FILE "interfaces[$i].ip"
            eth_ip=$config_answer
            get_config $CFG_FILE "interfaces[$i].netmask"
            eth_netmask=$config_answer
            get_config $CFG_FILE "interfaces[$i].gateway"
            eth_gateway=$config_answer
            # 先判断interfaces[$i]的ip、netmask是否为空，如果为空就用管理面配置的ip、netmask、gateway
            # 如果管理面的ip、netmask也为空那么就报错，返回1
            if [[ $eth_ip = "" || $eth_netmask = "" ]]; then
                if [ $management_ip = "" -o $management_netmask = "" -a $length2 -ne 0 ]; then
                     pxelog "[error]interfaces[$i] ip/netmask is null, please check!" "console"
                     return 1
                else
                    eth_ip=$management_ip
                    eth_netmask=$management_netmask
                    eth_gateway=$management_gateway
                fi
            fi
        fi
        pxelog "eth_name=$eth_name"
        pxelog "eth_type=$eth_type"
        pxelog "eth_pci=$eth_pci"
        pxelog "eth_ip=$eth_ip"
        pxelog "eth_netmask=$eth_netmask"
        pxelog "eth_gateway=$eth_gateway"
        pxelog "network_type=$network_type"
        pxelog "vlan_id=$vlan_id"

        #在NET_FILE 后面追加第i个网口的网口固化规则和网口配置
        echo "#config $eth_name" >> $NET_FILE

        #如果网口类型是ether，那么直接做网口配置
        if [[ $eth_type = "ether" ]];then
            echo "eth_nicfix \"$eth_name\"  \"$eth_pci\"" >> $NET_FILE
            if [[ $vlan_id != "" ]]; then
                echo "vlan_config \"$eth_name\" \"$vlan_id\" \"$eth_ip\" \"$eth_netmask\" \"$eth_gateway\"" >> $NET_FILE
                echo "eth_config \"$eth_name\" \"\" \"\" \"\" \"\"" >> $NET_FILE
            else
                echo "eth_config \"$eth_name\" \"$eth_ip\" \"$eth_netmask\" \"$eth_gateway\" \"\"" >> $NET_FILE
            fi
        fi

        #如果网口类型是bond，且有管理面，那么做bond配置
        if [[ $eth_type = "bond" && $network_type = "MANAGEMENT" ]];then
            get_config $CFG_FILE "interfaces[$i].mode"
            local eth_mode=$config_answer
            get_config $CFG_FILE "interfaces[$i].slave1"
            local eth_slave1=$config_answer
            get_config $CFG_FILE "interfaces[$i].slave2"
            local eth_slave2=$config_answer
            pxelog "eth_mode=$eth_mode"
            pxelog "eth_slave1=$eth_slave1"
            pxelog "eth_slave2=$eth_slave2"
            if [[ $vlan_id != "" ]]; then
                echo "vlan_config \"$eth_name\" \"$vlan_id\" \"$eth_ip\" \"$eth_netmask\" \"$eth_gateway\"" >> $NET_FILE
                echo "bond_config \"$eth_name\" \"\" \"\" \"\" \"$eth_mode\" \"$eth_slave1\" \"$eth_slave2\"" >> $NET_FILE
            else
                echo "bond_config \"$eth_name\" \"$eth_ip\" \"$eth_netmask\" \"$eth_gateway\" \"$eth_mode\" \"$eth_slave1\" \"$eth_slave2\"" >> $NET_FILE
            fi
        fi

        echo  >> $NET_FILE
    done

    pxelog "started custom_ks_net_config!\n"
    return 0
}

#添加package组，非tfg版本添加Base组。tfg版本仅仅使用Core组
function custom_ks_package_group
{
    local CFG_FILE=$1
    local KS_FILE=$2
    #非tfg版本，添加Base组

    pxelog "starting custom_ks_package_group!\n"

    get_config $CFG_FILE "group_list"
    group_list=$config_answer
    group_list_array=`echo ${group_list} |sed "s/,/ /g"`
    pxelog "group_list_array=${group_list_array}"

    if [[ $IS_TFG_ISO != "yes" ]] ;then
        for i in ${group_list_array}
        do
            if [[ $i != "Core" ]];then
                sed -i "/\@Core/a\@$i"  $KS_FILE ;
                pxelog "add @$i in %packages of pxe_kickstart.cfg"
            fi
        done
    fi
    pxelog "started custom_ks_package_group!\n"

    return 0

}

#生成ks文件
function custom_ks_cfg
{
   local CFG_FILE=$1
   local KS_FILE=${INSTALLSHAREPATH}/pxe_kickstart.cfg
   local NET_FILE=${INSTALLSHAREPATH}/usrdata/nic_net_cfg.sh

   pxelog "starting custom_ks_cfg!"

   custom_ks_server_ip $KS_FILE
   custom_ks_nfs_dir $KS_FILE
   custom_ks_rootpwd $CFG_FILE $KS_FILE
   custom_ks_vg  $CFG_FILE $KS_FILE || return 1
   custom_ks_vmm $CFG_FILE $KS_FILE
   custom_ks_reboot $CFG_FILE $KS_FILE
   custom_ks_hugepages $CFG_FILE $KS_FILE  || return 1
   custom_ks_hostname $CFG_FILE $KS_FILE
   custom_ks_net_config $CFG_FILE $KS_FILE $NET_FILE || return 1
   custom_ks_isolcpus $CFG_FILE $KS_FILE
   custom_ks_package_group $CFG_FILE $KS_FILE

   pxelog "started custom_ks_cfg!\n"
   return 0
}
