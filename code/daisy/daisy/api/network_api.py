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
/Initialize network configuration about neutron
"""
import time
from oslo_log import log as logging
import daisy.registry.client.v1.api as registry
from webob.exc import HTTPBadRequest
from neutronclient.v2_0 import client as clientv20
from daisy.common import exception
LOG = logging.getLogger(__name__)

class network(object):
    """
    network config
    """
    def __init__(self, req, neutron_host, keystone_host, cluster_id):
        registry.configure_registry_client()
        auth_url = 'http://' + keystone_host + ':35357/v2.0'
        end_url = 'http://' + neutron_host + ':9696'
        params = {'username': 'admin',
                  'ca_cert': None,
                  'tenant_name': 'admin',
                  'insecure': False,
                  'auth_url': auth_url,
                  'timeout': 30,
                  'password': 'keystone',
                  'endpoint_url': end_url,
                  'auth_strategy': 'keystone'
                  }
        self.cluster_id = cluster_id
        self.neutron = clientv20.Client(**params)
        try:
            cluster = registry.get_cluster_metadata(req.context, cluster_id)
        except exception.Invalid as e:
            LOG.exception(e.msg)
            raise HTTPBadRequest(explanation=e.msg, request=req)
        LOG.info("<<<CLUSTER:%s,NEUTRON HOST:%s,KEYSTOEN:%s>>>", cluster, neutron_host, keystone_host)
        if 'logic_networks' in cluster and cluster['logic_networks'] is not None:
            self.nets = cluster['logic_networks']
            #self._flat_network_uniqueness_check()
            if 'routers' in cluster and cluster['routers'] is not None:
                self.routers = cluster['routers']
            else:
                self.routers = []
            self._network_check()
            self.name_mappings = {}
            self._network_config()

    def _router_create(self, name):
        body = {}
        body['router'] = {"name": name, "admin_state_up": True}
        router = self.neutron.create_router(body)
        return router['router']['id']

    def _subnet_create(self, net_id, **kwargs):
        body = {}
        body['subnet'] = {'enable_dhcp': True,
                          'network_id': net_id,
                          'ip_version': 4
                          }
        for k in kwargs.keys():
            body['subnet'][k] = kwargs[k]
        LOG.info("<<<BODY:%s>>>", body)
        subnet = self.neutron.create_subnet(body)
        return subnet['subnet']['id']

    def _router_link(self):
        for router in self.routers:
            router_id = self._router_create(router['name'])
            if 'external_logic_network' in router:
                body = {'network_id': self.name_mappings[router['external_logic_network']]}
                self.neutron.add_gateway_router(router_id, body)
            if 'subnets' in router:
                for i in router['subnets']:
                    body = {'subnet_id': self.name_mappings[i]}
                    self.neutron.add_interface_router(router_id, body)

    def _net_subnet_same_router_check(self, ex_network, subnet):
        for router in self.routers:
            if 'external_logic_network' in router and router['external_logic_network'] == ex_network:
                if 'subnets' in router:
                    for i in router['subnets']:
                        if i == subnet:
                            return True
        return False

    def _subnet_check_and_create(self, net_id, subnet):
        kwargs = {}
        key_list = ['name', 'cidr', 'floating_ranges', 'dns_nameservers']
        for i in key_list:
            if i not in subnet:
                raise exception.Invalid()
        kwargs['name'] = subnet['name']
        kwargs['cidr'] = subnet['cidr']
        if len(subnet['dns_nameservers']) != 0:
            kwargs['dns_nameservers'] = subnet['dns_nameservers']
        kwargs['allocation_pools'] = []
        if len(subnet['floating_ranges']) != 0:
            for pool in subnet['floating_ranges']:
                if len(pool) != 2:
                    raise exception.Invalid()
                else:
                    alloc_pool = {}
                    alloc_pool['start'] = pool[0]
                    alloc_pool['end'] = pool[1]
                    kwargs['allocation_pools'].append(alloc_pool)
        if 'gateway' in subnet and subnet['gateway'] is not None:
            kwargs['gateway_ip'] = subnet['gateway']
        subnet_id = self._subnet_create(net_id, **kwargs)
        return subnet_id

    def _network_check(self):
        execute_times = 0
        while True:
            try:
                nets = self.neutron.list_networks()
            except:
                LOG.info("can not connect neutron server,sleep 5s,try")
                time.sleep(5)
                execute_times += 1
                if execute_times >= 60:
                    LOG.info("connect neutron server failed")
                    break
            else:
                LOG.info("connect neutron server sucessful")
                if 'networks' in nets and len(nets['networks']) > 0:
                    raise exception.Invalid()
                break

    def _flat_network_uniqueness_check(self):
        flat_mapping = []
        for net in self.nets:
            if net['physnet_name'] in flat_mapping:
                raise exception.Invalid()
            else:
                if net['segmentation_type'].strip() == 'flat':
                    flat_mapping.append(net['physnet_name'])

    def _network_config(self):
        for net in self.nets:
            body = {}
            if net['type'] == 'external':
                body['network'] = {'name': net['name'],
                                   'router:external': True,
                                   'provider:network_type': net['segmentation_type']}
                if net['segmentation_type'].strip() == 'flat':
                    body['network']['provider:physical_network'] = net['physnet_name']
                elif net['segmentation_type'].strip() == 'vxlan':
                    if 'segmentation_id' in net and net['segmentation_id'] is not None:
                        body['network']['provider:segmentation_id'] = net['segmentation_id']
                else:
                    if 'segmentation_id' in net and net['segmentation_id'] is not None:
                        body['network']['provider:segmentation_id'] = net['segmentation_id']
                    body['network']['provider:physical_network'] = net['physnet_name']
                if net['shared']:
                    body['network']['shared'] = True
                else:
                    body['network']['shared'] = False
                external = self.neutron.create_network(body)
                self.name_mappings[net['name']] = external['network']['id']
                last_create_subnet = []
                for subnet in net['subnets']:
                    if self._net_subnet_same_router_check(net['name'], subnet['name']):
                        last_create_subnet.append(subnet)
                    else:
                        subnet_id = self._subnet_check_and_create(external['network']['id'], subnet)
                        self.name_mappings[subnet['name']] = subnet_id
                for subnet in last_create_subnet:
                    subnet_id = self._subnet_check_and_create(external['network']['id'], subnet)
                    self.name_mappings[subnet['name']] = subnet_id
            else:
                body['network'] = {'name': net['name'],
                                   'provider:network_type': net['segmentation_type']}
                if net['segmentation_type'].strip() == 'vlan':
                    body['network']['provider:physical_network'] = net['physnet_name']
                if 'segmentation_id' in net and net['segmentation_id'] is not None:
                    body['network']['provider:segmentation_id'] = net['segmentation_id']
                if net['shared']:
                    body['network']['shared'] = True
                else:
                    body['network']['shared'] = False
                inner = self.neutron.create_network(body)
                self.name_mappings[net['name']] = inner['network']['id']
                for subnet in net['subnets']:
                    subnet_id = self._subnet_check_and_create(inner['network']['id'], subnet)
                    self.name_mappings[subnet['name']] = subnet_id
        self._router_link()
