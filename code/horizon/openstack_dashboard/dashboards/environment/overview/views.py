from django import http
from django import shortcuts
from horizon.utils import memoized
from horizon import views
from horizon import forms
from horizon import tables
from django import template
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.http import HttpResponse
from horizon import exceptions
from horizon import messages
from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.deploy \
    import views as deploy_view
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ungettext_lazy

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
            cluster.target_system = "OS+TECS"
            cluster.os = "CGSL"
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
def cluster_create_by_template(request):
    data = json.loads(request.body)
    cluster_new = []
    cluster_info = data["cluster_info"]
    try:
        cluster_created = api.daisy.import_template_to_db(request,
                                                          **cluster_info)
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


@csrf_exempt
def ModifyCluster(request):
    data = json.loads(request.body)
    msg = ('Cluster modify request.body::::::: %s') % request.body
    LOG.info(msg)

    cluster_info = data["cluster_info"]
    response = HttpResponse()
    try:
        if cluster_info["other"] == 1:
            api.daisy.cluster_update(request,
                                     cluster_info["id"],
                                     name=cluster_info["name"],
                                     auto_scale=cluster_info["auto_scale"])
        else:
            np = cluster_info["networking_parameters"]
            api.daisy.cluster_update(request,
                                     cluster_info["id"],
                                     name=cluster_info["name"],
                                     networking_parameters=np,
                                     auto_scale=cluster_info["auto_scale"],
                                     description=cluster_info["description"])
            messages.success(request, "Cluster modify success!")
    except Exception, e:
        LOG.info("INFO: %s" % e)
        messages.error(request, e)
        exceptions.handle(request, "Cluster modify failed!(%s)" % e)
        response.status_code = 500
        return response

    response.status_code = 200
    return response


class HostListFilterAction(tables.FilterAction):
    def filter(self, table, hosts, filter_string):
        pass


class AddHostsToClusterForm(forms.SelfHandlingForm):
    host_id = forms.CharField(widget=forms.HiddenInput())
    cluster = forms.ChoiceField(label=_("Cluster"),
                                required=False)

    def __init__(self, request, *args, **kwargs):
        super(AddHostsToClusterForm, self).__init__(request, *args, **kwargs)
        host_id = kwargs.get('initial', {}).get('host_id')
        self.fields['host_id'].initial = host_id
        self.fields['cluster'].choices = self.get_clusters(request)

    def get_clusters(self, request):
        clusters = api.daisy.cluster_list(request)
        cluster_choices = []
        for cluster in clusters:
            one_choice = (cluster.id, cluster.name)
            cluster_choices.append(one_choice)
        return cluster_choices

    def handle(self, request, data):
        LOG.info("S.J data: %s" % data)
        try:
            api.daisy.host_update(request, data["host_id"],
                                  cluster=data["cluster"])
        except Exception, e:
            messages.error(request, e)
            return False
        messages.success(request, "Add host to cluster success.")
        return True


class AddHostsToClusterView(forms.ModalFormView):
    form_class = AddHostsToClusterForm
    template_name = "environment/overview/addHostToCluster.html"
    submit_url = "horizon:environment:overview:addtocluster"
    success_url = reverse_lazy('horizon:environment:overview:hosts')

    def get_context_data(self, **kwargs):
        context = super(AddHostsToClusterView, self).get_context_data(**kwargs)
        context['host_id'] = self.kwargs['host_id']
        return context

    def get_initial(self):
        return {'host_id': self.kwargs['host_id']}


class AddToCluster(tables.LinkAction):
    name = "add to cluster"
    verbose_name = _("Add To Cluster")
    url = "horizon:environment:overview:addtocluster"
    classes = ("ajax-modal", "btn-primary")

    def allowed(self, request, datum):
        if datum is not None:
            if hasattr(datum, "status"):
                if datum.status == "init":
                    return True

        return False


def get_cluster_id(request, cluster_name):
    try:
        clusters = api.daisy.cluster_list(request)
        for cluster in clusters:
            if cluster.name == cluster_name:
                return cluster.id
    except Exception, e:
        messages.error(request, e)


