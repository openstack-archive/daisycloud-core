#! /bin/bash

###################################################################################
#  询问与安装系统（OS/OPENCOS）相关的配置参数
#  入口：interact_setup
#  各模块的交互脚本放在/custom/interact/目录下,并在此interfact()添加调用脚本函数
###################################################################################
export WORKDIR
source $WORKDIR/scripts/custom/interact/neutron_interact.sh
#交互函数
function interfact()
{
    local CUSTOM_CFG_FILE=$1
    ask_manage_bond $CUSTOM_CFG_FILE $2
    ask_virtualization_mechanism $CUSTOM_CFG_FILE 
}



