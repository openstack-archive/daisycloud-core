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
Simple client class to speak with any RESTful service that implements
the Glance Registry API
"""

from oslo_serialization import jsonutils
from oslo_log import log as logging
from oslo_utils import excutils

from daisy.common import client
from daisy.common import crypt
from daisy import i18n
from daisy.registry.api.v1 import images
from daisy.registry.api.v1 import hosts
from daisy.registry.api.v1 import config_files
from daisy.registry.api.v1 import config_sets
from daisy.registry.api.v1 import configs
from daisy.registry.api.v1 import networks
from daisy.registry.api.v1 import template
from daisy.registry.api.v1 import hwms

LOG = logging.getLogger(__name__)
_LE = i18n._LE
_LI = i18n._LI


class RegistryClient(client.BaseClient):

    """A client for the Registry image metadata service."""

    DEFAULT_PORT = 19191

    def __init__(self, host=None, port=None, metadata_encryption_key=None,
                 identity_headers=None, **kwargs):
        """
        :param metadata_encryption_key: Key used to encrypt 'location' metadata
        """
        self.metadata_encryption_key = metadata_encryption_key
        # NOTE (dprince): by default base client overwrites host and port
        # settings when using keystone. configure_via_auth=False disables
        # this behaviour to ensure we still send requests to the Registry API
        self.identity_headers = identity_headers
        client.BaseClient.__init__(self, host, port, configure_via_auth=False,
                            **kwargs)

    def decrypt_metadata(self, image_metadata):
        if self.metadata_encryption_key:
            if image_metadata.get('location'):
                location = crypt.urlsafe_decrypt(self.metadata_encryption_key,
                                                 image_metadata['location'])
                image_metadata['location'] = location
            if image_metadata.get('location_data'):
                ld = []
                for loc in image_metadata['location_data']:
                    url = crypt.urlsafe_decrypt(self.metadata_encryption_key,
                                                loc['url'])
                    ld.append({'id': loc['id'], 'url': url,
                               'metadata': loc['metadata'],
                               'status': loc['status']})
                image_metadata['location_data'] = ld
        return image_metadata

    def encrypt_metadata(self, image_metadata):
        if self.metadata_encryption_key:
            location_url = image_metadata.get('location')
            if location_url:
                location = crypt.urlsafe_encrypt(self.metadata_encryption_key,
                                                 location_url,
                                                 64)
                image_metadata['location'] = location
            if image_metadata.get('location_data'):
                ld = []
                for loc in image_metadata['location_data']:
                    if loc['url'] == location_url:
                        url = location
                    else:
                        url = crypt.urlsafe_encrypt(
                            self.metadata_encryption_key, loc['url'], 64)
                    ld.append({'url': url, 'metadata': loc['metadata'],
                               'status': loc['status'],
                               # NOTE(zhiyan): New location has no ID field.
                               'id': loc.get('id')})
                image_metadata['location_data'] = ld
        return image_metadata

    def get_images(self, **kwargs):
        """
        Returns a list of image id/name mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: image id after which to start page
        :param limit: max number of images to return
        :param sort_key: results will be ordered by this image attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, images.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/images", params=params)
        image_list = jsonutils.loads(res.read())['images']
        for image in image_list:
            image = self.decrypt_metadata(image)
        return image_list

    def do_request(self, method, action, **kwargs):
        try:
            kwargs['headers'] = kwargs.get('headers', {})
            kwargs['headers'].update(self.identity_headers or {})
            res = super(RegistryClient, self).do_request(method,
                                                         action,
                                                         **kwargs)
            status = res.status
            request_id = res.getheader('x-openstack-request-id')
            msg = ("Registry request %(method)s %(action)s HTTP %(status)s"
                   " request id %(request_id)s" %
                   {'method': method, 'action': action,
                    'status': status, 'request_id': request_id})
            LOG.debug(msg)

        except Exception as exc:
            with excutils.save_and_reraise_exception():
                exc_name = exc.__class__.__name__
                LOG.exception(_LE("Registry client request %(method)s "
                                  "%(action)s raised %(exc_name)s"),
                              {'method': method, 'action': action,
                               'exc_name': exc_name})
        return res

    def get_images_detailed(self, **kwargs):
        """
        Returns a list of detailed image data mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: image id after which to start page
        :param limit: max number of images to return
        :param sort_key: results will be ordered by this image attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, images.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/images/detail", params=params)
        image_list = jsonutils.loads(res.read())['images']
        for image in image_list:
            image = self.decrypt_metadata(image)
        return image_list

    def get_image(self, image_id):
        """Returns a mapping of image metadata from Registry."""
        res = self.do_request("GET", "/images/%s" % image_id)
        data = jsonutils.loads(res.read())['image']
        return self.decrypt_metadata(data)

    def add_image(self, image_metadata):
        """
        Tells registry about an image's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'image' not in image_metadata:
            image_metadata = dict(image=image_metadata)

        encrypted_metadata = self.encrypt_metadata(image_metadata['image'])
        image_metadata['image'] = encrypted_metadata
        body = jsonutils.dumps(image_metadata)

        res = self.do_request("POST", "/images", body=body, headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        image = data['image']
        return self.decrypt_metadata(image)

    def update_image(self, image_id, image_metadata, purge_props=False,
                     from_state=None):
        """
        Updates Registry's information about an image
        """
        if 'image' not in image_metadata:
            image_metadata = dict(image=image_metadata)

        encrypted_metadata = self.encrypt_metadata(image_metadata['image'])
        image_metadata['image'] = encrypted_metadata
        image_metadata['from_state'] = from_state
        body = jsonutils.dumps(image_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        if purge_props:
            headers["X-Glance-Registry-Purge-Props"] = "true"

        res = self.do_request("PUT", "/images/%s" % image_id, body=body,
                              headers=headers)
        data = jsonutils.loads(res.read())
        image = data['image']
        return self.decrypt_metadata(image)

    def delete_image(self, image_id):
        """
        Deletes Registry's information about an image
        """
        res = self.do_request("DELETE", "/images/%s" % image_id)
        data = jsonutils.loads(res.read())
        image = data['image']
        return image

    def get_image_members(self, image_id):
        """Return a list of membership associations from Registry."""
        res = self.do_request("GET", "/images/%s/members" % image_id)
        data = jsonutils.loads(res.read())['members']
        return data

    def get_member_images(self, member_id):
        """Return a list of membership associations from Registry."""
        res = self.do_request("GET", "/shared-images/%s" % member_id)
        data = jsonutils.loads(res.read())['shared_images']
        return data

    def replace_members(self, image_id, member_data):
        """Replace registry's information about image membership."""
        if isinstance(member_data, (list, tuple)):
            member_data = dict(memberships=list(member_data))
        elif (isinstance(member_data, dict) and
              'memberships' not in member_data):
            member_data = dict(memberships=[member_data])

        body = jsonutils.dumps(member_data)

        headers = {'Content-Type': 'application/json', }

        res = self.do_request("PUT", "/images/%s/members" % image_id,
                              body=body, headers=headers)
        return self.get_status_code(res) == 204

    def add_member(self, image_id, member_id, can_share=None):
        """Add to registry's information about image membership."""
        body = None
        headers = {}
        # Build up a body if can_share is specified
        if can_share is not None:
            body = jsonutils.dumps(dict(member=dict(can_share=can_share)))
            headers['Content-Type'] = 'application/json'

        url = "/images/%s/members/%s" % (image_id, member_id)
        res = self.do_request("PUT", url, body=body,
                              headers=headers)
        return self.get_status_code(res) == 204

    def delete_member(self, image_id, member_id):
        """Delete registry's information about image membership."""
        res = self.do_request("DELETE", "/images/%s/members/%s" %
                              (image_id, member_id))
        return self.get_status_code(res) == 204

    def add_host(self, host_metadata):
        """
        Tells registry about an host's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'host' not in host_metadata:
            host_metadata = dict(host=host_metadata)

        body = jsonutils.dumps(host_metadata)

        res = self.do_request("POST", "/nodes", body=body, headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['host']

    def delete_host(self, host_id):
        """
        Deletes Registry's information about an host
        """
        res = self.do_request("DELETE", "/nodes/%s" % host_id)
        data = jsonutils.loads(res.read())
        return data['host']

    def get_host(self, host_id):
        """Returns a mapping of host metadata from Registry."""
        res = self.do_request("GET", "/nodes/%s" % host_id)
        data = jsonutils.loads(res.read())['host']
        return data

    def get_host_interface(self, host_metadata):
        """Returns a mapping of host_interface metadata from Registry."""

        headers = {
            'Content-Type': 'application/json',
        }

        # if 'host' not in host_metadata:
        # host_metadata = dict(host=host_metadata)

        body = jsonutils.dumps(host_metadata)
        res = self.do_request(
            "GET",
            "/host-interface",
            body=body,
            headers=headers)
        host_interface = jsonutils.loads(res.read())

        return host_interface

    def get_all_host_interfaces(self, kwargs):
        """Returns a mapping of host_interface metadata from Registry."""
        headers = {
            'Content-Type': 'application/json',
        }

        if 'filters' not in kwargs:
            filters = dict(filters=kwargs)

        body = jsonutils.dumps(filters)
        res = self.do_request(
            "PUT",
            "/host-interfaces",
            body=body,
            headers=headers)
        host_interface = jsonutils.loads(res.read())

        return host_interface

    def get_assigned_network(self, host_interface_id, network_id):
        """Returns a mapping of host_assigned_network
        metadata from Registry."""

        body = None
        headers = {}

        headers['Content-Type'] = 'application/json'
        url = "/interfaces/%s/network/%s" % (host_interface_id, network_id)
        res = self.do_request("GET", url, body=body, headers=headers)
        host_assigned_network = jsonutils.loads(res.read())

        return host_assigned_network

    def update_host(self, host_id, host_metadata):
        """
        Updates Registry's information about an host
        """
        if 'host' not in host_metadata:
            host_metadata = dict(host=host_metadata)

        body = jsonutils.dumps(host_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/nodes/%s" % host_id, body=body,
                              headers=headers)
        data = jsonutils.loads(res.read())
        return data['host']

    def add_discover_host(self, discover_host_meta):
        """
        Tells registry about an host's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'discover_host' not in discover_host_meta:
            discover_host_meta = dict(discover_host=discover_host_meta)

        body = jsonutils.dumps(discover_host_meta)

        res = self.do_request(
            "POST",
            "/discover/nodes",
            body=body,
            headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['discover_host']

    def delete_discover_host(self, discover_host_id):
        """
        Deletes Registry's information about an host
        """
        res = self.do_request(
            "DELETE",
            "/discover/nodes/%s" %
            discover_host_id)
        data = jsonutils.loads(res.read())
        return data

    def get_discover_hosts_detailed(self, **kwargs):
        """
        Returns a list of detailed host data mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: host id after which to start page
        :param limit: max number of hosts to return
        :param sort_key: results will be ordered by this host attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, hosts.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/discover/nodes", params=params)
        host_list = jsonutils.loads(res.read())['nodes']
        return host_list

    def update_discover_host(self, host_id, discover_host_meta):
        '''
        '''
        headers = {
            'Content-Type': 'application/json',
        }

        if 'discover_host' not in discover_host_meta:
            discover_host_meta = dict(discover_host=discover_host_meta)

        body = jsonutils.dumps(discover_host_meta)

        res = self.do_request(
            "PUT", "/discover/nodes/%s" %
            host_id, body=body, headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['discover_host']

    def get_discover_host_metadata(self, host_id):
        res = self.do_request("GET", "/discover/nodes/%s" % host_id)
        data = jsonutils.loads(res.read())['discover_host']
        return data

    def add_cluster(self, cluster_metadata):
        """
        Tells registry about an cluster's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'cluster' not in cluster_metadata:
            cluster_metadata = dict(cluster=cluster_metadata)

        body = jsonutils.dumps(cluster_metadata)

        res = self.do_request("POST", "/clusters", body=body, headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['cluster']

    def update_cluster(self, cluster_id, cluster_metadata):
        """
        Updates Registry's information about an cluster
        """
        if 'cluster' not in cluster_metadata:
            cluster_metadata = dict(cluster=cluster_metadata)

        body = jsonutils.dumps(cluster_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/clusters/%s" % cluster_id, body=body,
                              headers=headers)
        data = jsonutils.loads(res.read())
        return data['cluster']

    def delete_cluster(self, cluster_id):
        """
        Deletes Registry's information about an cluster
        """
        res = self.do_request("DELETE", "/clusters/%s" % cluster_id)
        data = jsonutils.loads(res.read())
        return data['cluster']

    def get_cluster(self, cluster_id):
        """Returns a mapping of cluster metadata from Registry."""
        res = self.do_request("GET", "/clusters/%s" % cluster_id)
        data = jsonutils.loads(res.read())
        return data

    def add_cluster_host(self, cluster_id, host_id):
        """Add host to cluster."""
        body = None
        headers = {}

        headers['Content-Type'] = 'application/json'

        url = "/clusters/%s/nodes/%s" % (cluster_id, host_id)
        res = self.do_request("PUT", url, body=body,
                              headers=headers)
        return self.get_status_code(res) == 204

    def delete_cluster_host(self, cluster_id, host_id):
        """Delete host from cluster."""
        res = self.do_request("DELETE", "/clusters/%s/nodes/%s" %
                              (cluster_id, host_id))
        return self.get_status_code(res) == 204

    def get_hosts_detailed(self, **kwargs):
        """
        Returns a list of detailed host data mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: host id after which to start page
        :param limit: max number of hosts to return
        :param sort_key: results will be ordered by this host attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, hosts.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/nodes", params=params)
        host_list = jsonutils.loads(res.read())['nodes']
        return host_list

    def get_clusters_detailed(self, **kwargs):
        """
        Returns a list of detailed cluster data mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: host id after which to start page
        :param limit: max number of hosts to return
        :param sort_key: results will be ordered by this host attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, hosts.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/clusters", params=params)
        cluster_list = jsonutils.loads(res.read())['clusters']
        return cluster_list

    def get_cluster_hosts(self, cluster_id, host_id=None):
        """Return a list of membership associations from Registry."""
        if host_id:
            res = self.do_request(
                "GET", "/clusters/%s/nodes/%s" %
                (cluster_id, host_id))
        else:
            res = self.do_request("GET", "/clusters/%s/nodes" % cluster_id)
        data = jsonutils.loads(res.read())['members']
        return data

    def get_host_clusters(self, host_id):
        """Return a list of membership associations from Registry."""
        res = self.do_request("GET", "/multi_clusters/nodes/%s" % host_id)
        data = jsonutils.loads(res.read())['multi_clusters']
        return data

    def add_template(self, template):
        """ """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'template' not in template:
            template = dict(template=template)

        body = jsonutils.dumps(template)

        res = self.do_request("POST", "/template", body=body, headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['template']

    def add_hwm(self, hwm):
        """ """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'hwm' not in hwm:
            hwm = dict(hwm=hwm)

        body = jsonutils.dumps(hwm)

        res = self.do_request("POST", "/hwm", body=body, headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['hwm']

    def update_hwm(self, hwm_id, hwm):
        headers = {
            'Content-Type': 'application/json',
        }
        if 'hwm' not in hwm:
            hwm = dict(hwm=hwm)

        body = jsonutils.dumps(hwm)

        res = self.do_request(
            "PUT",
            "/hwm/%s" %
            hwm_id,
            body=body,
            headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['hwm']

    def delete_hwm(self, hwm_id):
        res = self.do_request("DELETE", "/hwm/%s" % hwm_id)
        data = jsonutils.loads(res.read())
        return data['hwm']

    def list_hwm(self, **kwargs):
        """ """
        params = self._extract_params(kwargs, hwms.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/hwm", params=params)
        data = jsonutils.loads(res.read())
        return data

    def get_hwm_detail(self, hwm_id):
        res = self.do_request("GET", "/hwm/%s" % hwm_id)
        data = jsonutils.loads(res.read())
        return data['hwm']

    def add_host_template(self, template):
        """ """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'template' not in template:
            template = dict(template=template)

        body = jsonutils.dumps(template)

        res = self.do_request(
            "POST",
            "/host_template",
            body=body,
            headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['host_template']

    def update_template(self, template_id, template):
        headers = {
            'Content-Type': 'application/json',
        }
        if 'template' not in template:
            template = dict(template=template)

        body = jsonutils.dumps(template)

        res = self.do_request(
            "PUT",
            "/template/%s" %
            template_id,
            body=body,
            headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['template']

    def update_host_template(self, template_id, template):
        headers = {
            'Content-Type': 'application/json',
        }
        if 'template' not in template:
            template = dict(template=template)

        body = jsonutils.dumps(template)

        res = self.do_request(
            "PUT",
            "/host_template/%s" %
            template_id,
            body=body,
            headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['host_template']

    def delete_template(self, template_id):
        res = self.do_request("DELETE", "/template/%s" % template_id)
        data = jsonutils.loads(res.read())
        return data['template']

    def delete_host_template(self, template_id):
        res = self.do_request("DELETE", "/host_template/%s" % template_id)
        data = jsonutils.loads(res.read())
        return data['host_template']

    def list_template(self, **kwargs):
        """ """
        params = self._extract_params(kwargs, template.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/template/list", params=params)
        data = jsonutils.loads(res.read())
        return data

    def list_host_template(self, **kwargs):
        """ """
        params = self._extract_params(kwargs, template.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/host_template/list", params=params)
        data = jsonutils.loads(res.read())
        return data

    def get_template_detail(self, template_id):
        res = self.do_request("GET", "/template/%s" % template_id)
        data = jsonutils.loads(res.read())
        return data['template']

    def get_host_template_detail(self, template_id):
        res = self.do_request("GET", "/host_template/%s" % template_id)
        data = jsonutils.loads(res.read())
        return data['host_template']

    def get_component(self, component_id):
        """Returns a mapping of component metadata from Registry."""
        res = self.do_request("GET", "/components/%s" % component_id)
        data = jsonutils.loads(res.read())['component']
        return data

    def add_component(self, component_metadata):
        """
        Tells registry about an component's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'component' not in component_metadata:
            component_metadata = dict(component=component_metadata)

        body = jsonutils.dumps(component_metadata)

        res = self.do_request(
            "POST",
            "/components",
            body=body,
            headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['component']

    def delete_component(self, component_id):
        """
        Deletes Registry's information about an component
        """
        res = self.do_request("DELETE", "/components/%s" % component_id)
        data = jsonutils.loads(res.read())
        return data['component']

    def get_components_detailed(self, **kwargs):
        """
        Returns a list of detailed component data mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: host id after which to start page
        :param limit: max number of hosts to return
        :param sort_key: results will be ordered by this host attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, hosts.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/components/detail", params=params)
        component_list = jsonutils.loads(res.read())['components']
        return component_list

    def update_component(self, component_id, component_metadata):
        """
        Updates Registry's information about an component
        """
        if 'component' not in component_metadata:
            component_metadata = dict(component=component_metadata)

        body = jsonutils.dumps(component_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/components/%s" % component_id,
                              body=body, headers=headers)
        data = jsonutils.loads(res.read())
        return data['component']

    def get_service(self, service_id):
        """Returns a mapping of service metadata from Registry."""
        res = self.do_request("GET", "/services/%s" % service_id)
        data = jsonutils.loads(res.read())['service']
        return data

    def add_service(self, service_metadata):
        """
        Tells registry about an service's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'service' not in service_metadata:
            service_metadata = dict(service=service_metadata)

        body = jsonutils.dumps(service_metadata)
        print body

        res = self.do_request("POST", "/services", body=body, headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['service']

    def delete_service(self, service_id):
        """
        Deletes Registry's information about an service
        """
        res = self.do_request("DELETE", "/services/%s" % service_id)
        data = jsonutils.loads(res.read())
        return data['service']

    def get_services_detailed(self, **kwargs):
        """
        Returns a list of detailed service data mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: host id after which to start page
        :param limit: max number of hosts to return
        :param sort_key: results will be ordered by this host attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, hosts.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/services/detail", params=params)
        service_list = jsonutils.loads(res.read())['services']
        return service_list

    def update_service(self, service_id, service_metadata):
        """
        Updates Registry's information about an service
        """
        if 'service' not in service_metadata:
            service_metadata = dict(service=service_metadata)

        body = jsonutils.dumps(service_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/services/%s" % service_id, body=body,
                              headers=headers)
        data = jsonutils.loads(res.read())
        return data['service']

    def get_role(self, role_id):
        """Returns a mapping of role metadata from Registry."""
        res = self.do_request("GET", "/roles/%s" % role_id)
        data = jsonutils.loads(res.read())['role']
        return data

    def add_role(self, role_metadata):
        """
        Tells registry about an role's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'role' not in role_metadata:
            role_metadata = dict(role=role_metadata)

        body = jsonutils.dumps(role_metadata)
        print body

        res = self.do_request("POST", "/roles", body=body, headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['role']

    def delete_role(self, role_id):
        """
        Deletes Registry's information about an role
        """
        res = self.do_request("DELETE", "/roles/%s" % role_id)
        data = jsonutils.loads(res.read())
        return data['role']

    def get_roles_detailed(self, **kwargs):
        """
        Returns a list of detailed role data mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: host id after which to start page
        :param limit: max number of hosts to return
        :param sort_key: results will be ordered by this host attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, hosts.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/roles/detail", params=params)
        role_list = jsonutils.loads(res.read())['roles']
        return role_list

    def update_role(self, role_id, role_metadata):
        """
        Updates Registry's information about an role
        """
        if 'role' not in role_metadata:
            role_metadata = dict(role=role_metadata)

        body = jsonutils.dumps(role_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/roles/%s" % role_id, body=body,
                              headers=headers)
        data = jsonutils.loads(res.read())
        return data['role']

    def get_role_services(self, role_id):
        """Returns the service list of a role."""
        res = self.do_request("GET", "/roles/%s/services" % role_id)
        data = jsonutils.loads(res.read())['role']
        return data

    def get_role_host(self, role_id):
        """Returns a mapping of role_host metadata from Registry."""
        res = self.do_request("GET", "/roles/%s/hosts" % role_id)
        data = jsonutils.loads(res.read())['role']
        return data

    def delete_role_host(self, role_id):
        """Returns a mapping of role_host metadata from Registry."""
        res = self.do_request("DELETE", "/roles/%s/hosts" % role_id)
        data = jsonutils.loads(res.read())['role']
        return data

    def update_role_host(self, role_host_id, role_host):
        """Returns a mapping of role_host metadata from Registry."""
        if 'role' not in role_host:
            role_metadata = dict(role=role_host)

        body = jsonutils.dumps(role_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/roles/%s/hosts" % role_host_id,
                              body=body, headers=headers)
        data = jsonutils.loads(res.read())
        return data

    def add_config_file(self, config_file_metadata):
        """
        Tells registry about an config_file's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'config_file' not in config_file_metadata:
            config_file_metadata = dict(config_file=config_file_metadata)

        body = jsonutils.dumps(config_file_metadata)

        res = self.do_request(
            "POST",
            "/config_files",
            body=body,
            headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['config_file']

    def delete_config_file(self, config_file_id):
        """
        Deletes Registry's information about an config_file
        """
        res = self.do_request("DELETE", "/config_files/%s" % config_file_id)
        data = jsonutils.loads(res.read())
        return data['config_file']

    def get_config_file(self, config_file_id):
        """Returns a mapping of config_file metadata from Registry."""
        res = self.do_request("GET", "/config_files/%s" % config_file_id)
        data = jsonutils.loads(res.read())['config_file']
        return data

    def update_config_file(self, config_file_id, config_file_metadata):
        """
        Updates Registry's information about an config_file
        """
        if 'config_file' not in config_file_metadata:
            config_file_metadata = dict(config_file=config_file_metadata)

        body = jsonutils.dumps(config_file_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/config_files/%s" % config_file_id,
                              body=body, headers=headers)
        data = jsonutils.loads(res.read())
        return data['config_file']

    def get_config_files_detailed(self, **kwargs):
        """
        Returns a list of detailed config_file data mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: config_file id after which to start page
        :param limit: max number of hosts to return
        :param sort_key: results will be ordered by this config_file attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, config_files.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/config_files/detail", params=params)
        config_file_list = jsonutils.loads(res.read())['config_files']
        return config_file_list

    def add_config_set(self, config_set_metadata):
        """
        Tells registry about an config_set's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'config_set' not in config_set_metadata:
            config_set_metadata = dict(config_set=config_set_metadata)

        body = jsonutils.dumps(config_set_metadata)

        res = self.do_request(
            "POST",
            "/config_sets",
            body=body,
            headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['config_set']

    def delete_config_set(self, config_set_id):
        """
        Deletes Registry's information about an config_set
        """
        res = self.do_request("DELETE", "/config_sets/%s" % config_set_id)
        data = jsonutils.loads(res.read())
        return data['config_set']

    def get_config_set(self, config_set_id):
        """Returns a mapping of config_set metadata from Registry."""
        res = self.do_request("GET", "/config_sets/%s" % config_set_id)
        data = jsonutils.loads(res.read())['config_set']
        return data

    def update_config_set(self, config_set_id, config_set_metadata):
        """
        Updates Registry's information about an config_set
        """
        if 'config_set' not in config_set_metadata:
            config_set_metadata = dict(config_set=config_set_metadata)

        body = jsonutils.dumps(config_set_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/config_sets/%s" % config_set_id,
                              body=body, headers=headers)
        data = jsonutils.loads(res.read())
        return data['config_set']

    def get_config_sets_detailed(self, **kwargs):
        """
        Returns a list of detailed config_set data mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: config_set id after which to start page
        :param limit: max number of hosts to return
        :param sort_key: results will be ordered by this config_set attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, config_sets.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/config_sets/detail", params=params)
        config_set_list = jsonutils.loads(res.read())['config_sets']
        return config_set_list

    def add_config(self, config_metadata):
        """
        Tells registry about an config's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'config' not in config_metadata:
            config_metadata = dict(config=config_metadata)

        body = jsonutils.dumps(config_metadata)

        res = self.do_request("POST", "/configs", body=body, headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['config']

    def delete_config(self, config_id):
        """
        Deletes Registry's information about an config
        """
        res = self.do_request("DELETE", "/configs/%s" % config_id)
        data = jsonutils.loads(res.read())
        return data['config']

    def get_config(self, config_id):
        """Returns a mapping of config metadata from Registry."""
        res = self.do_request("GET", "/configs/%s" % config_id)
        data = jsonutils.loads(res.read())['config']
        return data

    def update_config(self, config_id, config_metadata):
        """
        Updates Registry's information about an config
        """
        if 'config' not in config_metadata:
            config_metadata = dict(config=config_metadata)

        body = jsonutils.dumps(config_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/configs/%s" % config_id, body=body,
                              headers=headers)
        data = jsonutils.loads(res.read())
        return data['config']

    def update_config_by_role_hosts(self, config_metadatas):
        """
        Updates Registry's information about an config
        """
        if 'configs' not in config_metadatas:
            config_metadata = dict(configs=config_metadatas)

        body = jsonutils.dumps(config_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request(
            "POST",
            "/configs/update_config_by_role_hosts",
            body=body,
            headers=headers)
        data = jsonutils.loads(res.read())
        return data['configs']

    def get_configs_detailed(self, **kwargs):
        """
        Returns a list of detailed config data mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: config id after which to start page
        :param limit: max number of hosts to return
        :param sort_key: results will be ordered by this config attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, configs.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/configs/detail", params=params)
        config_list = jsonutils.loads(res.read())['configs']
        return config_list

    def get_networks(self, network_id):
        """Return a list of network associations from Registry."""
        res = self.do_request("GET", "/networks/%s" % network_id)
        data = jsonutils.loads(res.read())['network']
        return data

    def add_network(self, network_metadata):
        """
        Tells registry about an network's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'network' not in network_metadata:
            network_metadata = dict(network=network_metadata)

        body = jsonutils.dumps(network_metadata)

        res = self.do_request("POST", "/networks", body=body, headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['network']

    def update_phyname_of_network(self, network_phyname_set):
        """
        Updates Registry's information about an network phynet_name segment
        """
        body = jsonutils.dumps(network_phyname_set)

        headers = {
            'Content-Type': 'application/json',
        }

        self.do_request(
            "POST",
            "/networks/update_phyname_of_network",
            body=body,
            headers=headers)

    def update_network(self, network_id, network_metadata):
        """
        Updates Registry's information about an network
        """
        if 'network' not in network_metadata:
            network_metadata = dict(network=network_metadata)

        body = jsonutils.dumps(network_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/networks/%s" % network_id, body=body,
                              headers=headers)
        data = jsonutils.loads(res.read())
        return data['network']

    def delete_network(self, network_id):
        """
        Deletes Registry's information about an network
        """
        res = self.do_request("DELETE", "/networks/%s" % network_id)
        data = jsonutils.loads(res.read())
        return data['network']

    def get_networks_detailed(self, cluster_id, **kwargs):
        """
        Returns a list of detailed host data mappings from Registry

        :param filters: dict of keys & expected values to filter results
        :param marker: host id after which to start page
        :param limit: max number of hosts to return
        :param sort_key: results will be ordered by this host attribute
        :param sort_dir: direction in which to order results (asc, desc)
        """
        params = self._extract_params(kwargs, networks.SUPPORTED_PARAMS)
        res = self.do_request(
            "GET", "/clusters/%s/networks" %
            cluster_id, params=params)
        network_list = jsonutils.loads(res.read())['networks']
        return network_list

    def get_all_networks(self, **kwargs):
        params = self._extract_params(kwargs, hosts.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/networks", params=params)
        data = jsonutils.loads(res.read())
        return data

    def config_interface(self, config_interface):
        """
        Tells registry about an config_interface's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        body = jsonutils.dumps(config_interface)
        res = self.do_request(
            "POST",
            "/config_interface",
            body=body,
            headers=headers)
        config_interface = jsonutils.loads(res.read())['config_interface_meta']
        return config_interface

    def add_service_disk(self, service_disk_metadata):
        """
        Tells registry about an network's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'service_disk' not in service_disk_metadata:
            service_disk_metadata = dict(service_disk=service_disk_metadata)

        body = jsonutils.dumps(service_disk_metadata)

        res = self.do_request(
            "POST",
            "/service_disk",
            body=body,
            headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['service_disk']

    def delete_service_disk(self, service_disk_id):
        """
        Deletes Registry's information about an network
        """
        res = self.do_request("DELETE", "/service_disk/%s" % service_disk_id)
        data = jsonutils.loads(res.read())
        return data['service_disk']

    def update_service_disk(self, service_disk_id, service_disk_metadata):
        """
        Updates Registry's information about an service_disk
        """
        if 'service_disk' not in service_disk_metadata:
            service_disk_metadata = dict(service_disk=service_disk_metadata)

        body = jsonutils.dumps(service_disk_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/service_disk/%s" % service_disk_id,
                              body=body, headers=headers)
        data = jsonutils.loads(res.read())
        return data['service_disk']

    def get_service_disk_detail(self, service_disk_id):
        """Return a list of service_disk associations from Registry."""
        res = self.do_request("GET", "/service_disk/%s" % service_disk_id)
        data = jsonutils.loads(res.read())['service_disk']
        return data

    def list_service_disk(self, **kwargs):
        """
        Returns a list of service_disk data mappings from Registry
        """
        params = self._extract_params(kwargs, hosts.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/service_disk/list", params=params)
        service_disk_list = jsonutils.loads(res.read())['service_disks']
        return service_disk_list

    def add_cinder_volume(self, cinder_volume_metadata):
        """
        Tells registry about an network's metadata
        """
        headers = {
            'Content-Type': 'application/json',
        }

        if 'cinder_volume' not in cinder_volume_metadata:
            cinder_volume_metadata = dict(cinder_volume=cinder_volume_metadata)

        body = jsonutils.dumps(cinder_volume_metadata)

        res = self.do_request(
            "POST",
            "/cinder_volume",
            body=body,
            headers=headers)
        # Registry returns a JSONified dict(image=image_info)
        data = jsonutils.loads(res.read())
        return data['cinder_volume']

    def delete_cinder_volume(self, cinder_volume_id):
        """
        Deletes Registry's information about an network
        """
        res = self.do_request("DELETE", "/cinder_volume/%s" % cinder_volume_id)
        data = jsonutils.loads(res.read())
        return data['cinder_volume']

    def update_cinder_volume(self, cinder_volume_id, cinder_volume_metadata):
        """
        Updates Registry's information about an cinder_volume
        """
        if 'cinder_volume' not in cinder_volume_metadata:
            cinder_volume_metadata = dict(cinder_volume=cinder_volume_metadata)

        body = jsonutils.dumps(cinder_volume_metadata)

        headers = {
            'Content-Type': 'application/json',
        }

        res = self.do_request("PUT", "/cinder_volume/%s" % cinder_volume_id,
                              body=body, headers=headers)
        data = jsonutils.loads(res.read())
        return data['cinder_volume']

    def get_cinder_volume_detail(self, cinder_volume_id):
        """Return a list of cinder_volume associations from Registry."""
        res = self.do_request("GET", "/cinder_volume/%s" % cinder_volume_id)
        data = jsonutils.loads(res.read())['cinder_volume']
        return data

    def list_cinder_volume(self, **kwargs):
        """
        Returns a list of cinder_volume data mappings from Registry
        """
        params = self._extract_params(kwargs, hosts.SUPPORTED_PARAMS)
        res = self.do_request("GET", "/cinder_volume/list", params=params)
        cinder_volume_list = jsonutils.loads(res.read())['cinder_volumes']
        return cinder_volume_list
