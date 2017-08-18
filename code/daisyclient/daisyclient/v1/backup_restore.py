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

OS_REQ_ID_HDR = 'x-openstack-request-id'

BACKUP_PARAMS = ()
RESTORE_PARAMS = ('backup_file_path')
VERSION_PARAMS = ('type')


class BackupRestore(base.Resource):

    def __repr__(self):
        return "<BackupRestore %s>" % self._info

    def update(self, **fields):
        self.manager.update(self, **fields)

    def delete(self, **kwargs):
        return self.manager.delete(self)

    def data(self, **kwargs):
        return self.manager.data(self, **kwargs)


class BackupRestoreManager(base.ManagerWithFind):
    resource_class = BackupRestore

    def _backup_meta_to_headers(self, fields):
        headers = {}
        fields_copy = copy.deepcopy(fields)

        # NOTE(flaper87): Convert to str, headers
        # that are not instance of basestring. All
        # headers will be encoded later, before the
        # request is sent.

        for key, value in six.iteritems(fields_copy):
            headers['%s' % key] = utils.to_str(value)
        return headers

    def _restore_meta_to_headers(self, fields):
        headers = {}
        fields_copy = copy.deepcopy(fields)

        # NOTE(flaper87): Convert to str, headers
        # that are not instance of basestring. All
        # headers will be encoded later, before the
        # request is sent.

        for key, value in six.iteritems(fields_copy):
            headers['%s' % key] = utils.to_str(value)
        return headers

    def list(self, **kwargs):
        pass

    def backup(self, **kwargs):
        """Backup daisy data.
        TODO(bcwaldon): document accepted params
        """
        fields = {}
        for field in kwargs:
            if field in BACKUP_PARAMS:
                fields[field] = kwargs[field]
            else:
                msg = 'install() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        url = '/v1/backup'
        resp, body = self.client.post(url, headers=None, data=fields)
        return BackupRestore(self, body)

    def restore(self, **kwargs):
        """Restore daisy data

        TODO(bcwaldon): document accepted params
        """
        fields = {}
        for field in kwargs:
            if field in RESTORE_PARAMS:
                fields[field] = kwargs[field]
            else:
                msg = 'install() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        url = '/v1/restore'
        resp, body = self.client.post(url, headers=None, data=fields)

    def backup_file_version(self, **kwargs):
        """Get version of backup file.

        TODO(bcwaldon): document accepted params
        """
        fields = {}
        for field in kwargs:
            if field in RESTORE_PARAMS:
                fields[field] = kwargs[field]
            else:
                msg = 'install() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        url = '/v1/backup_file_version'
        resp, body = self.client.post(url, headers=None, data=fields)
        return BackupRestore(self, body)

    def version(self, **kwargs):
        """Get internal or external version of daisy.

        TODO(bcwaldon): document accepted params
        """
        fields = {}
        for field in kwargs:
            if field in VERSION_PARAMS:
                fields[field] = kwargs[field]
            else:
                msg = 'install() got an unexpected keyword argument \'%s\''
                raise TypeError(msg % field)

        url = '/v1/version'
        resp, body = self.client.post(url, headers=None, data=fields)
        return BackupRestore(self, body)
