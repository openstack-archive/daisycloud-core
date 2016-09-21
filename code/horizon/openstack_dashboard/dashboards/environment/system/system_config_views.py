from horizon import messages
from horizon import views


import logging
LOG = logging.getLogger(__name__)


class SystemConfigView(views.HorizonTemplateView):
    template_name = "environment/system/system_config.html"

    def get_context_data(self, **kwargs):
        context = super(SystemConfigView, self).get_context_data(**kwargs)
        return context
