from horizon import forms
from horizon import tables
from django import template
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from horizon import messages
from openstack_dashboard import api
from django.utils.translation import ungettext_lazy
from horizon import exceptions as horizon_exceptions
from django.core import exceptions as django_exceptions

import re
import logging
LOG = logging.getLogger(__name__)


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
    template_name = "environment/host/addHostToCluster.html"
    submit_url = "horizon:environment:host:addtocluster"
    success_url = reverse_lazy('horizon:environment:host:index')

    def get_context_data(self, **kwargs):
        context = super(AddHostsToClusterView, self).get_context_data(**kwargs)
        context['host_id'] = self.kwargs['host_id']
        return context

    def get_initial(self):
        return {'host_id': self.kwargs['host_id']}


class AddToCluster(tables.LinkAction):
    name = "add to cluster"
    verbose_name = _("Add To Cluster")
    url = "horizon:environment:host:addtocluster"
    classes = ("ajax-modal", "btn-primary")

    def allowed(self, request, datum):
        if datum is not None:
            if hasattr(datum, "status"):
                if datum.status == "init":
                    return True
        return False


class SshDiscoverOneHostForm(forms.SelfHandlingForm):
    host_id = forms.CharField(widget=forms.HiddenInput())
    ip = forms.CharField(label=_("IP"), max_length=255)
    username = forms.CharField(label=_("User Name"), max_length=255)
    password = forms.CharField(label=_("password"),
                               widget=forms.PasswordInput(render_value=False))

    def __init__(self, request, *args, **kwargs):
        super(SshDiscoverOneHostForm, self).__init__(request, *args, **kwargs)
        host_id = kwargs.get('initial', {}).get('host_id')
        self.fields['host_id'].initial = host_id

    def handle(self, request, data):
        try:
            host_detail = api.daisy.host_get(request, data["host_id"])
            host = {"ip": data["ip"],
                    "user": data["username"],
                    "passwd": data["password"]}
            api.daisy.add_discover_host(request, **host)
            api.daisy.discover_host(request)
        except Exception, e:
            messages.error(request, e)
            return False
        messages.success(request, "Start SSH discover success.")
        return True


class SshDiscoverOneHostView(forms.ModalFormView):
    form_class = SshDiscoverOneHostForm
    template_name = "environment/host/sshDiscover.html"
    submit_url = "horizon:environment:host:sshdiscover"
    success_url = reverse_lazy('horizon:environment:host:index')

    def get_context_data(self, **kwargs):
        context = super(SshDiscoverOneHostView,
                        self).get_context_data(**kwargs)
        context['host_id'] = self.kwargs['host_id']
        return context

    def get_initial(self):
        return {'host_id': self.kwargs['host_id']}


class SshDiscover(tables.LinkAction):
    name = "ssh discover"
    verbose_name = _("SSH Discover Host")
    url = "horizon:environment:host:sshdiscover"
    classes = ("ajax-modal",)

    def allowed(self, request, datum):
        return False


class PxeDiscover(tables.BatchAction):
    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"PXE Discover Host",
            u"PXE Discover Hosts",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"PXE Discover Host",
            u"PXE Discover Hosts",
            count
        )

    name = "pxe_discover"
    verbose_name = _("PXE Discover Host")
    classes = ("btn-danger",)

    def allowed(self, request, datum):
        return False

    def action(self, request, host_id):
        pass


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
            u"Remove Host",
            u"Remove Hosts",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Removed Host",
            u"Removed Hosts",
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


def get_backend_type_by_role_list(request):
    backends = []
    roles = api.daisy.role_list(request)
    for role in roles:
        backends.append(role.deployment_backend)
    back_ends = list(set(backends))
    return back_ends


