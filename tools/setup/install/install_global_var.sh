#!/bin/bash

#用于安装daisy使用的全局变量

if [ ! "$_INSTALL_GLOBAL_VAR_FILE" ];then

database_server_port=5432
cloudname=daisycloud
clustername=daisycluster
debugmode="no"
message_server=""

_INSTALL_GLOBAL_VAR_FILE="install_global_var.sh"
fi
