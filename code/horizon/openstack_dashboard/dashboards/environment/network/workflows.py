# Copyright 2012 NEC Corporation
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


import logging

from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
import netaddr

from horizon import exceptions
from horizon import forms
from horizon import messages
from horizon import workflows

from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ungettext_lazy

from openstack_dashboard import api
from openstack_dashboard.dashboards.environment.network.subnets import utils

from daisyclient.v1 import client as daisy_client


LOG = logging.getLogger(__name__)


class CreateNetworkInfoAction(workflows.Action):
    name = forms.CharField(max_length=255,
                               label=_("Network Name"),
                               required=True)
    shared = forms.BooleanField(label=_("Shared"),
                                initial=False, required=False)
    type = forms.ChoiceField(choices=[('external', _('external')),
                                             ('internal', _('internal'))],
                             label=_("Network Type"),
                             required=True)
    physnet_name = forms.ChoiceField(label=_("Physnet_Name"), required=True)
    segmentation_type = forms.ChoiceField(label=_("Segmentation_Type"),
        required=True,
        widget=forms.Select(attrs={
            'class': 'switchable',
            'data-slug': 'segmentation_type'
        }))
    segmentation_id = forms.IntegerField(label=_("Segmentation ID"),
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'switched',
            'data-is-required': 'true',
            'data-switch-on': 'segmentation_type',
            'data-segmentation_type-vlan': _('Segmentation ID'),
            'data-segmentation_type-gre': _('Segmentation ID'),
            'data-segmentation_type-vxlan': _('Segmentation ID')
        }))
    msg = ""

    def __init__(self, request, *args, **kwargs):
        super(CreateNetworkInfoAction, self).__init__(request, *args, **kwargs)
        reqStr = repr(request)
        strArr = reqStr.split("/")
        cluster_id = strArr[4]
        LOG.info('network_workflow __init__ cluster_id:%s' % cluster_id)
        #cluster_info = api.daisy.cluster_get(self.request, cluster_id)
        self.fields['physnet_name'].choices = self.populate_physnet_choices(request,cluster_id)

        cluster_info = api.daisy.cluster_get(self.request, cluster_id)
        # get segmentation_type choices
        LOG.info('network_workflow after segment_type:%s' % cluster_info.networking_parameters['segmentation_type'])
        segmentation_types = cluster_info.networking_parameters['segmentation_type'].split(",")
        segmentation_types_list = [(atype, atype)
                     for atype in segmentation_types]
        self.fields['segmentation_type'].choices = sorted(segmentation_types_list)


        # get segmentation_id range
        LOG.info('network_workflow after networking_parameters:%s' % cluster_info.networking_parameters)
        seg_id_range = cluster_info.networking_parameters
        self.seg_id_range = {
            'vlan': seg_id_range.get('vlan_range',
                                     [0,0]),
            'gre': seg_id_range.get('gre_id_range',
                                    [0,0]),
            'vxlan': seg_id_range.get('vni_range',
                                      [0,0])
        }
        seg_id_help = (
            _("For VLAN networks, the VLAN VID on the physical "
              "network that realizes the virtual network. Valid VLAN VIDs "
              "are %(vlan_min)s through %(vlan_max)s. For GRE or VXLAN "
              "networks, the tunnel ID. Valid tunnel IDs for GRE networks "
              "are %(gre_min)s through %(gre_max)s. For VXLAN networks, "
              "%(vxlan_min)s through %(vxlan_max)s.")
            % {'vlan_min': self.seg_id_range['vlan'][0],
               'vlan_max': self.seg_id_range['vlan'][1],
               'gre_min': self.seg_id_range['gre'][0],
               'gre_max': self.seg_id_range['gre'][1],
               'vxlan_min': self.seg_id_range['vxlan'][0],
               'vxlan_max': self.seg_id_range['vxlan'][1]})
        self.fields['segmentation_id'].help_text = seg_id_help


    def populate_physnet_choices(self, request, cluster_id):
        #networks = daisy_client.Client(version=1, endpoint="http://10.43.174.62:19292").networks.list(filters=qp)
        networks = api.daisy.network_list(request, cluster_id)
        networks_list = [(network.name, network.name) for network in networks]
        if networks_list:
            networks_list.insert(0, ("", _("Select a network")))
        else:
            networks_list.insert(0, ("", _("No other networks available.")))
        return sorted(networks_list)



    class Meta(object):
        name = _("Logic Network")
        help_text = _("Create a new logic network. "
                      "In addition, a subnet associated with the network "
                      "can be created in the next panel.")

    def _check_segmentation_id(self, cleaned_data):
        LOG.info('_check_segmentation_id entered....................')
        entertype = cleaned_data.get('segmentation_type', 1)
        enterid = cleaned_data.get('segmentation_id')
        if (not enterid) and (entertype != 'flat'):
            msg = (_('specify Segmentation ID .'))
            LOG.info(msg)
            raise forms.ValidationError(msg)

        reqStr = repr(self.request)
        strArr = reqStr.split("/")
        cluster_id = strArr[4]
        cluster_info = api.daisy.cluster_get(self.request, cluster_id)

        idrange = []
        if entertype == 'vlan':
              idrange  = cluster_info.networking_parameters['vlan_range']
        if entertype == 'gre':
              idrange  = cluster_info.networking_parameters['gre_id_range']
        if entertype == 'vxlan':
              idrange  = cluster_info.networking_parameters['vni_range']

        LOG.info('_check_segmentation_id idrange:%s' % idrange)

        if len(idrange) > 0:
            if enterid<idrange[0] or enterid>idrange[1]:
                 params = {'type': entertype, 'bottom': idrange[0], 'top': idrange[1]}
                 msg = (_('Segmentation id of %(type)s must be in range:%(bottom)s-%(top)s.') % params)
                 LOG.info(msg)
                 raise forms.ValidationError(msg)

    def clean(self):
        cleaned_data = super(CreateNetworkInfoAction, self).clean()
        self._check_segmentation_id(cleaned_data)
        return cleaned_data

