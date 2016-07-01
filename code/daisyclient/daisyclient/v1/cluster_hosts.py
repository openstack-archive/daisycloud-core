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

from daisyclient.openstack.common.apiclient import base


class ClusterHost(base.Resource):

    def __repr__(self):
        return "<ClusterHost %s>" % self._info

    def delete(self):
        self.manager.delete(self)


class ClusterHostManager(base.ManagerWithFind):
    resource_class = ClusterHost

    def get(self, cluster_id, host_id):
        url = '/v1/clusters/%s/nodes/%s' % (cluster_id, host_id)
        resp, body = self.client.get(url)
        member = body['member']
        member['cluster_id'] = cluster_id
        return ClusterHost(self, member, loaded=True)

    def list(self, cluster=None, host=None):
        pass
#      out = []
#      if cluster and host:
#           out.extend(self._list_by_cluster_and_host(cluster, host))
#       elif cluster:
#           out.extend(self._list_by_cluster(cluster))
#       elif host:
#           out.extend(self._list_by_host(host))
#      else:
#          pass
#      return out

#  def _list_by_cluster_and_host(self, cluster, host):
#       url = '/v1/clusters/%s/nodes/%s' % (cluster, host)
#       resp, body = self.client.get(url)

#        out = []
#        for member in body['members']:
#            member['cluster'] = cluster
#         out.append(ClusterHost(self, member, loaded=True))
#     return out

# def _list_by_cluster(self, cluster):
#     url = '/v1/clusters/%s/nodes' % cluster

#        resp, body = self.client.get(url)
#        out = []
#        for member in body['members']:
#            member['cluster_id'] = cluster
#            out.append(ClusterHost(self, member, loaded=True))
#        return out

#    def _list_by_host(self, host):
#       url = '/v1/multi-clusters/nodes/%s' % host
#       resp, body = self.client.get(url)
#       out = []
#       for member in body['multi-clusters']:
#           member['host_id'] = host
#           out.append(ClusterHost(self, member, loaded=True))
#       return out

    def delete(self, cluster_id, host_id):
        self._delete("/v1/clusters/%s/nodes/%s" % (cluster_id, host_id))