class RemoveFromCluster(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Delete Host",
            u"Delete Hosts",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Deleted Host",
            u"Deleted Hosts",
            count
        )

    def delete(self, request, obj_id):
        host_id = obj_id
        host = api.daisy.host_get(request, host_id)
        cluster_name = host.cluster
        cluster_id = get_cluster_id(request, cluster_name)
        try:
            api.daisy.delete_host_from_cluster(request, cluster_id, host_id)
        except Exception, e:
            messages.error(request, e)

    def allowed(self, request, datum):
        if datum is not None:
            if hasattr(datum, "status"):
                if datum.status == "init":
                    return False

        return True


def get_host_roles(host_detail):
    roles = []
    if hasattr(host_detail, "role"):
        for role in host_detail.role:
            roles.append(str(role))
    return roles


def get_install_status(host_detail):
    install_status = ""
    if host_detail.status == "init":
        install_status = ""
    elif hasattr(host_detail, "role_status"):
        if host_detail.os_status == "init"\
                and host_detail.role_status == "init":
            install_status = ""
        elif host_detail.os_status == "installing":
            install_status = _("os installing")
        elif host_detail.os_status == "install-failed":
            install_status = _("os install failed")
        elif host_detail.os_status == "active"\
                and host_detail.role_status == "init":
            install_status = _("os install successful")
        elif host_detail.os_status == "active"\
                and host_detail.role_status == "installing":
            install_status = _("os install successful, tecs installing")
        elif host_detail.os_status == "active"\
                and host_detail.role_status == "install-failed":
            install_status = _("os install successful, tecs install failed")
        elif host_detail.os_status == "active"\
                and host_detail.role_status == "active":
            install_status = _("install tecs successful")
        elif host_detail.os_status == "updating":
            install_status = _("os updating")
        elif host_detail.os_status == "update-failed":
            install_status = _("os update failed")
        elif host_detail.os_status == "active"\
                and host_detail.role_status == "updating":
            install_status = _("tecs updating")
        elif host_detail.role_status == "update-failed":
            install_status = _("tecs update failed")
        elif host_detail.role_status == "uninstalling":
            install_status = _("tecs uninstalling")
        elif host_detail.role_status == "uninstall-failed":
            install_status = _("tecs uninstall failed")
    else:
        if host_detail.os_status == "init":
            install_status = ""
        elif host_detail.os_status == "installing":
            install_status = _("os installing")
        elif host_detail.os_status == "install-failed":
            install_status = _("os install failed")
        elif host_detail.os_status == "update-failed":
            install_status = _("os update failed")
        elif host_detail.os_status == "active":
            install_status = _("os install successful")

    return install_status


def get_host_role_url(host):
    roles = get_host_roles(host)
    template_name = 'environment/overview/host_roles.html'
    context = {
        "roles": roles,
    }
    return template.loader.render_to_string(template_name, context)


class HostsTable(tables.DataTable):
    host_name = tables.Column("name",
                              verbose_name=_("Name"))
    ipmi_addr = tables.Column("ipmi_addr",
                              verbose_name=_("ipmi_addr"))
    host_status = tables.Column("status",
                                verbose_name=_("Status"))
    host_cluster = tables.Column("cluster",
                                 verbose_name=_("Cluster"))
    host_role = tables.Column(get_host_role_url,
                              verbose_name=_("Roles"))
    host_install_status = tables.Column(get_install_status,
                                        verbose_name=_("install_status"))

    class Meta:
        name = "hosts_list"
        verbose_name = _("HostsList")
        multi_select = True
        table_actions = (HostListFilterAction, RemoveFromCluster,)
        row_actions = (AddToCluster, RemoveFromCluster,)


class HostsView(tables.DataTableView):
    table_class = HostsTable
    template_name = "environment/overview/hosts.html"

    def get_data(self):
        hosts = []
        hosts_list = api.daisy.host_list(self.request)
        for host in hosts_list:
            if host.status == "init":
                hosts.append(host)
        cluster_list = api.daisy.cluster_list(self.request)
        for cluster in cluster_list:
            hosts_with_role = api.daisy.cluster_host_list(self.request,
                                                          cluster.id)
            for host in hosts_with_role:
                host_detail = api.daisy.host_get(self.request, host.id)
                host.cluster = host_detail.cluster
                if hasattr(host_detail, "role"):
                    roles = host_detail.role
                    roles.sort()
                    host.role = host_detail.role
            hosts.extend(hosts_with_role)
        return hosts

    def get_useful_hosts(self, hosts):
        hosts_useful = []
        for host in hosts:
            if host.ipmi_user is not None:
                hosts_useful.append(host)
        return hosts_useful

    def get_context_data(self, **kwargs):
        context = super(HostsView, self).get_context_data(**kwargs)
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        context['is_hosts'] = True
        return context


