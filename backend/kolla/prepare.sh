#! /bin/bash
echo "nameserver 8.8.8.8" > /etc/resolv.conf
daisy_management_ip=$1
yum -y install epel-release
#curl -sSL https://get.docker.io | bash
yum remove -y docker-engine
yum install -y https://yum.dockerproject.org/repo/main/centos/7/Packages/docker-engine-17.05.0.ce-1.el7.centos.x86_64.rpm
mkdir -p /etc/systemd/system/docker.service.d
config_path=/etc/systemd/system/docker.service.d/kolla.conf
touch /etc/sysconfig/docker
echo -e "other_args=\"--insecure-registry $daisy_management_ip:4000 --insecure-registry 127.0.0.1:4000\"" > /etc/sysconfig/docker
echo -e "[Service]\nMountFlags=shared\nEnvironmentFile=/etc/sysconfig/docker\nExecStart=\nExecStart=/usr/bin/docker daemon \$other_args" > $config_path
systemctl daemon-reload
systemctl restart docker
yum install -y python-docker-py
yum -y install ntp
systemctl enable ntpd.service
systemctl stop libvirtd.service
systemctl disable libvirtd.service
systemctl start ntpd.service
systemctl disable NetworkManager
systemctl stop NetworkManager
service network start
chkconfig network on
systemctl disable firewalld
systemctl stop firewalld
yum -y install ansible

# multicast related
prepare_dir=$(dirname $(readlink -f "$0"))
yum install -y $prepare_dir/jasmine*.rpm
docker load < $prepare_dir/registry-server.tar
