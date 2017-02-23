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
/install endpoint for tecs API
"""
from oslo_log import log as logging
import daisy.registry.client.v1.api as registry


LOG = logging.getLogger(__name__)


def get_used_networks(req, cluster_id):
    cluster_meta = registry.get_cluster_metadata(req.context, cluster_id)
    networks = registry.get_networks_detail(req.context, cluster_id)
    # only install os
    if cluster_meta.get('target_systems', '') == 'os':
        return [network for network in networks
                if network.get('network_type') in ['MANAGEMENT']]
    LOG.info("target_systems is %s" % cluster_meta.get('target_systems'))
    return []
