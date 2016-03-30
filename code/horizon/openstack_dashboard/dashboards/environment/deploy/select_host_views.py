from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core import exceptions as django_exceptions

from horizon import exceptions as horizon_exceptions
from horizon import messages
from horizon import tables
from horizon import exceptions
from horizon import forms

from django import template
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.deploy import actions
from openstack_dashboard.dashboards.environment.deploy import wizard_cache
from openstack_dashboard.dashboards.environment.deploy \
    import discover_host_cache

import json

import logging
LOG = logging.getLogger(__name__)


def conf_ipmi(request, cluster_id):
    response = HttpResponse()
    # key = 'show_host' + cluster_id
    # request.session[key] = True
    data = json.loads(request.body)

    try:
        hosts = api.daisy.host_list(request)
        i = 1
        for host in hosts:
            LOG.info("wmh dbg: host= %s" % host)
            api.daisy.host_update(request,
                                  host.id,
                                  # name=host_name,
                                  ipmi_user=data['ipmi_user'],
                                  ipmi_passwd=data['ipmi_passwd'])
            messages.success(request, "Update host ipmis success!")
            i += 1
    except:
        horizon_exceptions.handle(request, "update host ipmis failed!")
        response.status_code = 500
        return response

    response.status_code = 200
    return response


def list_discover_host(request, cluster_id):
    response = HttpResponse()
    host_list = []

    try:
        hosts = api.daisy.list_discover_host(request)
        host_list = [c.to_dict() for c in hosts]
        cache_discover_hosts = discover_host_cache.get_cache()
        for host_in_cache in cache_discover_hosts:
            for host in host_list:
                if host_in_cache['ip'] == host['ip']:
                    host_in_cache['status'] = host['status']
        discover_host_cache.set_cache(cache_discover_hosts)
        LOG.info("host_list = %s" % host_list)
    except Exception as e:
        messages.error(request, e)
        LOG.error('wmh dbg: e=%s' % e)
        response.status_code = 500
        return response

    return HttpResponse(json.dumps(host_list),
                        content_type="application/json")


def get_discover_result(request, cluster_id):
    response = HttpResponse()

    try:
        cache_discover_hosts = discover_host_cache.get_cache()
        discover_host_cache.clean_cache()
        LOG.info("cache_discover_hosts = %s" % cache_discover_hosts)
    except Exception as e:
        messages.error(request, e)
        LOG.error('wmh dbg2: e=%s' % e)
        response.status_code = 500
        return response

    return HttpResponse(json.dumps(cache_discover_hosts),
                        content_type="application/json")


def start_discover(request, cluster_id):
    response = HttpResponse()
    # key = 'show_host' + cluster_id
    # request.session[key] = True
    data = json.loads(request.body)
    try:
        hosts = data['hosts']
        for host in hosts:
            api.daisy.add_discover_host(request, **host)
        api.daisy.discover_host(request)
        for host in hosts:
            host["status"] = ""
        discover_host_cache.set_cache(hosts)
    except Exception as e:
        messages.error(request, e)
        response.status_code = 500
        return response

    response.status_code = 200
    return response


class DiscoverHosts(actions.OperateRegionAction):
    name = "discover_hosts"
    verbose_name = _("Discover Hosts")


class AutoFillHostsName(actions.AutofillAction):
    name = "autofill_hostname"
    verbose_name = _("Auto Fill Host Name")
    checked = True
    disabled = True


class HideHostsNotSelected():
    name = "hide_hosts"


class ComputerNodesAutoExpansion():
    name = "auto_expansion"


class UpdateRow(tables.Row):
    ajax = True

    def get_data(self, request, host_id):
        host = api.daisy.host_get(request, host_id)
        return host


class Update_host(tables.UpdateAction):
    def allowed(self, request, host, cell):
        return False

    def update_cell(self, request, datum, host_id,
                    cell_name, new_cell_value):
        try:
            host_obj = datum
            setattr(host_obj, cell_name, new_cell_value)
            api.daisy.host_update(request,
                                  host_id,
                                  name=new_cell_value)

        except horizon_exceptions.Conflict:
            message = _("This name is already taken.")
            messages.warning(request, message)
            raise django_exceptions.ValidationError(message)
        except Exception:
            horizon_exceptions.handle(request, ignore=True)
            return False
        return True