class TemplateDetailView(views.HorizonTemplateView):
    template_name = 'environment/overview/template_detail.html'
    page_title = _("Template Details:{{template_id}}")

    def get_context_data(self, **kwargs):
        context = super(TemplateDetailView, self).get_context_data(**kwargs)
        template_detail = self.get_data()
        context["template_id"] = template_detail.id
        context["name"] = template_detail.name
        context["type"] = template_detail.type
        context["content"] = template_detail.content
        context["hosts"] = template_detail.hosts
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        context['is_templates'] = True
        return context

    @memoized.memoized_method
    def get_data(self):
        try:
            template_id = self.kwargs['template_id']
            template_detail = api.daisy.template_detail(self.request,
                                                        template_id)
        except Exception:
            redirect = self.get_redirect_url()
            exceptions.handle(self.request,
                              _('Unable to retrieve template details.'),
                              redirect=redirect)
        return template_detail

    def get_redirect_url(self):
        return reverse('horizon:environment:overview:templates')


class DeleteTemplate(tables.DeleteAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Delete Template",
            u"Delete Templates",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Deleted Template",
            u"Deleted Templates",
            count
        )

    def delete(self, request, obj_id):
        try:
            api.daisy.template_delete(request, obj_id)
        except Exception as e:
            messages.error(request, e)


def download_template_file(request, template_id):
    template_file = 'environment/overview/cluster.template'
    try:
        template_detail = api.daisy.template_detail(request, template_id)
        template_json = {
            "name": template_detail.name,
            "type": template_detail.type,
            "content": json.loads(template_detail.content),
            "hosts": json.loads(template_detail.hosts)}
        template_json = json.dumps(template_json)
        context = {
            "content": template_json
        }

        response = shortcuts.render(request,
                                    template_file,
                                    context,
                                    content_type="text/plain")
        response['Content-Disposition'] = ('attachment; '
                                           'filename="%s.json"'
                                           % template_detail.name)
        response['Content-Length'] = str(len(response.content))
        return response

    except Exception as e:
        LOG.exception("Exception in generate_cluster_template.: %s" % e)
        messages.error(request, _('Error generate_cluster_template: %s') % e)
        return shortcuts.redirect(request.build_absolute_uri())


class DownLoadTemplate(tables.LinkAction):
    name = "download_template"
    verbose_name = _("Download Template")
    verbose_name_plural = _("Download Template")
    icon = "download"
    url = "horizon:environment:overview:download_template_file"

    def get_link_url(self, datum):
        template_id = self.table.get_object_id(datum)
        base_url = reverse(self.url, args=[template_id])
        return base_url


class InstanceTemplateForm(forms.SelfHandlingForm):
    cluster_name_regex = r'^[a-zA-Z][a-zA-Z0-9_]{3,15}$'
    cluster_name_help_text = _("Name must begin with letters,"
                               "and consist of numbers,letters or underscores."
                               "The length of name is 4 to 16.")
    cluster_name_error_message = {'invalid': cluster_name_help_text}
    cluster_name = forms.RegexField(label=_("Cluster Name"),
                                    required=True,
                                    regex=cluster_name_regex,
                                    error_messages=cluster_name_error_message)

    def handle(self, request, data):
        template_id = self.initial['template_id']
        try:
            cluster_template = api.daisy.template_detail(request, template_id)
            param = {
                "cluster": data["cluster_name"],
                "template_name": cluster_template.name
            }
            api.daisy.import_template_to_db(request, **param)
            message = _('Create cluster: "%s"') % data["cluster_name"]
            messages.success(request, message)
            return True
        except Exception:
            redirect = reverse("horizon:environment:overview:templates")
            exceptions.handle(request,
                              _('Unable to instance template.'),
                              redirect=redirect)


