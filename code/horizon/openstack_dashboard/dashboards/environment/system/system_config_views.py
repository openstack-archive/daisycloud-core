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
        return context
