
import subprocess
import daisy.registry.client.v1.api as registry
from oslo_log import log as logging
import webob.exc
from webob.exc import HTTPBadRequest
from daisy.common import exception
from daisy.common import utils
import daisy.api.backends.common as daisy_cmn

LOG = logging.getLogger(__name__)


class config_clushshell():

    """ Class for clush backend."""

    def __init__(self, req):
        self.context = req.context

        self.CLUSH_CMD = 'clush -S -w %(management_ip)s "%(sub_command)s"'
        self.SUB_COMMAND_SET = "openstack-config --set %(config_file)s"\
            " %(section)s %(key)s '%(value)s'"
        self.SUB_COMMAND_DEL = "openstack-config --del %(config_file)s"\
            " %(section)s %(key)s"

    def _openstack_set_config(self, host_ip, config_set):
        """
        Set all config items on one host
        :param host_ip:
        :param config_set:
        :return:
        """
        if not host_ip or not config_set:
            LOG.debug('<<<FUN:_openstack_set_config input params invalid.>>>')
            return

        config_cmd = []
        for config in config_set['config']:
            if config['config_version'] == config['running_version']:
                continue

            config_file = registry.get_config_file_metadata(
                self.context, config['config_file_id'])
            if config['value']:
                value = utils.translate_quotation_marks_for_shell(
                    config['value'])
                config_cmd.append(self.SUB_COMMAND_SET %
                                  {'config_file': config_file['name'],
                                   'section': config['section'],
                                   'key': config['key'],
                                   'value': value})
            else:
                # if value is empty, delete or comment it.
                config_cmd.append(self.SUB_COMMAND_DEL %
                                  {'config_file': config_file['name'],
                                   'section': config['section'],
                                   'key': config['key']})

        try:
            for cmd in config_cmd:
                clush_cmd = self.CLUSH_CMD % {
                    'management_ip': host_ip, 'sub_command': cmd}
                subprocess.check_output(
                    clush_cmd, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            msg = ("<<<Host %s excute clush failed:%s.>>>" %
                   (host_ip, e.output.strip()))
            LOG.exception(msg)
            raise webob.exc.HTTPServerError(explanation=msg)
        else:
            msg = ("<<<Complete to push configs for host %s.>>>" % host_ip)
            LOG.info(msg)

    # if push_status = None, we will push configs
    # to all hosts in the role
    def push_role_configs(self, role_id, push_status):
        """
        Push config to remote host.
        :param req: http req
        :param role_id: host role id
        :return:
        """
        role_info = registry.get_role_metadata(self.context, role_id)
        if not role_info.get('config_set_id'):
            LOG.info("<<<No config_set configed for role '%s'>>>"
                     % role_info['name'])
            return

        config_set = registry.get_config_set_metadata(
            self.context, role_info['config_set_id'])
        if not config_set:
            LOG.info("<<<Get config_set failed for role '%s'.>>>"
                     % role_info['name'])
            return
        else:
            if 'config' not in config_set:
                LOG.info("<<<No configs get for role '%s'.>>>"
                         % role_info['name'])
                return

        config_set['config'] = [config for config in config_set['config']
                                if config.get('config_version', 0) !=
                                config.get('running_version', 0)]

        if not config_set['config']:
            LOG.info("<<<No config need to push for role '%s'.>>>"
                     % role_info['name'])
            return

        self.role_hosts = registry.get_role_host_metadata(
            self.context, role_id)

        total_host_count = 0
        if push_status:
            for r_host in self.role_hosts:
                if r_host['status'] == push_status:
                    total_host_count += 1
        else:
            total_host_count = len(self.role_hosts)

        if total_host_count > 0:
            LOG.info("Begin to push config for role '%s'"
                     % role_info['name'])
        else:
            return
        current_count = 0
        # all_host_config_sets = []
        for role_host in self.role_hosts:
            host = registry.get_host_metadata(
                self.context, role_host['host_id'])
            if push_status and role_host['status'] != push_status:
                LOG.debug("<<<Status of host '%s' is not '%s',"
                          " don't push configs.>>>"
                          % (role_host['host_id'], push_status))
                continue

            host_management_ip = ''
            for interface in host['interfaces']:
                if ('assigned_networks' in interface and
                        interface['assigned_networks']):
                    for assigned_network in interface['assigned_networks']:
                        if (assigned_network['name'] == 'MANAGEMENT' and
                                'ip' in assigned_network):
                            host_management_ip = assigned_network['ip']

            if not host_management_ip:
                msg = "Can't find management ip for host %s"\
                    % role_host['host_id']
                raise HTTPBadRequest(explanation=msg)

            root_passwd = 'ossdbg1'
            daisy_cmn.trust_me([host_management_ip], root_passwd)

            self._openstack_set_config(host_management_ip, config_set)

            self._role_service_restart(role_info, host_management_ip)

            current_count += 1
            role_info['config_set_update_progress'] =\
                round(current_count * 1.0 / total_host_count, 2) * 100
            registry.update_role_metadata(
                self.context, role_id, role_info)

        all_config_sets = []
        for config in config_set['config']:
            config['running_version'] = config['config_version']
            all_config_sets.append(config_set)
            registry.update_configs_metadata_by_role_hosts(
                self.context, all_config_sets)

    def _host_service_restart(self, host_ip, components_name):
        params = {'limit': '200', 'filters': {}}
        try:
            services = registry.get_services_detail(self.context,
                                                    **params)
            components = registry.get_components_detail(self.context,
                                                        **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg)

        components_id = [comp['id'] for comp in components
                         for comp_name in components_name
                         if comp['name'] == comp_name]

        for service in services:
            if service['component_id'] not in components_id:
                continue

            services_name = daisy_cmn.service_map.get(service['name'])
            if not services_name:
                msg = "Can't find service for '%s'" % service
                raise HTTPBadRequest(explanation=msg)

            for service_name in services_name.split(','):
                active_service = "clush -S -w %s 'systemctl is-active\
                                  %s'" % (host_ip, service_name)
                if 0 == utils.simple_subprocess_call(active_service):
                    restart_service = "clush -S -w %s 'systemctl restart\
                                       %s'" % (host_ip, service_name)
                    LOG.info("Restart service %s after pushing config"
                             % service_name)
                    if 0 != utils.simple_subprocess_call(restart_service):
                        msg = "Service %s restart failed on host '%s'."\
                              % (service_name, host_ip)
                        LOG.error(msg)

    # now i don't known how to find component id by config file,
    # so add you must tell me, and it can be deleted if i can find it
    # in future.
    def push_host_configs(self, host_id, components_name):
        """
        Push config to remote host.
        :param req: http req
        :param host_id: host id
        :return:
        """
        host_detail = registry.get_host_metadata(self.context, host_id)

        if not host_detail.get('config_set_id'):
            LOG.info("<<<No config_set configed for host '%s'.>>>"
                     % host_id)
            return

        config_set =\
            registry.get_config_set_metadata(self.context,
                                             host_detail['config_set_id'])
        if not config_set:
            LOG.info("<<<Get config_set failed for host '%s'.>>>"
                     % host_id)
            return
        else:
            if 'config' not in config_set:
                LOG.info("<<<No configs get for host '%s'.>>>" % host_id)
                return

        config_set['config'] = [config for config in config_set['config']
                                if config.get('config_version', 0) !=
                                config.get('running_version', 0)]

        if not config_set['config']:
            LOG.info("<<<No config need to push for host '%s'.>>>"
                     % host_id)
            return

        host_management_ip = ''
        for interface in host_detail['interfaces']:
            if ('assigned_networks' in interface and
                    interface['assigned_networks']):
                for assigned_network in interface['assigned_networks']:
                    if (assigned_network['name'] == 'MANAGEMENT' and
                            'ip' in assigned_network):
                        host_management_ip = assigned_network['ip']

        if not host_management_ip:
            msg = "Can't find management ip for host %s"\
                % host_detail['host_id']
            raise HTTPBadRequest(explanation=msg)

        root_passwd = 'ossdbg1'
        daisy_cmn.trust_me([host_management_ip], root_passwd)

        self._openstack_set_config(host_management_ip, config_set)

        self._host_service_restart(host_management_ip, components_name)

        all_config_sets = []
        for config in config_set['config']:
            config['running_version'] = config['config_version']
            all_config_sets.append(config_set)
            registry.update_configs_metadata_by_role_hosts(self.context,
                                                           all_config_sets)

    def _role_service_restart(self, role_info, host_ip):
        """  """
        for service in role_info['service_name']:
            services_name = daisy_cmn.service_map.get(service)
            if not services_name:
                msg = "Can't find service for '%s'" % service
                raise HTTPBadRequest(explanation=msg)

            for service_name in services_name.split(','):
                active_service = "clush -S -w %s 'systemctl is-active\
                                  %s'" % (host_ip, service_name)
                if 0 == utils.simple_subprocess_call(active_service):
                    restart_service = "clush -S -w %s 'systemctl restart\
                                       %s'" % (host_ip, service_name)
                    LOG.info("Restart service %s after pushing config"
                             % service_name)
                    if 0 != utils.simple_subprocess_call(restart_service):
                        msg = "Service %s restart failed on host '%s'."\
                              % (service_name, host_ip)
                        LOG.error(msg)