class InstanceClusterTemplateView(forms.ModalFormView):
    form_class = InstanceTemplateForm
    modal_header = _("Instance")
    submit_label = _("Instance")
    template_name = 'environment/overview/instance_cluster_template.html'
    submit_url = "horizon:environment:overview:instance_cluster_template"
    page_title = _("Instance")

    def get_context_data(self, **kwargs):
        context = super(InstanceClusterTemplateView, self).\
            get_context_data(**kwargs)
        context['submit_url'] =\
            reverse(self.submit_url, args=[self.kwargs["template_id"]])
        return context

    def get_success_url(self):
        return reverse('horizon:environment:overview:templates')

    def get_initial(self):
        template_id = self.kwargs["template_id"]
        return {'template_id': template_id}


class InstanceClusterTemplate(tables.LinkAction):
    name = "instance_cluster_template"
    verbose_name = _("Instance")
    url = "horizon:environment:overview:instance_cluster_template"
    classes = ("ajax-modal", "btn-instance-template")


class TemplateListFilterAction(tables.FilterAction):
    def filter(self, table, hosts, filter_string):
        pass


class ImportTemplateForm(forms.SelfHandlingForm):
    template_file = forms.FileField(
        label=_('Template'),
        widget=forms.FileInput())

    def handle(self, request, data):
        try:
            template_data = request.FILES.get("template_file").read()
            param = {
                'template': template_data
            }
            api.daisy.import_json_to_template(request, **param)
            messages.success(request,
                             _('Your template %s has been imported.') %
                             data["template_file"])
            return True
        except Exception as e:
            LOG.error('dbg: e=%s' % e)
            msg = _('Unable to import template')
            exceptions.handle(request, msg)
            return False


class ImportTemplateView(forms.ModalFormView):
    template_name = 'environment/overview/import_template.html'
    form_class = ImportTemplateForm
    success_url = reverse_lazy('horizon:environment:overview:templates')


class ImportTemplate(tables.LinkAction):
    name = "import"
    verbose_name = _("Import Template")
    url = "horizon:environment:overview:import_template"
    icon = "plus"
    classes = ("btn-launch", "ajax-modal",)


class TemplatesTable(tables.DataTable):
    name = tables.Column("name",
                         link="horizon:environment:overview:template_detail",
                         verbose_name=_("Name"))
    type = tables.Column("type",
                         verbose_name=_("Type"))
    create_time = tables.Column("create_time",
                                verbose_name=_("Create Time"))
    description = tables.Column("description",
                                verbose_name=_("Description"))

    def get_object_id(self, datum):
        return datum["template_id"]

    class Meta:
        name = "template_list"
        verbose_name = _("TemplateList")
        multi_select = True
        table_actions = (TemplateListFilterAction,
                         ImportTemplate,
                         DeleteTemplate)
        row_actions = (DeleteTemplate,
                       DownLoadTemplate,
                       InstanceClusterTemplate)


class TemplatesView(tables.DataTableView):
    table_class = TemplatesTable
    template_name = "environment/overview/template.html"

    def get_data(self):
        templates = []
        template_list = api.daisy.template_list(self.request)
        for cluster_template in template_list:
            templates.append({
                "template_id": cluster_template.id,
                "name": cluster_template.name,
                "type": cluster_template.type,
                "create_time": cluster_template.created_at,
                "description": cluster_template.description
            })
        return templates

    def get_context_data(self, **kwargs):
        context = super(TemplatesView, self).get_context_data(**kwargs)
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        context['is_templates'] = True
        return context


@csrf_exempt
def generate_cluster_template(request):
    cluster_name = request.GET.get("cluster_name")
    template_name = request.GET.get("template_name")
    description = request.GET.get("description")
    try:
        param = {
            "cluster_name": cluster_name,
            "template_name": template_name,
            "description": description
        }
        LOG.info("generate_cluster_template %s", param)
        api.daisy.export_db_to_json(request, **param)
        messages.success(request, _('Generate cluster template success!'))
    except Exception as e:
        LOG.exception("Exception in generate_cluster_template.: %s" % e)
        messages.error(request, _('Error generate_cluster_template: %s') % e)
    url = reverse('horizon:environment:overview:index')
    response = http.HttpResponseRedirect(url)
    return response
