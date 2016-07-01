#【sprint42】 42242: 版本回退@daisy1

|修改日期	|修改人 | 	修改内容|
|:----|:----|:----:|:----|
|2016-06-17| 陈雪英 |    新增|

##1、特性简介
版本回退方案验证背景：TECS升级失败，需要回退。
环境信息

| 角色 |主控   |备控   |   计算节点|
|:----|:----|:----:|:----|
|主机 |  A |     B |     C|
|当前老版本| 100  |  100  |  100|
|待升新版本  | 101  | 101 | 101 |
正常升级流程：
第一步 HA禁止倒换，升级B/C版本到最新，  B 100--->101， C 100----->101
第二步 A--->B，AB主备倒换，B为主
第三步 等待20分钟，进行基本功能验证
第四步 升级A 100----->101
第五步 取消禁止倒换

如果版本升级之后，第三步验证时发现新版本101有问题，需要支持环境回退到老版本100。

##2、方案验证

**验证组网**：控制节点glance/db/dbbackup/monagodb使用共享磁盘方式+OVS
要求正常升级环境时到以上第三步发现异常后需要将B,C回退到老版本
### A 新版本使用有问题，回退B,C

当前环境信息

| 角色 |主控   |备控   |   计算节点|
|:----|:----|:----:|:----|
|主机 |  A备 |     B主 |     C计|
|当前环境版本| 100  |  101（异常）  |  101|

==**回退步骤**：==
**1、取消禁止倒换，B--->A，AB主备倒换，A转主**（A转主失败的情况暂不考虑）
取消禁止倒换：pcs resource clear lb_float_ip
ABy 主备倒换  pcs cluster move host_162_160_1_132， host_162_160_1_132 为A的主机名
time:10s

**2、再次禁止倒换**
禁止倒换命令：pcs resource ban lb_float_ip host_162_160_1_132
host_162_160_1_132即为B的主机名
time:2s

**3、在daisy中保存待回退版本100**
copy time:10s

**4、回退计算节点C（101---->100）**
1）如果计算节点使用的是DVS网络，保存计算节点上的nova.conf文件为nova_old.conf（需要关注计算节点是否还有其他配置需要保存，多后端iscsi_use_multipath的配置）
save nova.conf time:10s

2）如果计算节点有虚拟机，需要迁移相关虚拟机到其他计算节点
migrate vm time:unknown, 120
注意：虚拟如果不迁移，需要用户接受以下三种情况：
a、计算节点故障
b、用户能接受虚拟机中断业务
c、用户不能接受需要TECS保证不同版本之间支持迁移

3）运行在docker的daisy，进入如下/var/lib/daisy/tecs//f3e0fd0c-512b-43b6-a078-f9c41c0daa8a/目录获取tecs.conf，mappings.json文件，并拷贝到daisy的/home/tecs_install目录下
time:60s

4）修改tecs.conf文件中的EXCLUDE_SERVERS和CONFIG_NEUTRON_ML2_JSON_PATH配置项
EXCLUDE_SERVERS=A,B  (填写不需要重新安装的节点A和B)
CONFIG_NEUTRON_ML2_JSON_PATH = /home/tecs_install/mappings.json  (填写mappings.json文件所在的路径)
time=60s

5）到计算节点上B用bin包手动卸载异常版本101
time=120s

6）在daisy节点执行100.bin文件，使用5 conf方式安装计算节点TECS版本。
**注意：**安装bin前需要清理daisy主机上/root/.ssh/known_hosts文件中的C点的公钥信息，否则安装时会让输入ssh密码
Adding post install manifest entries                 [ DONE ]
root@10.43.203.90's password: 
time=200s

