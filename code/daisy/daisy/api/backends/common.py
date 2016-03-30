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
import copy
import subprocess
import time

import traceback
import webob.exc
from oslo_config import cfg
from oslo_log import log as logging
from webob.exc import HTTPBadRequest
from webob.exc import HTTPForbidden

from threading import Thread

from daisy import i18n
from daisy import notifier

from daisy.api import policy
import daisy.api.v1

from daisy.common import exception
import daisy.registry.client.v1.api as registry


try:
    import simplejson as json
except ImportError:
    import json

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE
_LI = i18n._LI
_LW = i18n._LW

daisy_path = '/var/lib/daisy/'
tecs_backend_name = "tecs"
zenic_backend_name = "zenic"
proton_backend_name = "proton"
os_install_start_time = 0.0

def subprocess_call(command,file=None):
    if file:
        return_code = subprocess.call(command,
                                      shell=True,
                                      stdout=file,
                                      stderr=file)
    else:
        return_code = subprocess.call(command,
                                      shell=True,
                                      stdout=open('/dev/null', 'w'),
                                      stderr=subprocess.STDOUT)
    if return_code != 0:
        msg = "execute '%s' failed by subprocess call." % command
        raise exception.SubprocessCmdFailed(msg)
    
def get_host_detail(req, host_id):
    try:
        host_detail = registry.get_host_metadata(req.context, host_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return host_detail
    
def get_roles_detail(req):
    try:
        roles = registry.get_roles_detail(req.context)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return roles

def get_cluster_roles_detail(req, cluster_id):
    try:
        params = {'cluster_id':cluster_id}
        roles = registry.get_roles_detail(req.context, **params)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return roles
    
def get_hosts_of_role(req, role_id):
    try:
        hosts = registry.get_role_host_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return hosts
    
def get_role_detail(req, role_id):
    try:
        role = registry.get_role_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return role

def update_role(req, role_id,role_meta):
    try:
        registry.update_role_metadata(req.context, role_id, role_meta)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)

def update_role_host(req, role_id, role_host):
    try:
        registry.update_role_host_metadata(req.context, role_id, role_host)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)  

def delete_role_hosts(req, role_id):
    try:
        registry.delete_role_host_metadata(req.context, role_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
 
def get_cluster_networks_detail(req, cluster_id):
    try:
        networks = registry.get_networks_detail(req.context, cluster_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return networks

def get_assigned_network(req, host_interface_id, network_id):
    try:
        assigned_network = registry.get_assigned_network(req.context, host_interface_id, network_id)
    except exception.Invalid as e:
        raise HTTPBadRequest(explanation=e.msg, request=req)
    return assigned_network

def _ping_hosts_test(ips):
    ping_cmd = 'fping'
    for ip in set(ips):
        ping_cmd = ping_cmd + ' ' + ip
    obj = subprocess.Popen(ping_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdoutput, erroutput) = obj.communicate()
    _returncode = obj.returncode
    if _returncode == 0 or _returncode == 1:
        ping_result = stdoutput.split('\n')
        unreachable_hosts = [result.split()[0] for result in ping_result if result and result.split()[2] != 'alive']
    else:
        msg = "ping failed beaceuse there is invlid ip in %s" % ips
        raise exception.InvalidIP(msg)
    return unreachable_hosts
    

def check_ping_hosts(ping_ips, max_ping_times):
    if not ping_ips:
        LOG.info(_("no ip got for ping test"))
        return ping_ips
    ping_count = 0
    time_step = 5
    LOG.info(_("begin ping test for %s" % ','.join(ping_ips)))
    while True:
        if ping_count == 0:
            ips = _ping_hosts_test(ping_ips)
        else:
            ips = _ping_hosts_test(ips)

        ping_count += 1
        if ips:
            LOG.debug(_("ping host %s for %s times" % (','.join(ips), ping_count)))
            if ping_count >= max_ping_times:
                LOG.info(_("ping host %s timeout for %ss" % (','.join(ips), ping_count*time_step)))
                return ips
            time.sleep(time_step)
        else:
            LOG.info(_("ping %s successfully" % ','.join(ping_ips)))
            return ips   

def _ping_reachable_to_unreachable_host_test(ip,max_ping_times):
    ping_cmd = 'fping'
    ping_cmd = ping_cmd + ' ' + ip
    ping_count = 0
    time_step = 5
    while True:
        obj = subprocess.Popen(ping_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdoutput, erroutput) = obj.communicate()
        _returncode = obj.returncode
        if _returncode != 0:
            return True
        ping_count += 1
        if ping_count >= max_ping_times:
            LOG.info(_("ping host %s timeout for %ss" % (ip, ping_count*time_step)))
            return False
        time.sleep(time_step)
    return False
    
def _ping_unreachable_to_reachable_host_test(ip, max_ping_times):
    ping_count = 0
    time_step = 5
    ping_cmd = 'fping'
    ping_cmd = ping_cmd + ' ' + ip
    while True:
        obj = subprocess.Popen(ping_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (stdoutput, erroutput) = obj.communicate()
        _returncode = obj.returncode
        if _returncode == 0:
            return True
        ping_count += 1
        if ping_count >= max_ping_times:
            LOG.info(_("ping host %s timeout for %ss" % (ip, ping_count*time_step)))
            return False
        time.sleep(time_step)
    return False
    
def check_reboot_ping(ip):
    stop_max_ping_times = 360 #ha host reboot may spend 20 min,so timeout time is 30min
    start_max_ping_times = 60
    _ping_reachable_to_unreachable_host_test(ip, stop_max_ping_times)
    _ping_unreachable_to_reachable_host_test(ip, start_max_ping_times)
    time.sleep(5)
    
def cidr_to_netmask(cidr):
    ip_netmask = cidr.split('/')
    if len(ip_netmask) != 2 or not ip_netmask[1]:
        raise exception.InvalidNetworkConfig("cidr is not valid")

    cidr_end = ip_netmask[1]
    mask = ~(2**(32 - int(cidr_end)) - 1)
    inter_ip = lambda x: '.'.join([str(x/(256**i)%256) for i in range(3,-1,-1)])
    netmask = inter_ip(mask)

    return netmask