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
import os
import copy
import subprocess
import time
import commands

import traceback
import webob.exc
from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden
from webob.exc import HTTPServerError

import threading
from threading import Thread

from daisy import i18n
from daisy import notifier

from daisy.api import policy
import daisy.api.v1

from daisy.common import exception
import daisy.registry.client.v1.api as registry
from daisy.api.backends.kolla import config
from daisy.api.backends import driver
from daisy.api.network_api import network as neutron
from ironicclient import client as ironic_client
import daisy.api.backends.os as os_handle
import daisy.api.backends.common as daisy_cmn
import daisy.api.backends.kolla.common as kolla_cmn
import daisy.api.backends.kolla.install as instl

try:
    import simplejson as json
except ImportError:
    import json

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

#zenic_state = zenic_cmn.ZENIC_STATE

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

        #instl.pxe_server_build(req, install_meta)
        # get hosts config which need to install OS
        #hosts_need_os = instl.get_cluster_hosts_config(req, cluster_id)
        # if have hosts need to install os, ZENIC installataion executed in OSInstallTask
        #if hosts_need_os:
            #os_install_obj = instl.OSInstallTask(req, cluster_id, hosts_need_os)
            #os_install_thread = Thread(target=os_install_obj.run)
            #os_install_thread.start()
        #else:
        LOG.info(_("No host need to install os, begin install kolla for cluster %s." % cluster_id))
        kolla_install_task = instl.KOLLAInstallTask(req, cluster_id)
        kolla_install_task.start()

            
