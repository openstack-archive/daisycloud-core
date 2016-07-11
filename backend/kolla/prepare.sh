#! /bin/bash

yum -y install epel-release
yum -y install python-pip
curl -sSL https://get.docker.io | bash
mkdir -p /etc/systemd/system/docker.service.d
config_name=`uuidgen`
config_path=/etc/systemd/system/docker.service.d/kolla.conf
echo -e "[Service]\nMountFlags=shared" > $config_path
systemctl daemon-reload
systemctl restart docker
yum install -y python-docker-py
yum -y install ntp
systemctl enable ntpd.service
systemctl stop libvirtd.service
systemctl disable libvirtd.service
systemctl start ntpd.service
yum -y install ansible1.9
