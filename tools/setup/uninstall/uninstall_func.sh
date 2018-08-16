#!/bin/bash
# 
if [ ! "$_UNINSTALL_FUNC" ];then
_UNINSTALL_FUNC_DIR=`pwd`
cd $_UNINSTALL_FUNC_DIR/../common
.  daisy_common_func.sh

cd $_UNINSTALL_FUNC_DIR

function operate_db
{
    local component="$1"
    local tecs_component_conf="$2"
    
    PS3="Please select an operation to process the database: " # 设置提示符字串.
    select db_operation in "rename" "drop" "nochange" "help"
    do
        echo
        echo "you select an operation: $db_operation."
        echo
        break  
    done   
    
    answer=$db_operation

    case $answer in
        "nochange")
        ;; 
        "rename")
        #确保之前已经执行过get_db_info和set_db_env
        rename_db "$component" "$tecs_component_conf"
        ;; 
        "drop")
        #确保之前已经执行过get_db_info和set_db_env
        clear_db "$component" "$tecs_component_conf"
        ;; 
        "help")
        echo "nochange: nothing to do"
        echo "rename: will reserve the database, and rename it to \"name__bak__'date'\""
        echo "drop: will delete the database."
        operate_db "$component" "$tecs_component_conf"
        ;;    
        *)
        echo "unknown install argument: $answer!"
        operate_db "$component" "$tecs_component_conf"
        ;;
    esac
}

#卸载过程中数据库处理
function db_process_uninstall
{  
    local component="$1"
    local tecs_component_conf="$2"
  
    #根据配置文件获取数据库信息
    get_db_info "$tecs_component_conf" || { echo "failed to process database of $component"; return 1; } 

    #设置环境变量
    set_db_env
    is_db_exist $component $tecs_component_conf
    if [ "$db_exist" != "" ];then
        echo -e "\n$component database exist, named \"$db_name\"."
    else
        return 0
    fi
    
    operate_db "$component" "$tecs_component_conf"
}

_UNINSTALL_FUNC="uninstall_func.sh"
fi
