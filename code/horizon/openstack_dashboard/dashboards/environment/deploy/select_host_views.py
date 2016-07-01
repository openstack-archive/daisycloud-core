from django.http import HttpResponse

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
from openstack_dashboard.dashboards.environment.template \
    import views as template_views
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


class HideHostsNotSelected():
    name = "hide_hosts"


class ComputerNodesAutoExpansion():
    name = "auto_expansion"


class UpdateRow(tables.Row):
    ajax = True

    def get_data(self, request, host_id):
        host_detail = api.daisy.host_get(request, host_id)
        hosts = api.daisy.host_list(request)
        for host in hosts:
            if (host.id == host_id):
                setattr(host_detail, "discover_state", host.discover_state)
                break
        return host_detail


def get_host_interfaces(host_detail):
    nics = []
    if hasattr(host_detail, "interfaces"):
        bond_names = []
        bond_interfaces = [i for i in host_detail.interfaces
                           if i['type'] == 'bond']
        for interface in bond_interfaces:
            bond_names.append(interface["slave1"])
            bond_names.append(interface["slave2"])
        for interface in host_detail.interfaces:
            if interface['type'] == 'ether':
                if interface["name"] not in bond_names:
                    nics.append(str(interface["name"]))
            else:
                if interface['type'] != "vlan":
                    nics.append(str(interface["name"]))
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
            "disks_size": disk_size_str,
            "position": host_detail.position
        }
        return template.loader.render_to_string(template_name, context)


class UpdateHostNameForm(forms.SelfHandlingForm):
    host_name_regex = r'^[a-zA-Z][a-zA-Z0-9-]{3,31}$'
    host_name_help_text = _("Name must begin with letters,"
                            "and consist of numbers,letters or strikethrough. "
                            "The length of name is 4 to 32.")
    host_name_error_message = {'invalid': host_name_help_text}
    host_name = forms.RegexField(label=_("Name"),
                                 required=True,
                                 regex=host_name_regex,
                                 error_messages=host_name_error_message)

    def __init__(self, request, *args, **kwargs):
        super(UpdateHostNameForm, self).__init__(request, *args, **kwargs)
        initial = kwargs.get('initial', {})
        host_id = initial.get('host_id')
        host_get = api.daisy.host_get(request, host_id)
        self.fields['host_name'].initial = host_get.name

    def clean(self):
        cleaned_data = super(UpdateHostNameForm, self).clean()
        return cleaned_data

    def handle(self, request, data):
        cluster_id = self.initial['cluster_id']
        host_id = self.initial['host_id']
        try:
            api.daisy.host_update(request,
                                  host_id,
                                  name=data["host_name"])
            message = _('Update host %s name successfully.') % host_id
            messages.success(request, message)
            return True
        except Exception as e:
            LOG.error('UpdateHostNameForm handle failed %s' % e)
            message = _('Unable to update host %s name.') % host_id
            messages.error(request, message)
            redirect = reverse("horizon:environment:deploy:selecthosts",
                               args=(cluster_id, ))
            exceptions.handle(request,
                              _('Unable to update host name.'),
                              redirect=redirect)


class UpdateHostNameView(forms.ModalFormView):
    form_class = UpdateHostNameForm
    modal_header = _("Update Host Name")
    submit_label = _("Update Host Name")
    template_name = 'environment/deploy/update_host_name.html'
    submit_url = "horizon:environment:deploy:update_host_name"
    page_title = _("Update Host Name")

    def get_context_data(self, **kwargs):
        context = \
            super(UpdateHostNameView, self).get_context_data(**kwargs)
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


class UpateHostName(tables.LinkAction):
    name = "update_host_name"
    verbose_name = _("Update Host Name")
    url = "horizon:environment:deploy:update_host_name"
    classes = ("ajax-modal", "btn-update-host-name")

    def get_link_url(self, datum):
        cluster_id = self.table.kwargs["cluster_id"]
        host_id = self.table.get_object_id(datum)
        base_url = reverse(self.url, args=(cluster_id, host_id))
        return base_url

    def allowed(self, request, host):
        return False


class SelectHostsTable(tables.DataTable):

    STATUS_CHOICES = (
        (None, False),
        ("", False),
        ("PXE:DISCOVERY_SUCCESSFUL", False),
        ("SSH:DISCOVERY_SUCCESSFUL", False),
        ("PXE:DISCOVERY_FAILED", False),
        ("SSH:DISCOVERY_FAILED", False),
        ("SSH:DISCOVERING", None),
        ("PXE:DISCOVERING", None),
    )

    host_name = tables.Column(get_host_detail,
                              verbose_name=_("Name"))
    mac = tables.Column(get_host_mac, verbose_name=_("MAC"))
    interfaces = tables.Column(get_host_interfaces,
                               verbose_name=_("interface"))
    host_discover_status = tables.Column("discover_state",
                                         verbose_name=_("Discover Status"),
                                         status_choices=STATUS_CHOICES,)

    class Meta(object):
        name = "select_hosts"
        verbose_name = _("SelectHosts")
        status_columns = ["host_discover_status", ]
        multi_select = True
        table_actions = (DiscoverHosts, )
        row_actions = (UpateHostName, template_views.InstanceHostTemplate, )
        row_class = UpdateRow


class SelectHostsView(tables.DataTableView):
    table_class = SelectHostsTable
    template_name = 'environment/deploy/select_hosts.html'
    page_title = _("SelectHosts")

    def get_data(self):
        handled_hosts = []
        # current_cluster = self.kwargs["cluster_id"]

        # key = 'show_host' + current_cluster
        # if (key in self.request.session) and self.request.session[key]:
        cluster_info = api.daisy.cluster_get(
            self.request, self.kwargs["cluster_id"])
        if(cluster_info.hwm_ip != ""):
            try:
                param = {
                    "hwm_ip": cluster_info.hwm_ip
                }
                hwm_nodes = api.daisy.node_update(self.request, **param)
                for hwm_node in hwm_nodes:
                    pass
            except Exception, e:
                messages.error(self.request, e)
        hosts = api.daisy.host_list(self.request)

        for host in hosts:
            host_detail = api.daisy.host_get(self.request, host.id)
            if (host_detail.status == "init"):
                if (cluster_info.hwm_ip != ""):
                    if(host_detail.hwm_ip == cluster_info.hwm_ip):
                        setattr(host_detail,
                                "discover_state", host.discover_state)
                        handled_hosts.append(host_detail)
                    else:
                        continue
                else:
                    handled_hosts.append(host_detail)

        return handled_hosts

    def get_current_cluster(self, clusters, current_id):
        for c in clusters:
            if c.id == current_id:
                return c.name
        return ""

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
        context["host_templates"] = template_views.\
            get_host_template_by_cluster(self.request, cluster_id)
        cluster_info = api.daisy.cluster_get(
            self.request, self.kwargs["cluster_id"])
        context["hwm_ip"] = cluster_info.hwm_ip
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
