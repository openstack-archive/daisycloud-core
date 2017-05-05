#! /bin/bash
echo "nameserver 8.8.8.8" > /etc/resolv.conf
daisy_management_ip=$1
yum -y install epel-release
curl -sSL https://get.docker.io | bash
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
yum -y install ansible

# multicast related
prepare_dir=$(dirname $(readlink -f "$0"))
yum install -y $prepare_dir/jasmine*.rpm
docker load < $prepare_dir/registry-server.tar

sysctl net.core.netdev_max_backlog=65536
sysctl net.core.optmem_max=25165824
sysctl net.core.rmem_default=25165824
sysctl net.core.rmem_max=25165824
sysctl net.ipv4.tcp_rmem="20480 12582912 25165824"
sysctl net.ipv4.udp_rmem_min=16384
sysctl net.core.wmem_default=25165824
sysctl net.core.wmem_max=25165824
sysctl net.ipv4.tcp_wmem="20480 12582912 25165824"
sysctl net.ipv4.udp_wmem_min=16384

echo -e 'net.core.netdev_max_backlog=65536
net.core.optmem_max=25165824
net.core.rmem_default=25165824
net.core.rmem_max=25165824
net.ipv4.tcp_rmem=20480 12582912 25165824
net.ipv4.udp_rmem_min=16384
net.core.wmem_default=25165824
net.core.wmem_max=25165824
net.ipv4.tcp_wmem=20480 12582912 25165824
net.ipv4.udp_wmem_min=16384' > /etc/sysctl.d/94-daisy.conf