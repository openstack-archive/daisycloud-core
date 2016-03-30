#
#   Copyright ZTE
#   Daisy Tools Dashboard
#

from django.http import HttpResponse
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django import shortcuts
from django import template
from django.core.urlresolvers import reverse_lazy
from django.utils.translation import ugettext_lazy as _

from daisyclient.v1 import client as daisy_client

import json

from horizon import messages
from horizon import exceptions
from horizon import forms
from horizon import tables

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.deploy import wizard_cache

import logging
LOG = logging.getLogger(__name__)


def format_deploy_info(host_list):
    data = []
    on_going_host_status_list = []
    failed_host_status_list = []
    success_host_status_list = []

    for host in host_list:
        if not hasattr(host, 'role_status'):
            host.role_status = ''
        if not hasattr(host, 'role_progress'):
            host.role_progress = 0  

        if host.os_progress == None:
            host.os_progress = 0
        if host.messages == None:
            host.messages = " "
        if host.role_status == "active" and host.os_status == "active":
            success_host_info = {"name": host.name,
                                 "os_status": host.os_status,
                                 "os_progress": host.os_progress,
                                 "role_status": host.role_status,
                                 "role_progress": host.role_progress
                                 }
            success_host_status_list.append(success_host_info)
        elif host.role_status == "installing " or host.os_status == "installing ":
            on_going_host_info = {"name": host.name,
                                  "os_status": host.os_status,
                                  "os_progress": host.os_progress,
                                  "role_status": host.role_status,
                                  "role_progress": host.role_progress
                                  }
            on_going_host_status_list.append(on_going_host_info)
        else:
            failed_host_info = {"name": host.name,
                                "os_status": host.os_status,
                                "os_progress": host.os_progress,
                                "role_status": host.role_status,
                                "role_progress": host.role_progress,
                                "messages": host.messages}
            failed_host_status_list.append(failed_host_info)
            
    data.append({
        "host_status": "deploying",
        "count": len(on_going_host_status_list),
        "host_status_list": on_going_host_status_list
    })
    data.append({
        "host_status": "failed",
        "count": len(failed_host_status_list),
        "host_status_list": failed_host_status_list
    })
    data.append({
        "host_status": "success",
        "count": len(success_host_status_list),
        "host_status_list": success_host_status_list
    })
    return data


class AddHostForm(forms.SelfHandlingForm):
    name = forms.CharField(label=_("Name"), 
                           max_length=255)
    description = forms.CharField(label=_("Description"),
                                  widget=forms.Textarea,
                                  required=False)

    def handle(self, request, data):
        try:
            api.daisy.host_add(request,
                               name=data["name"],
                               description=data["description"])
            return True
        except Exception:
            exceptions.handle(request, "Failed to add host!")


class AddHostView(forms.ModalFormView):
    form_class = AddHostForm
    template_name = "environment/deploy/addhost.html"    

    def get_context_data(self, **kwargs):
        context = super(AddHostView, self).get_context_data(**kwargs)
        context["cluster_id"] = self.kwargs["cluster_id"]
        return context

    def get_success_url(self):
        return ('/dashboard/environment/deploy/%s/hosts'
                % self.kwargs["cluster_id"])


class DeployView(generic.TemplateView):
    template_name = "environment/deploy/index.html"
    
    def get_data(self, request, cluster_id):
        try:
            qp = {"cluster_id": cluster_id}
            host_list = api.daisy.host_list(request, filters=qp)
            return format_deploy_info(host_list)
        except Exception:
            exceptions.handle(request, "cluster_host_list failed!")
            data = []
            return data
        return data

    def get_context_data_ext(self, cls, **kwargs):
        context = super(DeployView, self).get_context_data(**kwargs)
        context["pre_url"] = "/dashboard/environment/"
        context["cluster_id"] = cls.kwargs["cluster_id"]

        clusters = api.daisy.cluster_list(cls.request)
        context["cluster_name"] = ""

        for c in clusters:
            if c.id == context["cluster_id"]:
                context["cluster_name"] = c.name

        context["data"] = self.get_data(cls.request, context["cluster_id"])
        return context

    def get_context_data(self, **kwargs):
        return self.get_context_data_ext(self, **kwargs)


@csrf_exempt
def get_deploy_info_time(request):
    data = json.loads(request.body)
    msg = ('Cluster modify request.body::::::: %s') % request.body
    LOG.info(msg)
    cluster_info = data["cluster_info"]
    try:
        qp = {"cluster_id": cluster_info["cluster_id"]}
        host_list = api.daisy.host_list(request, filters=qp)
        deploy_info = format_deploy_info(host_list)
        response = HttpResponse(json.dumps(deploy_info), content_type="application/json")
        response.status_code = 200
        return response
    except Exception:
        exceptions.handle(request, "Delete failed!")
        response = HttpResponse()
        response.status_code = 500
        return response


