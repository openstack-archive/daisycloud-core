# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Nebula, Inc.
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

from django import shortcuts
from horizon.utils import memoized
from horizon import views
from horizon import forms
from horizon import tables
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.http import HttpResponse
from horizon import exceptions
from horizon import messages
from openstack_dashboard import api
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ungettext_lazy

import json
import logging
LOG = logging.getLogger(__name__)

LOG = logging.getLogger(__name__)


@csrf_exempt
def generate_cluster_template(request):
    response = HttpResponse()
    data = json.loads(request.body)
    try:
        param = {
            "cluster_name": data["cluster_name"],
            "template_name": data["template_name"],
            "description": data["description"]
        }
        api.daisy.export_db_to_json(request, **param)
        messages.success(request, _('Generate cluster template success!'))
    except Exception as e:
        LOG.exception("Exception in generate_cluster_template.: %s" % e)
        messages.error(request, _('Error generate_cluster_template: %s') % e)
        response.status_code = 500
        return response
    response.status_code = 200
    return response


class TemplateDetailView(views.HorizonTemplateView):
    template_name = 'environment/template/template_detail.html'
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
        except Exception as e:
            LOG.info(" TemplateDetailView get_data failed!(%s)" % e)
            redirect = self.get_redirect_url()
            exceptions.handle(self.request,
                              _('Unable to retrieve template details.'),
                              redirect=redirect)
        return template_detail

    def get_redirect_url(self):
        return reverse('horizon:environment:template:index')


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
    template_file = 'environment/template/cluster.template'
    try:
        template_detail = api.daisy.template_detail(request, template_id)
        template_json = {
            "name": template_detail.name,
            "type": template_detail.type,
            "content": json.loads(template_detail.content),
            "hosts": json.loads(template_detail.hosts)}
        template_json = json.dumps(template_json, indent=2)
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
    url = "horizon:environment:template:download_template_file"

    def get_link_url(self, datum):
        template_id = self.table.get_object_id(datum)
        base_url = reverse(self.url, args=[template_id])
        return base_url


class InstanceTemplateForm(forms.SelfHandlingForm):
    cluster_name_regex = r'^[a-zA-Z][a-zA-Z0-9_]{3,15}$'
    cluster_name_help_text = _("Name must begin with letters,"
                               "and consist of numbers,letters "
                               "or underscores."
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
        except Exception as e:
            LOG.info(" InstanceTemplateForm handle failed!(%s)" % e)
            redirect = reverse("horizon:environment:template:index")
            exceptions.handle(request,
                              _('Unable to instance template.'),
                              redirect=redirect)


class InstanceClusterTemplateView(forms.ModalFormView):
    form_class = InstanceTemplateForm
    modal_header = _("Instance")
    submit_label = _("Instance")
    template_name = 'environment/template/instance_cluster_template.html'
    submit_url = "horizon:environment:template:instance_cluster_template"
    page_title = _("Instance")

    def get_context_data(self, **kwargs):
        context = super(InstanceClusterTemplateView, self).\
            get_context_data(**kwargs)
        context['submit_url'] =\
            reverse(self.submit_url, args=[self.kwargs["template_id"]])
        return context

    def get_success_url(self):
        return reverse('horizon:environment:template:index')

    def get_initial(self):
        template_id = self.kwargs["template_id"]
        return {'template_id': template_id}


class InstanceClusterTemplate(tables.LinkAction):
    name = "instance_cluster_template"
    verbose_name = _("Instance")
    url = "horizon:environment:template:instance_cluster_template"
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
                'template': json.dumps(json.loads(template_data))
            }
            api.daisy.import_json_to_template(request, **param)
            messages.success(request,
                             _('Your template %s has been imported.') %
                             data["template_file"])
            return True
        except Exception as e:
            LOG.error('ImportTemplateForm handle failed %s' % e)
            msg = _('Unable to import template')
            exceptions.handle(request, msg)
            return False


class ImportTemplateView(forms.ModalFormView):
    template_name = 'environment/template/import_template.html'
    form_class = ImportTemplateForm
    success_url = reverse_lazy('horizon:environment:template:index')


class ImportTemplate(tables.LinkAction):
    name = "import"
    verbose_name = _("Import Template")
    url = "horizon:environment:template:import_template"
    icon = "plus"
    classes = ("btn-launch", "ajax-modal",)


