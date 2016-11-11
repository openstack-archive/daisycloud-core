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
/roles endpoint for Daisy v1 API
"""

from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPConflict
from webob.exc import HTTPForbidden
from webob.exc import HTTPNotFound
from webob import Response

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
SUPPORTED_DEPLOYMENT_BACKENDS = ('tecs', 'zenic', 'proton', 'kolla')
SUPPORTED_ROLE = (
    'CONTROLLER_LB',
    'CONTROLLER_HA',
    'COMPUTER',
    'ZENIC_CTL',
    'ZENIC_NFM',
    'ZENIC_MDB',
    'PROTON',
    'CHILD_CELL_1_COMPUTER',
    'CONTROLLER_CHILD_CELL_1')
SUPPORT_DISK_LOCATION = ('local', 'share')

CONF = cfg.CONF
CONF.import_opt('disk_formats', 'daisy.common.config', group='image_format')
CONF.import_opt('container_formats', 'daisy.common.config',
                group='image_format')
CONF.import_opt('image_property_quota', 'daisy.common.config')


class Controller(controller.BaseController):
    """
    WSGI controller for roles resource in Daisy v1 API

    The roles resource API is a RESTful web role for role data. The API
    is as follows::

        GET  /roles -- Returns a set of brief metadata about roles
        GET  /roles/detail -- Returns a set of detailed metadata about
                              roles
        HEAD /roles/<ID> -- Return metadata about an role with id <ID>
        GET  /roles/<ID> -- Return role data for role with id <ID>
        POST /roles -- Store role data and return metadata about the
                        newly-stored role
        PUT  /roles/<ID> -- Update role metadata and/or upload role
                            data for a previously-reserved role
        DELETE /roles/<ID> -- Delete the role with id <ID>
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

    def _raise_404_if_host_deleted(self, req, host_id):
        host = self.get_host_meta_or_404(req, host_id)
        if host['deleted']:
            msg = _("Node with identifier %s has been deleted.") % host_id
            raise HTTPNotFound(msg)

    def _raise_404_if_service_deleted(self, req, service_id):
        service = self.get_service_meta_or_404(req, service_id)
        if service['deleted']:
            msg = _("Service with identifier %s has been deleted.") % \
                service_id
            raise HTTPNotFound(msg)

    def _raise_404_if_config_set_deleted(self, req, config_set_id):
        config_set = self.get_config_set_meta_or_404(req, config_set_id)
        if config_set['deleted']:
            msg = _("Config_Set with identifier %s has been deleted.") % \
                config_set_id
            raise HTTPNotFound(msg)

    def _raise_404_if_cluster_deleted(self, req, cluster_id):
        cluster = self.get_cluster_meta_or_404(req, cluster_id)
        if cluster['deleted']:
            msg = _("cluster with identifier %s has been deleted.") % \
                cluster_id
            raise HTTPNotFound(msg)

    def _get_service_name_list(self, req, role_service_id_list):
        service_name_list = []
        for service_id in role_service_id_list:
            service_meta = registry.get_service_metadata(
                req.context, service_id)
            service_name_list.append(service_meta['name'])
        return service_name_list

    def _get_host_disk_except_os_disk_by_info(self, host_info):
        '''
        type(host_info): <type 'dict'>
        host_disk_except_os_disk_lists: disk_size , type = int
        '''
        # import pdb;pdb.set_trace()
        host_disk_except_os_disk_lists = 0
        os_disk_m = host_info.get('root_lv_size', 102400)
        swap_size_m = host_info.get('swap_lv_size', None)
        if swap_size_m:
            swap_size_m = (swap_size_m / 4) * 4
        else:
            swap_size_m = 0
        boot_partition_m = 400
        redundant_partiton_m = 600
        if not os_disk_m:
            os_disk_m = 102400
        # host_disk = 1024
        host_disks = host_info.get('disks', None)
        host_disk_size_m = 0
        if host_disks:
            for key, value in host_disks.items():
                if value['disk'].find("-fc-") != -1 \
                        or value['disk'].find("-iscsi-") != -1 \
                        or value['name'].find("mpath") != -1 \
                        or value['name'].find("spath") != -1 \
                        or value['removable'] == 'removable':
                    continue
                disk_size_b = str(value.get('size', None))
                disk_size_b_str = disk_size_b.strip().split()[0]
                if disk_size_b_str:
                    disk_size_b_int = int(disk_size_b_str)
                    disk_size_m = disk_size_b_int // (1024 * 1024)
                    host_disk_size_m = host_disk_size_m + disk_size_m
            host_disk_except_os_disk_lists = host_disk_size_m - os_disk_m - \
                swap_size_m - boot_partition_m - redundant_partiton_m
        LOG.warn(
            '----start----host_disk_except_os_disk_lists: %s -----end--' %
            host_disk_except_os_disk_lists)
        return host_disk_except_os_disk_lists

    def _check_host_validity(self, **paras):
        '''
        paras['db_lv_size'], paras['glance_lv_size'] , paras['disk_size']
        '''
        disk_size = paras.get('disk_size', None)
        LOG.warn('--------disk_size:----- %s' % disk_size)
        if disk_size:
            disk_size_m = int(disk_size)
        else:
            disk_size_m = 0
        if disk_size_m == 0:  # Host hard disk size was 0,
            # think that the host does not need to install the system
            return  # Don't need to ckeck the validity of hard disk size

        db_lv_size_m = paras.get('db_lv_size', 300)
        if db_lv_size_m:
            db_lv_size_m = int(db_lv_size_m)
        else:
            db_lv_size_m = 0

        glance_lv_size_m = paras.get('glance_lv_size', 17100)
        if glance_lv_size_m:
            glance_lv_size_m = int(glance_lv_size_m)
        else:
            glance_lv_size_m = 0

        nova_lv_size_m = paras.get('nova_lv_size', 0)
        if nova_lv_size_m:
            nova_lv_size_m = int(nova_lv_size_m)
        else:
            nova_lv_size_m = 0
        if nova_lv_size_m == -1:
            nova_lv_size_m = 0
        glance_lv_size_m = (glance_lv_size_m / 4) * 4
        db_lv_size_m = (db_lv_size_m / 4) * 4
        nova_lv_size_m = (nova_lv_size_m / 4) * 4
        if glance_lv_size_m + db_lv_size_m + nova_lv_size_m > disk_size_m:
            msg = _("There isn't enough disk space to specify database or "
                    "glance or nova disk, please specify database or "
                    "glance or nova disk size again")
            LOG.debug(msg)
            raise HTTPForbidden(msg)

    def _check_nodes_exist(self, req, nodes):
        for role_host_id in nodes:
            self._raise_404_if_host_deleted(req, role_host_id)

    def _check_services_exist(self, req, services):
        for role_service_id in services:
            self._raise_404_if_service_deleted(req, role_service_id)

    def _check_config_set_id_exist(self, req, config_set_id):
        self._raise_404_if_config_set_deleted(req, config_set_id)

    def _check_glance_lv_value(
            self,
            req,
            glance_lv_value,
            role_name,
            service_name_list):
        if int(glance_lv_value) < 0 and int(glance_lv_value) != -1:
            msg = _("glance_lv_size can't be negative except -1.")
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        if not service_name_list or 'glance' not in service_name_list:
            msg = _("service 'glance' is not in role %s, so can't "
                    "set the size of glance lv.") % role_name
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")

    def _check_db_lv_size(self, req, db_lv_size, service_name_list):
        if int(db_lv_size) < 0 and int(db_lv_size) != -1:
            msg = _("The size of database disk can't be negative except -1.")
            LOG.debug(msg)
            raise HTTPForbidden(msg)
            # Only the role with database service can be formulated the size of
            # a database.
        if 'mariadb' not in service_name_list and 'mongodb' not in \
                service_name_list:
            msg = _('The role without database service is unable '
                    'to specify the size of the database!')
            LOG.debug(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")

    def _check_nova_lv_size(self, req, nova_lv_size, role_name):
        if role_name != "COMPUTER":
            msg = _("The role is not COMPUTER, it can't set logic "
                    "volume disk for nova.")
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        try:
            if int(nova_lv_size) < 0 and int(nova_lv_size) != -1:
                msg = _("The nova_lv_size must be -1 or [0, N).")
                raise HTTPForbidden(explanation=msg,
                                    request=req,
                                    content_type="text/plain")
        except:
            msg = _("The nova_lv_size must be -1 or [0, N).")
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")

    def _check_all_lv_size(self, req, db_lv_size, glance_lv_size, nova_lv_size,
                           host_id_list, cluster_id, argws):
        if db_lv_size or glance_lv_size or nova_lv_size:
            for host_id in host_id_list:
                host_disk_db_glance_nova_size = \
                    self.get_host_disk_db_glance_nova_size(
                        req, host_id, cluster_id)
                if host_disk_db_glance_nova_size['db_lv_size'] and \
                        db_lv_size and int(
                        db_lv_size) < int(host_disk_db_glance_nova_size[
                        'db_lv_size']):
                    argws['db_lv_size'] = host_disk_db_glance_nova_size[
                        'db_lv_size']
                else:
                    argws['db_lv_size'] = db_lv_size
                if host_disk_db_glance_nova_size['glance_lv_size'] and \
                        glance_lv_size and int(
                        glance_lv_size) < int(host_disk_db_glance_nova_size[
                        'glance_lv_size']):
                    argws['glance_lv_size'] = host_disk_db_glance_nova_size[
                        'glance_lv_size']
                else:
                    argws['glance_lv_size'] = glance_lv_size
                if host_disk_db_glance_nova_size['nova_lv_size'] and \
                        nova_lv_size and int(
                        nova_lv_size) < int(host_disk_db_glance_nova_size[
                        'nova_lv_size']):
                    argws['nova_lv_size'] = host_disk_db_glance_nova_size[
                        'nova_lv_size']
                else:
                    argws['nova_lv_size'] = nova_lv_size
                argws['disk_size'] = host_disk_db_glance_nova_size['disk_size']
                LOG.warn(
                    '--------host(%s) check_host_validity argws:----- %s' %
                    (host_id, argws))
                self._check_host_validity(**argws)

    def _check_deployment_backend(self, req, deployment_backend):
        if deployment_backend not in SUPPORTED_DEPLOYMENT_BACKENDS:
            msg = "deployment backend '%s' is not supported." % \
                  deployment_backend
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")

    def _check_role_type_in_update_role(self, req, role_type, orig_role_meta):
        if orig_role_meta['type'].lower() != role_type.lower():
            msg = _("Role type can not be updated to other type.")
            LOG.debug(msg)
            raise HTTPForbidden(msg)

    def _check_cluster_id_in_role_update(
            self, req, role_cluster, orig_role_meta):
        if orig_role_meta['type'].lower() == 'template':
            msg = _("The template role does not belong to any cluster.")
            LOG.debug(msg)
            raise HTTPForbidden(msg)
        orig_role_cluster = orig_role_meta['cluster_id']
        if orig_role_cluster != role_cluster:  # Can not change the cluster
            # which the role belongs to
            msg = _("Can't update the cluster of the role.")
            LOG.debug(msg)
            raise HTTPForbidden(msg)
        else:
            self._raise_404_if_cluster_deleted(req, role_cluster)

    def _check_role_name_in_role_update(self, req, role_meta, orig_role_meta):
        role_name = role_meta['name']
        cluster_id = role_meta.get('cluster_id', orig_role_meta['cluster_id'])
        if cluster_id:
            self.check_cluster_role_name_repetition(req, role_name, cluster_id)
        else:  # role type was template, cluster id was None
            self.check_template_role_name_repetition(req, role_name)

    def _check_all_lv_size_of_nodes_with_role_in_role_update(
            self, req, role_meta, orig_role_meta, role_host_id_list):
        # check host with this role at the same time
        cluster_id = role_meta.get('cluster_id', None)
        if not cluster_id:  # role with cluster
            cluster_id = orig_role_meta['cluster_id']
        if not cluster_id:  # without cluster id, raise Error
            msg = _("The cluster_id parameter can not be None!")
            LOG.debug(msg)
            raise HTTPForbidden(msg)
        argws = dict()
        if 'db_lv_size' in role_meta:
            db_lv_size = role_meta['db_lv_size']
        else:  # The db_lv_size has been specified before.
            db_lv_size = orig_role_meta.get('db_lv_size')
        if 'glance_lv_size' in role_meta:
            glance_lv_size = role_meta['glance_lv_size']
        else:
            glance_lv_size = orig_role_meta.get('glance_lv_size')
        if 'nova_lv_size' in role_meta:
            nova_lv_size = role_meta['nova_lv_size']
        else:
            nova_lv_size = orig_role_meta.get('nova_lv_size')
        if 'nodes' in role_meta:
            host_id_list = list(eval(role_meta['nodes'])) + role_host_id_list
        else:
            host_id_list = role_host_id_list
        self._check_all_lv_size(req, db_lv_size, glance_lv_size,
                                nova_lv_size, host_id_list, cluster_id, argws)

    def _check_ntp_server(self, req, role_name):
        if role_name != 'CONTROLLER_HA':
            msg = 'The role %s need no ntp_server' % role_name
            raise HTTPForbidden(explanation=msg)

    def _check_role_type_in_role_add(self, req, role_meta):
        # role_type == None or not template, cluster id must not be None
        role_type = role_meta['type']
        if role_type.lower() != 'template':
            role_cluster_id = role_meta.get('cluster_id', None)
            if not role_cluster_id:  # add role without cluster id parameter,
                # raise error
                msg = _(
                    "The cluster_id parameter can not be None "
                    "if role was not a template type.")
                LOG.debug(msg)
                raise HTTPForbidden(msg)
        else:  # role_type == template, cluster id is not necessary
            if 'cluster_id' in role_meta:
                msg = _("Tht template role cannot be added to any cluster.")
                LOG.debug(msg)
                raise HTTPForbidden(msg)

    def _check_all_lv_size_with_role_in_role_add(self, req, role_meta):
        cluster_id = role_meta.get('cluster_id', None)
        if not cluster_id:  # without cluster id, raise Error
            msg = _("The cluster_id parameter can not be None!")
            LOG.debug(msg)
            raise HTTPForbidden(msg)
        argws = dict()
        db_lv_size = role_meta.get('db_lv_size', 0)
        glance_lv_size = role_meta.get('glance_lv_size', 0)
        nova_lv_size = role_meta.get('nova_lv_size', 0)
        host_id_list = list(eval(role_meta['nodes']))
        self._check_all_lv_size(req, db_lv_size, glance_lv_size,
                                nova_lv_size, host_id_list, cluster_id, argws)

    def get_host_disk_db_glance_nova_size(self, req, host_id, cluster_id):
        '''
            return :
                host_disk_db_glance_nova_size['disk_size'] = 1024000
                host_disk_db_glance_nova_size['db_lv_size'] = 1011
                host_disk_db_glance_nova_size['glance_lv_size'] = 1011
                host_disk_db_glance_nova_size['nova_lv_size'] = 1011
        '''
        # import pdb;pdb.set_trace()
        host_disk_db_glance_nova_size = dict()
        db_lv_size = list()
        glance_lv_size = list()
        nova_lv_size = list()
        # disk_size = list()

        host_info = self.get_host_meta_or_404(req, host_id)
        if host_info:
            if 'deleted' in host_info and host_info['deleted']:
                msg = _("Node with identifier %s has been deleted.") % \
                    host_info[
                    'id']
                LOG.debug(msg)
                raise HTTPNotFound(msg)
            # get host disk infomation
            host_disk = self._get_host_disk_except_os_disk_by_info(host_info)
            host_disk_db_glance_nova_size['disk_size'] = host_disk
            # get role_host db/galnce/nova infomation
            cluster_info = self.get_cluster_meta_or_404(req, cluster_id)
            if 'cluster' in host_info:  # host with cluster
                if host_info['cluster'] != cluster_info['name']:
                    # type(host_info['cluster']) = list,
                    # type(cluster_info['name']) = str
                    msg = _("Role and hosts belong to different cluster.")
                    LOG.debug(msg)
                    raise HTTPNotFound(msg)
                else:
                    all_roles = registry.get_roles_detail(req.context)
                    cluster_roles = [
                        role for role in all_roles if role['cluster_id'] ==
                        cluster_id]
                    # roles infomation saved in cluster_roles
                    if 'role' in host_info and host_info[
                            'role']:  # host with role
                        for role in cluster_roles:
                            if role['name'] in host_info[
                                    'role'] and cluster_roles:
                                db_lv_size.append(role.get('db_lv_size', None))
                                glance_lv_size.append(
                                    role.get('glance_lv_size', None))
                                nova_lv_size.append(
                                    role.get('nova_lv_size', None))

        if db_lv_size:
            host_disk_db_glance_nova_size['db_lv_size'] = max(db_lv_size)
        else:  # host without cluster
            host_disk_db_glance_nova_size['db_lv_size'] = 0
        if glance_lv_size:
            host_disk_db_glance_nova_size[
                'glance_lv_size'] = max(glance_lv_size)
        else:
            host_disk_db_glance_nova_size['glance_lv_size'] = 0
        if nova_lv_size:
            host_disk_db_glance_nova_size['nova_lv_size'] = max(nova_lv_size)
        else:
            host_disk_db_glance_nova_size['nova_lv_size'] = 0
        LOG.warn('--------host(%s)disk_db_glance_nova_size:----- %s' %
                 (host_id, host_disk_db_glance_nova_size))
        return host_disk_db_glance_nova_size

    def check_cluster_role_name_repetition(self, req, role_name, cluster_id):
        all_roles = registry.get_roles_detail(req.context)
        cluster_roles = [role for role in all_roles if role[
            'cluster_id'] == cluster_id]
        cluster_roles_name = [role['name'].lower() for role in cluster_roles]
        if role_name.lower() in cluster_roles_name:
            msg = _(
                "The role %s has already been in the cluster %s!" %
                (role_name, cluster_id))
            LOG.debug(msg)
            raise HTTPForbidden(msg)

    def check_template_role_name_repetition(self, req, role_name):
        all_roles = registry.get_roles_detail(req.context)
        template_roles = [
            role for role in all_roles if role['cluster_id'] is None]
        template_roles_name = [role['name'].lower() for role in template_roles]
        if role_name.lower() in template_roles_name:
            msg = _(
                "The role %s has already been in the the template role." %
                role_name)
            LOG.debug(msg)
            raise HTTPForbidden(msg)

    def _check_disk_parameters(self, req, role_meta):
        if ('disk_location' in role_meta and
                role_meta['disk_location'] not in SUPPORT_DISK_LOCATION):
            msg = _("value of disk_location is not supported.")
            raise HTTPForbidden(msg)

    def _check_type_role_reasonable(self, req, role_meta):
        if role_meta['role_type'] not in SUPPORTED_ROLE:
            msg = 'The role type %s is illegal' % role_meta['role_type']
            raise HTTPForbidden(explanation=msg)

    def _check_role_update_parameters(self, req, role_meta, orig_role_meta,
                                      role_service_id_list, role_host_id_list):
        role_name = orig_role_meta['name']
        if role_meta.get('type', None):
            self._check_role_type_in_update_role(
                req, role_meta['type'], orig_role_meta)
        if 'ntp_server' in role_meta:
            self._check_ntp_server(req, role_name)
        if 'nodes' in role_meta:
            self._check_nodes_exist(req, list(eval(role_meta['nodes'])))
        if 'services' in role_meta:
            self._check_services_exist(req, list(eval(role_meta['services'])))
            role_service_id_list.extend(list(eval(role_meta['services'])))
        if 'config_set_id' in role_meta:
            self._check_config_set_id_exist(
                req, str(role_meta['config_set_id']))
        if 'cluster_id' in role_meta:
            self._check_cluster_id_in_role_update(
                req, str(role_meta['cluster_id']), orig_role_meta)
        if 'name' in role_meta:
            self._check_role_name_in_role_update(
                req, role_meta, orig_role_meta)
        service_name_list = self._get_service_name_list(
            req, role_service_id_list)
        glance_lv_value = role_meta.get(
            'glance_lv_size', orig_role_meta['glance_lv_size'])
        if glance_lv_value:
            self._check_glance_lv_value(
                req, glance_lv_value, role_name, service_name_list)
        if role_meta.get('db_lv_size', None) and role_meta['db_lv_size']:
            self._check_db_lv_size(
                req, role_meta['db_lv_size'], service_name_list)
        if role_meta.get('nova_lv_size', None):
            self._check_nova_lv_size(req, role_meta['nova_lv_size'], role_name)
        if 'nodes' in role_meta or role_host_id_list:
            self._check_all_lv_size_of_nodes_with_role_in_role_update(
                req, role_meta, orig_role_meta, role_host_id_list)
        self._check_disk_parameters(req, role_meta)
        if 'deployment_backend' in role_meta:
            self._check_deployment_backend(
                req, role_meta['deployment_backend'])
        if role_meta.get('role_type', None):
            self._check_type_role_reasonable(req, role_meta)

    def _check_role_add_parameters(self, req, role_meta, role_service_id_list):
        role_name = role_meta.get('name', None)
        if role_meta.get('type', None):
            self._check_role_type_in_role_add(req, role_meta)
        if 'nodes' in role_meta:
            self._check_nodes_exist(req, list(eval(role_meta['nodes'])))
        if 'services' in role_meta:
            self._check_services_exist(req, list(eval(role_meta['services'])))
            role_service_id_list.extend(list(eval(role_meta['services'])))
        if 'config_set_id' in role_meta:
            self._check_config_set_id_exist(
                req, str(role_meta['config_set_id']))
        if 'cluster_id' in role_meta:
            orig_cluster = str(role_meta['cluster_id'])
            self._raise_404_if_cluster_deleted(req, orig_cluster)
            self.check_cluster_role_name_repetition(
                req, role_name, orig_cluster)
        else:
            self.check_template_role_name_repetition(req, role_name)
        service_name_list = self._get_service_name_list(
            req, role_service_id_list)
        glance_lv_value = role_meta.get('glance_lv_size', None)
        if glance_lv_value:
            self._check_glance_lv_value(
                req, glance_lv_value, role_name, service_name_list)
        if role_meta.get('db_lv_size', None) and role_meta['db_lv_size']:
            self._check_db_lv_size(
                req, role_meta['db_lv_size'], service_name_list)
        if role_meta.get('nova_lv_size', None):
            self._check_nova_lv_size(req, role_meta['nova_lv_size'], role_name)
        if 'nodes' in role_meta:
            self._check_all_lv_size_with_role_in_role_add(req, role_meta)
        self._check_disk_parameters(req, role_meta)
        if 'deployment_backend' in role_meta:
            self._check_deployment_backend(
                req, role_meta['deployment_backend'])
        else:
            role_meta['deployment_backend'] = 'tecs'
        if role_meta.get('role_type', None):
            self._check_type_role_reasonable(req, role_meta)

    @utils.mutating
    def add_role(self, req, role_meta):
        """
        Adds a new role to Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about role

        :raises HTTPBadRequest if x-role-name is missing
        """

        self._enforce(req, 'add_role')
        role_service_id_list = []
        self._check_role_add_parameters(req, role_meta, role_service_id_list)
        role_name = role_meta["name"]
        role_description = role_meta["description"]
        print role_name
        print role_description

        role_meta = registry.add_role_metadata(req.context, role_meta)

        return {'role_meta': role_meta}

    @utils.mutating
    def delete_role(self, req, id):
        """
        Deletes a role from Daisy.

        :param req: The WSGI/Webob Request object
        :param image_meta: Mapping of metadata about role

        :raises HTTPBadRequest if x-role-name is missing
        """
        self._enforce(req, 'delete_role')

        # role = self.get_role_meta_or_404(req, id)
        print "delete_role:%s" % id
        try:
            registry.delete_role_metadata(req.context, id)
        except exception.NotFound as e:
            msg = (_("Failed to find role to delete: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to delete role: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except exception.InUseByStore as e:
            msg = (_("role %(id)s could not be deleted because it is in use: "
                     "%(exc)s") % {"id": id, "exc": utils.exception_to_str(e)})
            LOG.warn(msg)
            raise HTTPConflict(explanation=msg,
                               request=req,
                               content_type="text/plain")
        else:
            # self.notifier.info('role.delete', role)
            return Response(body='', status=200)

    @utils.mutating
    def get_role(self, req, id):
        """
        Returns metadata about an role in the HTTP headers of the
        response object

        :param req: The WSGI/Webob Request object
        :param id: The opaque role identifier

        :raises HTTPNotFound if role metadata is not available to user
        """
        self._enforce(req, 'get_role')
        role_meta = self.get_role_meta_or_404(req, id)
        return {'role_meta': role_meta}

    def detail(self, req):
        """
        Returns detailed information for all available roles

        :param req: The WSGI/Webob Request object
        :retval The response body is a mapping of the following form::

            {'roles': [
                {'id': <ID>,
                 'name': <NAME>,
                 'description': <DESCRIPTION>,
                 'created_at': <TIMESTAMP>,
                 'updated_at': <TIMESTAMP>,
                 'deleted_at': <TIMESTAMP>|<NONE>,}, ...
            ]}
        """
        self._enforce(req, 'get_roles')
        params = self._get_query_params(req)
        filters = params.get('filters', None)
        if 'cluster_id' in filters:
            cluster_id = filters['cluster_id']
            self._raise_404_if_cluster_deleted(req, cluster_id)

        try:
            roles = registry.get_roles_detail(req.context, **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg, request=req)
        return dict(roles=roles)

    @utils.mutating
    def update_role(self, req, id, role_meta):
        """
        Updates an existing role with the registry.

        :param request: The WSGI/Webob Request object
        :param id: The opaque image identifier

        :retval Returns the updated image information as a mapping
        """
        orig_role_meta = self.get_role_meta_or_404(req, id)
        role_service_list = registry.get_role_services(req.context, id)
        role_service_id_list = [role_service['service_id']
                                for role_service in role_service_list]
        role_host_info_list = registry.get_role_host_metadata(req.context, id)
        role_host_id_list = [role_host['host_id']
                             for role_host in role_host_info_list]
        self._check_role_update_parameters(
            req,
            role_meta,
            orig_role_meta,
            role_service_id_list,
            role_host_id_list)

        if orig_role_meta['role_type'] == "CONTROLLER_HA":
            cluster_meta = {}
            cluster_meta['public_vip'] = role_meta.get(
                'public_vip') or role_meta.get('vip')
            if cluster_meta['public_vip']:
                cluster_meta = registry.update_cluster_metadata(
                    req.context, orig_role_meta['cluster_id'], cluster_meta)

        self._enforce(req, 'modify_image')
        # orig_role_meta = self.get_role_meta_or_404(req, id)

        # Do not allow any updates on a deleted image.
        # Fix for LP Bug #1060930
        if orig_role_meta['deleted']:
            msg = _("Forbidden to update deleted role.")
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        try:
            role_meta = registry.update_role_metadata(req.context,
                                                      id,
                                                      role_meta)

        except exception.Invalid as e:
            msg = (_("Failed to update role metadata. Got error: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPBadRequest(explanation=msg,
                                 request=req,
                                 content_type="text/plain")
        except exception.NotFound as e:
            msg = (_("Failed to find role to update: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPNotFound(explanation=msg,
                               request=req,
                               content_type="text/plain")
        except exception.Forbidden as e:
            msg = (_("Forbidden to update role: %s") %
                   utils.exception_to_str(e))
            LOG.warn(msg)
            raise HTTPForbidden(explanation=msg,
                                request=req,
                                content_type="text/plain")
        except (exception.Conflict, exception.Duplicate) as e:
            LOG.warn(utils.exception_to_str(e))
            raise HTTPConflict(body=_('Host operation conflicts'),
                               request=req,
                               content_type='text/plain')
        else:
            self.notifier.info('role.update', role_meta)

        return {'role_meta': role_meta}


class RoleDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result["role_meta"] = utils.get_role_meta(request)
        return result

    def add_role(self, request):
        return self._deserialize(request)

    def update_role(self, request):
        return self._deserialize(request)


class RoleSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def add_role(self, response, result):
        role_meta = result['role_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(role=role_meta))
        return response

    def delete_role(self, response, result):
        role_meta = result['role_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(role=role_meta))
        return response

    def get_role(self, response, result):
        role_meta = result['role_meta']
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(dict(role=role_meta))
        return response


def create_resource():
    """Roles resource factory method"""
    deserializer = RoleDeserializer()
    serializer = RoleSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
