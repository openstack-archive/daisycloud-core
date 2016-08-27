#!/bin/sh
#to be trusted by other host£¬and no password needed when use ssh command

#check parameters legality
logfile=/var/log/trustme.log
function print_log
{
   local promt="$1"
   echo -e "$promt"
   echo -e "`date -d today +"%Y-%m-%d %H:%M:%S"`  $promt" >> $logfile
}
ip=$1
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

#ping other host
unreachable=`ping $ip -c 1 -W 3 | grep -c "100% packet loss"`
if [ $unreachable -eq 1 ]; then
  print_log "host $ip is unreachable"
  exit 1
fi

#generate ssh pubkey
if [ ! -e ~/.ssh/id_dsa.pub ]; then
  print_log "generating ssh public key ..."
  ssh-keygen -t dsa -f /root/.ssh/id_dsa -N "" <<EOF
n
EOF
  if [ $? != 0 ]; then
    print_log "ssh-keygen failed"
    exit 1
  fi
fi

#clear old public key
user=`whoami`
host=`hostname`
keyend="$user@$host"
print_log "my keyend = $keyend"
cmd="sed '/$keyend$/d'  -i ~/.ssh/authorized_keys"
print_log "clear my old pub key on $local_host ..."
ssh-keygen -f "/root/.ssh/known_hosts" -R $ip
if [ $? != 0 ]; then
    print_log "delete pub key of $ip from known_hosts failed"
    exit 1
fi
sshpass -p $passwd ssh -o StrictHostKeyChecking=no $ip "mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys"
if [ $? != 0 ]; then
    print_log "ssh $ip to create file authorized_keys failed"
    exit 1
fi
sshpass -p $passwd ssh -o StrictHostKeyChecking=no $ip "$cmd"
if [ $? != 0 ]; then
    print_log "ssh $ip to edit authorized_keys failed"
    exit 1
fi
#copy new public key
print_log "copy my public key to $ip ..."
tmpfile=/tmp/`hostname`.key.pub
sshpass -p $passwd scp -o StrictHostKeyChecking=no ~/.ssh/id_dsa.pub  $ip:$tmpfile
if [ $? != 0 ]; then
    print_log "scp file to $ip failed"
    exit 1
fi
#copy public key to authorized_keys
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

