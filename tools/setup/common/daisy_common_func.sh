#!/bin/bash
# 最高全局公用函数，可能会被所有其他脚本调用

#防止脚本重复被包含
if [ ! "$_DAISY_COMMON_FUNC_FILE" ];then

#######################问答交互相关基本函数############################
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

# 获取读取一个IP列表的功能
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

#######################配置读写相关基本函数############################

function get_config
{
    local file=$1
    local key=$2

    [ ! -e $file ] && return
    #忽略井号开头的注释行以及空行之后再grep过滤"key"所在的行
    local line=`sed '/^[[:space:]]*#/d' $file | sed /^[[:space:]]*$/d | grep -w "$key"| grep "$key[[:space:]]*=" -m1`
    if [ -z "$line" ]; then
        config_answer=""
    else
        #将第一个=号替换为空格，再删除第一个单词得到value
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
    #注意：如果某行是注释，开头第一个字符必须是#号!!!
    local comment=`grep -c "^[[:space:]]*#[[:space:]]*$key[[:space:]]*=[[:space:]]*.*"  $file`
    
    if [[ $value == "#" ]];then
        if [ $exist -gt 0 ];then
            sed  -i "/^[^#]/s/$key[[:space:]]*=/\#$key=/" $file       
        fi
        return
    fi

    if [ $exist -gt 0 ];then
        #如果已经存在未注释的有效配置行，直接更新value
        sed  -i "/^[^#]/s#$key[[:space:]]*=.*#$key=$value#" $file
        
    elif [ $comment -gt 0 ];then
        #如果存在已经注释掉的对应配置行，则去掉注释，更新value
        sed -i "s@^[[:space:]]*#[[:space:]]*$key[[:space:]]*=[[:space:]]*.*@$key=$value@" $file
    else
        #否则在末尾追加有效配置行
        echo "$key=$value" >> $file
    fi
}

#可以根据[section]的位置在后面插入key=value，或者只有key的字段
#某些配置文件中存在value为空的开关量，此函数试用于value为空的情况，不会把value为空时时设置为错误。
function update_section_config
{
    local file=$1
    local section=$2
    local key=$3
    local value=$4

    [ ! -e $file ] && return

    #根据section搜寻文件中是否有某个key
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

#获取文件中string的数量
function get_string_num
{
    local file=$1
    local string=$2

    [ ! -e $file ] && { echo "$file doesn't exist."; exit 1; }
    #忽略井号开头的注释行以及空行之后再grep过滤"key"所在的行
    string_num=`sed '/^[[:space:]]*#/d' $file | sed /^[[:space:]]*$/d | grep -cw "$string"`
}

#保存配置信息,指定配置文件安装方式和卸载不需要保存
#调用本函数时应保证同一模块的配置参数一次性配置完，如不能先配置部分tc，然后配置cc，又回头配置tc
function user_config_save
{  
    local component="$1"
    local key="$2"
    local value="$3"

    if [ "$operation" = "install" ];then
        #如果用户配置文件已经存在则备份旧的配置
        if [ ! -f $user_config_save_file ];then
            mkdir -p ${user_config_save_path}     
            touch $user_config_save_file 
            echo -e "## opencos installation configure file at ${current_time}" >$user_config_save_file
            echo -e "## you can edit it and install opencos by conf_file option, as \"./installopencos_(arch).bin conf_file /home/tecs_install/user_install.conf\"\n" >>$user_config_save_file
            echo -e "## global configration section\nmode=$mode\n">>$user_config_save_file
            echo -e "## component configration section">>$user_config_save_file
        fi
        # 如果，没有组件归属，则放在mode后
        if [ "$component" = "" ];then
            [ "$key" = "" ] && { echo -e "\nkey is null, please check!"; exit 1; }
            sed -i "/mode=$mode/a $key=$value" $user_config_save_file
        else        
            [ -z "`cat $user_config_save_file |grep -w "\[$component\]"`" ] && echo -e "\n[$component]" >>$user_config_save_file
            [[ $key != "" ]] && echo "$key=$value" >>$user_config_save_file
        fi
    fi
}

#######################rpm包处理相关基本函数############################

#判断某rpm包是否已安装
function check_installed
{
    has_installed="no"
    
    rpm -q $1 &>/dev/null
    
    if [ 0 == $? ];then
        has_installed="yes"
    fi    
}

# 检查rpm包是否被依赖
function check_depend
{
    local rpm_name=$1
    # 检测依赖包是否被别人使用
    rpm -q --whatrequires $rpm_name &>/dev/null
    # 当查询不到被依赖的关系或rpm未安装，返回的是1，否则为0
    return "$?"
}

# 安装包的函数
function install_rpm_by_yum
{
    local rpm_name=$1

    yum install $rpm_name

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
# 检测要安装的包是否存在，如果不存在，则提示是否需要安装
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

# 检测要安装的包是否存在，如果不存在，则提示是否需要安装，如果存在，则需要升级
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

# 检测是否协助RPM包，如果已经安装过了，提示是否要卸载
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

# 检测指定包是否需要升级
function check_app_is_upgrade
{ 
    local app=$1
    is_update="yes"

    num=`$daisy_yum list updates | awk -F ' ' '{print$1}' | grep $app -c`
    if [[ $num == 0 ]];then
        is_update="no"
    fi
}

# 升级包的函数
function upgrade_rpms_by_yum
{
    local app_list="$1"
    
    if [ "$app_list" = "" ];then
        echo -e "\nsorry, there is no rpm need to upgrade"!
        exit 0
    fi    
    #此处如果把app_list作为upgrade的参数，如果有一个不需要升级或已被升级
    #过的daisy服务，会导致整个升级失败，因此这里写为把每个服务单独判断是否升级
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


#######################服务处理相关基本函数############################
# 停止服务
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

# 启动服务服务
function service_start
{
    local app=$1
    [ ! -f ${systemd_path}/$app.service ] && return

    #此处cd /与cd -不可去掉，为了处理安装后启动临时目录/tmp/selfgzxxxxxxxx删除的问题
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

# 重启动服务服务
function service_restart
{
    local app=$1
    [ ! -f ${systemd_path}/$app.service ] && return

    cd /
    systemctl restart $app.service >/dev/null
    cd - >/dev/null
}

# 根据询问结果来停止服务
function ask_service_stop
{
    local app=$1
    [ ! -f ${systemd_path}/$app.service ] && return

    read_bool  "Stop service $app?" "yes"
    [ "$answer" == "yes" ] && systemctl stop $app.service >/dev/null 
}

# 根据询问结果来启动服务
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

# 自动打开所有服务
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
