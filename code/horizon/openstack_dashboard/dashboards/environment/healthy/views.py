#
#   Copyright ZTE
#   Daisy Tools Dashboard
#

from django.http import HttpResponse
from django.views import generic


class HealthyView(generic.TemplateView):
    template_name = "environment/healthy/index.html"
    
    def get_context_data(self, **kwargs):
        context = super(HealthyView, self).get_context_data(**kwargs)
        context["viewclass"] = "HealthyView"
        return context 


def test(request):
    return HttpResponse('this is a test view')
