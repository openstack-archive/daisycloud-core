#!/bin/bash
# global function，can be called by other script

#avoid to be repeat include
if [ ! "$_DAISY_COMMON_FUNC_FILE" ];then

#######################get answer from user functions############################
# get 'yes' or 'no' answer from user
function read_bool
{
    local prompt=$1
    local default=$2

    [[ $prompt != "" ]] && echo -e "$prompt (y/n? default: $default): \c "
    read answer
    [[ ! -z `echo $answer |grep -iwE "y|yes"` ]] && answer=yes
    [[ ! -z `echo $answer |grep -iwE "n|no"` ]] && answer=no
    case $answer in
            "yes")
            answer="y";;
            "no")
            answer="n";;
            "")
            answer="$default";;
            *)
            echo "Please input y or n"
            read_bool "$prompt" "$default";;
            
    esac
    return 0
}

#get common string answer from user
function read_string
{
    local prompt=$1
    local default=$2

    [[ $prompt != "" ]] && echo -e "$prompt (default: $default): \c "
    read answer
    [ -z "$answer" ] && answer="$default"
}

function read_string_input_null_check
{
    read_string "$1" "$2"
    if [[ $answer == "" ]];then
        read_string_input_null_check "$1" "$2"
    fi
}

#read ip list
function read_iplist
{
    local prompt=$1
    local ip_list=$2
    local recommend=$3
    if [[ $prompt != "" ]];then
        echo -e "$prompt"
        echo -e "local ip list:"
        echo -e "$ip_list"
        echo -e "(recommend: $recommend): \c "
    fi 
    read answer
    [ -z $answer ] && answer="$recommend"
}

#######################configuration functions############################

function get_config
{
    local file=$1
    local key=$2

    [ ! -e $file ] && return
    local line=`sed '/^[[:space:]]*#/d' $file | sed /^[[:space:]]*$/d | grep -w "$key"| grep "$key[[:space:]]*=" -m1`
    if [ -z "$line" ]; then
        config_answer=""
    else
        config_answer=`echo $line | sed 's/=/ /' | sed -e 's/^\w*\ *//'`
    fi
}

#update key = value config option in an ini file
function update_config
{
    local file=$1
    local key=$2
    local value=$3

    [ ! -e $file ] && return

    #echo update key $key to value $value in file $file ...
    local exist=`grep "^[[:space:]]*[^#]" $file | grep -c "$key[[:space:]]*=[[:space:]]*.*"`
    #action：If a line is a comment, the beginning of the first character must be a #!!!
    local comment=`grep -c "^[[:space:]]*#[[:space:]]*$key[[:space:]]*=[[:space:]]*.*"  $file`
    
    if [[ $value == "#" ]];then
        if [ $exist -gt 0 ];then
            sed  -i "/^[^#]/s/$key[[:space:]]*=/\#$key=/" $file       
        fi
        return
    fi

    if [ $exist -gt 0 ];then
        #if there have been a effective configuration line did not comment, update value directly
        sed  -i "/^[^#]/s#$key[[:space:]]*=.*#$key=$value#" $file
        
    elif [ $comment -gt 0 ];then
        #if there is a configuration line has been commented out, then remove the comments, update the value
        sed -i "s@^[[:space:]]*#[[:space:]]*$key[[:space:]]*=[[:space:]]*.*@$key=$value@" $file
    else
        #add effective configuration line at the end
        echo "$key=$value" >> $file
    fi
}

#accord to the location of the section insert key = value, or only a key field
#this function isused in cases where the value is empty, will not raise error when the value is empty
function update_section_config
{
    local file=$1
    local section=$2
    local key=$3
    local value=$4

    [ ! -e $file ] && return

    #find key according to section
    if [ -z $value ];then
        local exist=`sed  -n "/\[$section\]/,/\[*\]/p" $file | grep "^[[:space:]]*[^#]" |grep -c "[[:space:]]*$key[[:space:]]*"`
        if [ $exist -eq 0 ];then
            local linenumber=`grep -n "\[$section\]" $file| awk -F ':' '{print $1}'`
            sed -i "$linenumber a$key" $file
        fi
    else
        local exist=`sed  -n "/\[$section\]/,/\[*\]/p" $file | grep "^[[:space:]]*[^#]" |grep -c "[[:space:]]*$key[[:space:]]*=[[:space:]]*"`
        if [ $exist -eq 0 ];then
            local linenumber=`grep -n "\[$section\]" $file| awk -F ':' '{print $1}'`
            sed -i "$linenumber a$key=$value" $file        
        else
            sed -i "/\[$section\]/,/\[*\]/s/[[:space:]]*$key[[:space:]]*=[[:space:]]*.*/$key=$value/g" $file
        fi
    fi
}

