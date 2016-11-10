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
/install endpoint for kolla API
"""
from oslo_log import log as logging

from daisy import i18n
from daisy.api.backends import driver
import daisy.api.backends.kolla.install as instl


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW


class API(driver.DeploymentDriver):

    def __init__(self):
        super(API, self).__init__()
        return

    def install(self, req, cluster_id):
        """
        Install kolla to a cluster.

        param req: The WSGI/Webob Request object
        cluster_id:cluster id
        """

        LOG.info(_("No host need to install os, begin install \
                     kolla for cluster %s." % cluster_id))
        kolla_install_task = instl.KOLLAInstallTask(req, cluster_id)
        kolla_install_task.start()

    def update_progress_to_db(self, req, update_info, discover_host_meta):
        discover = {}
        discover['status'] = update_info['status']
        discover['message'] = update_info['message']
        if update_info.get('host_id'):
            discover['host_id'] = update_info['host_id']
        LOG.info("discover:%s", discover)
        registry.update_discover_host_metadata(req.context,
                                               discover_host_meta['id'],
                                               discover)

    def _check_uninstall_hosts(self, req, cluster_id, uninstall_hosts):
        pass

    def prepare_ssh_discovered_node(self, req, fp, discover_host_meta):
        try:
            trustme_result = subprocess.check_output(
                '/var/lib/daisy/kolla/trustme.sh %s %s' %
                (discover_host_meta['ip'], discover_host_meta['passwd']),
                shell=True, stderr=subprocess.STDOUT)
            if 'Permission denied' in trustme_result:
                # when passwd was wrong
                update_info = {}
                update_info['status'] = 'DISCOVERY_FAILED'
                update_info['message'] = "Passwd was wrong, do" \
                                         "trustme.sh %s failed!"\
                                         % discover_host_meta['ip']
                self.update_progress_to_db(req, update_info,
                                           discover_host_meta)
                msg = (_("Do trustme.sh %s failed!" %
                         discover_host_meta['ip']))
                LOG.warn(_(msg))
                fp.write(msg)
            elif 'is unreachable' in trustme_result:
                # when host ip was unreachable
                update_info = {}
                update_info['status'] = 'DISCOVERY_FAILED'
                update_info['message'] = "Host ip was unreachable," \
                                         " do trustme.sh %s failed!" %\
                                         discover_host_meta['ip']
                self.update_progress_to_db(req, update_info,
                                           discover_host_meta)
                msg = (_("Do trustme.sh %s failed!" %
                         discover_host_meta['ip']))
                LOG.warn(_(msg))
        except subprocess.CalledProcessError as e:
            update_info = {}
            update_info['status'] = 'DISCOVERY_FAILED'
            msg = "discover host for %s failed! raise CalledProcessError" \
                  " when execute trustme.sh." % discover_host_meta['ip']
            update_info['message'] = msg
            self.update_progress_to_db(
                req, update_info, discover_host_meta)
            LOG.error(_(msg))
            fp.write(e.output.strip())
            return
        except:
            update_info = {}
            update_info['status'] = 'DISCOVERY_FAILED'
            update_info['message'] = "discover host for %s failed!" \
                                     % discover_host_meta['ip']
            self.update_progress_to_db(
                req, update_info, discover_host_meta)
            LOG.error(_("discover host for %s failed!"
                        % discover_host_meta['ip']))
            fp.write("discover host for %s failed!"
                     % discover_host_meta['ip'])
            return

        try:
            cmd = 'clush -S -b -w %s "rm -rf /home/daisy/discover_host"'\
                  % (discover_host_meta['ip'],)
            daisy_cmn.subprocess_call(cmd, fp)
            cmd = 'clush -S -w %s "mkdir -p /home/daisy/discover_host"'\
                  % (discover_host_meta['ip'],)
            daisy_cmn.subprocess_call(cmd, fp)
            cmd = 'clush -S -w %s "chmod 777 /home/daisy/discover_host"'\
                  % (discover_host_meta['ip'],)
            daisy_cmn.subprocess_call(cmd, fp)
        except subprocess.CalledProcessError as e:
            update_info = {}
            update_info['status'] = 'DISCOVERY_FAILED'
            msg = "raise CalledProcessError when execute cmd for host %s."\
                  % discover_host_meta['ip']
            update_info['message'] = msg
            self.update_progress_to_db(
                req, update_info, discover_host_meta)
            LOG.error(_(msg))
            fp.write(e.output.strip())
            return

        try:
            subprocess.check_output(
                'clush -S -w %s -c /var/lib/daisy/kolla/getnodeinfo.sh '
                '--dest=/home/daisy/discover_host' %
                (discover_host_meta['ip'],),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            update_info = {}
            update_info['status'] = 'DISCOVERY_FAILED'
            update_info['message'] = "scp getnodeinfo.sh" \
                                     " failed!" % discover_host_meta['ip']
            self.update_progress_to_db(req, update_info,
                                       discover_host_meta)
            LOG.error(_("scp getnodeinfo.sh for %s failed!"
                        % discover_host_meta['ip']))
            fp.write(e.output.strip())
            return

        try:
            subprocess.check_output(
                'clush -S -w %s yum install -y epel-release'
                % (discover_host_meta['ip'],),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            update_info = {}
            update_info['status'] = 'DISCOVERY_FAILED'
            update_info['message'] = \
                "creat repo epel for %s failed!"\
                % discover_host_meta['ip']
            self.update_progress_to_db(req, update_info,
                                       discover_host_meta)
            LOG.error(_("creat repo epel for %s failed!"
                        % discover_host_meta['ip']))
            fp.write(e.output.strip())

            return
        try:
            subprocess.check_output(
                'clush -S -w %s yum install -y jq'
                % (discover_host_meta['ip'],),
                shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            update_info = {}
            update_info['status'] = 'DISCOVERY_FAILED'
            update_info['message'] = \
                "install jq rpm for %s failed!"\
                % discover_host_meta['ip']
            self.update_progress_to_db(req, update_info,
                                       discover_host_meta)
            LOG.error(_("install jq rpm for %s failed!"
                        % discover_host_meta['ip']))
            fp.write(e.output.strip())
            return

    def getnodeinfo_ip(self, daisy_management_ip):
        cmd = 'dhcp_linenumber=`grep -n "dhcp_ip="' \
              ' /var/lib/daisy/kolla/getnodeinfo.sh|cut -d ":" -f 1` && ' \
              'sed -i "${dhcp_linenumber}c dhcp_ip=\'%s\'" ' \
              '/var/lib/daisy/kolla/getnodeinfo.sh' \
              % (daisy_management_ip,)
        daisy_cmn.subprocess_call(cmd)

    def getnodeinfo_listen_port(self, listen_port):
        cmd = 'port_linenumber=`grep -n "listen_port="' \
              ' /var/lib/daisy/kolla/getnodeinfo.sh|cut -d ":" -f 1` && ' \
              'sed -i "${port_linenumber}c listen_port=\'%s\'" ' \
              '/var/lib/daisy/kolla/getnodeinfo.sh' % (listen_port,)
        daisy_cmn.subprocess_call(cmd)
