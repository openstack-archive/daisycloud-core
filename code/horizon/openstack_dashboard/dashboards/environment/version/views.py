#
#   Copyright ZTE
#   Daisy Tools Dashboard
#

import os
import logging

from django import http
from django.views import generic
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from horizon import messages

from openstack_dashboard import api

LOG = logging.getLogger(__name__)


def get_version_path():
    return getattr(settings, 'DAISY_VER_PATH', "/var/lib/daisy/tecs/")


def get_files():
    VER_PATH = get_version_path()

    files = []
    try:
        items = os.listdir(VER_PATH)
        for item in items:
            full_path = os.path.join(VER_PATH, item)
            if os.path.isfile(full_path):
                files.append(item)
    except Exception, e:
        files = ['Directory of the Version file does not exist.']

    return files


def delete_file(newfile):
    VER_PATH = get_version_path()
    begins = newfile.split('_')
    begin = begins[0]
    ends = newfile.split('.')
    end = ends[-1]

    files = get_files()
    for f in files:
        if (begin in f) and (end in f) and newfile != f:
            full_path = os.path.join(VER_PATH, f)
            if(os.path.isfile(full_path)):
                os.remove(full_path)


class VersionView(generic.TemplateView):
    template_name = "environment/version/index.html"

    def get_context_data(self, **kwargs):
        context = super(VersionView, self).get_context_data(**kwargs)
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        context['files'] = get_files()
        context['is_version'] = True

        return context


def upload_version(request):
    VER_PATH = get_version_path()
    try:
        os_version = request.FILES.get("os_version")
        if os_version is not None:
            destination = open(VER_PATH + os_version.name, 'wb+')
            for chunk in os_version.chunks():
                destination.write(chunk)
            destination.close()
            delete_file(os_version.name)

        tecs_version = request.FILES.get("role_version")
        if tecs_version is not None:
            destination = open(VER_PATH + tecs_version.name, 'wb+')
            for chunk in tecs_version.chunks():
                destination.write(chunk)
            destination.close()
            delete_file(tecs_version.name)

        if os_version is not None or tecs_version is not None:
            messages.success(request, _('Upload file success!'))

        if os_version is None and tecs_version is None:
            messages.error(request, _("Please select version files!"))

    except Exception, e:
        messages.error(request, _('Upload file failed! %s' % e))

    url = reverse('horizon:environment:version:index')
    response = http.HttpResponseRedirect(url)
    return response