def get_backends_deploy_info(backends, os_status, role_status,
                             os_progress=None, os_message=None,
                             role_progress=None, role_message=None):
    backend = str(backends[0])
    deploy_info = {}
    os_status_list = {
        "init": {
            "progress": 0,
            "message": os_message,
            "bar_type": "progress-bar-info",
            "count": "undeploy_host_num",
            "i18n": "init"},
        "pre-install": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-info",
            "count": "on_going_host_num",
            "i18n": "OS installing"},
        "installing": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-info",
            "count": "on_going_host_num",
            "i18n": "OS installing"},
        "updating": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-update",
            "count": "on_updating_host_num",
            "i18n": "OS updating"},
        "install-failed": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-danger",
            "count": "failed_host_num",
            "i18n": "OS install failed"},
        "update-failed": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-danger",
            "count": "failed_host_num",
            "i18n": "OS update failed"},
        "active": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-success",
            "count": "success_host_num",
            "i18n": "OS install successful"}
    }
    role_status_list = {
        "init": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-info",
            "count": "on_going_host_num",
            "i18n": "OS install successful"},
        "installing": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-info",
            "count": "on_going_host_num",
            "i18n": "OS install successful," + backend + "  installing"},
        "uninstalling": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-update",
            "count": "on_uninstalling_host_num",
            "i18n": "" + backend + " uninstalling"},
        "updating": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-update",
            "count": "on_updating_host_num",
            "i18n": "" + backend + " updating"},
        "install-failed": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-danger",
            "count": "failed_host_num",
            "i18n": "OS install successful," + backend + "  install failed"},
        "uninstall-failed": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-danger",
            "count": "failed_host_num",
            "i18n": "" + backend + " uninstall failed"},
        "update-failed": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-danger",
            "count": "failed_host_num",
            "i18n": "" + backend + " update failed"},
        "active": {
            "progress": 100,
            "message": role_message,
            "bar_type": "progress-bar-success",
            "count": "success_host_num",
            "i18n": "install " + backend + " successful"}
    }
    if os_status in os_status_list:
        if os_status == "active":
            deploy_info = os_status_list[os_status]
            if role_status in role_status_list:
                deploy_info = role_status_list[role_status]
        else:
            deploy_info = os_status_list[os_status]
    return deploy_info


def get_deploy_info(os_status, role_status,
                    os_progress=None, os_message=None,
                    role_progress=None, role_message=None):
    deploy_info = {}
    os_status_list = {
        "init": {
            "progress": 0,
            "message": os_message,
            "bar_type": "progress-bar-info",
            "count": "undeploy_host_num",
            "i18n": "init"},
        "pre-install": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-info",
            "count": "on_going_host_num",
            "i18n": "OS installing"},
        "installing": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-info",
            "count": "on_going_host_num",
            "i18n": "OS installing"},
        "updating": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-update",
            "count": "on_updating_host_num",
            "i18n": "OS updating"},
        "install-failed": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-danger",
            "count": "failed_host_num",
            "i18n": "OS install failed"},
        "update-failed": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-danger",
            "count": "failed_host_num",
            "i18n": "OS update failed"},
        "active": {
            "progress": os_progress,
            "message": os_message,
            "bar_type": "progress-bar-success",
            "count": "success_host_num",
            "i18n": "OS install successful"}
    }
    role_status_list = {
        "init": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-info",
            "count": "on_going_host_num",
            "i18n": "OS install successful"},
        "installing": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-info",
            "count": "on_going_host_num",
            "i18n": "OS install successful, TECS installing"},
        "uninstalling": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-update",
            "count": "on_uninstalling_host_num",
            "i18n": "TECS uninstalling"},
        "updating": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-update",
            "count": "on_updating_host_num",
            "i18n": "TECS updating"},
        "install-failed": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-danger",
            "count": "failed_host_num",
            "i18n": "OS install successful, TECS install failed"},
        "uninstall-failed": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-danger",
            "count": "failed_host_num",
            "i18n": "TECS uninstall failed"},
        "update-failed": {
            "progress": role_progress,
            "message": role_message,
            "bar_type": "progress-bar-danger",
            "count": "failed_host_num",
            "i18n": "TECS update failed"},
        "active": {
            "progress": 100,
            "message": role_message,
            "bar_type": "progress-bar-success",
            "count": "success_host_num",
            "i18n": "install TECS successful"}
    }
    if os_status in os_status_list:
        if os_status == "active":
            deploy_info = os_status_list[os_status]
            if role_status in role_status_list:
                deploy_info = role_status_list[role_status]
        else:
            deploy_info = os_status_list[os_status]
    return deploy_info


