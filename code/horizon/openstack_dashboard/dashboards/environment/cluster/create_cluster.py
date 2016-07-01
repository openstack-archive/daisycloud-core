#
#   Copyright ZTE
#   Daisy Tools Dashboard
#
import json
from django.utils.translation import ugettext_lazy as _
from horizon import exceptions

from django.http import HttpResponse

from horizon import messages
from horizon import views

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.cluster import net_plane \
    as cluster_net_plane
from openstack_dashboard.dashboards.environment.cluster import role \
    as cluster_role
from openstack_dashboard.dashboards.environment.deploy import deploy_rule_lib

import logging
LOG = logging.getLogger(__name__)


class CreateView(views.HorizonTemplateView):
    template_name = "environment/cluster/create_cluster.html"

    def get_roles_data(self):
        roles_data = []
        try:
            role_list = api.daisy.role_list(self.request)
            roles = [role for role in role_list if role.type == "template"]
            for role in roles:
                roles_data.append({
                    "id": role.id,
                    "name": role.name
                })
            roles_data = cluster_role.sort_roles(roles_data)
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve host list.'))
        return roles_data

    def get_context_data(self, **kwargs):
        context = super(CreateView, self).get_context_data(**kwargs)
        context["network"] = {
            "networks": cluster_net_plane.get_default_net_plane()}
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        context["roles"] = self.get_roles_data()
        hwms = api.daisy.hwm_list(self.request)
        hwmip_list = [hwm.hwm_ip for hwm in hwms]
        context["hwmip_list"] = hwmip_list
        return context


def create_submit(request):
    data = json.loads(request.body)
    msg = ('Create cluster request.body::::::: %s') % data
    LOG.info(msg)

    cluster_new = []
    status_code = 200
    cluster = data["cluster_info"]

    try:
        cluster_created = api.daisy.cluster_add(
            request,
            name=cluster["cluster_name"],
            description=cluster["description"],
            networking_parameters=cluster["networking_parameters"],
            use_dns=cluster["use_dns"],
            hwm_ip=cluster["hwm_ip"])
        cluster_new.append({
            "id": cluster_created.id
        })

        # check param valid
        deploy_rule_lib.net_plane_4_role_rule(request,
                                              cluster_created.id,
                                              data["role_info"],
                                              data["netplane_info"])

        role_list = api.daisy.role_list(request)
        roles = [role for role in role_list
                 if role.cluster_id == cluster_created.id]
        for role in roles:
            if role.name == "CONTROLLER_HA":
                cluster_role.\
                    set_ha_role_for_new_cluster(request,
                                                role.id,
                                                data["role_info"]["ha"])
            if role.name == "CONTROLLER_LB":
                cluster_role.set_role_info(request,
                                           role.id,
                                           data["role_info"]["lb"])
            if role.name == "COMPUTER":
                cluster_role.\
                    set_computer_role_info(request,
                                           role.id,
                                           data["role_info"]["computer"])
            if role.name == "ZENIC_NFM":
                cluster_role.set_role_info(request,
                                           role.id,
                                           data["role_info"]["zenic_nfm"])
            if role.name == "ZENIC_CTL":
                cluster_role.set_role_info(request,
                                           role.id,
                                           data["role_info"]["zenic_ctl"])
        cluster_net_plane.add_net_plane_for_add_cluster(request,
                                                        cluster_created.id,
                                                        data["netplane_info"])
    except Exception as e:
        if len(cluster_new) > 0:
            api.daisy.cluster_delete(request, cluster_created.id)
        status_code = 500
        LOG.error('Create Cluster Failed: %s' % e)
        messages.error(request, 'Create Cluster Failed: %s' % e)

    return HttpResponse(json.dumps(cluster_new),
                        content_type="application/json",
                        status=status_code)
