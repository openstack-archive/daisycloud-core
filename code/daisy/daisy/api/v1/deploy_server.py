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

"""
/deploy_server endpoint for Daisy v1 API
"""
import webob.exc
import re
import commands
import subprocess
from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden
from daisy.api import policy
import daisy.api.v1
from daisy.api.v1 import controller
from daisy.api.v1 import filters
from daisy.common import exception
from daisy.common import utils
from daisy.common import wsgi
from daisy import i18n
from daisy import notifier
import daisy.registry.client.v1.api as registry

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE


class Controller(controller.BaseController):
    """
    WSGI controller for deploy_servers resource in Daisy v1 API

    The deploy_servers resource API is a RESTful web service for
    template_service data.
    The API is as follows::

        GET  /deploy_servers -- Returns a set of brief metadata about
                                    deploy_servers
        GET  /deploy_servers/detail -- Returns a set of detailed metadata
                                    about deploy_servers
        HEAD /deploy_servers/<ID> --
        Return metadata about an template_service with id <ID>
        GET  /deploy_servers/<ID> --
        Return template_service data for template_service with id <ID>
        POST /deploy_servers --
        Store template_service data and return metadata about the
                        newly-stored template_service
        PUT  /deploy_servers/<ID> --
        Update template_service metadata and/or upload template_service
                            data for a previously-reserved template_service
        DELETE /deploy_servers/<ID> -- Delete the deploy_servers with id
    """

    def __init__(self):
        self.notifier = notifier.Notifier()
        registry.configure_registry_client()
        self.policy = policy.Enforcer()

    def _enforce(self, req, action, target=None):
        """Authorize an action against our policies"""
        if target is None:
            target = {}
        try:
            self.policy.enforce(req.context, action, target)
        except exception.Forbidden:
            raise HTTPForbidden()

    def _get_filters(self, req):
        """
        Return a dictionary of query param filters from the request

        :param req: the Request object coming from the wsgi layer
        :retval a dict of key/value filters
        """
        query_filters = {}
        for param in req.params:
            if param in SUPPORTED_FILTERS:
                query_filters[param] = req.params.get(param)
                if not filters.validate(param, query_filters[param]):
                    raise HTTPBadRequest(_('Bad value passed to filter '
                                           '%(filter)s got %(val)s')
                                         % {'filter': param,
                                            'val': query_filters[param]})
        return query_filters

    def _get_query_params(self, req):
        """
        Extracts necessary query params from request.

        :param req: the WSGI Request object
        :retval dict of parameters that can be used by registry client
        """
        params = {'filters': self._get_filters(req)}

        for PARAM in SUPPORTED_PARAMS:
            if PARAM in req.params:
                params[PARAM] = req.params.get(PARAM)
        return params

    def get_nics(self):
        nics = set()
        (status, output) = commands.getstatusoutput('ifconfig')
        net_card_pattern = re.compile('\S*: ')
        for net_card in re.finditer(net_card_pattern, str(output)):
            nic_name = net_card.group().split(': ')[0]
            if nic_name == "lo":
                continue
            eth_port_name = nic_name.split(":")[0].split(".")[0]
            nics.add(eth_port_name)
        return nics

    def get_pxe_nic(self, pxe_server_ip):
        if_addr_nic_cmd = "ip addr show | grep %s | awk '{ print $7 }'" \
                          % pxe_server_ip
        (status, output) = commands.getstatusoutput(if_addr_nic_cmd)
        if status:
            LOG.warn("get_pxe_server_port error %s." % status)
            return
        return str(output).split(":")[0].split(".")[0]

    def list_deploy_server(self, req):
        """
        Returns detailed information for all available deploy_servers

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'deploy_servers': [
                {'id': <ID>,
                 'name': <NAME>,
                 ......
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._enforce(req, 'list_deploy_server')
        params = self._get_query_params(req)
        params['filters'] = {'type': 'system'}
        try:
            deploy_servers = registry.get_all_networks(req.context, **params)
        except Exception:
            LOG.error("Get system net plane failed.")
            raise HTTPBadRequest(
                explanation="Get system net plane failed.",
                request=req)
        if len(deploy_servers) != 1:
            msg = (_("system net plane is not only, "
                     "%s." % len(deploy_servers)))
            LOG.error(msg)
            raise HTTPBadRequest(
                explanation=msg,
                request=req)
        deploy_servers[0]["nics"] = self.get_nics()
        deploy_servers[0]["pxe_nic"] = self.get_pxe_nic(
            deploy_servers[0]["ip"])
        return dict(deploy_servers=deploy_servers)

    @utils.mutating
    def pxe_env_check(self, req, deploy_server_meta):

        def get_error_msg(in_child):
            end_flag = 'end check'
            error_flag = "[error]"
            error_msg = ""
            while True:
                buff = in_child.stdout.readline()
                if (buff == '' or buff.find(end_flag) > 0) and \
                        (in_child.poll() is not None):
                    break
                if buff.find(error_flag) == 0:
                    error_msg += buff[len(error_flag):]
            return error_msg

        self._enforce(req, 'pxe_env_check')
        interface = deploy_server_meta["deployment_interface"]
        server_ip = deploy_server_meta["server_ip"]
        cmd = "pxe_env_check %s %s" % (interface, server_ip)
        try:
            child = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            child.wait()
            if child.returncode != 0:
                msg = get_error_msg(child)
                LOG.error(msg)
                raise webob.exc.HTTPBadRequest(explanation=msg)
        except subprocess.CalledProcessError as e:
            msg = "pxe env check failed!%s" % e.output.strip()
            LOG.error(msg)
            raise webob.exc.HTTPBadRequest(explanation=msg)
        except Exception as e:
            msg = "Failed to pxe env check,%s" % e
            LOG.error(msg)
            raise webob.exc.HTTPBadRequest(explanation=msg)
        else:
            LOG.info("pxe env check ok!")
        return {'deploy_server_meta': {'return_code': 0}}


class DeployServerDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["deploy_server_meta"] = utils.get_dict_meta(request)
        return result

    def pxe_env_check(self, request):
        return self._deserialize(request)


class DeployServerSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def pxe_env_check(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response


def create_resource():
    """deploy server resource factory method"""
    deserializer = DeployServerDeserializer()
    serializer = DeployServerSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