#get string number
function get_string_num
{
    local file=$1
    local string=$2

    [ ! -e $file ] && { echo "$file doesn't exist."; exit 1; }
    string_num=`sed '/^[[:space:]]*#/d' $file | sed /^[[:space:]]*$/d | grep -cw "$string"`
}

#Save the configuration information, the configuration file of installation and uninstall don't need to save
#when call this function,you should make sure one-time finish configuration module configuration parameters, if not,you can configuration part tc first, and then configure the cc, and back to tc
function user_config_save
{  
    local component="$1"
    local key="$2"
    local value="$3"

    if [ "$operation" = "install" ];then
        #If the user configuration file already exists, a backup the configuration of the old
        if [ ! -f $user_config_save_file ];then
            mkdir -p ${user_config_save_path}     
            touch $user_config_save_file 
            echo -e "## opencos installation configure file at ${current_time}" >$user_config_save_file
            echo -e "## you can edit it and install opencos by conf_file option, as \"./installopencos_(arch).bin conf_file /home/tecs_install/user_install.conf\"\n" >>$user_config_save_file
            echo -e "## global configration section\nmode=$mode\n">>$user_config_save_file
            echo -e "## component configration section">>$user_config_save_file
        fi
        # If there is no component belonging to, put it after on mode
        if [ "$component" = "" ];then
            [ "$key" = "" ] && { echo -e "\nkey is null, please check!"; exit 1; }
            sed -i "/mode=$mode/a $key=$value" $user_config_save_file
        else        
            [ -z "`cat $user_config_save_file |grep -w "\[$component\]"`" ] && echo -e "\n[$component]" >>$user_config_save_file
            [[ $key != "" ]] && echo "$key=$value" >>$user_config_save_file
        fi
    fi
}

#######################rpm related functions############################

#check rpm install
function check_installed
{
    has_installed="no"
    
    rpm -q $1 &>/dev/null
    
    if [ 0 == $? ];then
        has_installed="yes"
    fi    
}

# check rpm depends
function check_depend
{
    local rpm_name=$1
    # check if the rpm is used by someone else
    rpm -q --whatrequires $rpm_name &>/dev/null
    return "$?"
}

# install rpm by yum
function install_rpm_by_yum
{
    local rpm_name=$1

    yum install -y $rpm_name

    local result=$?
    if [ $result -ne 0 ];then
        echo -e "\ninstall $rpm_name failed!"
        exit $result
    fi    
}
# install rpm by daisy yum
function install_rpm_by_daisy_yum
{
    local rpm_name=$1

    [[ $daisy_yum = "" ]] && { echo "yum repository doesn't create!"; exit 1; }
    $daisy_yum install $rpm_name

    local result=$?
    if [ $result -ne 0 ];then
        echo -e "\ninstall $rpm_name failed!"
        exit $result
    fi
}
# check existence of packge，if not, indicates whether need to install
function check_and_install_rpm
{
    local rpm_name=$1
    check_installed $rpm_name
    if [[ "$has_installed" != "yes" ]];then
        echo "$rpm_name not installed, need to install"
        install_rpm_by_yum $rpm_name
        return 0
    else
        echo "$rpm_name has installed"
        return 1
    fi
}

# check existence of packge，if exist，there is a need to upgrade
function install_or_upgrade_rpm
{
    local rpm_name=$1
    check_installed $rpm_name
    if [[ "$has_installed" != "yes" ]];then
        echo "$rpm_name not installed, need to install"
        install_rpm_by_yum $rpm_name
        return 0
    else
        echo "$rpm_name has installed"
        check_app_is_upgrade $rpm_name
        if [[ "$is_update" = "yes" ]];then
            echo "$rpm_name need to update ..."
            upgrade_rpms_by_yum $rpm_name
        fi
        return 1
    fi
}

# if packate have installed, suggest whether to unload
function check_uninstall_tecs_rpm
{
    local rpm_name=$1
    check_installed "$rpm_name"
    if [[ "$has_installed" == "no" ]];then
        return 1
    fi
    
    read_bool "$rpm_name already installed, remove it?"  "no"
    if [ $answer == "yes" ]; then
        service_stop $rpm_name
        return 0
    fi
    return 1
}


