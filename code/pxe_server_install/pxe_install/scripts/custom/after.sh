##此脚本用来一键式执行/home/opencos_install/after目录下的shell脚本
##将脚本用户shell脚本文件放入/home/usrdata/目录下，执行./after.sh就可以执行所有/home/opencos_install/after脚本
GUARD_DIR=/home/opencos_install/custom/after
[ ! -d $GUARD_DIR ] && exit 0
cd $GUARD_DIR
ALL_FILE=`ls $GUARD_DIR|grep .sh$`
RETVAL=
for FILE in $ALL_FILE
do    
    chmod +x $FILE
    bash $FILE
    RETVAL=$?
done
rpm -qi openstack-neutron-openvswitch >/dev/null && sed -i "/after.sh/d" /etc/rc.d/rc.local && sed -i "/sleep 30/d" /etc/rc.d/rc.local




