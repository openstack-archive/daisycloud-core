# Copyright (c) 2014 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import copy
import itertools

import daisy.api.middleware.context
import daisy.api.versions
import daisy.common.config
import daisy.common.property_utils
import daisy.common.rpc
import daisy.common.wsgi
import daisy.image_cache
import daisy.image_cache.drivers.sqlite
import daisy.notifier
import daisy.registry
import daisy.registry.client
import daisy.registry.client.v1.api

__all__ = [
    'list_api_opts',
    'list_registry_opts',
    'list_cache_opts',
    'list_manage_opts'
]


_api_opts = [
    (None, list(itertools.chain(
        daisy.api.middleware.context.context_opts,
        daisy.api.versions.versions_opts,
        daisy.common.config.common_opts,
        daisy.common.property_utils.property_opts,
        daisy.common.rpc.rpc_opts,
        daisy.common.wsgi.bind_opts,
        daisy.common.wsgi.eventlet_opts,
        daisy.common.wsgi.socket_opts,
        daisy.image_cache.drivers.sqlite.sqlite_opts,
        daisy.image_cache.image_cache_opts,
        daisy.notifier.notifier_opts,
        daisy.registry.registry_addr_opts,
        daisy.registry.client.registry_client_ctx_opts,
        daisy.registry.client.registry_client_opts,
        daisy.registry.client.v1.api.registry_client_ctx_opts))),
    ('task', daisy.common.config.task_opts),
    ('paste_deploy', daisy.common.config.paste_deploy_opts)
]
_registry_opts = [
    (None, list(itertools.chain(
        daisy.api.middleware.context.context_opts,
        daisy.common.config.common_opts,
        daisy.common.wsgi.bind_opts,
        daisy.common.wsgi.socket_opts,
        daisy.common.wsgi.eventlet_opts))),
    ('paste_deploy', daisy.common.config.paste_deploy_opts)
]
_cache_opts = [
    (None, list(itertools.chain(
        daisy.common.config.common_opts,
        daisy.image_cache.drivers.sqlite.sqlite_opts,
        daisy.image_cache.image_cache_opts,
        daisy.registry.registry_addr_opts,
        daisy.registry.client.registry_client_ctx_opts))),
]
_manage_opts = [
    (None, [])
]


def list_api_opts():
    """Return a list of oslo_config options available in Glance API service.

    Each element of the list is a tuple. The first element is the name of the
    group under which the list of elements in the second element will be
    registered. A group name of None corresponds to the [DEFAULT] group in
    config files.

    This function is also discoverable via the 'daisy.api' entry point
    under the 'oslo_config.opts' namespace.

    The purpose of this is to allow tools like the Oslo sample config file
    generator to discover the options exposed to users by daisy.

    :returns: a list of (group_name, opts) tuples
    """

    return [(g, copy.deepcopy(o)) for g, o in _api_opts]


def list_registry_opts():
    """Return a list of oslo_config options available in Glance Registry
    service.
    """
    return [(g, copy.deepcopy(o)) for g, o in _registry_opts]


def list_cache_opts():
    """Return a list of oslo_config options available in Glance Cache
    service.
    """
    return [(g, copy.deepcopy(o)) for g, o in _cache_opts]


def list_manage_opts():
    """Return a list of oslo_config options available in Glance manage."""
    return [(g, copy.deepcopy(o)) for g, o in _manage_opts]
