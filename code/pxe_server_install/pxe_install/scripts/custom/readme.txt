说明：
1.在此目录中的文件，都将自动拷贝到安装系统后的目标机的/home/opencos_install/custom/目录
2.before.sh 文件是用来一键执行/home/opencos_install/custom/before下的所有的before_开头的shell脚本
3.after.sh 文件是用来一键执行/home/opencos_install/custom/after的所有的after_开头的shell脚本
4.before文件夹放安装opencos文件夹前执行的脚本，after为安装文件夹后执行的脚本
5.各模块的交互脚本放在custom/interact目录下，添加新脚本后须在custom目录interact.sh中添加调用代码。