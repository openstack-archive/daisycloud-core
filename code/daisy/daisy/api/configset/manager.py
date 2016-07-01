from daisy.api.configset.clush import config_clushshell


class configBackend():

    def __init__(self, type, req):
        self.type = type
        self._instance = None

        if type == "clushshell":
            self._instance = config_clushshell(req)
        elif type == "puppet":
            pass

    # if push_status = None, we will push configs
    # to all hosts in the role
    def push_config_by_roles(self, role_ids, push_status=None):
        for role_id in role_ids:
            self._instance.push_role_configs(role_id, push_status)

    def push_config_by_hosts(self, host_ids, component_names=[]):
        for host_id in host_ids:
            self._instance.push_host_configs(host_id,
                                             component_names)
