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

import six

from daisyclient.common import utils
from daisyclient.openstack.common.apiclient import base
# import daisy.queue_process as queue
# from daisy.queue_process import exec_cmd

CREATE_PARAMS = ('cluster_id', 'version_id',
                 'deployment_interface', 'skip_pxe_ipmi', 'pxe_only')
OS_REQ_ID_HDR = 'x-openstack-request-id'


class Install(base.Resource):

    def __repr__(self):
        return "<Install %s>" % self._info

    def update(self, **fields):
        self.manager.update(self, **fields)

    def delete(self, **kwargs):
        return self.manager.delete(self)

    def data(self, **kwargs):
        return self.manager.data(self, **kwargs)


class InstallManager(base.ManagerWithFind):
    resource_class = Install

    def _install_meta_to_headers(self, fields):
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
    def _format_install_meta_for_user(meta):
        for key in ['size', 'min_ram', 'min_disk']:
            if key in meta:
                try:
                    meta[key] = int(meta[key]) if meta[key] else 0
                except ValueError:
                    pass
        return meta

    def list(self, **kwargs):
        pass

    def install(self, **kwargs):
        """Install a cluster

        TODO(bcwaldon): document accepted params
        """
        fields = {}
        for field in kwargs:
            if field in CREATE_PARAMS:
                fields[field] = kwargs[field]
            else:
                msg = 'install() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        # if fields.has_key("version_id"):
            # url = '/v1/install/%s/version/%s' % (fields['cluster_id'],
            # fields['version_id'])
        # else:
        url = '/v1/install'

        hdrs = self._install_meta_to_headers(fields)
        resp, body = self.client.post(url, headers=None, data=hdrs)
        return Install(self, self._format_install_meta_for_user(body))

    def export_db(self, **kwargs):
        """export database to tecs and HA config file

        TODO(bcwaldon): document accepted params
        """
        fields = {}
        for field in kwargs:
            if field in CREATE_PARAMS:
                fields[field] = kwargs[field]
            else:
                msg = 'export_db() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        url = '/v1/export_db'
        hdrs = self._install_meta_to_headers(fields)
        resp, body = self.client.post(url, headers=None, data=hdrs)
        return Install(self, self._format_install_meta_for_user(body))

    def disk_array_update(self, cluster, **kwargs):
        UPDATE_DISK_ARRAY_PARAMS = []
        fields = {}
        for field in kwargs:
            if field in UPDATE_DISK_ARRAY_PARAMS:
                fields[field] = kwargs[field]
            else:
                msg = 'disk_array_update() \
                      got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        url = '/v1/disk_array/%s' % base.getid(cluster)
        hdrs = self._install_meta_to_headers(fields)
        resp, body = self.client.post(url, headers=None, data=hdrs)
        return Install(self, self._format_install_meta_for_user(body))
