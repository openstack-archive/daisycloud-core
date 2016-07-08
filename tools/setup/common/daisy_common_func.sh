#!/bin/bash
# ×î¸ßÈ«¾Ö¹«ÓÃº¯Êý£¬¿ÉÄÜ»á±»ËùÓÐÆäËû½Å±¾µ÷ÓÃ

#·ÀÖ¹½Å±¾ÖØ¸´±»°üº¬
if [ ! "$_DAISY_COMMON_FUNC_FILE" ];then

#######################ÎÊ´ð½»»¥Ïà¹Ø»ù±¾º¯Êý############################
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

# »ñÈ¡¶ÁÈ¡Ò»¸öIPÁÐ±íµÄ¹¦ÄÜ
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

#######################ÅäÖÃ¶ÁÐ´Ïà¹Ø»ù±¾º¯Êý############################

function get_config
{
    local file=$1
    local key=$2

    [ ! -e $file ] && return
    #ºöÂÔ¾®ºÅ¿ªÍ·µÄ×¢ÊÍÐÐÒÔ¼°¿ÕÐÐÖ®ºóÔÙgrep¹ýÂË"key"ËùÔÚµÄÐÐ
    local line=`sed '/^[[:space:]]*#/d' $file | sed /^[[:space:]]*$/d | grep -w "$key"| grep "$key[[:space:]]*=" -m1`
    if [ -z "$line" ]; then
        config_answer=""
    else
        #½«µÚÒ»¸ö=ºÅÌæ»»Îª¿Õ¸ñ£¬ÔÙÉ¾³ýµÚÒ»¸öµ¥´ÊµÃµ½value
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
    #×¢Òâ£ºÈç¹ûÄ³ÐÐÊÇ×¢ÊÍ£¬¿ªÍ·µÚÒ»¸ö×Ö·û±ØÐëÊÇ#ºÅ!!!
    local comment=`grep -c "^[[:space:]]*#[[:space:]]*$key[[:space:]]*=[[:space:]]*.*"  $file`
    
    if [[ $value == "#" ]];then
        if [ $exist -gt 0 ];then
            sed  -i "/^[^#]/s/$key[[:space:]]*=/\#$key=/" $file       
        fi
        return
    fi

    if [ $exist -gt 0 ];then
        #Èç¹ûÒÑ¾­´æÔÚÎ´×¢ÊÍµÄÓÐÐ§ÅäÖÃÐÐ£¬Ö±½Ó¸üÐÂvalue
        sed  -i "/^[^#]/s#$key[[:space:]]*=.*#$key=$value#" $file
        
    elif [ $comment -gt 0 ];then
        #Èç¹û´æÔÚÒÑ¾­×¢ÊÍµôµÄ¶ÔÓ¦ÅäÖÃÐÐ£¬ÔòÈ¥µô×¢ÊÍ£¬¸üÐÂvalue
        sed -i "s@^[[:space:]]*#[[:space:]]*$key[[:space:]]*=[[:space:]]*.*@$key=$value@" $file
    else
        #·ñÔòÔÚÄ©Î²×·¼ÓÓÐÐ§ÅäÖÃÐÐ
        echo "$key=$value" >> $file
    fi
}

