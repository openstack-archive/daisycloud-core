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
