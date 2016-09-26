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
/orchestration for tecs API
"""

from oslo_config import cfg
from oslo_log import log as logging
from webob import exc

from daisy.common import exception
from daisyclient.v1 import client
import ConfigParser
from daisy.orchestration import manager

LOG = logging.getLogger(__name__)
CONF = cfg.CONF
    
def find_auto_scale_cluster():
    try:
        daisy_version = 1.0
        config_discoverd = ConfigParser.ConfigParser()
        config_discoverd.read("/etc/daisy/daisy-api.conf")
        bind_port = config_discoverd.get("DEFAULT", "bind_port")
        daisy_endpoint = "http://127.0.0.1:" + bind_port
        # daisy_endpoint="http://127.0.0.1:19292"
        daisy_client = client.Client(
            version=daisy_version, endpoint=daisy_endpoint)
        orchestrationManager = manager.OrchestrationManager()
        cluster_meta = {'auto_scale': '1'}
        params = {'filters': cluster_meta}
        clusters_gen = daisy_client.clusters.list(**params)
        clusters = [cluster.to_dict()
                    for cluster in clusters_gen if cluster.auto_scale == 1]
        if clusters:
            cluster_id = clusters[0]['id']
            params = {'filters': ''}
            hosts_gen = daisy_client.hosts.list(**params)
            init_hosts = [host.to_dict(
            ) for host in hosts_gen if host.os_status == "init" or
                host.os_status == "install-failed"]
            if not init_hosts:
                LOG.info("no init or install-failed host")
                return {"status": "no init host"}

            params = {'filters': {'cluster_id': cluster_id}}
            roles_gen = daisy_client.roles.list(**params)
            roles_in_cluster = [role.to_dict() for role in roles_gen]
            roles = [role for role in roles_in_cluster if role[
                'name'] == "CONTROLLER_LB" and role['status'] == "active"]
            if not roles:
                LOG.info("no active CONTROLLER_LB role")
                return {"status": "no active CONTROLLER_LB role"}
            for host in init_hosts:
                if host['status'] == "init":
                    host_info = daisy_client.hosts.get(host['id'])
                    if hasattr(host_info, "interfaces"):
                        scale_host = \
                            orchestrationManager.set_scale_host_interface(
                                cluster_id, host_info, daisy_client)
                        if scale_host:
                            host_meta = {
                                'hugepagesize': scale_host.hugepagesize,
                                'hugepages': scale_host.hugepages,
                                'isolcpus': scale_host.isolcpus,
                                'name': scale_host.name,
                                'os_version': scale_host.os_version_file,
                                'root_lv_size': scale_host.root_lv_size,
                                'swap_lv_size': scale_host.swap_lv_size,
                                'role': ['COMPUTER'],
                                'cluster': cluster_id,
                                'interfaces': scale_host.interfaces}
                            daisy_client.hosts.update(
                                host['id'], **host_meta)
                        else:
                            LOG.error("can not set scale host")
                            return {"status": "no scale host"}

                    else:
                        LOG.info("not interfaces in host %s" % host['id'])
                        raise exc.HTTPNotFound(
                            "not interfaces in host %s" % host['id'])
            orchestrationManager._os_install(
                cluster_id, daisy_client)
    except exception.Invalid as e:
        LOG.exception(e.message)