def get_host_interfaces(host_detail):
    nics = []
    if hasattr(host_detail, "interfaces"):
        for nic in host_detail.interfaces:
            nics.append(str(nic['name']))
    return nics


def get_host_mac(host_detail):
    mac = ""
    if hasattr(host_detail, "interfaces"):
        for nic in host_detail.interfaces:
            if nic['is_deployment']:
                mac = nic['mac']
    return mac


def get_host_detail(host_detail):
        template_name = 'environment/deploy/_host_detail.html'
        cpu_num = ""
        memory_size = 0
        memory_size_str = ""
        manufacturer = ""
        product = ""
        disk_size = 0
        disk_size_str = ""

        if hasattr(host_detail, "cpu"):
            cpu_num = host_detail.cpu["total"]
        if hasattr(host_detail, "memory"):
            memory_size_raw = int(host_detail.memory["total"][:-2])
            memory_size = memory_size_raw / (1024 * 1024)
        if(memory_size > 0):
            memory_size_str = str(memory_size)
        if hasattr(host_detail, "system") \
                and "product" in host_detail.system.keys():
            product = host_detail.system["product"]
        if hasattr(host_detail, "system") \
                and "manufacturer" in host_detail.system.keys():
            manufacturer = host_detail.system["manufacturer"]
        if hasattr(host_detail, "disks"):
            for key, value in host_detail.disks.items():
                size = int(value["size"][:-5])
                disk_size += size
        if(disk_size > 0):
            disk_size_str = str(disk_size / (1024 * 1024 * 1024))
        context = {
            "host_id": host_detail.id,
            "host_name": host_detail.name,
            "cpu_num": cpu_num,
            "host_memory_size": memory_size_str,
            "product": product,
            "manufacturer": manufacturer,
            "disks_size": disk_size_str
        }
        return template.loader.render_to_string(template_name, context)


class InstanceHostTemplateForm(forms.SelfHandlingForm):
    host_template = forms.ChoiceField(label=_("Host Template"))

    def __init__(self, request, *args, **kwargs):
        super(InstanceHostTemplateForm, self).\
            __init__(request, *args, **kwargs)
        initial = kwargs.get('initial', {})
        cluster_id = initial.get('cluster_id')
        cluster = api.daisy.cluster_get(request, cluster_id)
        param = {
            "cluster_name": cluster.name
        }
        host_templates = api.daisy.host_template_list(request, **param)
        self.fields['host_template'].choices = \
            self.get_host_template(host_templates)

    def get_host_template(self, host_templates):
        return [(it.name, it.name) for it in host_templates]

    def clean(self):
        cleaned_data = super(InstanceHostTemplateForm, self).clean()
        return cleaned_data

    def handle(self, request, data):
        cluster_id = self.initial['cluster_id']
        host_id = self.initial['host_id']
        try:
            cluster = api.daisy.cluster_get(request, cluster_id)
            param = {
                "cluster_name": cluster.name,
                "host_template_name": data['host_template'],
                "host_id": host_id
            }
            LOG.info("@@@@@@@@@@@@@@param %s", param)
            api.daisy.template_to_host(request, **param)
            message = _('Instance template: "%s"') % data['host_template']
            messages.success(request, message)
            return True
        except Exception:
            redirect = reverse("horizon:environment:deploy:selecthosts",
                               args=(cluster_id, ))
            exceptions.handle(request,
                              _('Unable to instance template.'),
                              redirect=redirect)


class InstanceHostTemplateView(forms.ModalFormView):
    form_class = InstanceHostTemplateForm
    modal_header = _("Instance Template")
    submit_label = _("Instance Template")
    template_name = 'environment/deploy/host_template_detail.html'
    submit_url = "horizon:environment:deploy:instance_host_template"
    page_title = _("Instance Template")

    def get_context_data(self, **kwargs):
        context = \
            super(InstanceHostTemplateView, self).get_context_data(**kwargs)
        cluster_id = self.kwargs["cluster_id"]
        host_id = self.kwargs["host_id"]
        context['submit_url'] = \
            reverse(self.submit_url, args=(cluster_id, host_id))
        cluster = api.daisy.cluster_get(self.request, cluster_id)
        param = {
            "cluster_name": cluster.name
        }
        context["host_templates"] = \
            api.daisy.host_template_list(self.request, **param)
        return context

    def get_success_url(self):
        return reverse("horizon:environment:deploy:selecthosts",
                       args=(self.kwargs["cluster_id"],))

    def get_initial(self):
        ret = {
            'cluster_id': self.kwargs["cluster_id"],
            'host_id': self.kwargs["host_id"]}
        return ret


