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
/Templates endpoint for Daisy v1 API
"""

import os
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPConflict
from webob.exc import HTTPForbidden
from webob.exc import HTTPNotFound
from webob import Response
import copy
import json
import subprocess
from oslo_utils import importutils
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

import daisy.api.backends.common as daisy_cmn

# TODO (huzhj) move it into common sub module
daisy_path = '/var/lib/daisy/'


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = template.SUPPORTED_PARAMS
SUPPORTED_FILTERS = template.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE


class Controller(controller.BaseController):
    """
    WSGI controller for Templates resource in Daisy v1 API

    The Templates resource API is a RESTful web Template for Template data.
    The API is as follows::

        GET  /Templates -- Returns a set of brief metadata about Templates
        GET  /Templates/detail -- Returns a set of detailed metadata about
                              Templates
        HEAD /Templates/<ID> -- Return metadata about an Template with id <ID>
        GET  /Templates/<ID> -- Return Template data for Template with id <ID>
        POST /Templates -- Store Template data and return metadata about the
                        newly-stored Template
        PUT  /Templates/<ID> -- Update Template metadata and/or upload Template
                            data for a previously-reserved Template
        DELETE /Templates/<ID> -- Delete the Template with id <ID>
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
    def add_template(self, req, template):
        """
        Adds a new cluster template to Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about Template

        :raises HTTPBadRequest if x-Template-name is missing
        """
        self._enforce(req, 'add_template')

        template = registry.add_template_metadata(req.context, template)

        return {'template': template}

    @utils.mutating
    def update_template(self, req, template_id, template):
        """
        Updates an existing Template with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'update_template')
        try:
            template = registry.update_template_metadata(req.context,
                                                         template_id,
                                                         template)

        except exception.Invalid as e:
            msg = (_("Failed to update template metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find template to update: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update template: %s") %
                   utils.exception_to_str(e))
            LOG.warning(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.warning(utils.exception_to_str(e))
            raise HTTPConflict(body=_('template operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('template.update', template)

        return {'template': template}

    @utils.mutating
    def delete_template(self, req, template_id):
        """
        delete a existing cluster template with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'delete_template')
        try:
            registry.delete_template_metadata(req.context, template_id)
        except exception.NotFound as e:
            msg = (_("Failed to find template to delete: %s") %
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
                     "%(exc)s") % {"id": template_id,
                                   "exc": utils.exception_to_str(e)})
            LOG.error(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            return Response(body='', status=200)

    def _del_general_params(self, param):
        del param['created_at']
        del param['updated_at']
        del param['deleted']
        del param['deleted_at']
        del param['id']

    def _del_cluster_params(self, cluster):
        del cluster['networks']
        del cluster['vlan_start']
        del cluster['vlan_end']
        del cluster['vni_start']
        del cluster['vni_end']
        del cluster['gre_id_start']
        del cluster['gre_id_end']
        del cluster['net_l23_provider']
        del cluster['public_vip']
        del cluster['segmentation_type']
        del cluster['base_mac']
        del cluster['name']

    def _get_cinder_volumes(self, req, role):
        cinder_volume_params = {'filters': {'role_id': role['id']}}
        cinder_volumes = registry.list_cinder_volume_metadata(
            req.context, **cinder_volume_params)
        for cinder_volume in cinder_volumes:
            if cinder_volume.get('role_id', None):
                cinder_volume['role_id'] = role['name']
            self._del_general_params(cinder_volume)
        return cinder_volumes

    def _get_neutron_backends(self, req, role):
        neutron_backend_params = {'filters': {'role_id': role['id']}}
        neutron_backends = registry.list_neutron_backend_metadata(
            req.context, **neutron_backend_params)
        for neutron_backend in neutron_backends:
            if neutron_backend.get('role_id', None):
                neutron_backend['role_id'] = role['name']
            self._del_general_params(neutron_backend)
        return neutron_backends

    def _get_optical_switchs(self, req, role):
        optical_switch_params = {'filters': {'role_id': role['id']}}
        optical_switchs = registry.list_optical_switch_metadata(
            req.context, **optical_switch_params)
        for optical_switch in optical_switchs:
            if optical_switch.get('role_id', None):
                optical_switch['role_id'] = role['name']
            self._del_general_params(optical_switch)
        return optical_switchs

    def _get_services_disk(self, req, role):
        params = {'filters': {'role_id': role['id']}}
        services_disk = registry.list_service_disk_metadata(
            req.context, **params)
        for service_disk in services_disk:
            if service_disk.get('role_id', None):
                service_disk['role_id'] = role['name']
            self._del_general_params(service_disk)
        return services_disk

    @utils.mutating
    def export_db_to_json(self, req, template):
        """
        Template backend to a cluster.
        :param req: The WSGI/Webob Request object
        :raises HTTPBadRequest if x-Template-cluster is missing
        """
        cluster_name = template.get('cluster_name', None)
        type = template.get('type', None)
        description = template.get('description', None)
        template_name = template.get('template_name', None)
        self._enforce(req, 'export_db_to_json')
        cinder_volume_list = []
        neutron_backend_list = []
        service_disk_list = []
        optical_switch_list = []
        template_content = {}
        template_json = {}
        template_id = ""
        if not type or type == "tecs":
            try:
                params = {'filters': {'name': cluster_name}}
                clusters = registry.get_clusters_detail(req.context, **params)
                if clusters:
                    cluster_id = clusters[0]['id']
                else:
                    msg = "the cluster %s is not exist" % cluster_name
                    LOG.error(msg)
                    raise HTTPForbidden(
                        explanation=msg,
                        request=req,
                        content_type="text/plain")

                params = {'filters': {'cluster_id': cluster_id}}
                cluster = registry.get_cluster_metadata(
                    req.context, cluster_id)
                roles = registry.get_roles_detail(req.context, **params)
                networks = registry.get_networks_detail(
                    req.context, cluster_id, **params)
                for role in roles:
                    cinder_volumes = self._get_cinder_volumes(req, role)
                    cinder_volume_list += cinder_volumes
                    services_disk = self._get_services_disk(req, role)
                    service_disk_list += services_disk
                    optical_switchs = self._get_optical_switchs(req, role)
                    optical_switch_list += optical_switchs
                    neutron_backends = self._get_neutron_backends(req, role)
                    neutron_backend_list += neutron_backends

                    if role.get('config_set_id', None):
                        config_set = registry.get_config_set_metadata(
                            req.context, role['config_set_id'])
                        if config_set.get("config", None):
                            role['config_set'] = config_set['config']
                    del role['cluster_id']
                    del role['status']
                    del role['progress']
                    del role['messages']
                    del role['config_set_update_progress']
                    self._del_general_params(role)
                for network in networks:
                    network_detail = registry.get_network_metadata(
                        req.context, network['id'])
                    if network_detail.get('ip_ranges', None):
                        network['ip_ranges'] = network_detail['ip_ranges']
                    del network['cluster_id']
                    self._del_general_params(network)
                if cluster.get('routers', None):
                    for router in cluster['routers']:
                        del router['cluster_id']
                        self._del_general_params(router)
                if cluster.get('logic_networks', None):
                    for logic_network in cluster['logic_networks']:
                        for subnet in logic_network['subnets']:
                            del subnet['logic_network_id']
                            del subnet['router_id']
                            self._del_general_params(subnet)
                        del logic_network['cluster_id']
                        self._del_general_params(logic_network)
                if cluster.get('nodes', None):
                    del cluster['nodes']
                self._del_general_params(cluster)
                self._del_cluster_params(cluster)
                cluster['tecs_version_id'] = ""
                template_content['cluster'] = cluster
                template_content['cluster_name'] = cluster_name
                template_content['roles'] = roles
                template_content['networks'] = networks
                template_content['cinder_volumes'] = cinder_volume_list
                template_content['neutron_backends'] = neutron_backend_list
                template_content['optical_switchs'] = optical_switch_list
                template_content['services_disk'] = service_disk_list
                template_json['content'] = json.dumps(template_content)
                template_json['type'] = 'tecs'
                template_json['name'] = template_name
                template_json['description'] = description

                template_host_params = {'cluster_name': cluster_name}
                template_hosts = registry.host_template_lists_metadata(
                    req.context, **template_host_params)
                if template_hosts:
                    template_json['hosts'] = template_hosts[0]['hosts']
                else:
                    template_json['hosts'] = "[]"

                template_params = {'filters': {'name': template_name}}
                template_list = registry.template_lists_metadata(
                    req.context, **template_params)
                if template_list:
                    update_template = registry.update_template_metadata(
                        req.context, template_list[0]['id'], template_json)
                    template_id = template_list[0]['id']
                else:
                    add_template = registry.add_template_metadata(
                        req.context, template_json)
                    template_id = add_template['id']

                if template_id:
                    template_detail = registry.template_detail_metadata(
                        req.context, template_id)
                    self._del_general_params(template_detail)
                    template_detail['content'] = json.loads(
                        template_detail['content'])
                    if template_detail['hosts']:
                        template_detail['hosts'] = json.loads(
                            template_detail['hosts'])

                    tecs_json = daisy_path + "%s.json" % template_name
                    cmd = 'rm -rf  %s' % (tecs_json,)
                    daisy_cmn.subprocess_call(cmd)
                    with open(tecs_json, "w+") as fp:
                        json.dump(template_detail, fp, indent=2)

            except exception.Invalid as e:
                raise HTTPBadRequest(explanation=e.msg, request=req)

        return {"template": template_detail}

    @utils.mutating
    def import_json_to_template(self, req, template):
        template_id = ""
        template = json.loads(template.get('template', None))
        template_cluster = copy.deepcopy(template)
        template_name = template_cluster.get('name', None)
        template_params = {'filters': {'name': template_name}}
        try:
            if template_cluster.get('content', None):
                template_cluster['content'] = json.dumps(
                    template_cluster['content'])
            if template_cluster.get('hosts', None):
                template_cluster['hosts'] = json.dumps(
                    template_cluster['hosts'])
            else:
                template_cluster['hosts'] = "[]"

            template_list = registry.template_lists_metadata(
                req.context, **template_params)
            if template_list:
                registry.update_template_metadata(
                    req.context, template_list[0]['id'], template_cluster)
                template_id = template_list[0]['id']
            else:
                add_template_cluster = registry.add_template_metadata(
                    req.context, template_cluster)
                template_id = add_template_cluster['id']

            if template_id:
                template_detail = registry.template_detail_metadata(
                    req.context, template_id)
                del template_detail['deleted']
                del template_detail['deleted_at']

        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)

        return {"template": template_detail}

    def _import_cinder_volumes_to_db(self, req,
                                     template_cinder_volumes, roles):
        for template_cinder_volume in template_cinder_volumes:
            has_template_role = False
            for role in roles:
                if template_cinder_volume['role_id'] == role['name']:
                    has_template_role = True
                    template_cinder_volume['role_id'] = role['id']
                    break
            if has_template_role:
                registry.add_cinder_volume_metadata(req.context,
                                                    template_cinder_volume)
            else:
                msg = "can't find role %s in new cluster when\
                       import cinder_volumes from template"\
                       % template_cinder_volume['role_id']
                raise HTTPBadRequest(explanation=msg, request=req)

    def _import_neutron_backends_to_db(self, req,
                                       template_neutron_backends, roles):
        for template_neutron_backend in template_neutron_backends:
            has_template_role = False
            for role in roles:
                if template_neutron_backend['role_id'] == role['name']:
                    has_template_role = True
                    template_neutron_backend['role_id'] = role['id']
                    break
            if has_template_role:
                registry.add_neutron_backend_metadata(req.context,
                                                      template_neutron_backend)
            else:
                msg = "can't find role %s in new cluster when\
                       import neutron_backends from template"\
                       % template_neutron_backend['role_id']
                LOG.error(msg)
                raise HTTPBadRequest(explanation=msg, request=req)

    def _import_optical_switchs_to_db(self, req,
                                      template_optical_switchs, roles):
        for template_optical_switch in template_optical_switchs:
            has_template_role = False
            for role in roles:
                if template_optical_switch['role_id'] == role['name']:
                    has_template_role = True
                    template_optical_switch['role_id'] = role['id']
                    break
            if has_template_role:
                registry.add_optical_switch_metadata(req.context,
                                                     template_optical_switch)
            else:
                msg = "can't find role %s in new cluster when\
                       import optical_switchs from template"\
                       % template_optical_switch['role_id']
                raise HTTPBadRequest(explanation=msg, request=req)

    def _import_services_disk_to_db(self, req,
                                    template_services_disk, roles):
        for template_service_disk in template_services_disk:
            has_template_role = False
            for role in roles:
                if template_service_disk['role_id'] == role['name']:
                    has_template_role = True
                    template_service_disk['role_id'] = role['id']
                    break
            if has_template_role:
                registry.add_service_disk_metadata(req.context,
                                                   template_service_disk)
            else:
                msg = "can't find role %s in new cluster when\
                       import service_disks from template"\
                       % template_service_disk['role_id']
                raise HTTPBadRequest(explanation=msg, request=req)

    @utils.mutating
    def import_template_to_db(self, req, template):
        """
        create cluster
        """
        cluster_id = ""
        template_cluster = {}
        cluster_meta = {}
        template_meta = copy.deepcopy(template)
        template_name = template_meta.get('template_name', None)
        cluster_name = template_meta.get('cluster', None)
        template_params = {'filters': {'name': template_name}}
        template_list = registry.template_lists_metadata(
            req.context, **template_params)
        if template_list:
            template_cluster = template_list[0]
        else:
            msg = "the template %s is not exist" % template_name
            LOG.error(msg)
            raise HTTPForbidden(
                explanation=msg,
                request=req,
                content_type="text/plain")

        try:
            template_content = json.loads(template_cluster['content'])
            template_content_cluster = template_content['cluster']
            template_content_cluster['name'] = cluster_name
            template_content_cluster['logic_networks'] = \
                template_content_cluster[
                'logic_networks'].replace("\'true\'", "True")

            if template_cluster['hosts']:
                template_hosts = json.loads(template_cluster['hosts'])
                template_host_params = {'cluster_name': cluster_name}
                template_host_list = registry.host_template_lists_metadata(
                    req.context, **template_host_params)
                if template_host_list:
                    update_template_meta = {
                        "cluster_name": cluster_name,
                        "hosts": json.dumps(template_hosts)}
                    registry.update_host_template_metadata(
                        req.context, template_host_list[0]['id'],
                        update_template_meta)
                else:
                    template_meta = {
                        "cluster_name": cluster_name,
                        "hosts": json.dumps(template_hosts)}
                    registry.add_host_template_metadata(
                        req.context, template_meta)

            cluster_params = {'filters': {'name': cluster_name}}
            clusters = registry.get_clusters_detail(
                req.context, **cluster_params)
            if clusters:
                msg = "the cluster %s is exist" % clusters[0]['name']
                LOG.error(msg)
                raise HTTPForbidden(
                    explanation=msg,
                    request=req,
                    content_type="text/plain")
            else:
                if template_content_cluster.get('auto_scale', None) == 1:
                    params = {'filters': ''}
                    clusters_list = registry.get_clusters_detail(
                        req.context, **params)
                    for cluster in clusters_list:
                        if cluster.get('auto_scale', None) == 1:
                            template_content_cluster['auto_scale'] = 0
                            break

                if template_cluster.get('type') in utils.SUPPORT_BACKENDS:
                    template_content['cluster'].setdefault(
                        'target_systems', 'os+%s' % template_cluster['type'])
                else:
                    msg = 'type in template: "%s" not support' % \
                          template_cluster
                    LOG.error(msg)
                    raise HTTPBadRequest(explanation=msg, request=req)

                cluster_meta = registry.add_cluster_metadata(
                    req.context, template_content['cluster'])
                cluster_id = cluster_meta['id']

            params = {'filters': {}}
            networks = registry.get_networks_detail(
                req.context, cluster_id, **params)
            template_content_networks = template_content['networks']
            for template_content_network in template_content_networks:
                network_exist = 'false'
                for network in networks:
                    if template_content_network['name'] == network['name']:
                        update_network_meta = registry.update_network_metadata(
                            req.context, network['id'],
                            template_content_network)
                        network_exist = 'true'

                if network_exist == 'false':
                    template_content_network['cluster_id'] = cluster_id
                    add_network_meta = registry.add_network_metadata(
                        req.context, template_content_network)

            params = {'filters': {'cluster_id': cluster_id}}
            roles = registry.get_roles_detail(req.context, **params)
            template_content_roles = template_content['roles']
            for template_content_role in template_content_roles:
                role_exist = 'false'
                del template_content_role['config_set_id']
                for role in roles:
                    if template_content_role['name'] == role['name']:
                        update_role_meta = registry.update_role_metadata(
                            req.context, role['id'], template_content_role)
                        role_exist = 'true'

                if role_exist == 'false':
                    template_content_role['cluster_id'] = cluster_id
                    registry.add_role_metadata(
                        req.context, template_content_role)

            self._import_cinder_volumes_to_db(
                req, template_content['cinder_volumes'], roles)
            if 'neutron_backends' in template_content:
                self._import_neutron_backends_to_db(
                    req, template_content['neutron_backends'], roles)
            if 'optical_switchs' in template_content:
                self._import_optical_switchs_to_db(
                    req, template_content['optical_switchs'], roles)
            self._import_services_disk_to_db(req,
                                             template_content['services_disk'],
                                             roles)

            # add extension content for cluster_template
            path = os.path.join(os.path.abspath(os.path.dirname(
                os.path.realpath(__file__))), 'ext')
            for root, dirs, names in os.walk(path):
                filename = 'router.py'
                if filename in names:
                    ext_name = root.split(path)[1].strip('/')
                    ext_func = "%s.api.hosts" % ext_name
                    extension = importutils.import_module(
                        'daisy.api.v1.ext.%s' % ext_func)
                    if 'import_template_to_db_ext' in dir(extension):
                        extension.import_template_to_db_ext(req, cluster_id)

        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return {"template": cluster_meta}

    @utils.mutating
    def get_template_detail(self, req, template_id):
        """
        delete a existing cluster template with the registry.
        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifie
        :retval Returns the updated image information as a mapping
        """
        self._enforce(req, 'get_template_detail')
        try:
            template = registry.template_detail_metadata(
                req.context, template_id)
            if template.get("tecs_version_id", None):
                template['tecs_version_id'] = ""
            obj = subprocess.Popen("which daisy-manage >/dev/null "
                                   "&& daisy-manage db_version",
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            (stdoutput, erroutput) = obj.communicate()
            if stdoutput:
                template['version'] = stdoutput.strip('\n')
            return {'template': template}
        except exception.NotFound as e:
            msg = (_("Failed to find template: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to get template: %s") %
                   utils.exception_to_str(e))
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("template %(id)s could not be get because it is in use: "
                     "%(exc)s") % {"id": template_id,
                                   "exc": utils.exception_to_str(e)})
            LOG.error(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            return Response(body='', status=200)

    @utils.mutating
    def get_template_lists(self, req):
        self._enforce(req, 'get_template_lists')
        params = self._get_query_params(req)
        try:
            template_lists = registry.template_lists_metadata(
                req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(template=template_lists)


class TemplateDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["template"] = utils.get_template_meta(request)
        return result

    def add_template(self, request):
        return self._deserialize(request)

    def update_template(self, request):
        return self._deserialize(request)

    def export_db_to_json(self, request):
        return self._deserialize(request)

    def import_json_to_template(self, request):
        return self._deserialize(request)

    def import_template_to_db(self, request):
        return self._deserialize(request)


class TemplateSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_template(self, response, result):
        template = result['template']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(template=template))
        return response

    def delete_template(self, response, result):
        template = result['template']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(template=template))
        return response

    def get_template_detail(self, response, result):
        template = result['template']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(template=template))
        return response

    def update_template(self, response, result):
        template = result['template']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(template=template))
        return response

    def export_db_to_json(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def import_json_to_template(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def import_template_to_db(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response


def create_resource():
    """Templates resource factory method"""
    deserializer = TemplateDeserializer()
    serializer = TemplateSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
