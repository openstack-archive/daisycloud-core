# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Nebula, Inc.
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

import logging

from django.utils.translation import ugettext_lazy as _
from horizon import tables
from openstack_dashboard.dashboards.environment.deploy import actions


LOG = logging.getLogger(__name__)


def Update_hostName(Object):
    pass


class DiscoverHosts(actions.OperateRegionAction):
    name = "dis_hosts"
    verbose_name = _("Dis_hosts")


class SelectHostsTable(tables.DataTable):
    host_name = tables.Column("name",
                              verbose_name=_("Name"),
                              update_action=Update_hostName)
    MAC = tables.Column("mac",
                        verbose_name=_("MAC"))
    interfaces = tables.Column("interface",
                               verbose_name=_("interface"))

    class Meta(object):
        name = "selectHosts"
        verbose_name = _("SelectHosts")
        # table_actions = (DiscoverHosts, AutoFillHostsName)
