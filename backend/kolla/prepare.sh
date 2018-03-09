#! /bin/bash
##############################################################################
# Copyright (c) 2016 ZTE Coreporation and others.
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Apache License, Version 2.0
# which accompanies this distribution, and is available at
# http://www.apache.org/licenses/LICENSE-2.0
##############################################################################
set -e

prepare_dir=$(dirname $(readlink -f "$0"))
config_path=/etc/systemd/system/docker.service.d/kolla.conf
if [ -f "$config_path" ]; then
    # Prevent prepare.sh to run again
    exit 0
fi

echo "nameserver 8.8.8.8" > /etc/resolv.conf
daisy_management_ip=$1
yum -y install epel-release centos-release-openstack-pike
yum clean all
#curl -sSL https://get.docker.io | bash
yum remove -y docker-engine
yum install -y $prepare_dir/docker-engine.rpm
[ "$?" -ne 0 ] && { exit 1; }

mkdir -p /etc/systemd/system/docker.service.d
touch /etc/sysconfig/docker
echo -e "other_args=\"--insecure-registry $daisy_management_ip:4000 --insecure-registry 127.0.0.1:4000\"" > /etc/sysconfig/docker
echo -e "[Service]\nMountFlags=shared\nEnvironmentFile=/etc/sysconfig/docker\nExecStart=\nExecStart=/usr/bin/docker daemon \$other_args" > $config_path
systemctl daemon-reload
systemctl restart docker
systemctl enable docker
yum install -y python2-docker

yum -y install ntp crudini
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

# multicast related
yum install -y $prepare_dir/daisy4nfv-jasmine*.rpm
docker load < $prepare_dir/registry-server.tar

#enlarge the TCP source port range to deal with functest thousands requests
sudo sysctl net.ipv4.ip_local_port_range="5000 65000"
echo -e "net.ipv4.ip_local_port_range= 5000 65000" >> /etc/sysctl.conf

