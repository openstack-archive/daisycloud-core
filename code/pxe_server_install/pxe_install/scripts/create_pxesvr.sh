#! /bin/bash

WORKDIR=/etc/pxe_install
source $WORKDIR/scripts/common.sh
source $WORKDIR/scripts/interface.sh
PXE_CFG=$2

#准备工作，安装json文件解析工具jq包
rpm -qi jq >/dev/null 
[ $? -ne 0 ] && rpm -ivh ${WORKDIR}/pxe/jq-1.3-2.el7.x86_64.rpm

#准备和清理文件夹
# 创建/linuxinstall以及清除里面的内容
systemctl disable linuxinstall.mount &>/dev/null 
systemctl stop linuxinstall.mount &>/dev/null 


umount -l /linuxinstall &>/dev/null
for (( i=1; i<=$ISO_MOUNT_DIR_NUM; i++))
do
    [ ! -d /linuxinstall/linuxinstall_$i ] && mkdir -p /linuxinstall/linuxinstall_$i
    systemctl disable linuxinstall-linuxinstall_$i.mount &>/dev/null 
    systemctl stop linuxinstall-linuxinstall_$i.mount &>/dev/null
    umount -l /linuxinstall/linuxinstall_$i &>/dev/null
    rm -rf /linuxinstall/linuxinstall_$i/* &>/dev/null
done

# 创建/home/install_share以及清除里面的内容
[ ! -d /home/install_share ] && mkdir -p /home/install_share
rm -rf /home/install_share/* 2>/dev/null

# 创建/tftpboot以及清除里面的内容
[ ! -d /tftpboot ] && mkdir /tftpboot
rm -rf /tftpboot/* 2>/dev/null

# 设置dhcp服务端ip地址
pxelog "set dhcp ip..." "console"
#set_svrip $WORKDIR/pxe/pxe_env.conf

set_svrip $PXE_CFG

# 安装pxe服务器组件
pxelog "install pxe..." "console"
PXE_FILE_PATH=$WORKDIR/pxe
install_pxe $PXE_FILE_PATH

# 网络文件共享
pxelog "config nfs..." "console"
systemctl stop nfs

# 查看/etc/exports是否有#注释标记，如果有的话，则进行清理
install_share_dir=`cat /etc/exports | grep /home/install_share | grep \#`
[ -n "$install_share_dir" ] && sed -i "\/home\/install_share/d" /etc/exports

tftpboot_dir=`cat /etc/exports | grep /tftpboot | grep \#`
[ -n "$tftpboot_dir" ] && sed -i "\/tftpboot/d" /etc/exports

linuxinstall_dir=`cat /etc/exports | grep /linuxinstall | grep \#`
[ -n "$linuxinstall_dir" ] && sed -i "\/linuxinstall/d" /etc/exports

linuxinstall_dir=`cat /etc/exports | grep -w "/linuxinstall "`
[ -n "$linuxinstall_dir" ] && sed -i "\/linuxinstall/d" /etc/exports


#/* 启动文件共享 */
[ `cat /etc/exports | grep -c /home/install_share` -eq 0 ] && { echo "/home/install_share *(rw,no_root_squash)">> /etc/exports; } \
             || { sed -i "s%/home/install_share.*%/home/install_share *(rw,no_root_squash)%g" /etc/exports; }
[ `cat /etc/exports | grep -c /tftpboot` -eq 0 ]           && { echo "/tftpboot *(ro)"      >> /etc/exports; } \
             || { sed -i "s%/tftpboot.*%/tftpboot *(ro)%g" /etc/exports; }
for (( i=1; i<=$ISO_MOUNT_DIR_NUM; i++))
do
    [ `cat /etc/exports | grep -c -w "/linuxinstall/linuxinstall_$i"` -eq 0 ]  && { echo "/linuxinstall/linuxinstall_$i *(ro)"  >> /etc/exports; } \
             || { sed -i "s%\/linuxinstall\/linuxinstall_$i .*%\/linuxinstall\/linuxinstall_$i *(ro)%g" /etc/exports; }
done

#创建一张表格，存放10个iso的nfs路径以及当前被使用的次数
rm -f $ISO_NFS_TAB &>/dev/null
touch $ISO_NFS_TAB
echo "iso_mount_point                    used" >>$ISO_NFS_TAB
for (( i=1; i<=$ISO_MOUNT_DIR_NUM; i++))
do
    echo "/linuxinstall/linuxinstall_$i        0" >>$ISO_NFS_TAB
done

# 拷贝ISO中的引导程序到根目录
if [  -f "$WORKDIR/ramdisk/initrd.img" ]; then 
cp -f $WORKDIR/ramdisk/initrd.img        /tftpboot/
fi 

if [  -f "$WORKDIR/ramdisk/vmlinuz"  ]; then 
cp -f $WORKDIR/ramdisk/vmlinuz           /tftpboot/
fi 

cp -f /usr/share/syslinux/pxelinux.0           /tftpboot/


# 定制pxe配置文件，包括ks文件. 修改的文件路径：/home/install_share/pxe_kickstart.cfg
#custom_pxecfg $WORKDIR/pxe/pxe_env.conf
custom_pxecfg $PXE_CFG


#启动pxe服务器
start_pxesvr
 
