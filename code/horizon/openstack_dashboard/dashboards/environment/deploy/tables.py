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
