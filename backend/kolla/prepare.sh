#! /bin/bash

daisy_management_ip=$1
yum -y install epel-release
curl -sSL https://get.docker.io | bash
mkdir -p /etc/systemd/system/docker.service.d
config_path=/etc/systemd/system/docker.service.d/kolla.conf
touch /etc/sysconfig/docker
echo -e "other_args=\"--insecure-registry $daisy_management_ip:4000\"" > /etc/sysconfig/docker
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
