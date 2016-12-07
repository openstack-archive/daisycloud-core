##此脚本用来一键式执行/home/opencos_install/目录下的shell脚本
##将脚本用户shell脚本文件放入/home/opencos_install/目录下，执行./before.sh就可以执行所有/home/opencos_install/脚本的脚本
GUARD_DIR=/home/opencos_install/custom/before
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
echo before>>/var/log/log.txt
[ $RETVAL -eq 0 ] && sed -i "/before.sh/d" /etc/rc.d/rc.local




