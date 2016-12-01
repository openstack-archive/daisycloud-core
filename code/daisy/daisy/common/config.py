
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

"""
Routines for configuring Glance
"""

import logging
import logging.config
import logging.handlers
import os
import tempfile

from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_policy import policy
from paste import deploy

from daisy import i18n
from daisy.version import version_info as version

_ = i18n._

paste_deploy_opts = [
    cfg.StrOpt('flavor',
               help=_('Partial name of a pipeline in your paste configuration '
                      'file with the service name removed. For example, if '
                      'your paste section name is '
                      '[pipeline:glance-api-keystone] use the value '
                      '"keystone"')),
    cfg.StrOpt('config_file',
               help=_('Name of the paste configuration file.')),
]
common_opts = [
    cfg.StrOpt('max_parallel_os_number', default=10,
               help='Maximum number of hosts install os at the same time.'),
    cfg.StrOpt('max_parallel_os_upgrade_number', default=10,
               help='Maximum number of hosts upgrade os at the same time.'),
    cfg.StrOpt('data_api', default='daisy.db.sqlalchemy.api',
               help=_('Python module path of data access API')),
    cfg.IntOpt('limit_param_default', default=25,
               help=_('Default value for the number of items returned by a '
                      'request if not specified explicitly in the request')),
    cfg.IntOpt('api_limit_max', default=1000,
               help=_('Maximum permissible number of items that could be '
                      'returned by a request')),
    cfg.BoolOpt('show_image_direct_url', default=False,
                help=_('Whether to include the backend image storage location '
                       'in image properties. Revealing storage location can '
                       'be a security risk, so use this setting with '
                       'caution!')),
    cfg.BoolOpt('show_multiple_locations', default=False,
                help=_('Whether to include the backend image locations '
                       'in image properties. '
                       'For example, if using the file system store a URL of '
                       '"file:///path/to/image" will be returned to the user '
                       'in the \'direct_url\' meta-data field. '
                       'Revealing storage location can '
                       'be a security risk, so use this setting with '
                       'caution!  The overrides show_image_direct_url.')),
    cfg.IntOpt('image_size_cap', default=1099511627776,
               help=_("Maximum size of image a user can upload in bytes. "
                      "Defaults to 1099511627776 bytes (1 TB)."
                      "WARNING: this value should only be increased after "
                      "careful consideration and must be set to a value under "
                      "8 EB (9223372036854775808).")),
    cfg.StrOpt('user_storage_quota', default='0',
               help=_("Set a system wide quota for every user. This value is "
                      "the total capacity that a user can use across "
                      "all storage systems. A value of 0 means unlimited."
                      "Optional unit can be specified for the value. Accepted "
                      "units are B, KB, MB, GB and TB representing "
                      "Bytes, KiloBytes, MegaBytes, GigaBytes and TeraBytes "
                      "respectively. If no unit is specified then Bytes is "
                      "assumed. Note that there should not be any space "
                      "between value and unit and units are case sensitive.")),
    cfg.BoolOpt('enable_v1_api', default=True,
                help=_("Deploy the v1 OpenStack Images API.")),
    cfg.BoolOpt('enable_v2_api', default=True,
                help=_("Deploy the v2 OpenStack Images API.")),
    cfg.BoolOpt('enable_v1_registry', default=True,
                help=_("Deploy the v1 OpenStack Registry API.")),
    cfg.BoolOpt('enable_v2_registry', default=True,
                help=_("Deploy the v2 OpenStack Registry API.")),
    cfg.StrOpt('pydev_worker_debug_host',
               help=_('The hostname/IP of the pydev process listening for '
                      'debug connections')),
    cfg.IntOpt('pydev_worker_debug_port', default=5678,
               help=_('The port on which a pydev process is listening for '
                      'connections.')),
    cfg.StrOpt('digest_algorithm', default='sha1',
               help=_('Digest algorithm which will be used for digital '
                      'signature; the default is sha1 the default in Kilo '
                      'for a smooth upgrade process, and it will be updated '
                      'with sha256 in next release(L). Use the command '
                      '"openssl list-message-digest-algorithms" to get the '
                      'available algorithms supported by the version of '
                      'OpenSSL on the platform. Examples are "sha1", '
                      '"sha256", "sha512", etc.')),
]

CONF = cfg.CONF
CONF.register_opts(paste_deploy_opts, group='paste_deploy')
CONF.register_opts(common_opts)
policy.Enforcer(CONF)


def parse_args(args=None, usage=None, default_config_files=None):
    if "OSLO_LOCK_PATH" not in os.environ:
        lockutils.set_defaults(tempfile.gettempdir())

    CONF(args=args,
         project='daisy',
         version=version.cached_version_string(),
         usage=usage,
         default_config_files=default_config_files)


def _get_deployment_flavor(flavor=None):
    """
    Retrieve the paste_deploy.flavor config item, formatted appropriately
    for appending to the application name.

    :param flavor: if specified, use this setting rather than the
                   paste_deploy.flavor configuration setting
    """
    if not flavor:
        flavor = CONF.paste_deploy.flavor
    return '' if not flavor else ('-' + flavor)


def _get_paste_config_path():
    paste_suffix = '-paste.ini'
    conf_suffix = '.conf'
    if CONF.config_file:
        # Assume paste config is in a paste.ini file corresponding
        # to the last config file
        path = CONF.config_file[-1].replace(conf_suffix, paste_suffix)
    else:
        path = CONF.prog + paste_suffix
    return CONF.find_file(os.path.basename(path))


def _get_deployment_config_file():
    """
    Retrieve the deployment_config_file config item, formatted as an
    absolute pathname.
    """
    path = CONF.paste_deploy.config_file
    if not path:
        path = _get_paste_config_path()
    if not path:
        msg = _("Unable to locate paste config file for %s.") % CONF.prog
        raise RuntimeError(msg)
    return os.path.abspath(path)


def load_paste_app(app_name, flavor=None, conf_file=None):
    """
    Builds and returns a WSGI app from a paste config file.

    We assume the last config file specified in the supplied ConfigOpts
    object is the paste config file, if conf_file is None.

    :param app_name: name of the application to load
    :param flavor: name of the variant of the application to load
    :param conf_file: path to the paste config file

    :raises RuntimeError when config file cannot be located or application
            cannot be loaded from config file
    """
    # append the deployment flavor to the application name,
    # in order to identify the appropriate paste pipeline
    app_name += _get_deployment_flavor(flavor)

    if not conf_file:
        conf_file = _get_deployment_config_file()

    try:
        logger = logging.getLogger(__name__)
        logger.debug("Loading %(app_name)s from %(conf_file)s",
                     {'conf_file': conf_file, 'app_name': app_name})

        app = deploy.loadapp("config:%s" % conf_file, name=app_name)

        # Log the options used when starting if we're in debug mode...
        if CONF.debug:
            CONF.log_opt_values(logger, logging.DEBUG)

        return app
    except (LookupError, ImportError) as e:
        msg = (_("Unable to load %(app_name)s from "
                 "configuration file %(conf_file)s."
                 "\nGot: %(e)r") % {'app_name': app_name,
                                    'conf_file': conf_file,
                                    'e': e})
        logger.error(msg)
        raise RuntimeError(msg)