class CreateNetworkInfo(workflows.Step):
    action_class = CreateNetworkInfoAction
    contributes = ("name", "shared", "type", "physnet_name", "segmentation_type", "segmentation_id")


class CreateSubnetInfoAction(workflows.Action):
    with_subnet = forms.BooleanField(label=_("Create Subnet"),
                                     widget=forms.CheckboxInput(attrs={
                                         'class': 'switchable',
                                         'data-slug': 'with_subnet',
                                         'data-hide-tab': 'create_network__'
                                                             'action',
                                         'data-hide-on-checked': 'false'
                                     }),
                                     initial=True,
                                     required=False)
    subnet_name = forms.CharField(max_length=255,
                                  widget=forms.TextInput(attrs={
                                      'class': 'switched',
                                      'data-switch-on': 'with_subnet',
                                      'data-is-required': 'true'}),
                                  label=_("Subnet Name"),
                                  required=False)
    cidr = forms.IPField(label=_("Network Address"),
                         required=False,
                         initial="",
                         widget=forms.TextInput(attrs={
                             'class': 'switched',
                             'data-switch-on': 'with_subnet',
                             'data-is-required': 'true'
                         }),
                         help_text=_("Network address in CIDR format "
                                     "(e.g. 192.168.0.0/24, 2001:DB8::/48)"),
                         version=forms.IPv4 | forms.IPv6,
                         mask=True)
    '''
    floating_ranges = forms.IntegerField(
                         widget=forms.TextInput(attrs={
                             'class': 'switched',
                             'data-switch-on': 'with_subnet',
                             'data-is-required': 'true'
                             }),
                         label=_("Floating Ranges"),
                         required=True)
    '''

    floating_ranges = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'switched',
                                     'data-switch-on': 'with_subnet'}),
        label=_("Floating Ranges"),
        help_text=_("IP address floating ranges. Each entry is: "
                    "start_ip_address,end_ip_address "
                    "(e.g., 192.168.1.100,192.168.1.120) "
                    "and one entry per line."),
        required=False)

    dns_nameservers = forms.CharField(
        widget=forms.widgets.Textarea(attrs={'rows': 4, 'class': 'switched',
                                             'data-switch-on': 'with_subnet'}),
        label=_("DNS Name Servers"),
        help_text=_("IP address list of DNS name servers for this subnet. "
                    "One entry per line."),
        required=False)

    gateway = forms.IPField(
        label=_("Gateway IP"),
        widget=forms.TextInput(attrs={
            'class': 'switched',
            'data-switch-on': 'with_subnet gateway_ip'
        }),
        required=False,
        initial="",
        help_text=_("IP address of Gateway (e.g. 192.168.0.254) "
                    "The default value is the first IP of the "
                    "network address "
                    "(e.g. 192.168.0.1 for 192.168.0.0/24, "
                    "2001:DB8::1 for 2001:DB8::/48). "),
        version=forms.IPv4 | forms.IPv6,
        mask=False)

    msg = _('Specify "Network Address" or '
            'clear "Create Subnet" checkbox.')

    def _convert_ip_address(self, ip, field_name):
        try:
            return netaddr.IPAddress(ip)
        except (netaddr.AddrFormatError, ValueError):
            msg = (_('%(field_name)s: Invalid IP address (value=%(ip)s)')
                   % {'field_name': field_name, 'ip': ip})
            raise forms.ValidationError(msg)

    def _convert_ip_network(self, network, field_name):
        try:
            return netaddr.IPNetwork(network)
        except (netaddr.AddrFormatError, ValueError):
            msg = (_('%(field_name)s: Invalid IP address (value=%(network)s)')
                   % {'field_name': field_name, 'network': network})
            raise forms.ValidationError(msg)

    def _check_dns_nameservers(self, dns_nameservers):
        for ns in dns_nameservers.split('\n'):
            ns = ns.strip()
            if not ns:
                continue
            self._convert_ip_address(ns, "dns_nameservers")

    def _check_subnet_data(self, cleaned_data, is_create=True):
        subnet_name = cleaned_data.get('subnet_name')
        if not subnet_name:
            msg = _('specify Subnet Name.')
            raise forms.ValidationError(msg)
        cidr = cleaned_data.get('cidr')
        #LOG.info('_check_subnet_data.....cleaned_data=%s.....' % cleaned_data)
        if not cidr:
            raise forms.ValidationError(self.msg)
        if cidr:
            subnet = netaddr.IPNetwork(cidr)
            if subnet.version != 4:
                msg = _('Network Address and IP version are inconsistent.')
                raise forms.ValidationError(msg)
            if (subnet.prefixlen == 32):
                msg = _("The subnet in the Network Address is "
                        "too small (/%s).") % subnet.prefixlen
                raise forms.ValidationError(msg)

        gateway_ip = cleaned_data.get('gateway')
        if gateway_ip and netaddr.IPAddress(gateway_ip).version is not 4:
            msg = _('Gateway IP and IP version are inconsistent.')
            raise forms.ValidationError(msg)
        self._check_allocation_pools(cleaned_data.get('floating_ranges'))
        self._check_dns_nameservers(cleaned_data.get('dns_nameservers'))

    def _check_allocation_pools(self, allocation_pools):
        for p in allocation_pools.split('\n'):
            p = p.strip()
            if not p:
                continue
            pool = p.split(',')
            if len(pool) != 2:
                msg = _('Start and end addresses must be specified '
                        '(value=%s)') % p
                raise forms.ValidationError(msg)
            start, end = [self._convert_ip_address(ip, "allocation_pools")
                          for ip in pool]
            if start > end:
                msg = _('Start address is larger than end address '
                        '(value=%s)') % p
                raise forms.ValidationError(msg)


    class Meta(object):
        name = _("Subnet")
        help_text = _('Create a subnet associated with the new network, '
                      'in which case "Network Address" must be specified. '
                      'If you wish to create a network without a subnet, '
                      'uncheck the "Create Subnet" checkbox.')

    def __init__(self, request, context, *args, **kwargs):
        super(CreateSubnetInfoAction, self).__init__(request, context, *args,
                                                     **kwargs)


    def clean(self):
        cleaned_data = super(CreateSubnetInfoAction, self).clean()
        with_subnet = cleaned_data.get('with_subnet')
        if not with_subnet:
            return cleaned_data
        self._check_subnet_data(cleaned_data)
        return cleaned_data


