#
#   Copyright ZTE
#   Daisy Tools Dashboard
#

from django.http import HttpResponse
from django.views import generic


class ConfigureView(generic.TemplateView):
    template_name = 'environment/configure/index.html'

    def get_context_data(self, **kwargs):
        context = super(ConfigureView, self).get_context_data(**kwargs)
        context["viewclass"] = 'ConfigureView'
        return context


def test(request):
    return HttpResponse('this is a test view')
