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
import daisy.api.v1
import daisy.registry.client.v1.api as registry
from daisy.api.backends import driver
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

        LOG.info(_("No host need to install os, begin install kolla for cluster %s." % cluster_id))
        kolla_install_task = instl.KOLLAInstallTask(req, cluster_id)
        kolla_install_task.start()


