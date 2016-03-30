import logging
from horizon import forms
from django.core.urlresolvers import reverse
from django import template
from django.template import defaultfilters as filters
from django.utils.translation import pgettext_lazy
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext_lazy

from horizon import exceptions
from horizon import messages
from horizon import tables

from openstack_dashboard import api


LOG = logging.getLogger(__name__)

 
class CreateRoute(tables.LinkAction):
    name = "create"
    verbose_name = _("Create Route")
    classes = ("ajax-modal",)
    icon = "plus"

    def get_link_url(self, datum=None):
        cluster_id = self.table.kwargs["cluster_id"]
        url = "/dashboard/environment/network/" + cluster_id + "/routes/create/"
        return url


class DeleteRoutesAction(tables.DeleteAction):
    name = "delete"
    data_type_singular = _("Route")
    data_type_plural = _("Routes")

    def __init__(self, **kwargs):
        super(DeleteRoutesAction, self).__init__(**kwargs)
        self.icon = "remove"

    def delete(self, request, obj_name):
        try:
            cluster_id = self.table.kwargs["cluster_id"]
            cluster = api.daisy.cluster_get(request, cluster_id)
            routers = cluster.routers

            for router in routers:
                if router["name"] == obj_name:
                    routers.remove(router)
            api.daisy.cluster_update(request, cluster_id, **(cluster.__dict__))
        except Exception:
            #obj = self.table.get_object_by_id(obj_id)
            name = obj_name
            msg = _('Unable to delete router "%s"') % name
            LOG.info(msg)
            exceptions.handle(request, msg)


class RouteTable(tables.DataTable):
    name = tables.Column('name', verbose_name=_('Name'),
                         form_field=forms.CharField(required=True,
                                                    max_length=64))
    description = tables.Column('description',
                                verbose_name=_('Description'),
                                form_field=forms.CharField(
                                    widget=forms.Textarea(),
                                    required=False))
    external_logic_network = tables.Column('external_logic_network',
                                           verbose_name=_('External_logic_network'))
    subnets = tables.Column('subnets', verbose_name=_('Subnets'),
                            form_field=forms.CharField(required=False))

    def get_object_id(self, datum):
       # return datum["id"]
        return datum["name"]

    def get_object_display(self, obj):
        return obj["name"]

    class Meta:
        name = "routes"
        verbose_name = _("Routes")
        multi_select = True
        row_actions = (DeleteRoutesAction,)
        table_actions = (CreateRoute, DeleteRoutesAction)


class CreateSubnet(tables.LinkAction):
    name = "subnet"
    verbose_name = _("Add Subnet")
    url = "/logicnet/subnets/create"
    classes = ("ajax-modal",)
    icon = "plus"

    def allowed(self, request, datum=None):
        return True

    def get_link_url(self, datum=None):
        if datum:
            logicnet_id = self.table.get_object_id(datum).split("#")[1]
            self.url = logicnet_id + self.url
        return self.url


class CreateNetwork(tables.LinkAction):
    name = "create"
    verbose_name = _("Create LogicNetwork")
    url = "logicnet/create"
    classes = ("ajax-modal",)
    icon = "plus"

    def allowed(self, request, datum=None):
        return True


class DeleteNetwork(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Delete Network",
            u"Delete Networks",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Deleted Network",
            u"Deleted Networks",
            count
        )

    def delete(self, request, network_id):
        try:
            cluster_id = network_id.split("#")[0]
            cluster = api.daisy.cluster_get(request, cluster_id)
            LOG.info("logic delete cluster:%s" % cluster)
            nets = cluster.logic_networks
            _network_id = network_id.split("#")[1]
            LOG.info("logic delete cluster_id:%s    _network_id:%s" % (cluster_id, _network_id))

            for net in nets:
                if net["id"] == _network_id:
                    network_name = net.get('name')
                    LOG.info("logic delete network:%s" % network_name)
                    nets.remove(net)

            api.daisy.cluster_update(request,
                                     cluster_id,
                                     description = cluster.description,
                                     name = cluster.name,
                                     networking_parameters = cluster.networking_parameters,
                                     networks = cluster.networks,
                                     routers = cluster.routers,
                                     logic_networks=nets)
        except Exception as e:
            msg = _('Unable to delete network "%s": %s') % (network_name,e)
            LOG.info(msg)
            messages.error(request, msg)
            redirect = reverse("horizon:environment:network:logicnet",
                               args=[cluster_id])
            raise exceptions.Http302(redirect)

class NetworksTable(tables.DataTable):
    name = tables.Column("name",
                         verbose_name=_("Name"),
                         link='horizon:environment:network:logicnetdetail')
    type = tables.Column("type",
                         verbose_name=_("Type"))
    shared = tables.Column("shared", verbose_name=_("Shared"),
                           filters=(filters.yesno, filters.capfirst))
    segmentation_type = tables.Column("segmentation_type",
                         verbose_name=_("Segmentation type"))
    physnet_name = tables.Column("physnet_name",
                         verbose_name=_("Physnet name"))


    def get_object_id(self, obj):
        reqStr = repr(self.request)
        strArr = reqStr.split("/")
        cluster_id = strArr[4]
        return "%s#%s" % (cluster_id,obj['id'])

    def get_object_display(self, obj):
        return obj['name']

    class Meta(object):
        name = "networks"
        verbose_name = _("Logic Networks")
        table_actions = (CreateNetwork, )
        row_actions = (CreateSubnet, DeleteNetwork)

