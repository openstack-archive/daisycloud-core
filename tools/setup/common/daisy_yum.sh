#!/bin/bash

if [ ! "$_DAISY_YUM_FILE" ];then

function make_yum_server
{
    path=`pwd`
    createrepo --update $path &>/dev/null
    [ "$?" -ne 0 ] && { echo "createrepo in $path failed"; exit 1; }
}

function make_yum_client
{
    path=`pwd`
    repo_name=`uuidgen`
    patch_repo_name=daisy_depend
    daisy_repofile=/etc/yum.repos.d/daisy_install_temp.repo
    os_iso_repofile=/etc/yum.repos.d/OS_ISO.repo
    tfg_depend_repofile=/etc/yum.repos.d/TFG_DEPEND_PACKAGE.repo
    echo -e "[$repo_name]\nname=$repo_name\nbaseurl=file:$path\nenabled=1\ngpgcheck=0" > $daisy_repofile
    daisy_yum="yum -y --disablerepo=* --enablerepo=$repo_name"
    if [ -f "$os_iso_repofile" ];then
        daisy_yum="${daisy_yum}"" --enablerepo=OS_ISO"
    fi
    if [ -f "$tfg_depend_repofile" ];then
        daisy_yum="${daisy_yum}"" --enablerepo=TFG_DEPEND_PACKAGE"
    fi
    yum clean all &>/dev/null
}
function yum_set
{
    rm -rf /var/lib/rpm/__db.*
    rm -rf /etc/yum.repos.d/daisy*
    echo "creating yum repo, please wait for several seconds..."
    yum install -y createrepo
    make_yum_server
    make_yum_client
    echo "creating epel yum repo, please wait for several seconds..."
    yum install -y epel-release
    echo "creating openstack newton yum repo, please wait for several seconds..."
    yum install -y centos-release-openstack-newton
}

fi
export _DAISY_YUM_FILE="daisy_yum.sh"
