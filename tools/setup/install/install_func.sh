#!/bin/bash
# DAISY upgrade

if [ ! "$_INSTALL_FUNC_FILE" ];then 
_INSTALL_FUNC_DIR=`pwd`

cd $_INSTALL_FUNC_DIR/../common/
.  daisy_common_func.sh
.  daisy_global_var.sh

cd $_INSTALL_FUNC_DIR/../uninstall/
.  uninstall_func.sh

cd $_INSTALL_FUNC_DIR
.  install_global_var.sh


function ip2int()
{
    local ip=$1
    [ `echo $ip |grep "^[0-9]\{1,3\}\.\([0-9]\{1,3\}\.\)\{2\}[0-9]\{1,3\}$"` ] || { echo "ip of $ip format error."; exit 1; }
    ip_list=${ip//./ }
    read -a ip_array <<<${ip_list}; 
    int_num=`echo $(( ${ip_array[0]}<<24 | ${ip_array[1]}<<16 | ${ip_array[2]}<<8 | ${ip_array[3]} ))`
}

function int2ip()
{
    A=$((($1 & 0xff000000 ) >>24))
    B=$((($1 & 0x00ff0000)>>16))
    C=$((($1 & 0x0000ff00)>>8))
    D=$(($1 & 0x000000ff))
    ip_addr=$A.$B.$C.$D
}

function netmask_to_int()
{
    local netmask=$1
    [ `echo $ip |grep "^[0-9]\{1,3\}\.\([0-9]\{1,3\}\.\)\{2\}[0-9]\{1,3\}$"` ] || { echo "netmask of $netmask format error."; exit 1; }
    netmask_int=`echo $netmask |awk -F. -vOFS=\; 'NF+=0{print "obase=2;"$0}'|bc |paste -s -d '' |grep -E '^1[1]*[0]*$' |grep -o '1' |wc -l`
    [ "$netmask_int" -eq 0 ] && { echo "error, $netmask is not a correct netmask."; exit 1; }
}
function ip_to_cidr()
{
    local ip=$1
    local netmask=$2

    netmask_to_int $netmask
    cidr_int=$netmask_int

    ip2int "$ip"
    local ip_int=$int_num
    ip2int "$netmask"    
    local netmask_int=$int_num

    cidr0_int=$(( $ip_int & $netmask_int ))
    int2ip "$cidr0_int"
    cidr_ip=$ip_addr
    cidr="$cidr_ip/$cidr_int"
}

function kolla_install
{
  write_install_log "Begin install kolla depends..."
  curl -sSL https://get.docker.io | bash
  mkdir -p /etc/systemd/system/docker.service.d
  config_path=/etc/systemd/system/docker.service.d/kolla.conf
  echo -e "[Service]\nMountFlags=shared" > $config_path
  systemctl daemon-reload
  systemctl restart docker
  yum install -y python-docker-py
  yum -y install ntp
  systemctl enable ntpd.service
  systemctl stop libvirtd.service
  systemctl disable libvirtd.service
  systemctl start ntpd.service
  yum -y install ansible1.9
  yum install -y python-setuptools.noarch
  yum install -y https://kojipkgs.fedoraproject.org//packages/python-jinja2/2.8/2.fc23/noarch/python-jinja2-2.8-2.fc23.noarch.rpm
  yum install -y python2-crypto
  yum install -y python-docker-py.noarch
  yum install -y python-gitdb
  yum install -y GitPython.noarch
  yum install -y python-pbr.noarch
  yum install -y python2-oslo-config.noarch
  yum install -y python-six.noarch
  yum install -y python-beautifulsoup4.noarch

  write_install_log "Begin clone kolla..."
  if [ -e "/home/kolla_install/kolla" ];then
      echo "kolla code already exit!" 
  else
      rm -rf /home/kolla_install
      mkdir /home/kolla_install
      cd /home/kolla_install
      git clone https://git.openstack.org/openstack/kolla
      cd kolla
      git checkout stable/mitaka
  fi
  cp -r /home/kolla_install/kolla/etc/kolla /etc 
  write_install_log "Begin copy images..."
  if [ -f "/home/kolla_install/kolla/docker/registry-2.0.3.tgz" ] && [ -f "/home/kolla_install/kolla/docker/registry-2.0.3.tgz" ];then
      echo "images already exit!"
  else
      rm -rf /home/kolla_install/docker
      mkdir /home/kolla_install/docker
      cd /home/kolla_install/docker
      wget "ftp://openuser:123@120.76.145.166/registry-2.0.3.tgz"
      tar mxvf registry-2.0.3.tgz
      wget "ftp://openuser:123@120.76.145.166/registry-server.tar"
  fi
  cd /home/kolla_install/docker
  docker load < ./registry-server.tar
  docker run -d -p 4000:5000 --restart=always -e REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY=/tmp/registry -v /home/kolla_install/docker/registry:/tmp/registry  --name registry registry:2

}
#rm daisy yum config file
function delete_unused_repo_file
{
    rm -f /etc/yum.repos.d/daisy*
}

#create ssh key
function generate_ssh_key
{
    local private_key_file=~/.ssh/id_dsa
    local public_key_file=~/.ssh/id_dsa.pub

    if [ ! -e $private_key_file ] || [ ! -e $public_key_file ]; then
        rm -rf $public_key_file
        rm -rf $private_key_file
        ssh-keygen -t dsa -f $private_key_file -q -P '' -b 1024
        [ $? == 0 ] && echo "ssh-keygen -t dsa succssfully!"
    else
        echo "ssh key is ready!"
    fi
}


function get_ip_from_ping
{
    input_ip=$1
    output_ip=$input_ip
    ping_result=`ping $input_ip -c 1 -w 5`
    if [ $? -eq 0 ];then
        ping_result=`echo $ping_result|tr '(' ' '|tr ')' ' '` 
        local ip=`echo $ping_result|sed -n '/from/ s/.*from[^0-9]* \([0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\).*/\1/p'`
        [ ! -z "$ip" ] && output_ip=$ip || echo -e "=============\nwarning: can't get ip address from \"ping $input_ip\"\n============="
    else
        echo -e "=============\nwarning: ping $input_ip failed.\n============="
    fi
}


function get_public_ip
{
    local_ip_list=`ifconfig  | grep "inet " | grep -v "127.0.0.1" | awk -F' ' {'print $2'} `

    local def_gw_if=`route | grep default | awk -F' ' '{print $8}'|uniq|head -1`
    public_ip=""
    if [[ -n "$def_gw_if" ]];then
        public_ip=`ifconfig "$def_gw_if" | grep 'inet ' | cut -d: -f2 | awk '{ print $2}'`
    fi
}

function get_default_gw_st
{
    defaultgw_ip=`route |grep default |awk  '{print $2}'`
}

function set_default_gw_st
{
    if [ -n "$defaultgw_ip" ] ; then 
    route add default gw  $defaultgw_ip
    fi
}

#create daisy component
function create_daisy_component
{
    write_install_log "Daisy init and create the component"

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "nova" "The OpenStack Compute component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of nova failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "cinder" "The OpenStack Block Storage component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of cinder failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "glance" "The OpenStack Image component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of glance failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "heat" "The OpenStack Orchestration component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of heat failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "ceilometer" "The OpenStack Telemetry component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of ceilometer failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "horizon" "The OpenStack dashboard component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of horizon failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "neutron" "The OpenStack Networking component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of neutron failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "keystone" "The OpenStack Identity component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of keystone failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "ironic" "The OpenStack Bare Metal component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of ironic failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "database" "Database component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of database failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "amqp" "Message queue component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of amqp failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "loadbalance" "Loadbalance component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of loadbalance failed"; exit 1; } 

    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "ha" "High availability component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of ha failed"; exit 1; } 
    
    /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "camellia" "Camellia component" >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:create the component of camellia failed"; exit 1; } 
    
 #   /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-add "log" "Log component" >> $install_logfile 2>&1
 #   [ "$?" -ne 0 ] && { write_install_log "Error:create the component of log failed"; exit 1; }
}

