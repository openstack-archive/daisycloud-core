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
OS_Driver base-classes:

    (Beginning of) the contract that os installation drivers must follow,
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


class OsDriver(object):

    """	base class for os installation interface.
    """

    def install(self, req, cluster_id):
        raise NotImplementedError()


def check_isinstance(obj, cls):
    """Checks that obj is of type cls, and lets PyLint infer types."""
    if isinstance(obj, cls):
        return obj
    raise Exception(_('Expected object of type: %s') % (str(cls)))


def load_install_os_dirver(os_install_type):

    """	Load a operating system installation driver.
    """
    os_installation_driver = "%s.api.OSInstall" % os_install_type

    LOG.info(_("Loading os driver '%s'") % os_installation_driver)
    try:
        driver = importutils.import_object_ns(
            'daisy.api.os', )
        return check_isinstance(driver, OsDriver)
    except ImportError:
        LOG.exception(
            _("Error, unable to load the os driver '%s'"
                % os_installation_driver))
        return None
