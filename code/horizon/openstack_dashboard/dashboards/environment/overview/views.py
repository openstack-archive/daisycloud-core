from horizon import views
from django.utils.translation import ugettext_lazy as _
from django.http import HttpResponse
from horizon import exceptions
from horizon import messages
from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.deploy \
    import views as deploy_view
from django.views.decorators.csrf import csrf_exempt

import json
import logging
LOG = logging.getLogger(__name__)


class OverviewView(views.HorizonTemplateView):
    template_name = "environment/overview/index.html"

    def get_clusters(self):
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]

        for cluster in cluster_lists:
            qp = {"cluster_id": cluster.id}
            host_list = api.daisy.host_list(self.request, filters=qp)
            cluster.host_count = len(host_list)
            cluster.model = _("Default")
            host_info = deploy_view.format_deploy_info(host_list)
            cluster.host_deploying = host_info[0]['count']
            cluster.host_failed = host_info[1]['count']
            cluster.host_success = host_info[2]['count']
            if not cluster.segmentation_type:
                cluster.segmentation_type = ""

        return cluster_lists

    def get_template(self):
        templates = []
        try:
            template_list = api.daisy.template_list(self.request)
            for cluster_template in template_list:
                template_detail =\
                    api.daisy.template_detail(self.request,
                                              cluster_template.id)
                content = json.loads(template_detail.content)
                cluster = content.get("cluster", None)
                network = cluster.get("networking_parameters", None)
                templates.append({
                    "name": cluster_template.name,
                    "description": cluster.get("description", None),
                    "base_mac": network.get("base_mac", None),
                    "segmentation_type": network.get("segmentation_type", None)
                })
        except Exception, e:
            LOG.info("INFO: %s" % e)
            messages.error(self.request, e)
            exceptions.handle(self.request, "Cluster create failed!(%s)" % e)
        return templates

    def get_context_data(self, **kwargs):
        context = super(OverviewView, self).get_context_data(**kwargs)
        context['clusters'] = self.get_clusters()
        context['templates'] = self.get_template()
        return context


@csrf_exempt
def cluster_create(request):
    data = json.loads(request.body)
    msg = ('Cluster create request.body::::::: %s') % request.body
    LOG.info(msg)

    cluster_new = []
    cluster = data["cluster_info"]
    try:
        nps = cluster["networking_parameters"]
        cluster_created = \
            api.daisy.cluster_add(request,
                                  name=cluster["cluster_name"],
                                  description=cluster["description"],
                                  networking_parameters=nps)
        cluster_new.append({
            "id": cluster_created.id
        })
        messages.success(request, "Cluster create success!")
    except Exception, e:
        LOG.info("INFO: %s" % e)
        messages.error(request, e)
        exceptions.handle(request, "Cluster create failed!(%s)" % e)

    return HttpResponse(json.dumps(cluster_new),
                        content_type="application/json")


@csrf_exempt
def GetCluster(request):
    data = json.loads(request.body)
    filter = data["cluster_info"]
    cluster_info = api.daisy.cluster_get(request, filter["cluster_id"])
    ret_cluster_list = []
    nps = cluster_info.networking_parameters
    ret_cluster_list.append({
        "id": cluster_info.id,
        "name": cluster_info.name,
        "base_mac": nps["base_mac"],
        "segmentation_type": nps["segmentation_type"],
        "gre_id_start": nps["gre_id_range"][0],
        "gre_id_end": nps["gre_id_range"][1],
        "vni_start": nps["vni_range"][0],
        "vni_end": nps["vni_range"][1],
        "auto_scale": cluster_info.auto_scale,
        "description": cluster_info.description})
    return HttpResponse(json.dumps(ret_cluster_list),
                        content_type="application/json")


@csrf_exempt
def GetClusters(request):
    clusters = api.daisy.cluster_list(request)
    cluster_lists = [c for c in clusters]
    ret_cluster_list = []
    for cluster in cluster_lists:
        ret_cluster_list.append({
            "id": cluster.id,
            "name": cluster.name,
            "auto_scale": cluster.auto_scale})
    return HttpResponse(json.dumps(ret_cluster_list),
                        content_type="application/json")