def do_deploy(request, cluster_id):
    try:
        api.daisy.install_cluster(request, cluster_id)
        response = HttpResponse()
        response.status_code = 200
        wizard_cache.clean_cache(cluster_id)
        return response
    except Exception as e:
        response = HttpResponse()
        response.status_code = 200
        return response            


class HostsView(generic.TemplateView):
    template_name = "environment/deploy/hosts.html"

    def get_data(self):
        #get all roles
        try:
            roles = api.daisy.role_list(self.request)
        except:
            roles = []
            exceptions.handle(self.request, "Unable to retrieve roles!")

        #get allocated nodes
        try:
            cluster_hosts = api.daisy.cluster_host_list(self.request, self.kwargs["cluster_id"])
            host_ids = [h.id for h in cluster_hosts]
        except:
            exceptions.handle(self.request, "Unable to retrieve hosts in cluster!")

        #get aviliable nodes
        try:
            hosts = api.daisy.host_list(self.request)

            nodes_unallocated = []
            nodes_allocated = []
            for node in hosts:
                if node.status == 'init':
                    nodes_unallocated.append(node)     
                else:
                    if node.id in host_ids:
                        nodes_allocated.append(node)
        except:
            nodes_unallocated = []    
            nodes_allocated = []
            exceptions.handle(self.request, "Unable to retrieve hosts!")

        return roles, nodes_unallocated, nodes_allocated

    def get_context_data(self, **kwargs):
        context = super(HostsView, self).get_context_data(**kwargs)
        
        roles, nodes_unallocated, nodes_allocated = self.get_data()

        cluster_id = self.kwargs["cluster_id"]

        context['roles'] = [role for role in roles if role.cluster_id == cluster_id]

        context["nodes_allocated"] = nodes_allocated;
        context["nodes_unallocated"] = nodes_unallocated;

        context['cluster_id'] = cluster_id
        clusters = api.daisy.cluster_list(self.request)
        context["cluster_name"] = ""
        
        for c in clusters:
            if c.id == cluster_id:
                context["cluster_name"] = c.name

        pre_url = self.request.META.get('HTTP_REFERER',"/")
        LOG.warning("################### pre_url = %s ###########################" % pre_url)
        if "network" in pre_url:
            context["pre_url"] = "/dashboard/environment/network/" + cluster_id + "/routes"
        else:
            context["pre_url"] = "/dashboard/environment/cluster/" + cluster_id + "/overview"

        return context


def allocate_host(request, cluster_id):    
    response = HttpResponse()

    data = json.loads(request.body)

    hosts = data["hosts"]
    roles = data["roles"]

    try:
        for host_id in hosts:
            api.daisy.host_update(request, host_id, cluster=cluster_id, role=roles)
            
    except:
        exceptions.handle(request, "add host to cluster failed!")
        response.status_code = 500        
        return response

    wizard_cache.set_cache(cluster_id, "selecthosts", 2)
    response.status_code = 200
    return response


def remove_host(request, cluster_id):  
    response = HttpResponse()  

    data = json.loads(request.body)

    hosts = data["hosts"]

    try:
        for host_id in hosts:
            api.daisy.delete_host_from_cluster(request, cluster_id, host_id)
    except:
        exceptions.handle(request, "delete host from cluster failed!")
        response.status_code = 500        
        return response

    response.status_code = 200
    return response        


def update_host_nics(request, cluster_id, host_id):
    response = HttpResponse()  

    data = json.loads(request.body)

    try:
        host = get_host_by_id(request, host_id)
        host_dict = host.to_dict()
        host_dict['cluster'] = cluster_id
        #LOG.warning("############## host_dict[interfaces] = %s #################" % host_dict["interfaces"])
        LOG.warning("-----------------updat interfaces--start---------- data[interfaces] = %s -----------end-----------" % data["interfaces"])
        host_interfaces = update_interfaces(host_dict["interfaces"], data["interfaces"])
        LOG.warning("-------!!!!!!!!!!!!----------updat interfaces------------ interfaces = %s ----!!!!!!!!!!------------" % host_interfaces)
        #host_dict["interfaces"] = host_interfaces
        '''for nic in host_interfaces:
            del nic['current_speed']
            del nic['deleted_at']
            del nic['deleted']
            del nic['pci']
            del nic['max_speed']
            if nic['assigned_networks'] == []:
                del nic['assigned_networks']'''
        #clean_none_attr(host_dict)
        LOG.info("$$$$$$$$$$$$$$ host_interfaces: %s" %host_interfaces)

        #api.daisy.host_update(request, host_id, **host_dict)
        api.daisy.host_update(request, host_id, cluster=cluster_id, interfaces=host_interfaces)
        messages.success(request, "Update host interface success!")
    except:
        exceptions.handle(request, "update host nics failed!")
        response.status_code = 500        
        return response

    response.status_code = 200
    return response       


