import logging
from django.utils.translation import ugettext_lazy as _
from django.forms import ValidationError

from horizon import forms
from horizon import exceptions
from horizon import messages
from openstack_dashboard import api

LOG = logging.getLogger(__name__)


class CreateRouteForm(forms.SelfHandlingForm):
    name = forms.CharField(max_length=255, label=_("Route Name"))
    description = forms.CharField(max_length=255,
                                  required=False,
                                  label=_("Description"))
    external_logic_network = forms.ChoiceField(label=_("External_logic_network"),
                                               required=False,
                                               choices=[])
    subnets = forms.MultipleChoiceField(label=_("Subnets"),
                                        initial=["default"],
                                        choices=[],
                                        required=False,
                                        widget=forms.CheckboxSelectMultiple())

    def __init__(self, request, *args, **kwargs):
        super(CreateRouteForm, self).__init__(request, *args, **kwargs)

        cluster_id = self.get_clusterID(request)
        cluster = api.daisy.cluster_get(request, cluster_id)

        self.fields['external_logic_network'].choices = self.get_external_logic_network_foruse(cluster)

        subnets = self.get_available_subnets(cluster)
        self.fields['subnets'].choices = [(subnet, subnet) for subnet in subnets]

    def get_clusterID(self, request):
        reqStr = repr(request)
        strArr = reqStr.split("/")
        cluster_id = strArr[4]
        return cluster_id
        
    def get_external_logic_network_foruse(self, cluster):
        logic_networks = cluster.logic_networks
        external_logic_network = [logic_network for logic_network in logic_networks
                                  if logic_network['type'] == 'external']
        external_logic_network_foruse = []
        for logic_network in external_logic_network:
            subnets = [b['name'] for b in logic_network['subnets']]
            network_name = logic_network["name"]
            one_logic = {"subnets": subnets, "name": network_name}
            external_logic_network_foruse.append(one_logic)

        network_name = [(a, a['name']) for a in external_logic_network_foruse]
        #network_name = [(a, a['name']) for a in external_logic_network]
        network_name.insert(0, ("", ""))
        return network_name
     
    def get_used_subnets(self, cluster):
        routers = cluster.routers
        used_subnets =[]
        for router in routers:
            subnets = router["subnets"]
            for subnet in subnets:
                used_subnets.append(subnet)
        LOG.info("!!!!!!!!!!! Used_subnets: %s" %used_subnets )
        return used_subnets

    def get_all_subnets(self, cluster):
        all_subnets = []
        logic_networks = cluster.logic_networks
        '''external_logic_networks = [logic_network for logic_network in logic_networks
                                  if logic_network['type'] == 'external']
        for external_logic_network in external_logic_networks:
            subnets = [b['name'] for b in external_logic_network['subnets']]
            #network_name = external_logic_network["name"]
            all_subnets += subnets
        LOG.info("!!!!!!!!!!! All_subnets: %s" %all_subnets )'''
        for logic_network in logic_networks:
            subnets = [b['name'] for b in logic_network['subnets']]
            all_subnets += subnets
        return all_subnets            
 
    def get_available_subnets(self, cluster):
        all_subnets = self.get_all_subnets(cluster)
        used_subnets = self.get_used_subnets(cluster)
        available_subnets = all_subnets
        for subnet in used_subnets:
            if subnet in available_subnets:
                available_subnets.remove(subnet)
        LOG.info("!!!!!!!!!!! Available_subnets: %s" %available_subnets )
        return available_subnets

    def get_external_logic_network_name(self, external_logic_network):
        network_name = ""
        if external_logic_network != "":
            subnets = external_logic_network.split("]")
            name = repr(subnets[1]).split(":")[1]
            network_name = name.split("'")[1]
        return network_name

    def handle(self, request, data):
        try:
            cluster_id = self.get_clusterID(request)
            cluster = api.daisy.cluster_get(request, cluster_id)
            router = cluster.routers
            logic_networks = cluster.logic_networks
            '''
            external_logic_network = [logic_network for logic_network in logic_networks
                                      if logic_network['type'] == 'external']
            external_logic_network_subnets=[b['name'] for b in external_logic_network['subnets']]
            if data["subnets"] == external_logic_network_subnets:
                        error_message = _('Can not choose all subnets in the external_logic_network.')
                        raise ValidationError(error_message)

            '''
            network_name = self.get_external_logic_network_name(data['external_logic_network'])
            for logic_network in logic_networks:
                if network_name == logic_network["name"]:
                    sunbets = [b['name'] for b in logic_network['subnets']]
                    if data["subnets"] == sunbets:
                        error_message = _('Can not choose all subnets in the external_logic_network.')
                        raise ValidationError(error_message)

            router_add = {"name": data["name"],
                          "description": data["description"],
                          "external_logic_network": network_name,
                          "subnets": data["subnets"]}
            router.append(router_add)
            LOG.info("@@@@@@@@@@@@@@@ router_add : %s" % router_add)
            api.daisy.cluster_update(request, cluster_id, **(cluster.__dict__))
            msg = _('The router %s is preparing to create.') % data['name']
            messages.success(request, msg)
            return True
        except ValidationError as e:
            self.api_error(e.messages[0])
            return False
        except Exception:
            messages.error(request, _("Unable to create router."))
            exceptions.handle(request, _("Unable to create router."))
            return False
