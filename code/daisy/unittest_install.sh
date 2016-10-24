#!/bin/bash
#********
#  This file is used to develop unittest environment
#
#  1 please copy it to the modules you want to 
#    such as: cp unittest_install.sh ../../openstack/keystone/
#  2 then run the bash, unittest environment can be developed
#
#  note: this bash only support CGSLV5
#*****
Install_version=`uname -a`
Right_version="3.10"
result=$(echo $Install_version | grep "${Right_version}")
if [[ "$result" == "" ]]
then
    echo "only support CGSLV5,please change your version first..."
    exit 1
fi

pip_ip=10.43.178.177

log_path=logs
mkdir -p $log_path

rm -rf /etc/yum.repos.d/opencos.repo
opencos_repo=/etc/yum.repos.d/opencos.repo
echo "Create $opencos_repo ..."
echo "[opencos]">>$opencos_repo 
echo "name=opencos">>$opencos_repo
echo "baseurl=http://$pip_ip/pypi/">>$opencos_repo 
echo "enabled=1">>$opencos_repo 
echo "gpgcheck=0">>$opencos_repo

rm -rf ~/.pip/pip.conf
pip_config=~/.pip/pip.conf
echo "Create $pip_config ..."
if [ ! -d `dirname $pip_config` ]; then
    mkdir -p `dirname $pip_config`
fi
echo "[global]">$pip_config
echo "find-links = http://$pip_ip/pypi">>$pip_config
echo "no-index = true">>$pip_config
echo "[install]">>$pip_config
echo "trusted-host = $pip_ip">>$pip_config

rm -rf ~/.pydistutils.cfg
pydistutils_cfg=~/.pydistutils.cfg
echo "Create $pydistutils_cfg ..."
echo "[easy_install]">$pydistutils_cfg
echo "index_url = http://$pip_ip/pypi">>$pydistutils_cfg


modules=(virtualenv mariadb-devel postgresql-devel libffi-devel  m2crypto openssl-devel 
         cyrus-sasl-devel sqlite-devel libxslt-devel openldap-devel mongodb-server)

yum clean all 1>/dev/null 2>/dev/null
# for virtual environment demand pip version>=1.6, so install it whether installed. 
yum --disablerepo=* --enablerepo=opencos install -y pip 1>$log_path/pip.log 2>$log_path/pip.err	
yum --disablerepo=* --enablerepo=opencos install -y swig 1>$log_path/swig.log 2>$log_path/swig.err	
yum --disablerepo=* --enablerepo=opencos install -y openstack-ceilometer-api 1>$log_path/ceilometer-api.log \
                                                                             2>$log_path/ceilometer-api.err	
# install modules
for mod in ${modules[@]}; do
    echo -n "yum install $mod ... "
    already_install=`rpm -qa | grep $mod`
    if [ "$already_install" == "" ]; then
        yum --disablerepo=* --enablerepo=opencos install -y $mod 1>$log_path/$mod.log 2>$log_path/$mod.err	
        if [ -s $log_path/$mod.err ]; then
            echo "fail"
            echo "Please contact li.guomin3@zte.com.cn,wu.wei266@zte.com.cn,liang.jingtao@zte.com.cn "
            exit 1
        else
            echo "ok(install finish)"
        fi
    else
        echo "ok(already exist)"
    fi
done

#modify for heat M2Crypto install error
file_name=/usr/include/openssl/opensslconf.h
action=`sed -i 's/#error "This openssl-devel package does not work your architecture?"/#include "opensslconf-x86_64.h"/g' $file_name`

echo "install venv ... "
chmod +x tools/*
python tools/install_venv.py 1>$log_path/install_venv.log 2>$log_path/install_venv.err
if grep "development environment setup is complete." $log_path/install_venv.log
   then
      echo "development environment setup is complete..."
else
  echo "development environment setup is fail,please check logs/install_venv.err"
  cat  $log_path/install_venv.err
fi
