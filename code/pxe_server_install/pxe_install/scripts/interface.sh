#!/bin/bash
WORKDIR=/etc/pxe_install
source $WORKDIR/scripts/setup_func.sh
#source ./pxe_func.sh
source $WORKDIR/scripts/custom/interact.sh



#######################
#为pxe server设置ip
#######################
function set_svrip
{
	local ENV_CFG=$1
	
	# 解析配置文件，获取dhcp服务守护的网卡名
	get_config $ENV_CFG "ethname_l"
	nic4dhcp=$config_answer
	
	# 获取网卡信息
	get_config $ENV_CFG "ip_addr_l"
	ipaddr=$config_answer
	get_config $ENV_CFG "net_mask_l"
	netmask=$config_answer
	pxelog "netmask is $netmask" "console"
	
	# 把多余的网口地址给清理掉
	for i in `ls /sys/class/net/`
	do
		is_link=`readlink /sys/class/net/$i | grep -c '/'`
		if [[ $is_link -eq 0 ]]; then
			continue
		fi    
		        
		if [ `ifconfig | grep -c $i:100` -eq 0 ]; then
			continue
		fi
		
		
		if [ `ifconfig $i:100 | grep -c "$ipaddr"` -eq 0 ]; then
			continue
		fi
		
		ifconfig $i:100 | grep -c "$ipaddr"
		
		ifconfig $i:100 0
		rm -rf /etc/sysconfig/network-scripts/ifcfg-"$i":100
	done

	# 为服务端配置ip地址，重启后有效
	[[ `ifconfig $nic4dhcp |grep flag |grep -w UP` == "" ]] && ifconfig $nic4dhcp up
	ifconfig $nic4dhcp:100 $ipaddr netmask $netmask up
		
	nicfile=/etc/sysconfig/network-scripts/ifcfg-"$nic4dhcp":100
	
	touch $nicfile
	echo "DEVICE=\"$nic4dhcp:100\""   >  $nicfile
	echo "BOOTPROTO=\"static\""       >> $nicfile
	echo "ONBOOT=\"yes\""             >> $nicfile
	echo "IPADDR=$ipaddr"             >> $nicfile
	echo "NETMASK=$netmask"           >> $nicfile

}

#######################
#安装pxe组件
#######################
function install_pxe
{
	local pxedir=$1
	cd $pxedir
	
	#/* 安装tftp 的RPM包 */
	rpm -qi xinetd >/dev/null 
	[ $? -ne 0 ] && rpm -ivh ./xinetd-2.3.15-12.el7.x86_64.rpm	
	rpm -qi tftp-server >/dev/null 
	[ $? -ne 0 ] && rpm -ivh ./tftp-server-5.2-11.el7.x86_64.rpm	
	rpm -qi tftp >/dev/null 
	[ $? -ne 0 ] && rpm -ivh ./tftp-5.2-11.el7.x86_64.rpm

	#/* 安装PXE包 */
	rpm -qi ipxe-roms-qemu >/dev/null 
	[ $? -ne 0 ] && rpm -ivh ./ipxe-roms-qemu-20130517-5.gitc4bce43.el7.noarch.rpm
	rpm -qi syslinux >/dev/null 
	[ $? -ne 0 ] && rpm -ivh ./syslinux-4.05-8.el7.x86_64.rpm

	#/* 安装DHCP包 */
	rpm -qi dhcp-common >/dev/null 
	[ $? -ne 0 ] && rpm -ivh ./dhcp-common-4.2.5-27.el7.x86_64.rpm	
	rpm -qi dhcp >/dev/null 
	[ $? -ne 0 ] && rpm -ivh ./dhcp-4.2.5-27.el7.x86_64.rpm

	#/* 安装ntpdate包 */	
	rpm -qi ntpdate >/dev/null 
	[ $? -ne 0 ] && rpm -ivh ./ntpdate-4.2.6p5-18.el7.x86_64.rpm
	
	# 配置tftp
	mkdir -p /tftpboot/pxelinux.cfg/

	# 拷贝当前目录下的tftp文件到 xinetd.d下面
	cp -rf ./tftp /etc/xinetd.d/

	cp -rf default /tftpboot/pxelinux.cfg/default
	
    cp -rf ./dhcpd.conf  /etc/dhcp
	
}


#######################
#定制pxe配置文件，需要修改dhcpd.conf/default
#######################
function custom_pxecfg
{
        pxelog "custom_pxecfg..." "console"
	local ENV_CFG=$1
	local DHCP_CFG=/etc/dhcp/dhcpd.conf
	local DEFAULT_CFG=/tftpboot/pxelinux.cfg/default
	
	get_config $ENV_CFG "ip_addr_l"
	svrip=$config_answer
	
	get_config $ENV_CFG "net_mask_l"
	mask=$config_answer

	subnet=`ipcalc -n "$svrip" "$mask" |awk -F'=' '{print $2}'`
	get_config $ENV_CFG "client_ip_begin"
	begin=$config_answer
	
	get_config $ENV_CFG "client_ip_end"
	end=$config_answer

	#sed -i "s/nfs:.*:\//nfs:$svrip:\//g"  	                        $DEFAULT_CFG
	#将default下的ks配置删除，增加dhcp_ip的配置
	sed -i "s/ks=.*pxe_kickstart.cfg/dhcp_ip=$svrip/g" $DEFAULT_CFG
	
	sed -i "s/next-server.*/next-server $svrip;/g"                  $DHCP_CFG
	
	sed -i "s/subnet.*netmask.*{/subnet $subnet netmask $mask {/g"  $DHCP_CFG
	
	sed -i "s/option routers.*;/option routers $svrip;/g"  	        $DHCP_CFG
	sed -i "s/option subnet-mask.*;/option subnet-mask $mask;/g"  	$DHCP_CFG
	sed -i "s/range.*;/range $begin $end;/g"                        $DHCP_CFG

}

#######################
#启动pxe服务
#######################
function start_pxesvr
{
	# 关闭防火墙
	service iptables stop

	#/* 启动NFS服务 */
	service nfs restart

	#/* 启动PXE服务 */
	service xinetd restart

	#/* 启动DHCP服务 */
	if [ `service dhcpd status | grep -c running` == 0 ]; then
		service dhcpd restart
		pxelog "Inatall Environment Prepare Success! Have fun!" "console"
	else
		service dhcpd restart
		pxelog "Warning............................" "console"
		pxelog "Warning............................" "console"
		pxelog "Warning: other DHCP is Running. Restart DHCP....." "console"
		pxelog "Please Check Current Dhcp config. Sure Current Dhcp Can Auto Install ISO" "console"
		pxelog "Warning............................" "console"
		pxelog "Warning............................" "console"
	fi

	# 设置pxe相关服务为开机自启动 --added by xuyang
	chkconfig  --level 2345 nfs-server  on
	chkconfig  --level 2345 xinetd on
	chkconfig  --level 2345 dhcpd  on
	chkconfig  --level 2345 iptables  off
}

#pxe从上层目录的usrdata拷贝第三方文件到系统
#拷贝到服务器的/home/install_share