class CreateSubnetInfo(workflows.Step):
    action_class = CreateSubnetInfoAction
    contributes = ("with_subnet", "subnet_name", "cidr",
                   "floating_ranges", "gateway", "dns_nameservers")


class CreateNetwork(workflows.Workflow):
    slug = "create_logicnetwork"
    name = _("Create LogicNetwork")
    finalize_button_name = _("Create")
    success_message = _('Created logic network "%s".')
    failure_message = _('Unable to create logic network "%s".')
    default_steps = (CreateNetworkInfo,
                     CreateSubnetInfo)
    wizard = True

    def __init__(self, request=None, context_seed=None, entry_point=None,
                 *args, **kwargs):
        super(CreateNetwork, self).__init__(request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)
    def _create_subnet(self, request, data):
        try:
            reqStr = repr(request)
            strArr = reqStr.split("/")
            cluster_id = strArr[4]
            lognet_id = strArr[5]
            LOG.info('_create_subnet cluster_id:%s  lognet_id:%s' % (cluster_id, lognet_id))
            cluster_info = api.daisy.cluster_get(request, cluster_id)
            _logic_networks = cluster_info.logic_networks
            for alogic in _logic_networks:
                if(alogic['id'] == lognet_id):
                     asubnet = {}
                     asubnet['name'] = data['subnet_name']
                     asubnet['cidr'] = data['cidr']
                     asubnet['gateway'] = data['gateway']
                     asubnet['floating_ranges'] = []
                     pools = [pool.strip().split(',')
                              for pool in data['floating_ranges'].split('\n')
                              if pool.strip()]
                     asubnet['floating_ranges'] = pools
                     asubnet['dns_nameservers'] = []
                     asubnet['dns_nameservers'].append(data['dns_nameservers'])
                     alogic['subnets'].append(asubnet)

            LOG.info('_create_subnet _logic_networks<<<<<:%s' % _logic_networks)
            api.daisy.cluster_update(request,
                                     cluster_id,
                                     description = cluster_info.description,
                                     name = cluster_info.name,
                                     networking_parameters = cluster_info.networking_parameters,
                                     networks = cluster_info.networks,
                                     routers = cluster_info.routers,
                                     logic_networks=_logic_networks)
            return True
        except Exception as e:
            msg = (_('Failed to create network "%(network)s": %(reason)s') %
                   {"network": data['subnet_name'], "reason": e})
            LOG.info(msg)
            messages.error(request, msg)
            redirect = self.get_failure_url()
            raise exceptions.Http302(redirect)
            #exceptions.handle(request, msg, redirect=redirect)
            return False

    def get_success_url(self):
        LOG.info('success url<<<<<:%s' % self.request)
        #return reverse("horizon/environment/network/overview")
        reqStr = repr(self.request)
        strArr = reqStr.split("/")
        cluster_id = strArr[4]
        return reverse("horizon:environment:network:logicnet",
                       args=(cluster_id,))
    

    def get_failure_url(self):
        LOG.info('fail url<<<<<:%s' % self.request)
        #return reverse("horizon/environment/network/overview")
        reqStr = repr(self.request)
        strArr = reqStr.split("/")
        cluster_id = strArr[4]
        return reverse("horizon:environment:network:logicnet",
                       args=(cluster_id,))

    def format_status_message(self, message):
        name = self.context.get('name') or self.context.get('id', '')
        LOG.info('message<<<<<:%s' % name)
        return message % name

    def _create_network(self, request, data):
        try:
            reqStr = repr(request)
            strArr = reqStr.split("/")
            cluster_id = strArr[4]
            cluster_info = api.daisy.cluster_get(request, cluster_id)
            LOG.info('cluster_info<<<<<:%s' % cluster_info)
            LOG.info('_create_network data<<<<<:%s' % data)
            _logic_networks = cluster_info.logic_networks

            _logic_network = {}
            _logic_network['name'] = data['name']
            _logic_network['physnet_name'] = data['physnet_name']
            _logic_network['cluster_id'] = cluster_id
            _logic_network['type'] = data['type']
            _logic_network['shared'] = data['shared']
            _logic_network['segmentation_type'] = data['segmentation_type']
            if data['segmentation_type'] == 'flat':
                _logic_network['segmentation_id'] = 10
            else:
                _logic_network['segmentation_id'] = data['segmentation_id']
            _logic_network['subnets'] = []
            if data['with_subnet']:
                asubnet = {}
                asubnet['name'] = data['subnet_name']
                asubnet['cidr'] = data['cidr']
                asubnet['gateway'] = data['gateway']
                asubnet['floating_ranges'] = []
                '''pools = [dict(zip(['start', 'end'], pool.strip().split(',')))
                         for pool in data['floating_ranges'].split('\n')
                         if pool.strip()]
                '''
                pools = [pool.strip().split(',')
                         for pool in data['floating_ranges'].split('\n')
                         if pool.strip()]
                asubnet['floating_ranges'] = pools
                asubnet['dns_nameservers'] = []
                asubnet['dns_nameservers'].append(data['dns_nameservers'])
                _logic_network['subnets'].append(asubnet)
            _logic_networks.append(_logic_network)

            LOG.info('****cluster_info.logic_networks<<<<<:%s' % cluster_info.logic_networks)

            api.daisy.cluster_update(request,
                                     cluster_id,
                                     description = cluster_info.description,
                                     name = cluster_info.name,
                                     networking_parameters = cluster_info.networking_parameters,
                                     networks = cluster_info.networks,
                                     routers = cluster_info.routers,
                                     logic_networks = _logic_networks)                                    
            return True
        except Exception as e:
            msg = (_('Failed to create network "%(network)s": %(reason)s') %
                   {"network": data['name'], "reason": e})
            LOG.info(msg)
            messages.error(request, msg)
            redirect = self.get_failure_url()
            raise exceptions.Http302(redirect)
            # exceptions.handle(request, msg, redirect=redirect)
            return False


    def _delete_network(self, request, network):
        """Delete the created network when subnet creation failed."""
        pass


    def handle(self, request, data):
        net = self._create_network(request, data)
        return True if net else False


