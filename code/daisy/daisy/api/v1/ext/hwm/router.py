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

from daisy.api.v1.ext.hwm import hwm_host


class APIExtension(object):

    """
    Class for API extension.
    """

    def __init__(self, mapper):
        hosts_resource = hwm_host.create_resource()

        mapper.connect("/hwm_nodes",
                       controller=hosts_resource,
                       action='update_hwm_host',
                       conditions={'method': ['POST']})