def get_host_by_id(request, host_id):
    host = api.daisy.host_get(request, host_id)
    return host


def update_host_ipmis(request, cluster_id, host_id):
    response = HttpResponse()  

    data = json.loads(request.body)

    try:
        host = get_host_by_id(request, host_id)
        host_dict = host.to_dict()
        LOG.info("!!!!!!!!!!!! Before clean host_dict: " % host_dict)

        clean_none_attr(host_dict)
        LOG.info("$$$$$$$$$$$$$$ After clean host_dict: %s" % host_dict)

        api.daisy.host_update(request, host_id,
                              cluster=cluster_id,
                              os_status=data['os_status'],
                              ipmi_user=data['ipmi_user'],
                              ipmi_passwd=data['ipmi_passwd'],
                              ipmi_addr=data['ipmi_addr'],
                              os_version=data['os_version'])
        messages.success(request, "Update host ipmis success!")
    except:
        exceptions.handle(request, "update host ipmis failed!")
        response.status_code = 500        
        return response

    response.status_code = 200
    return response  


def update_interfaces(interfaces_old, interfaces_new):
    ether_interfaces = [i for i in interfaces_old if i['type'] == 'ether']
    bond_interfaces = [i for i in interfaces_new if i['type'] == 'bond']

    for ether in ether_interfaces:
        clean_none_attr(ether)
        for inter_new in interfaces_new:
            if ether['name'] == inter_new['name']:
                ether['assigned_networks'] = inter_new['assigned_networks']
                if('ip' in inter_new):
                    ether['ip'] = inter_new['ip']
                break

    for bond in bond_interfaces:
        for inter_old in interfaces_old:
            if bond['name'] == inter_old['name']:
                clean_none_attr(inter_old)
                #do something
                break;

    #LOG.warning("############## ether_interfaces = %s #################" % ether_interfaces)                
    #LOG.warning("############## bond_interfaces = %s #################" % bond_interfaces)  

    ether_interfaces.extend(bond_interfaces)
    return ether_interfaces


def clean_none_attr(dict):
    for key in dict.keys():
        if dict[key] == None:
            del dict[key]
    if dict.has_key('created_at'):
        del dict['created_at']

    if dict.has_key('updated_at'):        
        del dict['updated_at']

    if dict.has_key('id'):         
        del dict['id']        


class HostNicsView(generic.TemplateView):
    template_name = "environment/deploy/nics.html"

    def get_data(self, cluster_id, host_id):
        host = get_host_by_id(self.request, host_id)
        if hasattr(host, 'interfaces'):
            nics = host.interfaces
        else:
            nics = []

        netplanes = self.get_netplane_data(cluster_id)
        LOG.info("!!!!!!!!!!!!!!!!!!!!``````` nics: %s" % nics)
        LOG.info("~~~~~~~~~~~~~~~~~~~~``````` netplanes: %s" % netplanes)

        ether_nics = []
        bond_nics  = []
        ether_nics_show = []

        for nic in nics:
            nic['networks'] = []
            if 'assigned_networks' in nic:
                for net in nic['assigned_networks']:
                    for i in range(len(netplanes)):
                        if net != "PRIVATE":
                            if net == netplanes[i].name:
                                #nic['networks'].append({'id': net, 'name': netplanes[i].name})
                                del netplanes[i]
                                break

            if nic['type'] == 'ether':
                ether_nics.append(nic)
            elif nic['type'] == 'bond':
                bond_nics.append(nic)

        # find nics have been bonded
        ether_bonded = []
        for bond in bond_nics:
            slave1 = bond['slave1']
            slave2 = bond['slave2']
            ether_bonded.append(slave1)
            ether_bonded.append(slave2)

        for ether in ether_nics:
            if ether['name'] in ether_bonded:
                pass
            else:
                ether_nics_show.append(ether)

        return netplanes, bond_nics, ether_nics_show, host.name

    def get_netplane_data(self, cluster_id):
        return api.daisy.network_list(self.request, cluster_id)

    def get_context_data(self, **kwargs):
        context = super(HostNicsView, self).get_context_data(**kwargs)
        context["cluster_id"] = self.kwargs["cluster_id"]
        context["host_id"] = self.kwargs["host_id"]

        netplanes, bond, ether_show, host_name = self.get_data(context["cluster_id"], context["host_id"])
        context["netplanes"] = netplanes
        context["bond_nics"] = bond
        context["ether_nics_show"] = ether_show
        context["host_name"] = host_name

        return context
