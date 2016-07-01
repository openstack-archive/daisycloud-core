import json

from django.http import HttpResponse
from horizon import messages
from horizon import views
from openstack_dashboard import api
from django.utils.translation import ugettext_lazy as _

import logging
LOG = logging.getLogger(__name__)


class SystemConfigView(views.HorizonTemplateView):
    template_name = "environment/system/system_config.html"

    def get_context_data(self, **kwargs):
        context = super(SystemConfigView, self).get_context_data(**kwargs)
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        context['is_system'] = True
        hwms = api.daisy.hwm_list(self.request)
        hwm_list = [hwm for hwm in hwms]
        if len(hwm_list):
            context["hwmip"] = hwm_list[0].hwm_ip
            context["hwmip_description"] = hwm_list[0].description

        context['net'] = api.daisy.get_pxeserver(self.request)[0]
        return context


def modify_systemconfig(request):
    data = json.loads(request.body)

    try:
        hwms = api.daisy.hwm_list(request)
        hwm_list = [hwm for hwm in hwms]

        if len(hwm_list):
            if data['hwmip'] == "":
                api.daisy.hwmip_delete(request, hwm_list[0].id)
            else:
                hwmip = {"hwm_ip": data['hwmip'],
                         "description": data['hwmip_description']}
                api.daisy.hwmip_update(request, hwm_list[0].id, **hwmip)

        else:
            if data['hwmip'] == "":
                pass
            else:
                hwmip = {"hwm_ip": data['hwmip'],
                         "description": data['hwmip_description']}
                api.daisy.hwmip_add(request, **hwmip)
    except Exception, e:
        messages.error(request, e)
        return

    messages.success(request, _("Save success!"))
    return


def set_pxeserver(request):
    data = json.loads(request.body)
    response = HttpResponse()

    try:
        pxe_param = {
            "ip": data["serverip"],
            "cidr": data["cidr"],
            "ip_ranges": [{"start": data["startip"],
                           "end": data["endip"]}]
        }
        api.daisy.set_pxeserver(request,
                                data["netid"],
                                data["deployment_interface"],
                                **pxe_param)
    except Exception:
        messages.error(request, _("Set deploy server failed!"))
        response.status_code = 500
        return response

    messages.success(request, _("Set deploy server successfully!"))
    response.status_code = 200
    return response
