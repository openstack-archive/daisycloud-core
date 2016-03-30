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

import logging

from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext_lazy

from horizon import exceptions
from horizon import messages
from horizon import tables
from horizon.utils import memoized

from openstack_dashboard import api
from openstack_dashboard import policy


LOG = logging.getLogger(__name__)

class DeleteSubnet(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Delete Subnet",
            u"Delete Subnets",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Deleted Subnet",
            u"Deleted Subnets",
            count
        )

    def get_success_url(self, request):
        reqStr = repr(request)
        strArr = reqStr.split("/")
        cluster_id = strArr[4].split('%23')[0]
        return reverse("horizon:environment:network:logicnet", args=[cluster_id])

    def get_failure_url(self, request):
        reqStr = repr(request)
        strArr = reqStr.split("/")
        id_num = strArr[4].split('%23')
        cluster_id = id_num[0]
        logicnet_id = id_num[1]
        LOG.info('subnet tables fail <<<<cluster_id=%s logicnet_id=%s>>>' % (cluster_id,logicnet_id))
        logicnet = "%s#%s" % (cluster_id,logicnet_id)
        LOG.info('subnet tables fail <<<<logicnet=%s>>>' % logicnet)
        return reverse("horizon:environment:network:logicnetdetail", args=[logicnet])

    def delete(self, request, obj_id):
        '''
        reqStr = repr(request)
        strArr = reqStr.split("/")
        cluster_id = strArr[4]
        '''
        try:
            LOG.info("*** del obj_id = %s" % obj_id)
            strArr = obj_id.split("#")
            cluster_id = strArr[0]
            LOG.info("*** delete cluster_id = %s" % cluster_id)
            cluster = api.daisy.cluster_get(request, cluster_id)
            nets = cluster.logic_networks
            LOG.debug("*** delete logic_networks = %s" % nets)
            _network_id = strArr[1]
            subnetname = strArr[2]
            LOG.info("*** del _network_id = %s" % _network_id)
            LOG.info("*** del subnetname = %s" % subnetname)

            for net in nets:
                if net["id"] == _network_id:
                    for subnet in net["subnets"]:
                          LOG.info("*** delete subnet = %s" % subnet)
                          if subnet["name"] == subnetname:
                                   net["subnets"].remove(subnet)
            api.daisy.cluster_update(request,
                                     cluster_id,
                                     description = cluster.description,
                                     name = cluster.name,
                                     networking_parameters = cluster.networking_parameters,
                                     networks = cluster.networks,
                                     routers = cluster.routers,
                                     logic_networks=nets)
        except Exception as e:
            msg = _('Unable to delete subnet "%s": %s') % (subnetname,e)
            LOG.info(msg)
            messages.error(request, msg)
            redirect = self.get_failure_url(request)
            raise exceptions.Http302(redirect)

            # exceptions.handle(request, msg, redirect=redirect)

        

class SubnetsTable(tables.DataTable):
    name = tables.Column("name", verbose_name=_("Name"))
    cidr = tables.Column("cidr", verbose_name=_("Network Address"))
    floating_ranges = tables.Column("floating_ranges", verbose_name=_("Floating Ranges"))
    dns_nameservers = tables.Column("dns_nameservers", verbose_name=_("Dns Nameservers"))
    gateway = tables.Column("gateway", verbose_name=_("Gateway"))
    failure_url = reverse_lazy('horizon:environment:network:index')

    def get_object_id(self, obj):
        reqStr = repr(self.request)
        LOG.debug("*** get_id reqStr = %s" % reqStr)
        strArr = reqStr.split("/")
        cluster = strArr[4].split("%23")
        cluster_id = cluster[0]
        logicnet_id = cluster[1]
        LOG.debug("*** subnet_id= %s#%s#%s" % (cluster_id, logicnet_id, obj['name']))
        return "%s#%s#%s" % (cluster_id, logicnet_id, obj['name'])

    def get_object_display(self, obj):
        return obj['name']

    class Meta(object):
        name = "subnets"
        verbose_name = _("Subnets")
        table_actions = (DeleteSubnet,)
        row_actions = (DeleteSubnet,)
        hidden_title = False
