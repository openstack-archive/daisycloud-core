#!/bin/sh
# 让某个主机彻底信任我，以后ssh登录过去不需要密码

#检查参数是否合法
logfile=/var/log/trustme.log
function print_log
{
   local promt="$1"
   echo -e "$promt"
   echo -e "`date -d today +"%Y-%m-%d %H:%M:%S"`  $promt" >> $logfile
}

ip=$1
if [ -z $ip ]; then
  print_log "Usage: `basename $0` ipaddr passwd"
  exit 1
fi

passwd=$2
if [ -z $passwd ]; then
  print_log "Usage: `basename $0` ipaddr passwd" 
  exit 1
fi

rpm -qi sshpass >/dev/null 
if [ $? != 0 ]; then
  print_log "Please install sshpass first"
  exit 1
fi

#试试对端能不能ping得通
unreachable=`ping $ip -c 1 -W 3 | grep -c "100% packet loss"`
if [ $unreachable -eq 1 ]; then
  print_log "host $ip is unreachable"
  exit 1
fi

#如果本机还没有ssh公钥，就生成一个
if [ ! -e ~/.ssh/id_dsa.pub ]; then
  print_log "generating ssh public key ..."
  ssh-keygen -t dsa -f /root/.ssh/id_dsa -N ""
  if [ $? != 0 ]; then
    print_log "ssh-keygen failed"
    exit 1
  fi
fi

#首先在对端删除原来保存的信任公钥
user=`whoami`
host=`hostname`
keyend="$user@$host"
print_log "my keyend = $keyend"
cmd="sed '/$keyend$/d'  -i ~/.ssh/authorized_keys"
#echo cmd:$cmd
print_log "clear my old pub key on $ip ..."
sshpass -p $passwd ssh -o StrictHostKeyChecking=no $ip "rm -rf /root/.ssh/known_hosts"
if [ $? != 0 ]; then
    print_log "ssh $ip to delete known_hosts failed"
    exit 1
fi
sshpass -p $passwd ssh -o StrictHostKeyChecking=no $ip "touch ~/.ssh/authorized_keys"
if [ $? != 0 ]; then
    print_log "ssh $ip to create file authorized_keys failed"
    exit 1
fi
sshpass -p $passwd ssh -o StrictHostKeyChecking=no $ip "$cmd"
if [ $? != 0 ]; then
    print_log "ssh $ip to edit authorized_keys failed"
    exit 1
fi
#把新生成的拷贝过去
print_log "copy my public key to $ip ..."
tmpfile=/tmp/`hostname`.key.pub
sshpass -p $passwd scp -o StrictHostKeyChecking=no ~/.ssh/id_dsa.pub  $ip:$tmpfile
if [ $? != 0 ]; then
    print_log "scp file to $ip failed"
    exit 1
fi
#在对端将其追加到authorized_keys
print_log "on $ip, append my public key to ~/.ssh/authorized_keys ..."
sshpass -p $passwd ssh -o StrictHostKeyChecking=no $ip "cat $tmpfile >> ~/.ssh/authorized_keys"
if [ $? != 0 ]; then
    print_log "ssh $ip to add public key for authorized_keys failed"
    exit 1
fi
print_log "rm tmp file $ip:$tmpfile"
sshpass -p $passwd ssh -o StrictHostKeyChecking=no $ip "rm $tmpfile" 
if [ $? != 0 ]; then
    print_log "ssh $ip to delete tmp file failed"
    exit 1
fi
print_log "trustme ok!"

