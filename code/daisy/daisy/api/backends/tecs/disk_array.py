# Copyright 2013 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
/install endpoint for tecs API
"""
import subprocess
from oslo_log import log as logging

from daisy import i18n

from daisy.common import exception
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.tecs.common as tecs_cmn

try:
    import simplejson as json
except ImportError:
    import json

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW


def _get_service_disk_for_disk_array(req, role_id):
    disk_info = []
    service_disks = tecs_cmn.get_service_disk_list(req,
                                                   {'filters': {
                                                       'role_id': role_id}})
    for service_disk in service_disks:
        share_disk = {}
        if service_disk['disk_location'] == 'share':
            share_disk['service'] = service_disk['service']
            share_disk['protocol_type'] = service_disk['protocol_type']
            share_disk['lun'] = service_disk['lun']
            if service_disk['protocol_type'] == 'FIBER':
                share_disk['fc_hba_wwpn'] = \
                    service_disk['data_ips'].split(',')
            else:
                share_disk['data_ips'] = service_disk['data_ips'].split(',')
            share_disk['lvm_config'] = {}
            share_disk['lvm_config']['size'] = service_disk['size']
            share_disk['lvm_config']['vg_name'] =\
                'vg_%s' % service_disk['service']
            share_disk['lvm_config']['lv_name'] =\
                'lv_%s' % service_disk['service']
            share_disk['lvm_config']['fs_type'] = 'ext4'
            disk_info.append(share_disk)
    return disk_info


def _get_share_cluster_disk_for_disk_array(req, role_id):
    '''
    disk_info = [{'service': 'db', 'lun': 'lun1', 'data_ips':'data_ip1'},
                {'service': 'db', 'lun': 'lun2', 'data_ips':'data_ip2'},
                {'service': 'glance', 'lun': 'lun3', 'data_ips':'data_ip3'},
                {'service': 'glance', 'lun': 'lun4', 'data_ips':'data_ip4'},]
    '''
    disk_info = []
    service_disks = \
        tecs_cmn.get_service_disk_list(req, {'filters': {'role_id': role_id}})
    service_name = 'db'
    for service_disk in service_disks:
        share_cluster_disk = {}
        if service_disk['disk_location'] == 'share_cluster':
            share_cluster_disk['service'] = service_disk['service']
            share_cluster_disk['protocol_type'] = service_disk['protocol_type']
            share_cluster_disk['lun'] = service_disk['lun']
            if service_disk['protocol_type'] == 'FIBER':
                share_cluster_disk['fc_hba_wwpn'] = \
                    service_disk['data_ips'].split(',')
            else:
                share_cluster_disk['data_ips'] = \
                    service_disk['data_ips'].split(',')
            share_cluster_disk['lvm_config'] = {}
            share_cluster_disk['lvm_config']['size'] = service_disk['size']
            share_cluster_disk['lvm_config']['vg_name'] =\
                'vg_%s' % service_disk['service']
            share_cluster_disk['lvm_config']['lv_name'] =\
                'lv_%s' % service_disk['service']
            share_cluster_disk['lvm_config']['fs_type'] = 'ext4'
            disk_info.append(share_cluster_disk)
    return disk_info


def _get_cinder_volume_for_disk_array(req, role_id):
    cinder_volume_info = []
    cinder_volumes = tecs_cmn.get_cinder_volume_list(req,
                                                     {'filters': {
                                                         'role_id': role_id}})
    for cinder_volume in cinder_volumes:
        cv_info = {}
        cv_info['management_ips'] =\
            cinder_volume['management_ips'].split(',')
        cv_info['data_ips'] = cinder_volume['data_ips'].split(',')
        cv_info['user_name'] = cinder_volume['user_name']
        cv_info['user_pwd'] = cinder_volume['user_pwd']
        index = cinder_volume['backend_index']
        cv_info['backend'] = {index: {}}
        cv_info['backend'][index]['volume_driver'] =\
            cinder_volume['volume_driver']
        cv_info['backend'][index]['volume_type'] =\
            cinder_volume['volume_type']
        cv_info['backend'][index]['pools'] =\
            cinder_volume['pools'].split(',')
        cinder_volume_info.append(cv_info)
    return cinder_volume_info


def get_disk_array_info(req, cluster_id):
    share_disk_info = []
    share_cluster_disk_info = []
    volume_disk_info = {}
    cinder_volume_disk_list = []
    roles = daisy_cmn.get_cluster_roles_detail(req, cluster_id)
    for role in roles:
        if role['deployment_backend'] != daisy_cmn.tecs_backend_name:
            continue
        if role['name'] == 'CONTROLLER_HA':
            share_disks = _get_service_disk_for_disk_array(req, role['id'])
            share_cluster_disks = \
                _get_share_cluster_disk_for_disk_array(req, role['id'])
            share_disk_info += share_disks
            share_cluster_disk_info += share_cluster_disks
            cinder_volumes =\
                _get_cinder_volume_for_disk_array(req, role['id'])
            cinder_volume_disk_list += cinder_volumes
    if cinder_volume_disk_list:
        volume_disk_info['disk_array'] = cinder_volume_disk_list
    return (share_disk_info, volume_disk_info, share_cluster_disk_info)


def config_ha_share_disk(share_disk_info,
                         controller_ha_nodes,
                         share_cluster_disk_info=None):
    '''
    share_disk_info = \
        [{'service': 'db', 'lun': 'lun1', 'data_ips':'data_ip1'},
        {'service': 'glance', 'lun': 'lun3', 'data_ips':'data_ip3'},]
    share_cluster_disk_info = \
                [{'service': 'db', 'lun': 'lun1', 'data_ips':'data_ip1', ...},
                {'service': 'db', 'lun': 'lun2', 'data_ips':'data_ip2', ...},
                {'service': 'glance', 'lun': 'lun3', 'data_ips':'data_ip3'},
                {'service': 'glance', 'lun': 'lun4', 'data_ips':'data_ip4'},]
    controller_ha_nodes[host_ip] = min_mac
    '''
    sorted_db_share_cluster = []
    if share_cluster_disk_info:
        db_share_cluster_disk = \
            [disk for disk in share_cluster_disk_info
                if disk['service'] == 'db']
        if len(db_share_cluster_disk) != 2:
            error_msg = 'share cluster disk: %s must be existed in pair.' % \
                db_share_cluster_disk
            LOG.error(error_msg)
            raise exception.InstallException(error_msg)
        sorted_db_share_cluster = \
            sorted(db_share_cluster_disk, key=lambda s: s['lun'])
    sorted_ha_nodes = \
        sorted(controller_ha_nodes.iteritems(), key=lambda d: d[1])
    sorted_ha_nodes_ip = [node[0] for node in sorted_ha_nodes]

    all_share_disk_info = []
    if sorted_db_share_cluster:
        all_share_disk_info = \
            [[disk] + share_disk_info for disk in sorted_db_share_cluster]
        # all_share_disk_info = \
        #   [[{'lun': 'lun1', 'service': 'db', 'data_ips': 'data_ip1'},
        #   {'lun': 'lun3', 'service': 'glance', 'data_ips': 'data_ip3'}],
        #   [{'lun': 'lun2', 'service': 'db', 'data_ips': 'data_ip2'},
        #   {'lun': 'lun3', 'service': 'glance', 'data_ips': 'data_ip3'}]]
    else:
        for index in range(len(sorted_ha_nodes)):
            all_share_disk_info.append(share_disk_info)
        # all_share_disk_info = \
        #    [{'lun': 'lun3', 'service': 'glance', 'data_ips': 'data_ip3'},
        #    {'lun': 'lun3', 'service': 'glance', 'data_ips': 'data_ip3'}]

    '''
    cmd = 'rm -rf /var/lib/daisy/tecs/storage_auto_config/base/*.json'
    daisy_cmn.subprocess_call(cmd)
    with open("/var/lib/daisy/tecs/storage_auto_config/base/control.json",\
              "w") as fp:
        json.dump(share_disk_info, fp, indent=2)

    for host_ip in controller_ha_nodes.keys():
        try:
            scp_bin_result = subprocess.check_output(
                'scp -o StrictHostKeyChecking=no -r\
                 /var/lib/daisy/tecs/storage_auto_config\
                 %s:/home/tecs_install' % (host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            error_msg = "scp /var/lib/daisy/tecs/storage_auto_config\
                         to %s failed!" % host_ip
            raise exception.InstallException(error_msg)
        try:
            LOG.info(_("Config share disk for host %s" % host_ip))
            cmd = "cd /home/tecs_install/storage_auto_config/;\
                   python storage_auto_config.py share_disk %s"\
                   % controller_ha_nodes[host_ip]
            exc_result = subprocess.check_output(
                            'clush -S -w %s "%s"' % (host_ip,cmd),
                            shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            LOG.info(_("Storage script error message: %s" % e.output))
            error_msg = "config Disk Array share disks\
                         on %s failed!" % host_ip
            raise exception.InstallException(error_msg)
    '''

    cmd = 'rm -rf /var/lib/daisy/tecs/storage_auto_config/base/*.json'
    daisy_cmn.subprocess_call(cmd)

    for (host_ip, share_disk) in zip(sorted_ha_nodes_ip, all_share_disk_info):
        with open("/var/lib/daisy/tecs/storage_auto_config/base/control.json",
                  "w") as fp:
            json.dump(share_disk, fp, indent=2)

        try:
            subprocess.check_output(
                'scp -o StrictHostKeyChecking=no -r\
                 /var/lib/daisy/tecs/storage_auto_config\
                 %s:/home/tecs_install' % (host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            error_msg = "scp /var/lib/daisy/tecs/storage_auto_config\
                         to %s failed!" % host_ip
            raise exception.InstallException(error_msg)

        try:
            LOG.info(_("Config share disk for host %s" % host_ip))
            cmd = "cd /home/tecs_install/storage_auto_config/;\
                   python storage_auto_config.py share_disk %s"\
                   % controller_ha_nodes[host_ip]
            subprocess.check_output(
                'clush -S -w %s "%s"' % (host_ip, cmd),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            LOG.info(_("Storage script error message: %s" % e.output))
            error_msg = "config Disk Array share disks\
                         on %s failed!" % host_ip
            raise exception.InstallException(error_msg)


def config_ha_cinder_volume(volume_disk_info, controller_ha_ips):
    cmd = 'rm -rf /var/lib/daisy/tecs/storage_auto_config/base/*.json'
    daisy_cmn.subprocess_call(cmd)
    with open("/var/lib/daisy/tecs/storage_auto_config/base/cinder.json",
              "w") as fp:
        json.dump(volume_disk_info, fp, indent=2)
    for host_ip in controller_ha_ips:
        try:
            subprocess.check_output(
                'scp -o StrictHostKeyChecking=no -r\
                 /var/lib/daisy/tecs/storage_auto_config\
                 %s:/home/tecs_install' % (host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            error_msg = "scp /var/lib/daisy/tecs/storage_auto_config\
                         to %s failed!" % host_ip
            raise exception.InstallException(error_msg)
        try:
            LOG.info(_("Config cinder volume for host %s" % host_ip))
            cmd = 'cd /home/tecs_install/storage_auto_config/;\
                   python storage_auto_config.py cinder_conf %s' % host_ip
            subprocess.check_output(
                'clush -S -w %s "%s"' % (host_ip, cmd),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            LOG.info(_("Storage script error message: %s" % e.output))
            error_msg = "config Disk Array cinder volumes\
                         on %s failed!" % host_ip
            raise exception.InstallException(error_msg)


def config_compute_multipath(hosts_ip):
    for host_ip in hosts_ip:
        try:
            subprocess.check_output(
                'scp -o StrictHostKeyChecking=no -r\
                 /var/lib/daisy/tecs/storage_auto_config\
                 %s:/home/tecs_install' % (host_ip,),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            error_msg = "scp /var/lib/daisy/tecs/storage_auto_config\
                         to %s failed!" % host_ip
            raise exception.InstallException(error_msg)
        try:
            LOG.info(_("Config multipath for host %s" % host_ip))
            cmd = 'cd /home/tecs_install/storage_auto_config/;\
                   python storage_auto_config.py check_multipath'
            subprocess.check_output(
                'clush -S -w %s "%s"' % (host_ip, cmd),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            LOG.info(_("Storage script error message: %s" % e.output))
            error_msg = "config Disk Array multipath\
                         on %s failed!" % host_ip
            raise exception.InstallException(error_msg)