7）TECS安装成功之后，
需要手动修改nova.conf文件：
compute_manager=nova.compute.manager.ComputeManager配置项修改为
compute_manager=nova.compute.tecs_manager.TecsComputeManager；(已知问题，TECS2.0_P7B1中未合入，最新DEV版本NOVA已经修改)
vncserver_proxyclient_address=127.0.0.1配置项修改为
vncserver_proxyclient_address=host-162-160-1-12.STORAGE
如果配置的是DVS，比较nova_old.conf与当前计算节点的nova.conf文件，手动修改nova.conf中的vcpu_pin_set和vcpupin_policy等配置项；
或者直接用原来的nova_old.conf文件替换当前nova.conf文件

8)重启C的服务openstack-service restart
注意:openstack-nova-storage服务也要手动重启一下

9)检查计算节点服务全部正常启动。

**5、回退控制节点备板B（100----->101）**
1）参考回退计算节点方法配置控制节点B的tecs.conf文件，EXCLUDE_SERVERS=A，C
CONFIG_NEUTRON_ML2_JSON_PATH = /home/tecs_install/mappings.json
2）到控制节点B上用bin包手动卸载异常版本101
time=3'35"=215s

3）在B板上执行100.bin文件，使用5 conf方式安装TECS版本。
time=11'15"=615s

注意：安装bin前需要清理daisy主机上/root/.ssh/known_hosts文件中的B点的公钥信息，否则安装时会让输入ssh密码
Adding post install manifest entries                 [ DONE ]
root@10.43.203.90's password: 

4）TECS版本安装完成之后，在备板B上执行/home/tecs_install/storage_auto_config目录下执行python storage_auto_config.py cinder_conf cinderManageIP，同步cinder多后端配置。
注意： 如果是自研KS3200磁阵，对于后端使用的cinder_zte_conf.xml文件需要手动修改这个字段：`<LocalIP>129.0.0.8</LocalIP>`；
也可以执行上面命令时加IP地址，如python storage_auto_config.py cinder_conf cinderManageIP
cinderManageIP为cinder组件的管理平面地址。
time=10s

5)从正常的控制节点A拷贝/etc/corosync/corosync.conf，/var/lib/pcsd/ip_name.conf，/var/lib/pcsd/pcs_settings.conf 到B的相同目录下


如果是集群方式，还需要拷贝/etc/drdb.d/WebData.res 文件到相同目录下
6）在备节点B上执行pcs cluster start命令启动集群
time=10s

7）用systemctl status pacemaker.service检查服务状态OK，crm_mon -1资源启动正常
8）清除禁止HA倒换操作，pcs resource clear lb_float_ip
9）HA可能会自动设置为维护模式，需要手动取消维护模式，相关命令，pcs property set unmanaged=false
10）如果glance/db/dbbackup/monagodb盘是集群方式还需要将主板上的数据手动同步到备板的磁盘上。


**6、检查回退的版本是否正常**
1）主备控制节点HA进行倒换，可以正常倒换
2）创建虚拟机正常

### B 升级节点B时异常回退B
参考以上5、回退控制节点备板B

| 角色 |主控   |备控   |   计算节点|
|:----|:----|:----:|:----|
|主机 |  A备 |     B主 |     C计|
|当前环境版本| 100  |  101（异常）  |  100|

### C 升级节点C时异常回退C
| 角色 |主控   |备控   |   计算节点|
|:----|:----|:----:|:----|
|主机 |  A备 |     B主 |     C计|
|当前环境版本| 100  |  100  |  101(异常)|
参考以上4、回退计算节点C

##3、遗留问题
本地集群和共享集群方式需要继续验证

##4、合入版本
无

##5、注意事项
LB的资源不能手动配置，通过安装保证
计算节点安装完成之后需要手动修改nova.conf文件中的巨页配置信息
计算节点安装完成之后需要手动修改nova.conf文件中的多路径配置信息
控制节点，cinder多后端配置会丢失，bin方式安装后默认只有LVM后端
CEPH后端需要手动修改CEPH相关配置。
对于有些数据库不兼容的情况需要单独考虑

##6、文档修改
无

##7、验收方法
无