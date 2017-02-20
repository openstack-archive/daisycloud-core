# Copyright 2011 OpenStack Foundation
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

from oslo_log import log as logging
import webob.exc

from daisy.common import exception
from daisy import i18n
import daisy.registry.client.v1.api as registry


LOG = logging.getLogger(__name__)
_ = i18n._


class BaseController(object):

    def get_image_meta_or_404(self, request, image_id):
        """
        Grabs the image metadata for an image with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param image_id: The opaque image identifier

        :raises HTTPNotFound if image does not exist
        """
        context = request.context
        try:
            return registry.get_image_metadata(context, image_id)
        except exception.NotFound:
            msg = "Image with identifier %s not found" % image_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden image access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_host_meta_or_404(self, request, host_id):
        """
        Grabs the host metadata for an host with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param host_id: The opaque host identifier

        :raises HTTPNotFound if host does not exist
        """
        context = request.context
        try:
            return registry.get_host_metadata(context, host_id)
        except exception.NotFound:
            msg = "Host with identifier %s not found" % host_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden host access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_cluster_meta_or_404(self, request, cluster_id):
        """
        Grabs the cluster metadata for an cluster with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param cluster_id: The opaque cluster identifier

        :raises HTTPNotFound if cluster does not exist
        """
        context = request.context
        try:
            return registry.get_cluster_metadata(context, cluster_id)
        except exception.NotFound:
            msg = "Cluster with identifier %s not found" % cluster_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden host access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_component_meta_or_404(self, request, component_id):
        """
        Grabs the component metadata for an component with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param component_id: The opaque component identifier

        :raises HTTPNotFound if component does not exist
        """
        context = request.context
        try:
            return registry.get_component_metadata(context, component_id)
        except exception.NotFound:
            msg = "Component with identifier %s not found" % component_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden host access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_service_meta_or_404(self, request, service_id):
        """
        Grabs the service metadata for an service with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param service_id: The opaque service identifier

        :raises HTTPNotFound if service does not exist
        """
        context = request.context
        try:
            return registry.get_service_metadata(context, service_id)
        except exception.NotFound:
            msg = "Service with identifier %s not found" % service_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden host access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_role_meta_or_404(self, request, role_id):
        """
        Grabs the role metadata for an role with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param role_id: The opaque role identifier

        :raises HTTPNotFound if role does not exist
        """
        context = request.context
        try:
            return registry.get_role_metadata(context, role_id)
        except exception.NotFound:
            msg = "Role with identifier %s not found" % role_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden host access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_network_meta_or_404(self, request, network_id):
        """
        Grabs the network metadata for an network with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param network_id: The opaque network identifier

        :raises HTTPNotFound if network does not exist
        """
        context = request.context
        try:
            return registry.get_network_metadata(context, network_id)
        except exception.NotFound:
            msg = "Network with identifier %s not found" % network_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden network access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_active_image_meta_or_error(self, request, image_id):
        """
        Same as get_image_meta_or_404 except that it will raise a 403 if the
        image is deactivated or 404 if the image is otherwise not 'active'.
        """
        image = self.get_image_meta_or_404(request, image_id)
        if image['status'] == 'deactivated':
            msg = "Image %s is deactivated" % image_id
            LOG.debug(msg)
            msg = _("Image %s is deactivated") % image_id
            raise webob.exc.HTTPForbidden(
                msg, request=request, content_type='type/plain')
        if image['status'] != 'active':
            msg = "Image %s is not active" % image_id
            LOG.debug(msg)
            msg = _("Image %s is not active") % image_id
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        return image

    def update_store_acls(self, req, image_id, location_uri, public=False):
        if location_uri:
            try:
                read_tenants = []
                write_tenants = []
                members = registry.get_image_members(req.context, image_id)
                if members:
                    for member in members:
                        if member['can_share']:
                            write_tenants.append(member['member_id'])
                        else:
                            read_tenants.append(member['member_id'])
                store.set_acls(location_uri, public=public,
                               read_tenants=read_tenants,
                               write_tenants=write_tenants,
                               context=req.context)
            except store.UnknownScheme:
                msg = _("Store for image_id not found: %s") % image_id
                raise webob.exc.HTTPBadRequest(explanation=msg,
                                               request=req,
                                               content_type='text/plain')

    def get_config_file_meta_or_404(self, request, config_file_id):
        """
        Grabs the config_file metadata for an config_file with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param host_id: The opaque config_file identifier

        :raises HTTPNotFound if config_file does not exist
        """
        context = request.context
        try:
            return registry.get_config_file_metadata(context, config_file_id)
        except exception.NotFound:
            msg = "config_file with identifier %s not found" % config_file_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden config_filke access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_config_set_meta_or_404(self, request, config_set_id):
        """
        Grabs the config_set metadata for an config_set with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param host_id: The opaque config_set identifier

        :raises HTTPNotFound if config_set does not exist
        """
        context = request.context
        try:
            return registry.get_config_set_metadata(context, config_set_id)
        except exception.NotFound:
            msg = "config_set with identifier %s not found" % config_set_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden config_set access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_config_meta_or_404(self, request, config_id):
        """
        Grabs the config metadata for an config with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param host_id: The opaque config identifier

        :raises HTTPNotFound if config does not exist
        """
        context = request.context
        try:
            return registry.get_config_metadata(context, config_id)
        except exception.NotFound:
            msg = "config with identifier %s not found" % config_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden config access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_service_disk_meta_or_404(self, request, id):
        """
        Grabs the config metadata for an config with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param host_id: The opaque config identifier

        :raises HTTPNotFound if config does not exist
        """
        context = request.context
        try:
            return registry.get_service_disk_detail_metadata(context, id)
        except exception.NotFound:
            msg = "service_disk with identifier %s not found" % id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden config access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_neutron_backend_meta_or_404(self, request, id):
        """
        Grabs the config metadata for an config with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param host_id: The opaque config identifier

        :raises HTTPNotFound if config does not exist
        """
        context = request.context
        try:
            return registry.get_neutron_backend_metadata(context, id)
        except exception.NotFound:
            msg = "neutron_backend with identifier %s not found" % id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden config access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_cinder_volume_meta_or_404(self, request, id):
        """
        Grabs the config metadata for an config with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param host_id: The opaque config identifier

        :raises HTTPNotFound if config does not exist
        """
        context = request.context
        try:
            return registry.get_cinder_volume_detail_metadata(context, id)
        except exception.NotFound:
            msg = "cinder_volume with identifier %s not found" % id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden config access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_optical_switch_meta_or_404(self, request, id):
        """
        Grabs the config metadata for an config with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param host_id: The opaque config identifier

        :raises HTTPNotFound if config does not exist
        """
        context = request.context
        try:
            return registry.get_optical_switch_detail_metadata(context, id)
        except exception.NotFound:
            msg = "config with identifier %s not found" % id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden config access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_version_meta_or_404(self, request, id):
        """
        Grabs the version metadata for an version with a supplied
        identifier or raises an HTTPNotFound (404) response
        """
        context = request.context
        try:
            return registry.get_version_metadata(context, id)
        except exception.NotFound:
            msg = "version with identifier %s not found" % id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden version access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_version_patch_meta_or_404(self, request, id):
        """
        Grabs the version patch metadata for an version patch with a supplied
        identifier or raises an HTTPNotFound (404) response
        """
        context = request.context
        try:
            return registry.get_version_patch_metadata(context, id)
        except exception.NotFound:
            msg = "version patch patch with identifier %s not found" % id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden version patch access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_template_func_meta_or_404(self, request, template_func_id,
                                      **params):
        """
        Grabs the template_func metadata for an template_func with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param host_id: The opaque template_func identifier

        :raises HTTPNotFound if template_func does not exist
        """
        context = request.context
        try:
            return registry.get_template_func_metadata(context,
                                                       template_func_id,
                                                       **params)
        except exception.NotFound:
            msg = "template_func with identifier %s not found" % \
                  template_func_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden template_func access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_template_config_meta_or_404(self, request, template_config_id):
        """
        Grabs the template_config metadata for an
        template_config with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param host_id: The opaque template_config identifier

        :raises HTTPNotFound if template_config does not exist
        """
        context = request.context
        try:
            return registry.get_template_config_metadata(context,
                                                         template_config_id)
        except exception.NotFound:
            msg = "template_config with " \
                  "identifier %s not found" % template_config_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden template_config access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def get_template_service_meta_or_404(self, request, template_service_id):
        """
        Grabs the template_service metadata for
        an template_service with a supplied
        identifier or raises an HTTPNotFound (404) response

        :param request: The WSGI/Webob Request object
        :param host_id: The opaque template_service identifier

        :raises HTTPNotFound if template_service does not exist
        """
        context = request.context
        try:
            return registry.get_template_service_metadata(context,
                                                          template_service_id)
        except exception.NotFound:
            msg = "template_service with"\
                  " identifier %s not found" % template_service_id
            LOG.debug(msg)
            raise webob.exc.HTTPNotFound(
                msg, request=request, content_type='text/plain')
        except exception.Forbidden:
            msg = "Forbidden template_service access"
            LOG.debug(msg)
            raise webob.exc.HTTPForbidden(msg,
                                          request=request,
                                          content_type='text/plain')

    def _raise_404_if_cluster_deleted(self, req, cluster_id):
        cluster = self.get_cluster_meta_or_404(req, cluster_id)
        if cluster['deleted']:
            msg = _("Cluster with identifier %s has been deleted.") % \
                cluster_id
            raise webob.exc.HTTPNotFound(msg)
