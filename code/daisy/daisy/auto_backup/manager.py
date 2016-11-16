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
/auto backup for tecs API
"""
import time
import os

from oslo_config import cfg
from oslo_log import log as logging

from daisy.common import exception
from daisyclient.v1.client import Client
import ConfigParser
import daisy.api.backends.tecs.common as tecs_cmn

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class AutoBackupManager():

    def __init__(self, *args, **kwargs):
        """Load auto backup options and initialization."""
        self.backup_hour = 23
        self.backup_min = 59
        self.config_path = '/home/daisy_install/daisy.conf'
        self.auto_back_path = '/home/daisy_backup/auto/'

    def get_auto_backup_config(self):
        auto_backup_switch = 'OFF'
        save_days = 10
        local_hour = time.localtime().tm_hour
        local_min = time.localtime().tm_min
        if local_hour == self.backup_hour and local_min == self.backup_min:
            config = ConfigParser.ConfigParser()
            config.read(self.config_path)
            if 'auto_backup_switch' in dict(config.items('DEFAULT')):
                auto_backup_switch = config.get("DEFAULT",
                                                "auto_backup_switch")
            else:
                auto_backup_switch = 'ON'
            if "save_days" in dict(config.items('DEFAULT')):
                save_days = config.getint("DEFAULT", "save_days")
        return {
            "auto_backup_switch": auto_backup_switch,
            "save_days": save_days
        }

    def clean_history_backup_file(self, save_days):
        if not os.path.exists(self.auto_back_path):
            return
        try:
            clean_scripts = []
            for item in os.listdir(self.auto_back_path):
                path = os.path.join(self.auto_back_path, item)
                if not os.path.isfile(path):
                    continue
                save_seconds = save_days * 24 * 3600
                if int(time.time()) - int(os.path.getctime(path)) > \
                        save_seconds:
                    clean_scripts.append('rm -rf {0}'.format(path))
            if clean_scripts:
                tecs_cmn.run_scrip(clean_scripts,
                                   msg='Delete Backup files failed!')
        except Exception as e:
            LOG.error("excute clean history backup file failed!%s",
                      e.message)

    def backup_daisy_system(self, daisy_client):
        try:
            backup = daisy_client.backup_restore.backup(**{})
            backup_file = getattr(backup, 'backup_file')
            if not backup_file:
                LOG.error("Auto backup daisy failed,file name is empty.")
                return
            backup_file_name = os.path.split(backup_file)[1]
            # copy backup file to dest directory
            scripts = [
                'test -d {0}||mkdir -p {0}'.format(self.auto_back_path),
                'cp -rf {0} {1}'.format(backup_file, self.auto_back_path),
                'chmod 777 {0} {0}{1}'.format(self.auto_back_path,
                                              backup_file_name),
                'rm -rf {0}'.format(backup_file)
            ]
            tecs_cmn.run_scrip(scripts, msg='Auto Backup file failed!')
        except Exception as e:
            LOG.error("backup daisy system failed!%s", e.message)

    @staticmethod
    def auto_backup():
        try:
            auto_backup_insl = AutoBackupManager()
            auto_backup_config = auto_backup_insl.get_auto_backup_config()
            if auto_backup_config['auto_backup_switch'] != 'ON':
                return
            # clean history backup file
            auto_backup_insl.clean_history_backup_file(
                auto_backup_config['save_days'])
            # back up daisy
            daisy_version = 1.0
            config_discoverd = ConfigParser.ConfigParser()
            config_discoverd.read("/etc/daisy/daisy-api.conf")
            bind_port = config_discoverd.get("DEFAULT", "bind_port")
            daisy_endpoint = "http://127.0.0.1:" + bind_port
            daisy_client = Client(
                version=daisy_version, endpoint=daisy_endpoint)
            auto_backup_insl.backup_daisy_system(daisy_client)
        except exception.Invalid as e:
            LOG.exception(e.message)
