#! /bin/bash
##############################################################################
# Copyright (c) 2016 ZTE Coreporation and others.
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Apache License, Version 2.0
# which accompanies this distribution, and is available at
# http://www.apache.org/licenses/LICENSE-2.0
##############################################################################
set -e

config_path=/etc/systemd/system/docker.service.d/kolla.conf
if [ -f "$config_path" ]; then
    # Prevent prepare.sh to run again
    exit 0
fi

echo "nameserver 8.8.8.8" > /etc/resolv.conf
daisy_management_ip=$1
yum -y install epel-release

#curl -sSL https://get.docker.io | bash
yum remove -y docker-engine
yum install -y https://yum.dockerproject.org/repo/main/centos/7/Packages/docker-engine-17.05.0.ce-1.el7.centos.x86_64.rpm
[ "$?" -ne 0 ] && { exit 1; }
mkdir -p /etc/systemd/system/docker.service.d
touch /etc/sysconfig/docker
echo -e "other_args=\"--insecure-registry $daisy_management_ip:4000 --insecure-registry 127.0.0.1:4000\"" > /etc/sysconfig/docker
echo -e "[Service]\nMountFlags=shared\nEnvironmentFile=/etc/sysconfig/docker\nExecStart=\nExecStart=/usr/bin/docker daemon \$other_args" > $config_path
systemctl daemon-reload
systemctl restart docker
systemctl enable docker
yum install -y python-docker-py

yum -y install ntp
systemctl enable ntpd.service
systemctl start ntpd.service

systemctl stop libvirtd.service || true
systemctl disable libvirtd.service || true

systemctl disable NetworkManager
systemctl stop NetworkManager
service network start
chkconfig network on

systemctl disable firewalld
systemctl stop firewalld

yum -y install ansible

# multicast related
prepare_dir=$(dirname $(readlink -f "$0"))
yum install -y $prepare_dir/daisy4nfv-jasmine*.rpm
docker load < $prepare_dir/registry-server.tar
