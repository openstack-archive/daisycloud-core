#!/bin/bash
#********
#  This file is used to develop tempest environment
#
#  1 please copy it to the modules you want to 
#    such as: cp tempest_envir_conf_install.sh tempest-master/
#  2 then run the bash, tempests environment can be developed
#
#  note: this bash only support CGSLV5
#*****
log_path=logs
mkdir -p $log_path
testday=`date +"%Y-%m-%d-%H-%M-%S"`
errfile=$log_path/err-$testday.txt



Install_version=`uname -a`
Right_version="3.10"
result=$(echo $Install_version | grep "${Right_version}")
if [[ "$result" == "" ]]
then
    echo "only support CGSLV5,please change your version first...">>$log_path/install_venv.err
    exit 1
fi

rm -rf /etc/yum.repos.d/opencos.repo
opencos_repo=/etc/yum.repos.d/opencos.repo
echo "Create $opencos_repo ..."
echo "[opencos]">>$opencos_repo
echo "name=opencos">>$opencos_repo
echo "baseurl=http://10.43.177.160/pypi/">>$opencos_repo
echo "enabled=1">>$opencos_repo
echo "gpgcheck=0">>$opencos_repo

rm -rf ~/.pip/pip.conf
pip_config=~/.pip/pip.conf
echo "Create $pip_config ..."
if [ ! -d `dirname $pip_config` ]; then
    mkdir -p `dirname $pip_config`
fi
echo "[global]">$pip_config
echo "find-links = http://10.43.177.160/pypi">>$pip_config
echo "no-index = true">>$pip_config

rm -rf ~/.pydistutils.cfg
pydistutils_cfg=~/.pydistutils.cfg
echo "Create $pydistutils_cfg ..."
echo "[easy_install]">$pydistutils_cfg
echo "index_url = http://10.43.177.160/pypi">>$pydistutils_cfg


modules=(virtualenv mariadb-devel testtools testrepository testresources fixtures python-subunit testscenarios postgresql-devel oslo.serialization oslo.utils libffi-devel
         cyrus-sasl-devel sqlite-devel libxslt-devel openldap-devel)

yum clean all 1>/dev/null 2>/dev/null
# for virtual environment demand pip version>=1.6, so install it whether installed. 
yum --disablerepo=* --enablerepo=opencos install -y pip extras 1>$log_path/$mod.log 2>$log_path/$mod.err
# install modules	
echo "install modules">>$log_path/install_venv.log	
for mod in ${modules[@]}; do
    echo -n "yum install $mod ... "
    already_install=`rpm -qa | grep $mod`
    if [ "$already_install" == "" ]; then
        yum --disablerepo=* --enablerepo=opencos install -y $mod 1>$log_path/$mod.log 2>$log_path/$mod.err
        if [ -s $log_path/$mod.err ]; then
            echo "fail!"
	    echo "Install $mod fail! Please manually using the yum installation package,commond is \"yum install $mod\"">>$log_path/install_venv.err
           # exit 1
        else
            echo "ok(install finish)"
        fi
    else
        echo "ok(already exist)"
    fi
done

#echo "install venv ... ">>$log_path/install_venv.log
#chmod +x tools/*
#python tools/install_venv.py 1>$log_path/install_venv.log 2>$log_path/install_venv.err
#if grep "development environment setup is complete." $log_path/install_venv.log
#   then
#      echo "development environment setup is complete...">>$log_path/install_venv.log
#else
#  echo "development environment setup is fail,please check $log_path/install_venv.err"
#  cat  $log_path/install_venv.err
##  exit 1
#fi

echo "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@"
echo "copy tempest.conf.sample to tempest.conf....."
tempestconf=etc/tempest.conf
if [ ! -e $tempestconf ];then
   cp etc/tempest.conf.sample etc/tempest.conf 2>>err.txt
fi

source /root/keystonerc_admin

#######Tempest CONF#######

#######[DEFAULT]#######
echo "config tempest.conf DEFAULT lock_path /tmp"
openstack-config --set $tempestconf DEFAULT lock_path /tmp 2>>$errfile

echo "config tempest.conf DEFAULT log_file tempest.log"
openstack-config --set $tempestconf DEFAULT log_file tempest.log 2>>$errfile

########[identity]########
if [  ! -n "`keystone user-list 2>>$errfile | grep -w Member`" ]; then
    keystone user-create --name Member 2>>$errfile
fi

if [ ! -n "`keystone role-list 2>>$errfile | grep -w Member`" ]; then
	keystone role-create --name Member 2>>$errfile
fi

if [ ! -n "`keystone tenant-list 2>>$errfile |grep -w demo`" ]; then
    keystone  tenant-create --name demo --enabled true 2>>$errfile
fi

if [ ! -n  "`keystone user-list 2>>$errfile |grep -w demo`" ]; then
    keystone  user-create --name demo --tenant demo --pass secret --enabled true 2>>$errfile
fi

if [ ! -n  "`keystone tenant-list 2>>$errfile |grep -w alt_demo`" ]; then
    keystone  tenant-create --name alt_demo --enabled true 2>>$errfile
fi