function remove_rpms_by_yum
{
    local rpm_name_list="$1"
    for rpm_name in $rpm_name_list
    do
        check_installed "$rpm_name"
        [ "$has_installed" = "no" ] && continue
        $daisy_yum remove $rpm_name
    done

}

#check packages need to upgrade
function check_app_is_upgrade
{ 
    local app=$1
    is_update="yes"

    num=`$daisy_yum list updates | awk -F ' ' '{print$1}' | grep $app -c`
    if [[ $num == 0 ]];then
        is_update="no"
    fi
}

# update rpm by yum
function upgrade_rpms_by_yum
{
    local app_list="$1"
    
    if [ "$app_list" = "" ];then
        echo -e "\nsorry, there is no rpm need to upgrade"!
        exit 0
    fi    
    #need to upgrade separately for each service
    [ "$daisy_yum" = "" ] && { echo "opencos yum doesn't set, update rpms failed!"; exit 1; }
    for app in $app_list
    do
        check_app_is_upgrade "$app"
        if [[ "$is_update" == "yes" ]];then             
            echo -e "\n$app will upgrade..."            
            $daisy_yum upgrade $app                
            local result=$?
            if [ $result -ne 0 ];then
                echo -e "\nupgrade $app failed,return $result"!
                exit $result
            fi 
        else
            echo -e "\n$app don't need to upgrade"!
        fi
    done    
}


#######################service related functions############################
# stop service
function service_stop
{
    local app=$1
    [ ! -f ${systemd_path}/$app.service ] && return

    cd /
    systemctl stop $app.service &>/dev/null 
    cd - >/dev/null
	
    local service_status="active"
    local timeout=0
    while [ "$service_status" != "inactive" ]
    do         
        service_status=`systemctl show $app|grep -w ActiveState|awk -F '=' '{print $2}'`
        if [ "$service_status" = "inactive" ];then
            break
        else
            timeout=$(($timeout+1))
            [ $timeout -gt 3 ] && { echo "warning: $app status is \"$service_status\" after stopping."; break; }
        fi
		
        sleep 1          
    done		
}

# start service
function service_start
{
    local app=$1
    [ ! -f ${systemd_path}/$app.service ] && return

    #cd / and cd -can't be removed ，in order to deal with deleting the temporary directory/TMP/selfgzxxxxxxxx 
    cd /
    systemctl start $app.service >/dev/null
    cd - >/dev/null
    timeout=0  
    while [ `systemctl status $app.service|grep -c active` -eq 0 ]
    do         
        sleep 1
        timeout=$(($timeout+1))
        if [ $timeout -gt 3 ]; then
            echo "$app can not be started"
            break
        fi           
    done
}

# restart service
function service_restart
{
    local app=$1
    [ ! -f ${systemd_path}/$app.service ] && return

    cd /
    systemctl restart $app.service >/dev/null
    cd - >/dev/null
}

# according to the result of asking to stop the service
function ask_service_stop
{
    local app=$1
    [ ! -f ${systemd_path}/$app.service ] && return

    read_bool  "Stop service $app?" "yes"
    [ "$answer" == "yes" ] && systemctl stop $app.service >/dev/null 
}

# according to the result of asking to start the service
function ask_service_start
{
    local app=$1
    [ ! -f ${systemd_path}/$app.service ] && return

    read_bool  "Start service $app?" "yes"
    if [ "$answer" == "yes" ]; then
        cd /
        systemctl start $app.service  >/dev/null
        cd - >/dev/null
    fi
}

function stop_service_all
{
    service_stop  "daisy-api"
    service_stop  "daisy-registry"
    service_stop  "openstack-ironic-api"
    service_stop  "openstack-ironic-conductor"
    service_stop  "openstack-ironic-discoverd"
    service_stop  "openstack-keystone"
    service_stop  "daisy-orchestration"
}

# start all the service automatically
function start_service_all
{
    service_start  "mariadb"
    service_start  "openstack-keystone"
    service_start  "daisy-api"
    service_start  "daisy-registry"
    service_start  "openstack-ironic-api"
    service_start  "openstack-ironic-conductor"
    service_start  "openstack-ironic-discoverd"
    service_start  "daisy-orchestration"
}

_DAISY_COMMON_FUNC_FILE="common_func.sh"
fi 
