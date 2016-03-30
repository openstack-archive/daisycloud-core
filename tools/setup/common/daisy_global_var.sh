#!/bin/bash
#1.最高全局变量，可能会被所有其他脚本调用，export后，也可被子进程中的执行的脚本调用
#2.所有脚本中不得有和这些变量名字冲突的变量
#3.请不要给这里的全局变量随意赋值，有些初始化必须为空 

#防止脚本重复被包含
if [ ! "$_GLOBAL_VAR_FILE" ];then

#daisy安装向导操作时间记录
export current_time=""
#daisy操作，包括install、uninstall、clean、upgrade等
export operation=""
#安装中的具体模式
export mode=""
#yum命令封装
export daisy_yum=""

#daisy安装文件目录
export daisy_install_path="/home/daisy_install"

export systemd_path="/usr/lib/systemd/system"
export lsb_path="/etc/init.d"
#用户指定配置文件

#数据库用户名密码
export dbusername=root
export dbpassword=root

export _GLOBAL_VAR_FILE="daisy_global_var.sh"
fi