#create daisy service
function create_daisy_service
{
    write_install_log "Daisy init and create the service"

    local nova_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "nova" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of nova component failed"; exit 1; }

    local ironic_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "ironic" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of ironic component failed"; exit 1; }

    local glance_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "glance" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of glance component failed"; exit 1; }

    local cinder_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "cinder" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of cinder component failed"; exit 1; }

    local keystone_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "keystone" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of keystone component failed"; exit 1; }

    local neutron_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "neutron" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of neutron component failed"; exit 1; }

    local horizon_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "horizon" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of horizon component failed"; exit 1; }

    local heat_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "heat" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of heat component failed"; exit 1; }

    local ceilometer_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "ceilometer" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of ceilometer component failed"; exit 1; }

    local amqp_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "amqp" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of amqp component failed"; exit 1; }

    local database_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "database" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of datebase component failed"; exit 1; }

    local ha_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "ha" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of ha component failed"; exit 1; }

    local lb_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "loadbalance" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of loadbalance component failed"; exit 1; }
    
    local camellia_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "camellia" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of camellia component failed"; exit 1; }
    
  #  local log_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "log" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
  #  [ "$?" -ne 0 ] && { write_install_log "Error:query the id of log component failed"; exit 1; }

    if [ ! -z $nova_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "nova-api" "The nova api service" --component-id $nova_component_id --backup-type lb >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of nova-api failed"; exit 1; } 

        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "nova-conductor" "The nova conductor service" --component-id $nova_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of nova conductor failed"; exit 1; } 

        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "nova-vncproxy" "The nova vnc proxy service" --component-id $nova_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of nova vnc proxy failed"; exit 1; } 

        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "nova-sched" "The nova scheduler service" --component-id $nova_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of nova scheduler failed"; exit 1; } 

        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "compute" "The nova compute service" --component-id $nova_component_id >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of nova scheduler failed"; exit 1; } 

        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "nova-cert" "The nova certificate service" --component-id $nova_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of nova certificate failed"; exit 1; } 

    else
        write_install_log "Error:there is no componet of nova"
        exit 1;   
    fi 

    if [ ! -z $ironic_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "ironic" "The nova ironic service" --component-id $ironic_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of ironic failed"; exit 1; } 
    else
        write_install_log "Error:there is no componet of ironic"
        exit 1;   
    fi

    if [ ! -z $glance_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "glance" "The glance api service" --component-id $glance_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of glance api failed"; exit 1; } 
    else
        write_install_log "Error:there is no componet of glance"
        exit 1;   
    fi

    if [ ! -z $cinder_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "cinder-api" "The cinder api service" --component-id $cinder_component_id --backup-type lb >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of cinder api failed"; exit 1; } 

        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "cinder-scheduler" "The cinder scheduler service" --component-id $cinder_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of cinder scheduler failed"; exit 1; } 

        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "cinder-volume" "The cinder volumes service" --component-id $cinder_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of cinder volumes failed"; exit 1; } 

    else
        write_install_log "Error:there is no componet of cinder"
        exit 1;   
    fi

    if [ ! -z $keystone_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "keystone" "The keystone service" --component-id $keystone_component_id --backup-type lb >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of keystone failed"; exit 1; } 
    else
        write_install_log "Error:there is no componet of keystone"
        exit 1;   
    fi

    if [ ! -z $neutron_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "neutron-server" "The neutron server service" --component-id $neutron_component_id --backup-type lb >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of neutron server failed"; exit 1; } 

        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "neutron-l3" "The neutron l3 service" --component-id $neutron_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of neutron l3 failed"; exit 1; } 

        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "neutron-dhcp" "The neutron dhcp service" --component-id $neutron_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of neutron dhcp failed"; exit 1; } 

        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "neutron-metadata" "The neutron metadata service" --component-id $neutron_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of neutron metadata failed"; exit 1; } 
    else
        write_install_log "Error:there is no componet of neutron"
        exit 1;   
    fi

    if [ ! -z $horizon_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "horizon" "The horizon service" --component-id $horizon_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of horizon failed"; exit 1; } 
    else
        write_install_log "Error:there is no componet of horizon"
        exit 1;   
    fi

    if [ ! -z $heat_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "heat-api" "The heat api service" --component-id $heat_component_id --backup-type lb >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of heat api failed"; exit 1; }     
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "heat-api-cfn" "The heat api cfn service" --component-id $heat_component_id --backup-type lb >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of heat api cfn failed"; exit 1; }     
        #/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "heat-api-cloudwatch" "The heat api cfn cloudwatch service" --component-id $heat_component_id --backup-type ha>> $install_logfile 2>&1
        #[ "$?" -ne 0 ] && { write_install_log "Error:create the service of heat api cloudwatch failed"; exit 1;}
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "heat-engine" "The heat engine service" --component-id $heat_component_id --backup-type ha>> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of heat engine failed"; exit 1;}
    else
        write_install_log "Error:there is no componet of heat"
        exit 1;   
    fi
    if [ ! -z $ceilometer_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "ceilometer-api" "The ceilometer api service" --component-id $ceilometer_component_id --backup-type lb >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of ceilometer api failed"; exit 1; } 
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "ceilometer-collector" "The ceilometer service" --component-id $ceilometer_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of ceilometer collector failed"; exit 1; } 
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "ceilometer-notification" "The ceilometer service" --component-id $ceilometer_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of ceilometer notification failed"; exit 1; } 
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "ceilometer-central" "The ceilometer service" --component-id $ceilometer_component_id --backup-type ha >> $install_logfile 2>&1
        
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of ceilometer central failed"; exit 1; }
        
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "ceilometer-alarm" "The ceilometer service" --component-id $ceilometer_component_id --backup-type ha >> $install_logfile 2>&1
        
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of ceilometer alarm failed"; exit 1; }
    else
        write_install_log "Error:there is no componet of ceilometer"
        exit 1;   
    fi

    if [ ! -z $amqp_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "amqp" "The amqp service" --component-id $amqp_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of amqp failed"; exit 1; } 
    else
        write_install_log "Error:there is no componet of amqp"
        exit 1;   
    fi

    if [ ! -z $database_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "mariadb" "The database service" --component-id $database_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of mariadb failed"; exit 1; } 
    else
        write_install_log "Error:there is no componet of database"
        exit 1;   
    fi

    if [ ! -z $ha_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "ha" "The high availability service" --component-id $ha_component_id >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of high availability failed"; exit 1; } 
    else
        write_install_log "Error:there is no componet of ha"
        exit 1;   
    fi

    if [ ! -z $lb_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "lb" "The loadbalance service" --component-id $lb_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of lb failed"; exit 1; } 
    else
        write_install_log "Error:there is no componet of loadbalance"
        exit 1;   
    fi

    # now ceilometer use mariadb default, 10132825 20160202
    if [ ! -z $database_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "mongodb" "The database service" --component-id $database_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of mongodb failed"; exit 1; } 
    else
        write_install_log "Error:there is no componet of database"
        exit 1;   
    fi
    
    if [ ! -z $camellia_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "camellia-api" "The camellia-api service" --component-id $camellia_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of camellia-api failed"; exit 1; } 
    else
        write_install_log "Error:there is no componet of camellia"
        exit 1;   
    fi
    
  # if [ ! -z $log_component_id ];then
  #      /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "log-server" "The log-server service" --component-id $log_component_id --backup-type ha >> $install_logfile 2>&1
  #      [ "$?" -ne 0 ] && { write_install_log "Error:create the service of log-server failed"; exit 1; } 
  #  else
  #      write_install_log "Error:there is no componet of log"
  #      exit 1;   
  #  fi
}

#create daisy network
function create_daisy_network
{
    write_install_log "Daisy init and create the network"

    daisy --os-endpoint="http://${public_ip}:$bind_port" network-add "PUBLICAPI" "For public api"  "PUBLICAPI" --cidr "192.168.1.1/24" --type template --capability high >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the network of publicAPI failed"; exit 1; }

    daisy --os-endpoint="http://${public_ip}:$bind_port" network-add "MANAGEMENT" "For internal API and AMQP" "MANAGEMENT" --cidr "192.168.1.1/24" --type template --capability high >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the network of MANAGEMENT failed"; exit 1; }

    daisy --os-endpoint="http://${public_ip}:$bind_port" network-add "STORAGE" "Storage network plane" "STORAGE"  --cidr "192.169.1.1/24" --type template --capability high >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the network of STORAGE failed"; exit 1; }

    daisy --os-endpoint="http://${public_ip}:$bind_port" network-add "physnet1" "Dataplane network for vms" "DATAPLANE" --type template --ml2-type ovs --capability high >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the network of DATAPLANE failed"; exit 1; }

    daisy --os-endpoint="http://${public_ip}:$bind_port" network-add "DEPLOYMENT" "For deploy the infrastructure" "DEPLOYMENT" --cidr "99.99.1.1/24" --type template --capability high >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the network of DEPLOYMENT failed"; exit 1; }

   daisy --os-endpoint="http://${public_ip}:$bind_port" network-add "EXTERNAL" "For external interactive" "EXTERNAL" --cidr "192.170.1.1/24" --type template --capability high >> $install_logfile 2>&1
   [ "$?" -ne 0 ] && { write_install_log "create the network of EXTERNAL failed"; exit 1; }

    daisy --os-endpoint="http://${public_ip}:$bind_port" network-add "DEPLOYMENT" "For build pxe server" "DEPLOYMENT" --cidr "99.99.1.1/24" --ip "99.99.1.5" --ip-ranges "start":"99.99.1.50","end":"99.99.1.150" --type system >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the network of DEPLOYMENT failed"; exit 1; }
}

#create daisy role with tecs
function create_daisy_role_with_tecs
{
    write_install_log "Daisy init and create the role with tecs"

    local service_type_LB_list=`daisy --os-endpoint="http://${public_ip}:$bind_port" service-list | awk -F "|" '{print $2$6}' | grep -w [Ll][Bb] | awk -F " " '{print $1}'`
    local service_type_HA_list=`daisy --os-endpoint="http://${public_ip}:$bind_port" service-list | awk -F "|" '{print $2$6}' | grep -w [Hh][Aa] | awk -F " " '{print $1}'`
    local service_type_compute_list=`daisy --os-endpoint="http://${public_ip}:$bind_port" service-list | awk -F "|" '{print $2$3}' | grep -w "compute" | awk -F " " '{print $1}'`

    if [ ! -z "$service_type_LB_list" ];then
        daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "CONTROLLER_LB" "Controller role,backup type is loadbalance" --services $service_type_LB_list --type template --role-type CONTROLLER_LB >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "create the role of CONTROLLER_LB failed"; exit 1; } 
    fi 

    if [ ! -z "$service_type_HA_list" ];then
        daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "CONTROLLER_HA" "Controller role,backup type is HA,active/standby" --services $service_type_HA_list --type template  --role-type CONTROLLER_HA >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "create the role of CONTROLLER_HA failed"; exit 1; } 
    fi

    if [ ! -z $service_type_compute_list ];then
        daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "COMPUTER" "Compute role" --services $service_type_compute_list --type template --role-type COMPUTER >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "create the role of COMPUTER failed"; exit 1; } 
    fi

    # daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "DOCTOR" "Role for health monitoring" --type template >> $install_logfile 2>&1
    # [ "$?" -ne 0 ] && { write_install_log "create the role of DOCTOR failed"; exit 1; } 
}

function create_daisy_role_with_zenic
{
    write_install_log "Daisy init and create the role with zenic"

    daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "ZENIC_CTL" "Role for zenic controller." --type template --deployment-backend zenic --role-type ZENIC_CTL >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the role of ZENIC_CTL failed"; exit 1; }

    daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "ZENIC_NFM" "Role for zenic nfmanager." --type template --deployment-backend zenic --role-type ZENIC_NFM >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the role of ZENIC_NFM failed"; exit 1; }

    #daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "ZENIC_MDB" "Role for zenic mongodb." --type template --deployment-backend zenic --role-type ZENIC_MDB >> $install_logfile 2>&1
    #[ "$?" -ne 0 ] && { write_install_log "create the role of ZENIC_MDB failed"; exit 1; } 
}

function create_daisy_role_with_proton
{
    write_install_log "Daisy init and create the role with proton"

    daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "PROTON" "Role for proton." --type template --deployment-backend proton --role-type PROTON >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the role of proton failed"; exit 1; }
}

function create_daisy_role_with_kolla
{
    write_install_log "Daisy init and create the role with kolla"
    daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "CONTROLLER_LB" "Controller Role for kolla." --type template --deployment-backend kolla --role-type CONTROLLER_LB >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the controller role of KOLLA failed"; exit 1; }
    daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "COMPUTER" "Computer Role for kolla." --type template --deployment-backend kolla --role-type COMPUTER >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the computer role of KOLLA failed"; exit 1; }
    
}

function create_daisy_service_role_with_cell
{
    write_install_log "Daisy init and create component and role with cell"

    local nova_component_id=`/usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" component-list |grep -w "nova" |awk -F  " " '{print $2}'` >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "Error:query the id of nova component failed"; exit 1; }

    if [ ! -z $nova_component_id ];then
        /usr/bin/daisy --os-endpoint="http://$public_ip:$bind_port" service-add "nova-cells" "The nova cells service" --component-id $nova_component_id --backup-type ha >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:create the service of nova cell failed"; exit 1; }
    fi

    daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "CHILD_CELL_1_COMPUTER" "Child cell compute role" --type template  --role-type CHILD_CELL_1_COMPUTER >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the role of CHILD CELL COMPUTER failed"; exit 1; }

    daisy --os-endpoint="http://${public_ip}:$bind_port" role-add "CONTROLLER_CHILD_CELL_1" "Controller role,backup type is cell" --type template  --role-type CONTROLLER_CHILD_CELL_1 >> $install_logfile 2>&1
    [ "$?" -ne 0 ] && { write_install_log "create the role of cell failed"; exit 1; }
}

function daisy_init_func
{
    get_public_ip
    if [ -z $public_ip ];then
        write_install_log "Error:default gateway is not set!!!"
        exit 1
    fi

    local file="/etc/daisy/daisy-api.conf"
    bind_port=""
    if [ -e $file ];then
        bind_port=`openstack-config --get $file DEFAULT "bind_port"`
        if [ $bind_port=="" ];then
            bind_port="19292"
        fi
    fi

    create_daisy_component
    create_daisy_service
    create_daisy_network

    config_file="/home/daisy_install/daisy.conf"
    [ ! -e $config_file ] && return
        get_config "$config_file" default_backend_types
        local default_backend_types_params=$config_answer
        cell=`echo $default_backend_types_params|grep 'cell'|wc -l`
        if [ $cell -ne 0 ];then
            create_daisy_service_role_with_cell
        fi

        tecs=`echo $default_backend_types_params|grep 'tecs'|wc -l`
        if [ -z "$default_backend_types_params" ] || [ $tecs -ne 0 ];then
            create_daisy_role_with_tecs
        fi

        zenic=`echo $default_backend_types_params|grep 'zenic'|wc -l`
        if [ $zenic -ne 0 ];then
            create_daisy_role_with_zenic
        fi

        proton=`echo $default_backend_types_params|grep 'proton'|wc -l`
        if [ $proton -ne 0 ];then
            create_daisy_role_with_proton
        fi
        kolla=`echo $default_backend_types_params|grep 'kolla'|wc -l`
        if [ $kolla -ne 0 ];then
            create_daisy_role_with_kolla
        fi
}

function modify_sudoers
{
    local file=$1
    local key=$2

    [ ! -e $file ] && { write_install_log "Error:$file is not exist"; exit 1;}

    #echo update key $key to value $value in file $file ...
    local exist=`grep "^[[:space:]]*[^#]" $file | grep -c "[[:space:]]*$key[[:space:]]*"`
    
    if [ $exist -gt 0 ];then
        sed  -i "/^[^#]/s/Defaults    requiretty/#Defaults    requiretty/" $file       
    fi
    
    sudoer_daisy="/etc/sudoers.d/daisy"
    if [ ! -e $sudoer_daisy ];then
        touch $sudoer_daisy
        echo "daisy   ALL=(ALL)       NOPASSWD: ALL" > $sudoer_daisy
    fi
}

function config_ironic
{
    local file=$1
    [ ! -e $file ] && { write_install_log "Error:$file is not exist"; exit 1;}
    
    openstack-config --set "$file" DEFAULT "rpc_backend" "rabbit"

    get_public_ip
    if [ -z $public_ip ];then
        write_install_log "Error:default gateway is not set!!!"
        exit 1
    else
        openstack-config --set "$file" DEFAULT "rabbit_host" "$public_ip"
        openstack-config --set "$file" database "connection" "mysql://ironic:ironic@$public_ip:3306/ironic?charset=utf8"
    fi
    openstack-config --set "$file" DEFAULT "rabbit_password" "guest"
    openstack-config --set "$file" DEFAULT "enabled_drivers" "pxe_ipmitool"
    mkdir -p /var/log/ironic
    chown -R ironic:ironic /var/log/ironic
    openstack-config --set "$file" DEFAULT "log_dir" "/var/log/ironic"
    openstack-config --set "$file" DEFAULT "verbose" "true"
    openstack-config --set "$file" DEFAULT "auth_strategy" "noauth"
}

function config_rabbitmq_env
{
    local config_file="/etc/rabbitmq/rabbitmq-env.conf"
    if [ ! -e $config_file ];then
        touch $config_file
        echo "NODE_PORT=5672" >> $config_file
    fi
}

function config_rabbitmq_config
{
    local config_file="/etc/rabbitmq/rabbitmq.config"
    if [ ! -e $config_file ];then
        cat > $config_file <<EOF
% This file managed by Puppet
% Template Path: rabbitmq/templates/rabbitmq.config
[
  {rabbit, [
    {loopback_users, []},
    {tcp_listen_options, [binary,{packet, raw},{reuseaddr, true},{backlog, 128},{nodelay, true},{exit_on_close, false},{keepalive, true}]},
    {default_user, <<"guest">>},
    {default_pass, <<"guest">>}
  ]},
  {kernel, [
    
  ]}
].
% EOF
EOF
    fi
}

function config_ironic_discoverd
{    
    local file=$1
    local ip=$2
    local daisy_file="/etc/daisy/daisy-api.conf"
    local bind_port=""
    if [ -e $daisy_file ];then
        bind_port=`openstack-config --get $daisy_file DEFAULT "bind_port"`
        if [ $bind_port=="" ];then
            bind_port="19292"
        fi
    fi
    [ ! -e $file ] && { write_install_log "Error:$file is not exist"; exit 1;}
    
    openstack-config --set "$file" discoverd "os_auth_token" "admin"
    openstack-config --set "$file" discoverd "ironic_url " "http://$ip:6385/v1"
    openstack-config --set "$file" discoverd "manage_firewall " "false"
    openstack-config --set "$file" discoverd "daisy_url " "http://$ip:$bind_port"
}

function daisyrc_admin
{
    local ip=$1
    local file="/root/daisyrc_admin"
    if [ -z $bind_port ];then
        bind_port="19292"
    fi
    
    if [ ! -e $file ];then
       touch $file
       echo "export OS_AUTH_TOKEN=admin" >> $file
       echo "export IRONIC_URL=http://$ip:6385/v1" >> $file
       echo "export OS_ENDPOINT=http://$ip:$bind_port" >> $file
       echo "export PS1='[\u@\h \W(daisy_admin)]\$ '" >> $file
       echo "export OS_SERVICE_TOKEN=e93e9abf42f84be48e0996e5bd44f096" >> $file
       echo "export OS_SERVICE_ENDPOINT=http://$ip:35357/v2.0" >> $file
    fi
}

function build_pxe_server
{
    local ip=$1
    local daisy_port=$2

    config_file="/home/daisy_install/daisy.conf"
    [ ! -e $config_file ] && return 
    
    get_config "$config_file" build_pxe
    local build_pxe_params=$config_answer
    if [ "$build_pxe_params" == yes ];then
        write_install_log "build pxe server"
        get_config "$config_file" eth_name
        pxe_bond_name=$config_answer
        if [  -z $pxe_bond_name ];then
            write_install_log "Error:In the configuration file daisy.conf,eth_name is blank"
        fi
        
        optional_parameters=()
        get_config "$config_file" ip_address 
        local ip_address_params=$config_answer
        if [ ! -z $ip_address_params ];then
            optional_parameters="--ip_address $ip_address_params "
        fi
        get_config "$config_file" net_mask 
        local net_mask_params=$config_answer
        if [ ! -z $net_mask_params ];then            
            optional_parameters="$optional_parameters --net_mask $net_mask_params"
        fi
        get_config "$config_file" client_ip_begin 
        local client_ip_begin_params=$config_answer
        if [ ! -z $client_ip_begin_params ];then
            optional_parameters="$optional_parameters --client_ip_begin $client_ip_begin_params"
        fi
        get_config "$config_file" client_ip_end 
        local client_ip_end_params=$config_answer
        if [ ! -z $client_ip_end_params ];then
            optional_parameters="$optional_parameters --client_ip_end $client_ip_end_params"
        fi
        ironic --ironic-url="http://${ip}:6385/v1" --os-auth-token daisy daisy-build-pxe $pxe_bond_name yes $optional_parameters >> $install_logfile 2>&1

        # write dhcp cidr to DEPLOYMENT network of system for daisy
        # to decide which is pxe mac
        if [ "$ip_address_params" -a "$net_mask_params" ];then
            ip_to_cidr "$ip_address_params" "$net_mask_params"
            [ -z "$cidr" ] && { write_install_log "Error: can't get cidr of dhcp"; exit 1; }
            dhcp_cidr=$cidr
            template_deploy_network_id=`/usr/bin/daisy --os-endpoint="http://${ip}:${daisy_port}" network-list --type "system"|grep -w system |grep -w 'DEPLOYMENT' |awk -F ' ' '{print $2}' 2>&1`
            if [ "$client_ip_begin_params" -a "$client_ip_end_params" ];then
                ip_ranges="start:$client_ip_begin_params,end:$client_ip_end_params"
            else
                ip_ranges=""
            fi
            [ -z "$template_deploy_network_id" ] && { write_install_log "Error:can't find DEPLOYMENT network of system"; exit 1; }
            write_install_log "write dhcp cidr to DEPLOYMENT network of system"
            if [ "$ip_ranges" ];then
                /usr/bin/daisy --os-endpoint="http://${ip}:${daisy_port}" network-update "$template_deploy_network_id" --cidr "$dhcp_cidr" --ip-ranges "$ip_ranges" >> $install_logfile 2>&1
            else
                /usr/bin/daisy --os-endpoint="http://${ip}:${daisy_port}" network-update "$template_deploy_network_id" --cidr "$dhcp_cidr" >> $install_logfile 2>&1
            fi
            [ "$?" -ne 0 ] && { write_install_log "Error:update DEPLOYMENT network $template_deploy_network_id of system failed"; exit 1; }
        fi

        systemctl is-active dhcpd.service >> $install_logfile 2>&1
        [ "$?" -ne 0 ] && { write_install_log "Error:dhcpd.service is not active,so build pxe server failed"; exit 1; }
    else
        write_install_log "Notice:No build PXE server"
    fi
}

function config_keystone_local_setting
{
    local dashboard_conf_file="/etc/openstack-dashboard/local_settings"
    local keystone_conf_file="/etc/keystone/keystone.conf"

    get_public_ip
    if [ -z $public_ip ];then
        write_install_log "Error:default gateway is not set!!!"
        exit 1
    fi
    
    update_config "$dashboard_conf_file" OPENSTACK_KEYSTONE_URL "\"http://${public_ip}:5000/v2.0\""
    update_config "$dashboard_conf_file" DAISY_ENDPOINT_URL "\"http://$public_ip:19292\""
    update_config "$dashboard_conf_file" WEBROOT "'/dashboard/'"
    update_config "$dashboard_conf_file" LOGIN_URL "'/dashboard/auth/login/'"
    update_config "$dashboard_conf_file" LOGOUT_URL "'/dashboard/auth/logout/'"
    update_config "$dashboard_conf_file" ALLOWED_HOSTS "['*']"
    update_config "$dashboard_conf_file" AUTHENTICATION_URLS "['openstack_auth.urls',]"
    openstack-config --set "$keystone_conf_file" DEFAULT admin_token "e93e9abf42f84be48e0996e5bd44f096"
    openstack-config --set "$keystone_conf_file" token expiration "90000"    
    
    touch /var/log/horizon/horizon.log
    chown apache:apache /var/log/horizon/horizon.log
    
    config_file="/home/daisy_install/daisy.conf"
    local director_theme_conf_file="/usr/share/openstack-dashboard/openstack_dashboard/enabled/_20_director_theme.py"
    [ ! -e $config_file ] && return
    get_config "$config_file" with_director
    local with_director=$config_answer
    if [ "$with_director" == yes ];then
        update_config "$director_theme_conf_file" DISABLED "False"
    else
        update_config "$director_theme_conf_file" DISABLED "True"
    fi
}

function config_get_node_info
{
    local get_node_info_file="/var/lib/daisy/kolla/getnodeinfo.sh"
    if [ ! -e $get_node_info_file ];then
        write_install_log "Error:the file $get_node_info_file is not exist"
        exit 1
    fi
    get_public_ip
    if [ -z $public_ip ];then
        write_install_log "Error:default gateway is not set!!!"
        exit 1
    fi
    sed -i "s/127.0.0.1/$public_ip/g" $get_node_info_file
    [ "$?" -ne 0 ] && { write_install_log "Error:config /var/lib/daisy/kolla/getnodeinfo.sh failed"; exit 1;}
}

_INSTALL_FUNC_FILE="install_func.sh"
fi