@csrf_exempt
def batch_instance_template(request, cluster_id):
    response = HttpResponse()
    data = json.loads(request.body)
    hosts = data["hosts"]
    try:
        cluster = api.daisy.cluster_get(request, cluster_id)
        for host in hosts:
            param = {
                "cluster_name": cluster.name,
                "host_template_name": data['host_template_name'],
                "host_id": host
            }
            api.daisy.template_to_host(request, **param)
            messages.success(request, "Instance template success.")
    except Exception, e:
        messages.error(request, e)
        response.status_code = 500
        LOG.info("instance template failed!")
        return response

    response.status_code = 200
    return response


class InstanceHostTemplate(tables.LinkAction):
    name = "instance_template"
    verbose_name = _("Instance Template")
    url = "horizon:environment:deploy:instance_host_template"
    classes = ("ajax-modal", "btn-instance-template")

    def get_link_url(self, datum):
        cluster_id = self.table.kwargs["cluster_id"]
        host_id = self.table.get_object_id(datum)
        base_url = reverse(self.url, args=(cluster_id, host_id))
        return base_url


class SelectHostsTable(tables.DataTable):
    host_name = tables.Column(get_host_detail,
                              verbose_name=_("Name"),
                              form_field=forms.CharField(),
                              update_action=Update_host)
    mac = tables.Column(get_host_mac, verbose_name=_("MAC"))
    interfaces = tables.Column(get_host_interfaces,
                               verbose_name=_("interface"))

    class Meta(object):
        name = "select_hosts"
        verbose_name = _("SelectHosts")
        multi_select = True
        table_actions = (AutoFillHostsName, DiscoverHosts, )
        row_actions = (InstanceHostTemplate, )
        row_class = UpdateRow


class SelectHostsView(tables.DataTableView):
    table_class = SelectHostsTable
    template_name = 'environment/deploy/select_hosts.html'
    page_title = _("SelectHosts")

    def get_data(self):
        handled_hosts = []
        current_cluster = self.kwargs["cluster_id"]
        
        # key = 'show_host' + current_cluster
        # if (key in self.request.session) and self.request.session[key]:

        hosts = api.daisy.host_list(self.request)

        for host in hosts:                   
            host_detail = api.daisy.host_get(self.request, host.id)
            if host_detail.status == "init":
                handled_hosts.append(host_detail)              

        return handled_hosts

    def get_current_cluster(self, clusters, current_id):
        for c in clusters:
            if c.id == current_id:
                return c.name
        return ""

    def get_host_template(self):
        cluster_id = self.kwargs["cluster_id"]
        host_templates = None
        try:
            cluster = api.daisy.cluster_get(self.request, cluster_id)
            param = {
                "cluster_name": cluster.name
            }
            host_templates = \
                api.daisy.host_template_list(self.request, **param)
        except Exception, e:
            messages.error(self.request, e)
        return host_templates

    def get_context_data(self, **kwargs):
        context = super(SelectHostsView, self).get_context_data(**kwargs)
        cluster_id = self.kwargs["cluster_id"]
        context['cluster_id'] = cluster_id
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        wizard_cache.set_cache(context['cluster_id'], "selecthosts", 1)
        context['wizard'] = wizard_cache.get_cache(context['cluster_id'])
        context["current_cluster"] = \
            self.get_current_cluster(context['clusters'],
                                     context["cluster_id"])
        context["host_templates"] = self.get_host_template()
        return context


def allocate_host(request, cluster_id):
    wizard_cache.set_cache(cluster_id, "selecthosts", 2)
    response = HttpResponse()
    data = json.loads(request.body)
    hosts = data["hosts"]
    try:
        for host_id in hosts:
            api.daisy.host_update(request, host_id, cluster=cluster_id)
    except Exception, e:
        messages.error(request, e)
        response.status_code = 500
        return response
    messages.success(request, "Add host to cluster success.")
    # key = 'show_host' + cluster_id
    # if (key in request.session) and request.session[key]:
    #     request.session[key] = False
    response.status_code = 200
    return response
