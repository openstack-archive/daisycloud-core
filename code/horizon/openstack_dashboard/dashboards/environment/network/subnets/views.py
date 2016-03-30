# Copyright 2012 NEC Corporation
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
Views for managing Neutron Subnets.
"""
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import tabs
from horizon.utils import memoized
from horizon import workflows

from openstack_dashboard import api

from openstack_dashboard.dashboards.environment.network.subnets \
    import tables as project_tables
from openstack_dashboard.dashboards.environment.network.subnets \
    import tabs as project_tabs
from openstack_dashboard.dashboards.environment.network.subnets import utils
from openstack_dashboard.dashboards.environment.network.subnets \
    import workflows as subnet_workflows


class CreateView(workflows.WorkflowView):
    workflow_class = subnet_workflows.CreateSubnet


