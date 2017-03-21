# Copyright 2012 OpenStack Foundation
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

import copy

from oslo_utils import encodeutils
import six
import six.moves.urllib.parse as urlparse
from daisyclient.common import utils
from daisyclient.openstack.common.apiclient import base

CREATE_SERVICE_DISK_PARAMS = ('service', 'data_ips', 'size',
                              'disk_location', 'role_id', 'lun',
                              'protocol_type', 'partition')
CREATE_CINDER_BACKEND_PARAMS = ('disk_array', 'role_id')
CREATE_CINDER_BACKEND_INTER_PARAMS = ('management_ips', 'data_ips',
                                      'pools', 'volume_driver',
                                      'volume_type', 'role_id',
                                      'user_name', 'user_pwd')
UPDATE_CINDER_BACKEND_PARAMS = ('id', 'disk_array', 'role_id')
DEFAULT_PAGE_SIZE = 20

SORT_DIR_VALUES = ('asc', 'desc')
SORT_KEY_VALUES = ('id', 'role_id', 'created_at', 'updated_at', 'status')
SERVICE_DISK_UPDATE_PARAMS = CREATE_SERVICE_DISK_PARAMS
OS_REQ_ID_HDR = 'x-openstack-request-id'


class Disk_array(base.Resource):

    def __repr__(self):
        return "<Disk_array %s>" % self._info

    def update(self, **fields):
        self.manager.update(self, **fields)

    def delete(self, **kwargs):
        return self.manager.delete(self)

    def data(self, **kwargs):
        return self.manager.data(self, **kwargs)