def get_install_status(host_detail):
    deploy_info = \
        get_backends_deploy_info(host_detail.backends,
                                 host_detail.os_status,
                                 getattr(host_detail, "role_status", None))
    return _(deploy_info.get("i18n", 'unknown'))


def get_host_role_url(host):
    roles = get_host_roles(host)
    template_name = 'environment/host/host_roles.html'
    context = {
        "roles": roles,
    }
    return template.loader.render_to_string(template_name, context)


class UpdateHostCell(tables.UpdateAction):

    def allowed(self, request, host, cell):
        return host.os_status == "init"

    def update_cell(self, request, datum, host_id,
                    cell_name, new_cell_value):
        try:
            pattern = re.compile(r'^[a-zA-Z][a-zA-Z0-9-]{3,31}$')
            match = pattern.match(new_cell_value)
            if match:
                host_obj = datum
                setattr(host_obj, cell_name, new_cell_value)
                api.daisy.host_update(request,
                                      host_id,
                                      name=new_cell_value)
            else:
                message = _("Name must begin with letters,"
                            "and consist of numbers,letters or strikethrough. "
                            "The length of name is 4 to 32.")
                messages.error(request, message)
                return False
        except horizon_exceptions.Conflict:
            message = _("This name is already taken.")
            messages.error(request, message)
            raise django_exceptions.ValidationError(message)
        except Exception:
            horizon_exceptions.handle(request, ignore=True)
            return False
        return True


class UpdateRow(tables.Row):
    ajax = True

    def get_data(self, request, host_id):
        try:
            hosts_list = api.daisy.host_list(request)
            for host in hosts_list:
                if host.id == host_id:
                    break

            if host is None:
                cluster_list = api.daisy.cluster_list(self.request)
                for cluster in cluster_list:
                    hosts_with_role = api.daisy.cluster_host_list(self.request,
                                                                  cluster.id)
                for host in hosts_with_role:
                    if host.id == host_id:
                        host_detail = api.daisy.host_get(self.request, host.id)
                        host.cluster = host_detail.cluster
                        if hasattr(host_detail, "role"):
                            roles = host_detail.role
                            roles.sort()
                            host.role = host_detail.role
                        break
            return host
        except Exception as e:
            LOG.error("wmh dbg: e=%s" % e)


class HostsTable(tables.DataTable):

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

    host_name = tables.Column("name",
                              verbose_name=_("Name"),
                              form_field=forms.CharField(),
                              update_action=UpdateHostCell)
    ipmi_addr = tables.Column("ipmi_addr",
                              verbose_name=_("ipmi_addr"))
    host_status = tables.Column("status",
                                verbose_name=_("Status"))
    host_cluster = tables.Column("cluster",
                                 verbose_name=_("Cluster"))
    host_role = tables.Column(get_host_role_url,
                              verbose_name=_("Roles"))
    host_install_status = tables.Column(get_install_status,
                                        verbose_name=_("Install Status"))
    host_discover_status = tables.Column("discover_state",
                                         verbose_name=_("Discover Status"),
                                         status_choices=STATUS_CHOICES,)

    class Meta:
        name = "hosts_list"
        verbose_name = _("HostsList")
        status_columns = ["host_discover_status"]
        multi_select = True
        table_actions = (HostListFilterAction, RemoveFromCluster, PxeDiscover)
        row_actions = (AddToCluster, RemoveFromCluster, PxeDiscover,
                       SshDiscover,)
        row_class = UpdateRow


class HostsView(tables.DataTableView):
    table_class = HostsTable
    template_name = "environment/host/index.html"

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
        backends = get_backend_type_by_role_list(self.request)
        for host in hosts:
            host.backends = backends

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