class TemplatesTable(tables.DataTable):
    name = tables.Column("name",
                         link="horizon:environment:template:template_detail",
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
    template_name = "environment/template/template.html"

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
            api.daisy.template_to_host(request, **param)
            message = _('Instance template: "%s"') % data['host_template']
            messages.success(request, message)
            return True
        except Exception as e:
            LOG.error('InstanceHostTemplateForm handle failed %s' % e)
            redirect = reverse("horizon:environment:deploy:selecthosts",
                               args=(cluster_id, ))
            exceptions.handle(request,
                              _('Unable to instance template.'),
                              redirect=redirect)


class InstanceHostTemplateView(forms.ModalFormView):
    form_class = InstanceHostTemplateForm
    modal_header = _("Instance Template")
    submit_label = _("Instance Template")
    template_name = 'environment/template/host_template_detail.html'
    submit_url = "horizon:environment:template:instance_host_template"
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
        LOG.error('batch_instance_template failed %s' % e)
        messages.error(request, e)
        response.status_code = 500
        LOG.info("instance host template failed!%s", e)
        return response

    response.status_code = 200
    return response


class InstanceHostTemplate(tables.LinkAction):
    name = "instance_template"
    verbose_name = _("Instance Template")
    url = "horizon:environment:template:instance_host_template"
    classes = ("ajax-modal", "btn-instance-template")

    def get_link_url(self, datum):
        cluster_id = self.table.kwargs["cluster_id"]
        host_id = self.table.get_object_id(datum)
        base_url = reverse(self.url, args=(cluster_id, host_id))
        return base_url


@csrf_exempt
def get_host_template_by_cluster(request, cluster_id):
    host_templates = None
    try:
        cluster = api.daisy.cluster_get(request, cluster_id)
        param = {
            "cluster_name": cluster.name
        }
        host_templates = \
            api.daisy.host_template_list(request, **param)
    except Exception, e:
        LOG.info("get host template failed!%s", e)
        messages.error(request, e)
    return host_templates


class GenerateHostTemplateForm(forms.SelfHandlingForm):
    name = forms.CharField(label=_("Name"), required=True)
    description = forms.CharField(widget=forms.widgets.Textarea(
                                  attrs={'rows': 4}),
                                  label=_("Description"),
                                  required=False)

    def clean(self):
        cleaned_data = super(GenerateHostTemplateForm, self).clean()
        return cleaned_data

    def handle(self, request, data):
        cluster_id = self.initial['cluster_id']
        host_id = self.initial['host_id']
        try:
            cluster = api.daisy.cluster_get(request, cluster_id)
            param = {
                "cluster_name": cluster.name,
                "host_template_name": data['name'],
                "host_id": host_id,
                "description": data["description"]
            }
            api.daisy.host_to_template(request, **param)
            message = _('Generate template: "%s"') % data['name']
            messages.success(request, message)
            return True
        except Exception as e:
            LOG.error('GenerateHostTemplateForm failed %s' % e)
            redirect = reverse('horizon:environment:cluster:overview',
                               args=[cluster_id])
            exceptions.handle(request,
                              _('Unable to generate template.'),
                              redirect=redirect)


class GenerateTemplate(tables.LinkAction):
    name = "generate"
    verbose_name = _("Generate Host Template")
    url = "horizon:environment:template:generate_host_template"
    classes = ("ajax-modal", "btn-generate-template")

    def get_link_url(self, datum):
        cluster_id = self.table.kwargs["cluster_id"]
        host_id = self.table.get_object_id(datum)
        base_url = reverse(self.url, args=(cluster_id, host_id))
        return base_url

    def allowed(self, request, host):
        return (host["host_os_status"] == 'active' and
                host["host_role_status"] == "active")


class GenerateHostTemplateView(forms.ModalFormView):
    form_class = GenerateHostTemplateForm
    modal_header = _("Generate Host Template")
    submit_label = _("Generate Host Template")
    template_name = 'environment/template/host_template.html'
    submit_url = "horizon:environment:template:generate_host_template"
    page_title = _("Generate Host Template")

    def get_context_data(self, **kwargs):
        context = super(GenerateHostTemplateView, self).\
            get_context_data(**kwargs)
        cluster_id = self.kwargs["cluster_id"]
        host_id = self.kwargs["host_id"]
        context['submit_url'] = \
            reverse(self.submit_url, args=(cluster_id, host_id))
        return context

    def get_success_url(self):
        cluster_id = self.kwargs["cluster_id"]
        return reverse('horizon:environment:cluster:overview',
                       args=[cluster_id])

    def get_initial(self):
        cluster_id = self.kwargs["cluster_id"]
        host_id = self.kwargs["host_id"]
        return {'cluster_id': cluster_id,
                'host_id': host_id}
