# -*- coding: utf-8 -*-
# Copyright 2011 Justin Santa Barbara
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
Driver base-classes:

    (Beginning of) the contract that deployment backends drivers must follow,
    and shared types that support that contract
"""


from oslo_log import log as logging
from oslo_utils import importutils

from daisy import i18n

_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
LOG = logging.getLogger(__name__)


def load_deployment_driver(backend_name):
    """Load a cluster backend installation driver.
    """
    backend_driver = "%s.manager.OrchestrationManager" % backend_name

    LOG.info(_("Loading deployment backend '%s'") % backend_driver)
    try:
        driver = importutils.import_object_ns(
            'daisy.orchestration', backend_driver)
        #return check_isinstance(driver, DeploymentDriver)
        return driver
    except ImportError:
        LOG.exception(
            _("Error, unable to load the deployment backends '%s'"
                % backend_driver))
        return None
