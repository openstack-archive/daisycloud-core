from django.utils.translation import ugettext_lazy as _
from django.views.decorators.debug import sensitive_variables
from django.forms.widgets import Textarea, RadioSelect

from horizon import exceptions
from horizon import messages
from horizon import workflows
from horizon import forms
from openstack_dashboard import api

import logging
LOG = logging.getLogger(__name__)

DEPLOY_MODE = ["Enable HA multi-node"]
SEGMENTATION_TYPE = ["flat", "vlan", "gre", "vxlan"]
NET_L23_PROVIDER = ["OVS", "OVDK", "SRIOV", "OVS-DPDK"]
BACKEND_STORAGE = ["default", "Ceph"]
ADDITIONAL_SERVICE = ["FireWareas", "LBaas", "VPNaas", "Celimeter"]


class SetClusterNameAction(workflows.Action):
    name = forms.CharField(label=_("Cluster Name"),
                           max_length=255)
    target = forms.ChoiceField(label=_("Target System"),
                           required=False)
    os = forms.ChoiceField(label=_("OS"),
                           required=False)
    model = forms.ChoiceField(label=_("Model"),
                           required=False)
    description = forms.CharField(label=_("Description"),
                              required=False,
                              max_length=255)

    def __init__(self, request, *args, **kwargs):
        super(SetClusterNameAction, self).__init__(request, *args, **kwargs)

    class Meta(object):
        name = _("Basic Info")


class SetClusterName(workflows.Step):
    action_class = SetClusterNameAction
    contributes = ("name", "target", "os", "model", "description")


class SetDeployModeAction(workflows.Action):
    deploy_mode = forms.MultipleChoiceField(label=_("Deploy Mode"),
                                            initial=["default"],
                                            required="True",
                                            widget=forms.CheckboxSelectMultiple(),
                                  help_text="")

    def __init__(self, request, *args, **kwargs):
        super(SetDeployModeAction, self).__init__(request, *args, **kwargs)
        # Set deploy_mode choices
        modes = [(mode, mode)
                 for mode in DEPLOY_MODE]
        self.fields['deploy_mode'].choices = modes

    class Meta(object):
        name = _("Deploy_mode")


class SetDeployMode(workflows.Step):
    action_class = SetDeployModeAction
    contributes = ("deploy_mode",)


class SetNetworkAction(workflows.Action):
    segmentation_type = forms.MultipleChoiceField(label=_("Network"),
                                initial="GRE",
                                required=False,
                                choices=[],
                                widget=forms.CheckboxSelectMultiple(),
                                  help_text="")

    def __init__(self, request, *args, **kwargs):
        super(SetNetworkAction, self).__init__(request, *args, **kwargs)
        # Set network choices
        networks = [(network, network)
                    for network in SEGMENTATION_TYPE]
        self.fields['segmentation_type'].choices = networks

    class Meta(object):
        name = _("Network")


class SetNetwork(workflows.Step):
    action_class = SetNetworkAction
    contributes = ("segmentation_type",)


class SetComputerNodeAction(workflows.Action):
    net_l23_provider = forms.ChoiceField(label=_("NET_L23_PROVIDER"),
                                                     initial="OVS",
                                                     required=False,
                                                     widget=RadioSelect(),
                                         help_text="")

    def __init__(self, request, *args, **kwargs):
        super(SetComputerNodeAction, self).__init__(request, *args, **kwargs)
        # Set computer node plugin type choices
        plus_types = [(plus_type, plus_type)
                      for plus_type in NET_L23_PROVIDER]
        self.fields['net_l23_provider'].choices = plus_types

    class Meta(object):
        name = _("NET_L23_PROVIDER")


class SetComputerNode(workflows.Step):
    action_class = SetComputerNodeAction
    contributes = ("net_l23_provider",)


class SetBackendStorageAction(workflows.Action):
    cinder_storage = forms.MultipleChoiceField(label=_("cinder_storage"),
                                               initial=["default"],
                                               required="True",
                                               widget=RadioSelect(),
                                               help_text="")
    glance_storage = forms.MultipleChoiceField(label=_("glance_storage"),
                                               initial=["default"],
                                               required="True",
                                               widget=RadioSelect(),
                                               help_text="")
    swift_storage = forms.MultipleChoiceField(label=_("swift_storage"),
                                              initial=["default"],
                                              required="True",
                                              widget=RadioSelect(),
                                              help_text="")

    def __init__(self, request, *args, **kwargs):
        super(SetBackendStorageAction, self).__init__(request, *args, **kwargs)
        # Set cinder_storage choices
        storage_types = [(storage_type, storage_type)
                         for storage_type in BACKEND_STORAGE]
        self.fields['cinder_storage'].choices = storage_types

        # Set glance_storage options
        self.fields['glance_storage'].choices = storage_types

        # Set glance_storage options
        self.fields['swift_storage'].choices = storage_types

    class Meta(object):
        name = _("Backend_storage")


class SetBackendStorage(workflows.Step):
    action_class = SetBackendStorageAction
    contributes = ("cinder_storage", "glance_storage", "swift_storage")


class SetAdditionalServicesAction(workflows.Action):
    additional_services = forms.MultipleChoiceField(label=_("Additional Services"),
                                                    initial=["default"],
                                                    widget=forms.CheckboxSelectMultiple(),
                                                    help_text=_(""))

    def __init__(self, request, *args, **kwargs):
        super(SetAdditionalServicesAction, self).__init__(request, *args, **kwargs)
        # Set additional_services choices
        services = [(service, service)
                    for service in ADDITIONAL_SERVICE]
        self.fields['additional_services'].choices = services

    class Meta(object):
        name = _("Additional Services")


class SetAdditionalServices(workflows.Step):
    action_class = SetAdditionalServicesAction
    contributes = ("additional_services",)


class CreateCluster(workflows.Workflow):
    slug = "create_cluster"
    name = _("Create Cluster")
    finalize_button_name = _("Create")
    success_message = _('Create cluster named "%(cluster_name)s" successed.')
    failure_message = _('Unable to create cluster named "%(cluster_name)s".')
    success_url = "horizon:environment:overview:index"
    multipart = True
    default_steps = (SetClusterName,
                     #SetDeployMode,
                     SetNetwork,
                     SetComputerNode,)
                     #SetBackendStorage,
                     #SetAdditionalServices)

    def format_status_message(self, message):
        cluster_name = self.context.get('name', 'unknown cluster')
        return message % {"cluster_name": cluster_name}

    @sensitive_variables('context')
    def handle(self, request, context):
        try:
            cluster = api.daisy.cluster_add(self.request,
                                            name=context["name"],
                                            description=context["description"])
            return True
        except Exception:
            LOG.info("Create cluster failed.")
            exceptions.handle(request, "Create cluster failed.")
            return False