class DiskArrayManager(base.ManagerWithFind):
    resource_class = Disk_array

    def _list(self, url, response_key, obj_class=None, body=None):
        resp, body = self.client.get(url)

        if obj_class is None:
            obj_class = self.resource_class

        data = body[response_key]
        return ([obj_class(self, res, loaded=True) for res in data if res],
                resp)

    def _service_disk_meta_to_headers(self, fields):
        headers = {}
        fields_copy = copy.deepcopy(fields)

        # NOTE(flaper87): Convert to str, headers
        # that are not instance of basestring. All
        # headers will be encoded later, before the
        # request is sent.

        for key, value in six.iteritems(fields_copy):
            headers['%s' % key] = utils.to_str(value)
        return headers

    def _cinder_volume_meta_to_headers(self, fields):
        headers = {}
        fields_copy = copy.deepcopy(fields)

        # NOTE(flaper87): Convert to str, headers
        # that are not instance of basestring. All
        # headers will be encoded later, before the
        # request is sent.

        for key, value in six.iteritems(fields_copy):
            headers['%s' % key] = utils.to_str(value)
        return headers

    @staticmethod
    def _format_service_disk_meta_for_user(meta):
        for key in ['size', 'min_ram', 'min_disk']:
            if key in meta:
                try:
                    meta[key] = int(meta[key]) if meta[key] else 0
                except ValueError:
                    pass
        return meta

    def list(self, **kwargs):
        pass

    def get(self, service_disk, **kwargs):
        """Get the metadata for a specific service_disk.

        :param service_disk: host object or id to look up
        :rtype: :class:`service_disk`
        """
        service_disk_id = base.getid(service_disk)
        resp, body = self.client.get('/v1/service_disk/%s'
                                     % urlparse.quote(str(service_disk_id)))
        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))
        # return Host(self, meta)
        return Disk_array(self, self._format_service_disk_meta_for_user(
            body['disk_meta']))

    def data(self, image, do_checksum=True, **kwargs):
        """Get the raw data for a specific image.

        :param image: image object or id to look up
        :param do_checksum: Enable/disable checksum validation
        :rtype: iterable containing image data
        """
        image_id = base.getid(image)
        resp, body = self.client.get('/v1/images/%s'
                                     % urlparse.quote(str(image_id)))
        content_length = int(resp.headers.get('content-length', 0))
        checksum = resp.headers.get('x-image-meta-checksum', None)
        if do_checksum and checksum is not None:
            body = utils.integrity_iter(body, checksum)
        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

        return utils.IterableWithLength(body, content_length)

    def _build_params(self, parameters):
        params = {'limit': parameters.get('page_size', DEFAULT_PAGE_SIZE)}

        if 'marker' in parameters:
            params['marker'] = parameters['marker']

        sort_key = parameters.get('sort_key')
        if sort_key is not None:
            if sort_key in SORT_KEY_VALUES:
                params['sort_key'] = sort_key
            else:
                raise ValueError('sort_key must be one of the following: %s.'
                                 % ', '.join(SORT_KEY_VALUES))

        sort_dir = parameters.get('sort_dir')
        if sort_dir is not None:
            if sort_dir in SORT_DIR_VALUES:
                params['sort_dir'] = sort_dir
            else:
                raise ValueError('sort_dir must be one of the following: %s.'
                                 % ', '.join(SORT_DIR_VALUES))

        filters = parameters.get('filters', {})
        params.update(filters)

        return params

    def service_disk_add(self, **kwargs):
        """Disk_array a cluster

        TODO(bcwaldon): document accepted params
        """
        fields = {}
        for field in kwargs:
            if field in CREATE_SERVICE_DISK_PARAMS:
                fields[field] = kwargs[field]
            else:
                msg = 'Disk_array() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        url = '/v1/service_disk'

        hdrs = self._service_disk_meta_to_headers(fields)
        resp, body = self.client.post(url, headers=None, data=hdrs)
        return Disk_array(self, self._format_service_disk_meta_for_user(
            body['disk_meta']))

    def service_disk_delete(self, id, **kwargs):
        """Delete an service_disk."""
        url = "/v1/service_disk/%s" % base.getid(id)
        resp, body = self.client.delete(url)
        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

    def service_disk_update(self, id, **kwargs):
        """Update an service_disk
        TODO(bcwaldon): document accepted params
        """
        hdrs = {}
        fields = {}
        for field in kwargs:
            if field in SERVICE_DISK_UPDATE_PARAMS:
                fields[field] = kwargs[field]
            elif field == 'return_req_id':
                continue
            else:
                msg = 'update() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        hdrs.update(self._service_disk_meta_to_headers(fields))

        url = '/v1/service_disk/%s' % base.getid(id)
        resp, body = self.client.put(url, headers=None, data=hdrs)
        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

        return Disk_array(self, self._format_service_disk_meta_for_user(
            body['disk_meta']))

    def service_disk_detail(self, id, **kwargs):
        """Get the metadata for a specific service_disk.

        :param service_disk: host object or id to look up
        :rtype: :class:`service_disk`
        """
        service_disk_id = base.getid(id)
        resp, body = self.client.get('/v1/service_disk/%s'
                                     % urlparse.quote(str(service_disk_id)))

        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

        return Disk_array(self, self._format_service_disk_meta_for_user(
            body['disk_meta']))

    def service_disk_list(self, **kwargs):
        """Get a list of service_disks.

        :param page_size: number of items to request in each paginated request
        :param limit: maximum number of service_disks to return
        :param marker: begin returning service_disks that
                       appear later in the service_disk
                       list than that represented by this service_disk id
        :param filters: dict of direct comparison filters that mimics the
                        structure of an service_disk object
        :param return_request_id: If an empty list is provided, populate this
                              list with the request ID value from the header
                              x-openstack-request-id
        :rtype: list of :class:`service_disk`
        """
        absolute_limit = kwargs.get('limit')
        page_size = kwargs.get('page_size', DEFAULT_PAGE_SIZE)

        def paginate(qp, return_request_id=None):
            for param, value in six.iteritems(qp):
                if isinstance(value, six.string_types):
                    # Note(flaper87) Url encoding should
                    # be moved inside http utils, at least
                    # shouldn't be here.
                    #
                    # Making sure all params are str before
                    # trying to encode them
                    qp[param] = encodeutils.safe_decode(value)

            url = '/v1/service_disk/list?%s' % urlparse.urlencode(qp)
            service_disks, resp = self._list(url, "disk_meta")

            if return_request_id is not None:
                return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

            for service_disk in service_disks:
                yield service_disk

        return_request_id = kwargs.get('return_req_id', None)

        params = self._build_params(kwargs)

        seen = 0
        while True:
            seen_last_page = 0
            filtered = 0
            for service_disk in paginate(params, return_request_id):
                last_service_disk = service_disk.id

                if (absolute_limit is not None and
                        seen + seen_last_page >= absolute_limit):
                    # Note(kragniz): we've seen enough images
                    return
                else:
                    seen_last_page += 1
                    yield service_disk

            seen += seen_last_page

            if seen_last_page + filtered == 0:
                # Note(kragniz): we didn't get any service_disks in the last
                # page
                return

            if absolute_limit is not None and seen >= absolute_limit:
                # Note(kragniz): reached the limit of service_disks to return
                return

            if page_size and seen_last_page + filtered < page_size:
                # Note(kragniz): we've reached the last page of the
                # service_disks
                return

            # Note(kragniz): there are more service_disks to come
            params['marker'] = last_service_disk
            seen_last_page = 0

    def cinder_volume_add(self, **kwargs):
        """Disk_array a cluster

        TODO(bcwaldon): document accepted params
        """
        fields = {}
        for field in kwargs:
            if field in CREATE_CINDER_BACKEND_PARAMS:
                fields[field] = kwargs[field]
            else:
                msg = 'Disk_array() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)
        url = '/v1/cinder_volume'

        hdrs = self._service_disk_meta_to_headers(fields)
        resp, body = self.client.post(url, headers=None, data=hdrs)
        return Disk_array(self, self._format_service_disk_meta_for_user(
            body['disk_meta']))

    def cinder_volume_delete(self, id, **kwargs):
        """Delete an cinder_volume."""
        url = "/v1/cinder_volume/%s" % base.getid(id)
        resp, body = self.client.delete(url)
        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

    def cinder_volume_update(self, id, **kwargs):
        """Update an cinder_volume

        TODO(bcwaldon): document accepted params
        """
        hdrs = {}
        fields = {}
        for field in kwargs:
            if field in CREATE_CINDER_BACKEND_INTER_PARAMS:
                fields[field] = kwargs[field]
            elif field == 'return_req_id':
                continue
            else:
                msg = 'update() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        hdrs.update(self._cinder_volume_meta_to_headers(fields))

        url = '/v1/cinder_volume/%s' % base.getid(id)
        resp, body = self.client.put(url, headers=None, data=hdrs)
        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

        return Disk_array(self, self._format_service_disk_meta_for_user(
            body['disk_meta']))

    def cinder_volume_detail(self, id, **kwargs):
        """Get the metadata for a specific cinder_volume.

        :param cinder_volume: host object or id to look up
        :rtype: :class:`cinder_volume`
        """

        cinder_volume_id = base.getid(id)
        resp, body = self.client.get('/v1/cinder_volume/%s'
                                     % urlparse.quote(str(cinder_volume_id)))

        return_request_id = kwargs.get('return_req_id', None)
        if return_request_id is not None:
            return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

        return Disk_array(self, self._format_service_disk_meta_for_user(
            body['disk_meta']))

    def cinder_volume_list(self, **kwargs):
        """Get a list of cinder_volumes.

        :param page_size: number of items to request in each paginated request
        :param limit: maximum number of cinder_volumes to return
        :param marker: begin returning cinder_volumes that appear later in
                       the cinder_volume
                       list than that represented by this cinder_volume id
        :param filters: dict of direct comparison filters that mimics the
                        structure of an cinder_volume object
        :param return_request_id: If an empty list is provided, populate this
                              list with the request ID value from the header
                              x-openstack-request-id
        :rtype: list of :class:`cinder_volume`
        """
        absolute_limit = kwargs.get('limit')
        page_size = kwargs.get('page_size', DEFAULT_PAGE_SIZE)

        def paginate(qp, return_request_id=None):
            for param, value in six.iteritems(qp):
                if isinstance(value, six.string_types):
                    # Note(flaper87) Url encoding should
                    # be moved inside http utils, at least
                    # shouldn't be here.
                    #
                    # Making sure all params are str before
                    # trying to encode them
                    qp[param] = encodeutils.safe_decode(value)

            url = '/v1/cinder_volume/list?%s' % urlparse.urlencode(qp)
            cinder_volumes, resp = self._list(url, "disk_meta")

            if return_request_id is not None:
                return_request_id.append(resp.headers.get(OS_REQ_ID_HDR, None))

            for cinder_volume in cinder_volumes:
                yield cinder_volume

        return_request_id = kwargs.get('return_req_id', None)

        params = self._build_params(kwargs)

        seen = 0
        while True:
            seen_last_page = 0
            filtered = 0
            for cinder_volume in paginate(params, return_request_id):
                last_cinder_volume = cinder_volume.id

                if (absolute_limit is not None and
                        seen + seen_last_page >= absolute_limit):
                    # Note(kragniz): we've seen enough images
                    return
                else:
                    seen_last_page += 1
                    yield cinder_volume

            seen += seen_last_page

            if seen_last_page + filtered == 0:
                # Note(kragniz): we didn't get any service_disks in the last
                # page
                return

            if absolute_limit is not None and seen >= absolute_limit:
                # Note(kragniz): reached the limit of service_disks to return
                return

            if page_size and seen_last_page + filtered < page_size:
                # Note(kragniz): we've reached the last page of the
                # service_disks
                return

            # Note(kragniz): there are more service_disks to come
            params['marker'] = last_cinder_volume
            seen_last_page = 0
