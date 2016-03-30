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

from daisyclient.common import http
from daisyclient.common import utils
from daisyclient.v1.image_members import ImageMemberManager
from daisyclient.v1.images import ImageManager
from daisyclient.v1.hosts import HostManager
from daisyclient.v1.clusters import ClusterManager
from daisyclient.v1.components import ComponentManager
from daisyclient.v1.services import ServiceManager
from daisyclient.v1.roles import RoleManager
from daisyclient.v1.cluster_hosts import ClusterHostManager
from daisyclient.v1.config_files import Config_fileManager
from daisyclient.v1.config_sets import Config_setManager
from daisyclient.v1.networks import NetworkManager
from daisyclient.v1.configs import ConfigManager
from daisyclient.v1.install import InstallManager
from daisyclient.v1.uninstall import UninstallManager
from daisyclient.v1.update import UpdateManager
from daisyclient.v1.disk_array import DiskArrayManager
from daisyclient.v1.template import TemplateManager
class Client(object):
    """Client for the OpenStack Images v1 API.

    :param string endpoint: A user-supplied endpoint URL for the glance
                            service.
    :param string token: Token for authentication.
    :param integer timeout: Allows customization of the timeout for client
                            http requests. (optional)
    """

    def __init__(self, endpoint, *args, **kwargs):
        """Initialize a new client for the daisy v1 API."""
        endpoint, version = utils.strip_version(endpoint)
        self.version = version or 1.0
        self.http_client = http.HTTPClient(endpoint, *args, **kwargs)
        self.images = ImageManager(self.http_client)
        self.image_members = ImageMemberManager(self.http_client)
        self.hosts = HostManager(self.http_client)
        self.clusters = ClusterManager(self.http_client)
        self.components = ComponentManager(self.http_client)
        self.services = ServiceManager(self.http_client)
        self.roles = RoleManager(self.http_client)
        self.cluster_hosts = ClusterHostManager(self.http_client)
        self.config_files = Config_fileManager(self.http_client)
        self.config_sets = Config_setManager(self.http_client)
        self.networks = NetworkManager(self.http_client)
        self.configs = ConfigManager(self.http_client)
        self.install = InstallManager(self.http_client)
        self.uninstall = UninstallManager(self.http_client)
        self.update = UpdateManager(self.http_client)
        self.disk_array = DiskArrayManager(self.http_client)
        self.template = TemplateManager(self.http_client)