#¿ÉÒÔ¸ù¾Ý[section]µÄÎ»ÖÃÔÚºóÃæ²åÈëkey=value£¬»òÕßÖ»ÓÐkeyµÄ×Ö¶Î
#Ä³Ð©ÅäÖÃÎÄ¼þÖÐ´æÔÚvalueÎª¿ÕµÄ¿ª¹ØÁ¿£¬´Ëº¯ÊýÊÔÓÃÓÚvalueÎª¿ÕµÄÇé¿ö£¬²»»á°ÑvalueÎª¿ÕÊ±Ê±ÉèÖÃÎª´íÎó¡£
function update_section_config
{
    local file=$1
    local section=$2
    local key=$3
    local value=$4

    [ ! -e $file ] && return

    #¸ù¾ÝsectionËÑÑ°ÎÄ¼þÖÐÊÇ·ñÓÐÄ³¸ökey
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

#»ñÈ¡ÎÄ¼þÖÐstringµÄÊýÁ¿
function get_string_num
{
    local file=$1
    local string=$2

    [ ! -e $file ] && { echo "$file doesn't exist."; exit 1; }
    #ºöÂÔ¾®ºÅ¿ªÍ·µÄ×¢ÊÍÐÐÒÔ¼°¿ÕÐÐÖ®ºóÔÙgrep¹ýÂË"key"ËùÔÚµÄÐÐ
    string_num=`sed '/^[[:space:]]*#/d' $file | sed /^[[:space:]]*$/d | grep -cw "$string"`
}

#±£´æÅäÖÃÐÅÏ¢,Ö¸¶¨ÅäÖÃÎÄ¼þ°²×°·½Ê½ºÍÐ¶ÔØ²»ÐèÒª±£´æ
#µ÷ÓÃ±¾º¯ÊýÊ±Ó¦±£Ö¤Í¬Ò»Ä£¿éµÄÅäÖÃ²ÎÊýÒ»´ÎÐÔÅäÖÃÍê£¬Èç²»ÄÜÏÈÅäÖÃ²¿·Ötc£¬È»ºóÅäÖÃcc£¬ÓÖ»ØÍ·ÅäÖÃtc
function user_config_save
{  
    local component="$1"
    local key="$2"
    local value="$3"

    if [ "$operation" = "install" ];then
        #Èç¹ûÓÃ»§ÅäÖÃÎÄ¼þÒÑ¾­´æÔÚÔò±¸·Ý¾ÉµÄÅäÖÃ
        if [ ! -f $user_config_save_file ];then
            mkdir -p ${user_config_save_path}     
            touch $user_config_save_file 
            echo -e "## opencos installation configure file at ${current_time}" >$user_config_save_file
            echo -e "## you can edit it and install opencos by conf_file option, as \"./installopencos_(arch).bin conf_file /home/tecs_install/user_install.conf\"\n" >>$user_config_save_file
            echo -e "## global configration section\nmode=$mode\n">>$user_config_save_file
            echo -e "## component configration section">>$user_config_save_file
        fi
        # Èç¹û£¬Ã»ÓÐ×é¼þ¹éÊô£¬Ôò·ÅÔÚmodeºó
        if [ "$component" = "" ];then
            [ "$key" = "" ] && { echo -e "\nkey is null, please check!"; exit 1; }
            sed -i "/mode=$mode/a $key=$value" $user_config_save_file
        else        
            [ -z "`cat $user_config_save_file |grep -w "\[$component\]"`" ] && echo -e "\n[$component]" >>$user_config_save_file
            [[ $key != "" ]] && echo "$key=$value" >>$user_config_save_file
        fi
    fi
}

#######################rpm°ü´¦ÀíÏà¹Ø»ù±¾º¯Êý############################

#ÅÐ¶ÏÄ³rpm°üÊÇ·ñÒÑ°²×°
function check_installed
{
    has_installed="no"
    
    rpm -q $1 &>/dev/null
    
    if [ 0 == $? ];then
        has_installed="yes"
    fi    
}

# ¼ì²érpm°üÊÇ·ñ±»ÒÀÀµ
function check_depend
{
    local rpm_name=$1
    # ¼ì²âÒÀÀµ°üÊÇ·ñ±»±ðÈËÊ¹ÓÃ
    rpm -q --whatrequires $rpm_name &>/dev/null
    # µ±²éÑ¯²»µ½±»ÒÀÀµµÄ¹ØÏµ»òrpmÎ´°²×°£¬·µ»ØµÄÊÇ1£¬·ñÔòÎª0
    return "$?"
}

# °²×°°üµÄº¯Êý
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
# ¼ì²âÒª°²×°µÄ°üÊÇ·ñ´æÔÚ£¬Èç¹û²»´æÔÚ£¬ÔòÌáÊ¾ÊÇ·ñÐèÒª°²×°
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

# ¼ì²âÒª°²×°µÄ°üÊÇ·ñ´æÔÚ£¬Èç¹û²»´æÔÚ£¬ÔòÌáÊ¾ÊÇ·ñÐèÒª°²×°£¬Èç¹û´æÔÚ£¬ÔòÐèÒªÉý¼¶
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

# ¼ì²âÊÇ·ñÐ­ÖúRPM°ü£¬Èç¹ûÒÑ¾­°²×°¹ýÁË£¬ÌáÊ¾ÊÇ·ñÒªÐ¶ÔØ
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

# ¼ì²âÖ¸¶¨°üÊÇ·ñÐèÒªÉý¼¶
function check_app_is_upgrade
{ 
    local app=$1
    is_update="yes"

    num=`$daisy_yum list updates | awk -F ' ' '{print$1}' | grep $app -c`
    if [[ $num == 0 ]];then
        is_update="no"
    fi
}

# Éý¼¶°üµÄº¯Êý
function upgrade_rpms_by_yum
{
    local app_list="$1"
    
    if [ "$app_list" = "" ];then
        echo -e "\nsorry, there is no rpm need to upgrade"!
        exit 0
    fi    
    #´Ë´¦Èç¹û°Ñapp_list×÷ÎªupgradeµÄ²ÎÊý£¬Èç¹ûÓÐÒ»¸ö²»ÐèÒªÉý¼¶»òÒÑ±»Éý¼¶
    #¹ýµÄdaisy·þÎñ£¬»áµ¼ÖÂÕû¸öÉý¼¶Ê§°Ü£¬Òò´ËÕâÀïÐ´Îª°ÑÃ¿¸ö·þÎñµ¥¶ÀÅÐ¶ÏÊÇ·ñÉý¼¶
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


#######################·þÎñ´¦ÀíÏà¹Ø»ù±¾º¯Êý############################
# Í£Ö¹·þÎñ
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

# Æô¶¯·þÎñ·þÎñ
function service_start
{
    local app=$1
    [ ! -f ${systemd_path}/$app.service ] && return

    #´Ë´¦cd /Óëcd -²»¿ÉÈ¥µô£¬ÎªÁË´¦Àí°²×°ºóÆô¶¯ÁÙÊ±Ä¿Â¼/tmp/selfgzxxxxxxxxÉ¾³ýµÄÎÊÌâ
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

# ÖØÆô¶¯·þÎñ·þÎñ
function service_restart
{
    local app=$1
    [ ! -f ${systemd_path}/$app.service ] && return

    cd /
    systemctl restart $app.service >/dev/null
    cd - >/dev/null
}

# ¸ù¾ÝÑ¯ÎÊ½á¹ûÀ´Í£Ö¹·þÎñ
function ask_service_stop
{
    local app=$1
    [ ! -f ${systemd_path}/$app.service ] && return

    read_bool  "Stop service $app?" "yes"
    [ "$answer" == "yes" ] && systemctl stop $app.service >/dev/null 
}

# ¸ù¾ÝÑ¯ÎÊ½á¹ûÀ´Æô¶¯·þÎñ
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

# ×Ô¶¯´ò¿ªËùÓÐ·þÎñ
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
