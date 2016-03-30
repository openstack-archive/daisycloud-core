# Copyright 2013 NEC Corporation
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

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from horizon import exceptions
from horizon import forms
from horizon import workflows

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.network import workflows \
    as network_workflows


LOG = logging.getLogger(__name__)


class CreateSubnetInfoAction(network_workflows.CreateSubnetInfoAction):
    with_subnet = forms.BooleanField(initial=True, required=False,
                                     widget=forms.HiddenInput())
    msg = _('Specify "Network Address"')

    class Meta(object):
        name = _("Subnet")

    def clean(self):
        cleaned_data = workflows.Action.clean(self)
        self._check_subnet_data(cleaned_data)
        return cleaned_data


class CreateSubnetInfo(network_workflows.CreateSubnetInfo):
    action_class = CreateSubnetInfoAction
    #depends_on = ("network_id",)


class CreateSubnet(network_workflows.CreateNetwork):
    slug = "create_subnet"
    name = _("Create Subnet")
    finalize_button_name = _("Create")
    success_message = _('Created subnet "%s".')
    failure_message = _('Unable to create subnet "%s".')
    default_steps = (CreateSubnetInfo, )

    def format_status_message(self, message):
        name = self.context.get('subnet_name') or self.context.get('subnet_id')
        return message % name

    def handle(self, request, data):
        '''
        reqStr = repr(request)
        strArr = reqStr.split("/")
        cluster_id = strArr[4]
        logicnet_id = strArr[5]
        LOG.info('CreateSubnet cluster_id:%s  logicnet_id:%s' % (cluster_id, logicnet_id))
        cluster_info = api.daisy.cluster_get(request, cluster_id)
        '''
        subnet = self._create_subnet(request, data)
        return True if subnet else False



