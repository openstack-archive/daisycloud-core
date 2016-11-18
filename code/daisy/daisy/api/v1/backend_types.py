# Copyright 2013 OpenStack Foundation
# All Rights Reserved.
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
import os
import subprocess
from oslo_log import log as logging
from webob.exc import HTTPForbidden

from daisy import i18n
from daisy import notifier

from daisy.api import policy
from daisy.common import utils
from daisy.common import wsgi
import daisy.registry.client.v1.api as registry
from daisy.api.v1 import controller

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW


class Controller(controller.BaseController):
    """
    WSGI controller for hosts resource in Daisy v1 API

    The hosts resource API is a RESTful web service for host data. The API
    is as follows::

        GET  /backend_types -- Returns a set of brief metadata
        about backend_types
    """

    def __init__(self):
        self.notifier = notifier.Notifier()
        registry.configure_registry_client()
        self.policy = policy.Enforcer()

    @utils.mutating
    def get(self, req):
        daisy_conf_path = "/home/daisy_install/daisy.conf"
        if os.path.exists(daisy_conf_path):
            scripts = "sed '/^[[:space:]]*#/d' " \
                      "/home/daisy_install/daisy.conf | sed " \
                      "/^[[:space:]]*$/d | grep " \
                      "'default_backend_types[[:space:]]*=' | sed " \
                      "'s/=/ /' | sed -e 's/^\w*\ *//'"
            try:
                default_backend_types = subprocess.check_output(
                    scripts,
                    shell=True,
                    stderr=subprocess.STDOUT).strip()
            except:
                msg = 'Error occurred when running scripts ' \
                      'to get default_backend_types'
                LOG.error(msg)
                raise HTTPForbidden(explanation=msg, request=req,
                                    content_type="text/plain")
            return {"default_backend_types": default_backend_types}

        else:
            msg = "/home/daisy_intall/daisy.conf is not exist"
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg, request=req,
                                content_type="text/plain")


class BackendTypesDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def get(self, request):
        result = {}
        return result


class BackendTypesSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def get(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response


def create_resource():
    """Version resource factory method"""
    deserializer = BackendTypesDeserializer()
    serializer = BackendTypesSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
