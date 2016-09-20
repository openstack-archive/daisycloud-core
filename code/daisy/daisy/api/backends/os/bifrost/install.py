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
import copy
import subprocess
import time

from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
import threading

from daisy import i18n

from daisy.common import exception
from daisy.api import common
from daisy.common import utils
import daisy.registry.client.v1.api as registry
from ironicclient import client as ironic_client
from daisyclient.v1 import client as daisy_client
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.tecs.common as tecs_cmn

import ConfigParser

DISCOVER_DEFAULTS = {
    'listen_port': '5050',
    'ironic_url': 'http://127.0.0.1:6385/v1',
}

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

CONF = cfg.CONF
install_opts = [
    cfg.StrOpt('max_parallel_os_number', default=10,
               help='Maximum number of hosts install os at the same time.'),
]
CONF.register_opts(install_opts)
upgrade_opts = [
    cfg.StrOpt('max_parallel_os_upgrade_number', default=10,
               help='Maximum number of hosts upgrade os at the same time.'),
]
CONF.register_opts(upgrade_opts)

host_os_status = {
    'INIT': 'init',
    'PRE_INSTALL': 'pre-install',
    'INSTALLING': 'installing',
    'ACTIVE': 'active',
    'INSTALL_FAILED': 'install-failed',
    'UPDATING': 'updating',
    'UPDATE_FAILED': 'update-failed'
}

LINUX_BOND_MODE = {'balance-rr': '0', 'active-backup': '1',
                   'balance-xor': '2', 'broadcast': '3',
                   '802.3ad': '4', 'balance-tlb': '5',
                   'balance-alb': '6'}

daisy_tecs_path = tecs_cmn.daisy_tecs_path


def get_ironicclient():  # pragma: no cover
    """Get Ironic client instance."""
    config_discoverd = ConfigParser.ConfigParser(defaults=DISCOVER_DEFAULTS)
    config_discoverd.read("/etc/ironic-discoverd/discoverd.conf")
    ironic_url = config_discoverd.get("discoverd", "ironic_url")
    args = {'os_auth_token': 'fake',
            'ironic_url': ironic_url}
    return ironic_client.get_client(1, **args)


def get_daisyclient():
    """Get Daisy client instance."""
    config_daisy = ConfigParser.ConfigParser()
    config_daisy.read("/etc/daisy/daisy-api.conf")
    daisy_port = config_daisy.get("DEFAULT", "bind_port")
    args = {'version': 1.0, 'endpoint': 'http://127.0.0.1:' + daisy_port}
    return daisy_client.Client(**args)


class OSInstall(Thread):

    """
    Class for bifrost install OS.
    """
    """ Definition for install states."""

    def __init__(self, req, cluster_id):
        self.req = req
        self.cluster_id = cluster_id
        # 5s
        self.time_step = 5
        # 30 min
        self.single_host_install_timeout = 30 * (12 * self.time_step)

        self.max_parallel_os_num = int(CONF.max_parallel_os_number)
        self.cluster_hosts_install_timeout = (
            self.max_parallel_os_num / 4 + 2) * 60 * (12 * self.time_step)
        self.ironicclient = get_ironicclient()
        self.daisyclient = get_daisyclient()