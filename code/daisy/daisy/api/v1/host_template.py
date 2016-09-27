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
/host_Templates endpoint for Daisy v1 API
"""

from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPConflict
from webob.exc import HTTPForbidden
from webob.exc import HTTPNotFound
from webob import Response

# import json

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
from daisy.registry.api.v1 import template

try:
    import simplejson as json
except ImportError:
    import json


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = template.SUPPORTED_PARAMS
SUPPORTED_FILTERS = template.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE
CONF = cfg.CONF
CONF.import_opt('disk_formats', 'daisy.common.config', group='image_format')
CONF.import_opt('container_formats', 'daisy.common.config',
                group='image_format')
CONF.import_opt('image_property_quota', 'daisy.common.config')


class Controller(controller.BaseController):
    """
    WSGI controller for Templates resource in Daisy v1 API

    The HostTemplates resource API is a RESTful web Template for Template data.
    The API is as follows::

        GET  /HostTemplates -- Returns a set of brief metadata about Templates
        GET  /HostTemplates/detail -- Returns a set of detailed metadata about
                              HostTemplates
        HEAD /HostTemplates/<ID> --
        Return metadata about an Template with id <ID>
        GET  /HostTemplates/<ID> --
        Return Template data for Template with id <ID>
        POST /HostTemplates --
        Store Template data and return metadata about the
                        newly-stored Template
        PUT  /HostTemplates/<ID> --
        Update Template metadata and/or upload Template
                            data for a previously-reserved Template
        DELETE /HostTemplates/<ID> -- Delete the Template with id <ID>
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

    def _raise_404_if_cluster_deleted(self, req, cluster_id):
        cluster = self.get_cluster_meta_or_404(req, cluster_id)
        if cluster['deleted']:
            msg = _("Cluster with identifier %s has been deleted.") % \
                cluster_id
            raise HTTPNotFound(msg)

    @utils.mutating
    def add_template(self, req, host_template):
        """
        Adds a new cluster template to Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about Template

        :raises HTTPBadRequest if x-Template-name is missing
        """
        self._enforce(req, 'add_host_template')

        host_template = registry.add_host_template_metadata(
            req.context, host_template)

        return {'host_template': template}

    @utils.mutating
    def update_host_template(self, req, template_id, host_template):
        """
        Updates an existing Template with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'update_host_template')
        # orig_Template_meta = self.get_Template_meta_or_404(req, id)
        '''
        if orig_Template_meta['deleted']:
            msg = _("Forbidden to update deleted Template.")
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        '''
        try:
            host_template = registry.update_host_template_metadata(
                req.context, template_id, host_template)

        except exception.Invalid as e:
            msg = (_("Failed to update template metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find host_template to update: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update host_template: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.warn(utils.exception_to_str(e))
            raise HTTPConflict(body=_('host_template operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('host_template.update', host_template)

        return {'host_template': host_template}

    def _filter_params(self, host_meta):
        for key in host_meta.keys():
            if key == "id" or key == "updated_at" or key == "deleted_at" or \
                    key == "created_at" or key == "deleted":
                del host_meta[key]
        if "memory" in host_meta:
            del host_meta['memory']

        if "system" in host_meta:
            del host_meta['system']

        if "disks" in host_meta:
            del host_meta['disks']

        if "os_status" in host_meta:
            del host_meta['os_status']

        if "status" in host_meta:
            del host_meta['status']

        if "messages" in host_meta:
            del host_meta['messages']

        if "cpu" in host_meta:
            del host_meta['cpu']

        if "ipmi_addr" in host_meta:
            del host_meta['ipmi_addr']

        if "interfaces" in host_meta:
            for interface in host_meta['interfaces']:
                for key in interface.keys():
                    if key == "id" or key == "updated_at" or \
                            key == "deleted_at" \
                            or key == "created_at" or key == "deleted" or \
                            key == "current_speed" \
                            or key == "max_speed" or key == "host_id" or \
                            key == "state":
                        del interface[key]
                for assigned_network in interface['assigned_networks']:
                    if "ip" in assigned_network:
                        assigned_network['ip'] = ""
        return host_meta

    @utils.mutating
    def get_host_template_detail(self, req, template_id):
        """
        delete a existing cluster template with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'get_host_template_detail')
        try:
            host_template = registry.host_template_detail_metadata(
                req.context, template_id)
            return {'host_template': host_template}
        except exception.NotFound as e:
            msg = (_("Failed to find host template: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to get host template: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("host template %(id)s could not be get "
                     "because it is in use: "
                     "%(exc)s") % {"id": template_id,
                                   "exc": utils.exception_to_str(e)})
            LOG.error(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            # self.notifier.info('host.delete', host)
            return Response(body='', status=200)

    @utils.mutating
    def get_host_template_lists(self, req):
        self._enforce(req, 'get_template_lists')
        params = self._get_query_params(req)
        template_meta = {}
        try:
            host_template_lists = registry.host_template_lists_metadata(
                req.context, **params)
            if host_template_lists and host_template_lists[0]:
                template_meta = json.loads(host_template_lists[0]['hosts'])
            return {'host_template': template_meta}
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(host_template=host_template_lists)

    @utils.mutating
    def host_to_template(self, req, host_template):
        """
        host to Template.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if x-Template-cluster is missing
        """
        self._enforce(req, 'host_to_template')
        if host_template.get('host_id', None):
            origin_host_meta = self.get_host_meta_or_404(
                req, host_template['host_id'])
            host_meta = self._filter_params(origin_host_meta)
            if host_template.get(
                    'host_template_name',
                    None) and host_template.get(
                    'cluster_name',
                    None):
                host_meta['name'] = host_template['host_template_name']
                host_meta['description'] = host_template.get(
                    'description', None)
                params = {
                    'filters': {
                        'cluster_name': host_template['cluster_name']}}
                templates = registry.host_template_lists_metadata(
                    req.context, **params)
                if templates and templates[0]:
                    had_host_template = False
                    if templates[0]['hosts']:
                        templates[0]['hosts'] = json.loads(
                            templates[0]['hosts'])
                    else:
                        templates[0]['hosts'] = []
                    for index in range(len(templates[0]['hosts'])):
                        if host_template['host_template_name'] == templates[
                                0]['hosts'][index]['name']:
                            had_host_template = True
                            templates[0]['hosts'][index] = host_meta
                            break
                    if not had_host_template:
                        host_meta['name'] = host_template['host_template_name']
                        templates[0]['hosts'].append(host_meta)
                    templates[0]['hosts'] = json.dumps(templates[0]['hosts'])
                    host_template = registry.update_host_template_metadata(
                        req.context, templates[0]['id'], templates[0])
                else:
                    param = {
                        "cluster_name": host_template['cluster_name'],
                        "hosts": json.dumps(
                            [host_meta])}
                    host_template = registry.add_host_template_metadata(
                        req.context, param)
        return {'host_template': host_template}

    @utils.mutating
    def template_to_host(self, req, host_template):
        if not host_template.get('cluster_name', None):
            msg = "cluster name is null"
            raise HTTPNotFound(explanation=msg)
        params = {'filters': {'cluster_name': host_template['cluster_name']}}
        templates = registry.host_template_lists_metadata(
            req.context, **params)
        hosts_param = []
        host_template_used = {}
        if templates and templates[0]:
            hosts_param = json.loads(templates[0]['hosts'])
            for host in hosts_param:
                if host['name'] == host_template['host_template_name']:
                    host_template_used = host
                    break
        if not host_template_used:
            msg = "not host_template %s" % host_template['host_template_name']
            raise HTTPNotFound(
                explanation=msg,
                request=req,
                content_type="text/plain")
        if host_template.get('host_id', None):
            self.get_host_meta_or_404(req, host_template['host_id'])
        else:
            msg = "host_id is not null"
            raise HTTPBadRequest(explanation=msg)
        host_id = host_template['host_id']
        params = {'filters': {'name': host_template['cluster_name']}}
        clusters = registry.get_clusters_detail(req.context, **params)
        if clusters and clusters[0]:
            host_template_used['cluster'] = clusters[0]['id']
        if 'role' in host_template_used and host_template_used['role']:
            role_id_list = []
            host_role_list = []
            if 'cluster' in host_template_used:
                params = self._get_query_params(req)
                role_list = registry.get_roles_detail(req.context, **params)
                for role_name in role_list:
                    if role_name['cluster_id'] == host_template_used[
                            'cluster']:
                        host_role_list = list(host_template_used['role'])
                        if role_name['name'] in host_role_list:
                            role_id_list.append(role_name['id'])
                host_template_used['role'] = role_id_list
        if 'name' in host_template_used:
            host_template_used.pop('name')
        if 'dmi_uuid' in host_template_used:
            host_template_used.pop('dmi_uuid')
        if 'ipmi_user' in host_template_used:
            host_template_used.pop('ipmi_user')
        if 'ipmi_passwd' in host_template_used:
            host_template_used.pop('ipmi_passwd')
        if 'ipmi_addr' in host_template_used:
            host_template_used.pop('ipmi_addr')
        host_template_interfaces = host_template_used.get('interfaces', None)
        if host_template_interfaces:
            template_ether_interface = [
                interface for interface in host_template_interfaces if
                interface['type'] == "ether"]
            orig_host_meta = registry.get_host_metadata(req.context, host_id)
            orig_host_interfaces = orig_host_meta.get('interfaces', None)
            temp_orig_host_interfaces = [
                interface for interface in orig_host_interfaces if
                interface['type'] == "ether"]
            if len(temp_orig_host_interfaces) != len(template_ether_interface):
                msg = (_('host_id %s does not match the host_id host_template '
                         '%s.') % (host_id,
                                   host_template['host_template_name']))
                raise HTTPBadRequest(explanation=msg)
            interface_match_flag = 0
            for host_template_interface in host_template_interfaces:
                if host_template_interface['type'] == 'ether':
                    for orig_host_interface in orig_host_interfaces:
                        if orig_host_interface[
                                'pci'] == host_template_interface['pci']:
                            interface_match_flag += 1
                            host_template_interface[
                                'mac'] = orig_host_interface['mac']
                            if 'ip' in host_template_interface:
                                host_template_interface.pop('ip')
            if interface_match_flag != len(template_ether_interface):
                msg = (_('host_id %s does not match the host '
                         'host_template %s.') % (
                    host_id, host_template['host_template_name']))
                raise HTTPBadRequest(explanation=msg)
            host_template_used['interfaces'] = str(host_template_interfaces)
            host_template = registry.update_host_metadata(
                req.context, host_id, host_template_used)
        return {"host_template": host_template}

    @utils.mutating
    def delete_host_template(self, req, host_template):
        """
        delete a existing host template with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'delete_host_template')
        try:
            if not host_template.get('cluster_name', None):
                msg = "cluster name is null"
                raise HTTPNotFound(explanation=msg)
            params = {
                'filters': {
                    'cluster_name': host_template['cluster_name']}}
            host_templates = registry.host_template_lists_metadata(
                req.context, **params)
            template_param = []
            had_host_template = False
            if host_templates and host_templates[0]:
                template_param = json.loads(host_templates[0]['hosts'])
                for host in template_param:
                    if host['name'] == host_template['host_template_name']:
                        template_param.remove(host)
                        had_host_template = True
                        break
                if not had_host_template:
                    msg = "not host template name %s" % host_template[
                        'host_template_name']
                    raise HTTPNotFound(explanation=msg)
                else:
                    host_templates[0]['hosts'] = json.dumps(template_param)
                    host_template = registry.update_host_template_metadata(
                        req.context, host_templates[0]['id'],
                        host_templates[0])
                    return {"host_template": host_template}
            else:
                msg = "host template cluster name %s is null" % host_template[
                    'cluster_name']
                raise HTTPNotFound(explanation=msg)

        except exception.NotFound as e:
            msg = (_("Failed to find host template to delete: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete template: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("template %(id)s could not be deleted "
                     "because it is in use: "
                     "%(exc)s") % {"id": host_template['host_id'],
                                   "exc": utils.exception_to_str(e)})
            LOG.error(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            return Response(body='', status=200)


class HostTemplateDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["host_template"] = utils.get_template_meta(request)
        return result

    def add_host_template(self, request):
        return self._deserialize(request)

    def update_host_template(self, request):
        return self._deserialize(request)

    def host_to_template(self, request):
        return self._deserialize(request)

    def template_to_host(self, request):
        return self._deserialize(request)

    def delete_host_template(self, request):
        return self._deserialize(request)


class HostTemplateSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_host_template(self, response, result):
        host_template = result['host_template']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host_template=host_template))
        return response

    def delete_host_template(self, response, result):
        host_template = result['host_template']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host_template=host_template))
        return response

    def get_host_template_detail(self, response, result):
        host_template = result['host_template']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host_template=host_template))
        return response

    def update_host_template(self, response, result):
        host_template = result['host_template']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host_template=host_template))
        return response

    def host_to_template(self, response, result):
        host_template = result['host_template']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host_template=host_template))
        return response

    def template_to_host(self, response, result):
        host_template = result['host_template']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host_template=host_template))
        return response

    def get_host_template_lists(self, response, result):
        host_template = result['host_template']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(host_template=host_template))


def create_resource():
    """Templates resource factory method"""
    deserializer = HostTemplateDeserializer()
    serializer = HostTemplateSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
