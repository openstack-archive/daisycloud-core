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
/hosts endpoint for Daisy v1 API
"""
import datetime
import os
import subprocess
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden

from daisy import i18n
from daisy import notifier

from daisy.api import policy
import daisy.api.v1
from daisy.common import exception
from daisy.common import utils
from daisy.common import wsgi
import daisy.registry.client.v1.api as registry
from daisy.api.v1 import controller
from daisy.api.v1 import filters
import daisy.api.backends.common as daisy_cmn
from daisy.version import version_info


LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW
SUPPORTED_PARAMS = daisy.api.v1.SUPPORTED_PARAMS
SUPPORTED_FILTERS = daisy.api.v1.SUPPORTED_FILTERS
ACTIVE_IMMUTABLE = daisy.api.v1.ACTIVE_IMMUTABLE
BACK_PATH = '/home/daisy_backup/'


class Controller(controller.BaseController):
    """
    WSGI controller for hosts resource in Daisy v1 API

    The hosts resource API is a RESTful web service for host data. The API
    is as follows::

        GET  /hosts -- Returns a set of brief metadata about hosts
        GET  /hosts/detail -- Returns a set of detailed metadata about
                              hosts
        HEAD /hosts/<ID> -- Return metadata about an host with id <ID>
        GET  /hosts/<ID> -- Return host data for host with id <ID>
        POST /hosts -- Store host data and return metadata about the
                        newly-stored host
        PUT  /hosts/<ID> -- Update host metadata and/or upload host
                            data for a previously-reserved host
        DELETE /hosts/<ID> -- Delete the host with id <ID>
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

    def hostname(self):
        if os.name == 'posix':
            host = os.popen('echo $HOSTNAME')
            try:
                return host.read()
            finally:
                host.close()
        else:
            return 'Unkwon hostname'

    def check_file_format(self, req, file_meta):
        if not os.path.exists(file_meta.get('backup_file_path', '')):
            msg = 'File not exists!'
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg, request=req,
                                content_type="text/plain")

        if not file_meta['backup_file_path'].endswith('.tar.gz'):
            msg = 'File format not supported! .tar.gz format is required!'
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg, request=req,
                                content_type="text/plain")

    @utils.mutating
    def backup(self, req):
        """
        Backup daisy data..

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if backup failed
        """
        version = self.version(req, {'type': 'internal'})
        date_str = filter(lambda x: x.isdigit(),
                          str(datetime.datetime.now())[:19])
        backup_file_name = '{0}_{1}_{2}.tar.gz'.format(
            self.hostname().strip(), date_str, version['daisy_version'])

        scripts = [
            'test -d {0}daisy_tmp||mkdir -p {0}daisy_tmp'.format(BACK_PATH),
            'echo {0}>{1}daisy_tmp/version.conf'.format(
                version['daisy_version'], BACK_PATH),
            'cp /home/daisy_install/daisy.conf {0}/daisy_tmp'.format(
                BACK_PATH),
            'mysqldump --all-databases > {0}daisy_tmp/database.sql'.format(
                BACK_PATH),
            'tar -zcvf {0}{1} -C {0} daisy_tmp >/dev/null 2>&1'.format(
                BACK_PATH, backup_file_name),
            'chmod 777 {0} {0}{1}'.format(BACK_PATH, backup_file_name),
            'rm -rf {0}daisy_tmp'.format(BACK_PATH)
        ]

        daisy_cmn.run_scrip(scripts, msg='Backup file failed!')
        return {"backup_file": BACK_PATH + backup_file_name}

    @utils.mutating
    def restore(self, req, file_meta):
        """
        Restore daisy data.
        :param req: The WSGI/Webob Request object
        :param file_meta: The daisy backup file path
        :raises HTTPBadRequest if restore failed
        """
        self.check_file_format(req, file_meta)
        restore_scripts = [
            'test -d {0} || mkdir {0}'.format(BACK_PATH),
            'test -d {0} || mkdir {0}'.format('/home/daisy_install/'),
            'tar -zxvf {1} -C {0}>/dev/null 2>&1'.format(
                BACK_PATH, file_meta['backup_file_path']),
            'mysql < {0}daisy_tmp/database.sql'.format(BACK_PATH),
            'cp {0}daisy_tmp/daisy.conf /home/daisy_install/'.format(
                BACK_PATH),
            'rm -rf {0}daisy_tmp'.format(BACK_PATH)
        ]

        daisy_cmn.run_scrip(restore_scripts, msg='Restore failed!')
        LOG.info('Restore successfully')

    @utils.mutating
    def get_backup_file_version(self, req, file_meta):
        """
        Get version of daisy backup file.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if can't get version of backup file
        """
        self.check_file_format(req, file_meta)
        scripts = [
            'test -d {0} || mkdir {0}'.format(BACK_PATH),
            'tar -zxvf {0} -C {1}>/dev/null 2>&1'.format(
                file_meta['backup_file_path'], BACK_PATH)
        ]

        daisy_cmn.run_scrip(scripts, msg='Decompression file failed!')

        try:
            version = subprocess.check_output(
                'cat {0}daisy_tmp/version.conf'.format(BACK_PATH),
                shell=True, stderr=subprocess.STDOUT).strip()
        except:
            msg = 'Error occurred when running scripts to get version of' \
                  ' backup file!'
            LOG.error(msg)
            raise HTTPForbidden(explanation=msg, request=req,
                                content_type="text/plain")
        daisy_cmn.run_scrip(['rm -rf {0}daisy_tmp'.format(BACK_PATH)])
        return {"backup_file_version": version}

    @utils.mutating
    def version(self, req, version):
        """
        Get version of daisy.

        :param req: The WSGI/Webob Request object

        :raises HTTPBadRequest if can't get version of daisy
        """
        if version.get('type') == 'internal':
            return {"daisy_version": version_info.version_string_with_vcs()}
        else:
            # reserved for external version
            return {"daisy_version": '1.0.0-1.1.0'}


class BackupRestoreDeserializer(wsgi.JSONRequestDeserializer):
    """Handles deserialization of specific controller method requests."""

    def _deserialize(self, request):
        result = {}
        result['file_meta'] = utils.get_dict_meta(request)
        return result

    def backup(self, request):
        return {}

    def restore(self, request):
        return self._deserialize(request)

    def get_backup_file_version(self, request):
        return self._deserialize(request)

    def version(self, request):
        result = {}
        result['version'] = utils.get_dict_meta(request)
        return result


class BackupRestoreSerializer(wsgi.JSONResponseSerializer):
    """Handles serialization of specific controller method responses."""

    def __init__(self):
        self.notifier = notifier.Notifier()

    def backup(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def restore(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def get_backup_file_version(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response

    def version(self, response, result):
        response.status = 201
        response.headers['Content-Type'] = 'application/json'
        response.body = self.to_json(result)
        return response


def create_resource():
    """Version resource factory method"""
    deserializer = BackupRestoreDeserializer()
    serializer = BackupRestoreSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