if [ ! -n  "`keystone user-list 2>>$errfile |grep -w alt_demo`" ]; then
    keystone  user-create --name alt_demo --tenant alt_demo --pass secret --enabled true 2>>$errfile
fi

openstack-config --set $tempestconf identity admin_username admin 2>>$errfile
openstack-config --set $tempestconf identity admin_role admin 2>>$errfile
openstack-config --set $tempestconf identity admin_tenant_name admin 2>>$errfile
openstack-config --set $tempestconf identity admin_password keystone 2>>$errfile
openstack-config --set $tempestconf identity alt_tenant_name alt_demo 2>>$errfile
openstack-config --set $tempestconf identity alt_username  alt_demo 2>>$errfile
openstack-config --set $tempestconf identity alt_password secret 2>>$errfile
openstack-config --set $tempestconf identity tenant_name  demo 2>>$errfile
openstack-config --set $tempestconf identity username  demo 2>>$errfile
openstack-config --set $tempestconf identity password  secret 2>>$errfile
openstack-config --set $tempestconf identity auth_version v2  2>>$errfile
openstack-config --set $tempestconf identity catalog_type identity  2>>$errfile
openstack-config --set $tempestconf identity endpoint_type  publicURL  2>>$errfile
openstack-config --set $tempestconf identity region  RegionOne 2>>$errfile
openstack-config --set $tempestconf identity uri  http://127.0.0.1:5000/v2.0/ 2>>$errfile
openstack-config --set $tempestconf identity uri_v3  http://127.0.0.1:5000/v3/  2>>$errfile

#######[cli]#######
openstack-config --set $tempestconf cli cli_dir /usr/bin 2>>$errfile

#######[compute]#######
openstack-config --set $tempestconf compute build_timeout 300 2>>$errfile
openstack-config --set $tempestconf compute run_ssh true 2>>$errfile
openstack-config --set $tempestconf compute ssh_auth_method adminpass 2>>$errfile
openstack-config --set $tempestconf compute ssh_user cirros 2>>$errfile
openstack-config --set $tempestconf compute image_ssh_user cirros 2>>$errfile
openstack-config --set $tempestconf compute image_ssh_password cubswin:\) 2>>$errfile

if [ ! -n "`glance image-list 2>>$errfile |grep -w cirros_icehouse_test |awk '{print $2}'`" ]; then
glance image-create --name cirros_icehouse_test --is-public true --disk-format qcow2  --copy-from  http://10.43.175.61:8081/files/linux/cirros-0.3.0-x86_64-disk.img 2>>$errfile
fi

if [ ! -n "`glance image-list 2>>$errfile |grep -w cirros_icehouse_test_alt |awk '{print $2}'`" ]; then
glance image-create --name cirros_icehouse_test_alt  --is-public true --disk-format qcow2  --copy-from  http://10.43.175.61:8081/files/linux/cirros-0.3.2-x86_64-disk.img 2>>$errfile
fi

IMAGE=`glance image-list 2>>$errfile |grep -w cirros_icehouse_test |awk -F " " '{print $2}'`
IMAGE_ALT=`glance image-list 2>>$errfile |grep -w cirros_icehouse_test_alt |awk -F " " '{print $2}'`

openstack-config --set $tempestconf compute image_ref $IMAGE 2>>$errfile
openstack-config --set $tempestconf compute image_ref_alt $IMAGE_ALT 2>>$errfile

#CONF.compute.flavor_ref
FLAVORNAME=m1.tiny
FLAVORALT=m1.small
FLAVORID=`nova flavor-list 2>>$errfile |grep -w $FLAVORNAME |awk  '{print $2}'`
FLAVORALTID=`nova flavor-list 2>>$errfile |grep -w $FLAVORALT |awk  '{print $2}'`
openstack-config --set $tempestconf compute flavor_ref $FLAVORID 2>>$errfile
openstack-config --set $tempestconf compute flavor_ref_alt $FLAVORALTID 2>>$errfile

#######[dashboard]#######
openstack-config --set $tempestconf dashboard dashboard_url http://localhost/dashboard/ 2>>$errfile
openstack-config --set $tempestconf dashboard login_url http://localhost/dashboard/auth/login/ 2>>$errfile

#######[service_available]#######
openstack-config --set $tempestconf service_available ceilometer false 2>>$errfile
openstack-config --set $tempestconf service_available cinder true 2>>$errfile
openstack-config --set $tempestconf service_available glance true 2>>$errfile
openstack-config --set $tempestconf service_available heat false 2>>$errfile
openstack-config --set $tempestconf service_available horizon true 2>>$errfile
openstack-config --set $tempestconf service_available ironic false 2>>$errfile
openstack-config --set $tempestconf service_available neutron true 2>>$errfile
openstack-config --set $tempestconf service_available nova true 2>>$errfile
openstack-config --set $tempestconf service_available sahara false 2>>$errfile
openstack-config --set $tempestconf service_available swift false 2>>$errfile
openstack-config --set $tempestconf service_available trove false 2>>$errfile
openstack-config --set $tempestconf service_available zaqar false 2>>$errfile


if [ -s err.txt ];then
    cat err.txt
    exit 1
fi
 
echo "tempest envirmonent and tempest.conf config successful..."
exit 0
