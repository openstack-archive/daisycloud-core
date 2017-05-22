# Copyright 2012 OpenStack Foundation.
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

    def push_origin_config_to_host(self, host_config):
        """
        push original config to remote host.
        :param host_config: The config of host
            {
                "ip":"the ip address of remote host",
                "config_set": [{
                    "section": "the section name, only if the file format is
                                SKV, the value is required.",
                    "key": "the key of config item, the value is required.",
                    "value": "the value of config item, if delete only key of
                              config item, the value don't fill in,
                              otherwise the value is required.",
                    "old_value": "the old value of config item,
                                  only if the action is set and duplicate key,
                                  the value is required."
                    "config_file": "the config file, the value is required.",
                    "action": "the action of config item,
                               format is add/delete/set, the value
                               is required.",
                    "services": "the service name list of config item,
                                 only force type is service, the value
                                 is required",
                    "force_type": "the force type of config item,
                                  if no force service/node,
                                  the value don't fill in,
                                  otherwise  the value is service/node",
                    "file_format": "the file format of config item,
                                    SKV/others,the value is required,
                                    SKV is section/key/value.",
                    "separator": "the separator of config item,
                                  only if the file format is others,
                                  the value is required"
                },...]
            }
        :return: Raise Invalid exception if host config is invalid
                 Raise webob.exc.HTTPServerError if call process error
        """
        self._instance.push_origin_config_to_host(host_config)

    def get_host_config_progress(self, host_config):
        return 100

    def get_config_by_host(self, host_id, template_configs):
        return self._instance.get_host_configs(host_id, template_configs)
