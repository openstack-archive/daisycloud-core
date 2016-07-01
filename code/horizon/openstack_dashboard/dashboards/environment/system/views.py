#
#   Copyright ZTE
#   Daisy Tools Dashboard
#

import os
import logging
import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views import generic
from django.core.urlresolvers import reverse
from django.core.servers.basehttp import FileWrapper
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from horizon import messages
from horizon import exceptions
from openstack_dashboard import api

LOG = logging.getLogger(__name__)


def get_restore_path():
    return getattr(settings, 'DAISY_RESTORE_PATH', "/home/daisy_backup/")


class SystemView(generic.TemplateView):
    template_name = "environment/system/index.html"

    def get_context_data(self, **kwargs):
        context = super(SystemView, self).get_context_data(**kwargs)
        clusters = api.daisy.cluster_list(self.request)
        cluster_lists = [c for c in clusters]
        context['clusters'] = cluster_lists
        context['is_system'] = True
        return context


@csrf_exempt
def backup_system(request):
    param = {}
    try:
        ret = api.daisy.backup_system(request, **param)
        file_full_path = ret.backup_file
        filename = file_full_path.split("/")[-1]
        wrapper = FileWrapper(file(file_full_path))
        response = HttpResponse(wrapper,
                                content_type='application/ostet-stream')
        response['Content-Disposition'] = 'attachment; filename=' + filename
        response['Content-Length'] = os.path.getsize(file_full_path)
        return response
    except Exception as e:
        redirect = reverse("horizon:environment:system:index")
        messages.error(request, e)
        LOG.info("backup system failed!(%s)" % e)
        exceptions.handle(request, _('Backup System failed.'), redirect)


@csrf_exempt
def restore_system(request):
    restore_path = get_restore_path()
    response = HttpResponse()
    status_code = 200
    try:
        restore_file = request.FILES.get("restore_file")
        if restore_file is not None:
            backup_file_full_path = restore_path + restore_file.name
            destination = open(backup_file_full_path, 'wb+')
            for chunk in restore_file.chunks():
                destination.write(chunk)
            destination.close()
            param = {'backup_file_path': backup_file_full_path}
            # query backup file version
            backup_file_version = api.daisy.get_backup_file_version(request,
                                                                    **param)
            # query daisy internal version
            daisy_version = api.daisy.get_daisy_internal_version(request)
            if backup_file_version.backup_file_version != \
                    daisy_version.daisy_version:
                different_version = {
                    "file_name": restore_file.name,
                    "backup_file_version":
                        backup_file_version.backup_file_version,
                    "daisy_version": daisy_version.daisy_version
                }
                status_code = 200
                return HttpResponse(json.dumps(different_version),
                                    content_type="application/json",
                                    status=status_code)
                return response
            else:
                api.daisy.restore_system(request, **param)
            messages.success(request, _('Restore system success!'))
            status_code = 200
        else:
            messages.error(request, _("Please select file!"))
            status_code = 500
    except Exception, e:
        LOG.info(_('Restore system failed! %s.') % e)
        messages.error(request, _('Restore system failed! %s.') % e)
        status_code = 500
    response.status_code = status_code
    return response


@csrf_exempt
def restore_system_force(request):
    data = json.loads(request.body)
    restore_path = get_restore_path()
    backup_file_full_path = restore_path + data["file_name"]
    response = HttpResponse()
    param = {'backup_file_path': backup_file_full_path}
    try:
        api.daisy.restore_system(request, **param)
        messages.success(request, _('Restore system success!'))
    except Exception, e:
        messages.error(request, _('Restore system failed! %s.') % e)
        exceptions.handle(request, _('Restore system failed! %s.') % e)
        LOG.info(_('Restore system failed! %s.') % e.message)
        response.status_code = 500
        return response
    response.status_code = 200
    return response
