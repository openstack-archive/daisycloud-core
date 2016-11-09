
import subprocess
from os import path
import daisy.registry.client.v1.api as registry
from oslo_log import log as logging
import webob.exc
from webob.exc import HTTPBadRequest
from daisy.common import exception
from daisy.common import utils
import daisy.api.backends.common as daisy_cmn
LOG = logging.getLogger(__name__)

# 1: no config file or no section or no key found in host by openstack-config
IGNORE_ERROR_CODE = [1]
COROSYNC_CONF = "/etc/corosync/corosync.conf"


def copy_file_and_run_cmd(host, files, commands):
    """
    host: {'ip': ip, 'root_pwd':pwd}
    files: [{'file': 'file1', 'remote_dir': '' },
           {'file': 'file2', 'remote_dir': '' },
             .....]
    commands: ['cmd1', 'cmd2', ...]
    """
    if not host.get('ip') or not host.get('root_pwd'):
        msg = "Error host format: '%s'" % host
        LOG.error(msg)
        raise HTTPBadRequest(msg)
    clush_cmd = []
    for item in files:
        if not path.exists(item.get('file') or ''):
            msg = "File: '%s' not exits" % (item.get('file') or '')
            LOG.error(msg)
            raise HTTPBadRequest(msg)

        remote_dir = item.get('remote_dir') or path.dirname(item['file'][:-1])
        remote_dir = path.join(remote_dir, '')
        cmd = [
            'clush -S -w %s "test -d %s || mkdir -p %s"' % (
                host['ip'], remote_dir, remote_dir),
            'clush -S -w %s --copy %s --dest %s' % (
                host['ip'], item['file'], remote_dir)
        ]
        clush_cmd.extend(cmd)

    shell_cmd = ['clush -S -w %s "%s"' % (host['ip'], cmd) for cmd in commands]
    clush_cmd.extend(shell_cmd)

    daisy_cmn.trust_me([host['ip']], host['root_pwd'])

    scrips = "\n".join(clush_cmd)
    try:
        LOG.info('On %s execute: \n%s' % (host['ip'], scrips))
        subprocess.check_output(scrips, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError, e:
        msg = ("<<<Failed to execute:\n%s>>>" % e.output.strip())
        LOG.error(msg)
        raise HTTPBadRequest(msg)
    LOG.info('Execute successfully')


class config_clushshell():

    """ Class for clush backend."""

    def __init__(self, req):
        self.context = req.context
        self.req = req
        self.CLUSH_CMD = 'clush -S -w %(management_ip)s "%(sub_command)s"'
        self.SUB_COMMAND_SET = "openstack-config --set %(config_file)s"\
            " '%(section)s' %(key)s '%(value)s'"
        self.SUB_COMMAND_DEL = "openstack-config --del %(config_file)s"\
            " %(section)s %(key)s"
        self.SUB_COMMAND_GET = "openstack-config --get %(config_file)s"\
            " %(section)s %(key)s"
        self.STOP_HA_MANAGE_CMD = "test -f %s && pcs property set " \
                                  "unmanaged=true --force" % COROSYNC_CONF
        self.ENABLE_HA_MANAGE_CMD = "test -f %s && pcs property set " \
                                    "unmanaged=false" % COROSYNC_CONF
        self.SUB_SHELL_COMMAND_ADD = "echo %(key)s%(separator)s'%(value)s' " \
                                     ">>%(config_file)s"
        self.SUB_SHELL_COMMAND_SET = "sed -i 's/^[[:space:]]*" \
                                     "%(key)s[[:space:]]*" \
                                     "%(separator)s[[:space:]]*" \
                                     "%(old_value)s.*$/" \
                                     "%(key)s%(separator)s" \
                                     "%(value)s/' %(config_file)s"
        self.SUB_SHELL_COMMAND_DEL = "sed -i '/^[[:space:]]*%(key)s" \
                                     "[[:space:]]*" \
                                     "%(separator)s[[:space:]]*%(value)s.*" \
                                     "/d' %(config_file)s"

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
                if config['value'].count("'") > 0:
                    self.SUB_COMMAND_SET = \
                        self.SUB_COMMAND_SET.replace("'", '\\"')
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

    @staticmethod
    def _get_orgin_config_for_clush(config):
        new_value = ''
        old_value = ''
        if config.get("file_format", "") in ['SKV']:
            new_value = config['value']
            if config.get('value') and config['value'].count("'") > 0:
                new_value = utils.translate_quotation_marks_for_shell(
                    new_value)
        else:
            if config.get('value'):
                if config.get("action", "") in ['add']:
                    new_value = config['value']
                else:
                    new_value = utils.translate_marks_4_sed_command(
                        config['value'])
            if config.get('old_value'):
                old_value = utils.translate_marks_4_sed_command(
                    config['old_value'])
        param = {
            'config_file': config.get('config_file'),
            'section': config.get('section'),
            'key': config.get('key'),
            'value': new_value,
            'old_value': old_value,
            'separator': config.get('separator')}
        return param

    def _push_origin_config_to_host(self, host_config):
        """
        Set all config items on one host
        :param host_config:
        :return:
        """
        def excute_query_clush_cmd(ip, clush_cmd):
            try:
                clush_cmd = self.CLUSH_CMD % {
                    'management_ip': ip,
                    'sub_command': clush_cmd}
                LOG.info("clush_cmd: %s", clush_cmd)
                subprocess.check_output(
                    clush_cmd, shell=True, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                if e.returncode in IGNORE_ERROR_CODE:
                    _msg = ("%s config item %s is no exist." %
                            (ip, clush_cmd))
                    LOG.error(_msg)
                    raise exception.Invalid(_msg)
                else:
                    _msg = ("<<<Host %s excute clush failed:%s.>>>" %
                            (ip, e.output.strip()))
                    LOG.error(_msg)
                    raise webob.exc.HTTPServerError(explanation=_msg)
            else:
                _msg = ("<<<Complete to push configs for host %s.>>>" % ip)
                LOG.info(_msg)

        def is_others_format_new_item_exist(ip, param):
            is_exist_cmd = "cat %(config_file)s | grep " \
                           "'^[[:space:]]*%(key)s[[:space:]]*" \
                           "%(separator)s[[:space:]]*" \
                           "%(old_value)s.*$' -wc" % param
            try:
                excute_query_clush_cmd(ip, is_exist_cmd)
            except exception.Invalid as e:
                # old value no exist, check new value is exist
                is_exist_cmd = "cat %(config_file)s | grep " \
                               "'^[[:space:]]*%(key)s[[:space:]]*" \
                               "%(separator)s[[:space:]]*" \
                               "%(value)s.*$' -wc" % param
                try:
                    excute_query_clush_cmd(ip, is_exist_cmd)
                except exception.Invalid as e:
                    _msg = ("Old value no exist, check new value invalid, "
                            "%s" % utils.exception_to_str(e))
                    LOG.error(_msg)
                    raise exception.Invalid(_msg)
                except webob.exc.HTTPServerError as e:
                    _msg = ("Old value no exist, check new value "
                            "http server error, "
                            "%s" % utils.exception_to_str(e))
                    LOG.error(_msg)
                    raise webob.exc.HTTPServerError(explanation=_msg)
                else:
                    LOG.info("excute clush %s, new item exist", is_exist_cmd)
                    return True
            except webob.exc.HTTPServerError as e:
                _msg = ("Check old value http server error, "
                        "%s" % utils.exception_to_str(e))
                LOG.error(_msg)
                raise webob.exc.HTTPServerError(explanation=_msg)
            else:
                LOG.info("excute clush %s, old item exist", is_exist_cmd)
                return False

        def get_config_cmd_list(in_host_config):
            cmd_list = []
            for config in in_host_config.get('config_set', []):
                param = self._get_orgin_config_for_clush(config)
                if config.get("file_format", "") in ['SKV']:
                    if config.get("action", "") in ['add', 'set']:
                        sub_command_set = self.SUB_COMMAND_SET
                        if (config.get("value")) and \
                                (config['value'].count("'") > 0):
                            sub_command_set =\
                                sub_command_set.replace("'", '\\"')
                        cmd_list.append(sub_command_set % param)
                    elif config.get("action", "") in ['delete']:
                        cmd_list.append(self.SUB_COMMAND_DEL % param)
                    else:
                        _msg = ("<<<Host %s action failed:%s.>>>" %
                                (host_config.get("ip"), config))
                        LOG.error(_msg)
                        raise webob.exc.HTTPServerError(explanation=_msg)
                elif config.get("file_format", "") in ['others']:
                    if config.get("action", "") in ['add']:
                        cmd_list.append(self.SUB_SHELL_COMMAND_ADD % param)
                    elif config.get("action", "") in ['set']:
                        if not is_others_format_new_item_exist(
                                host_config.get("ip"), param):
                            cmd_list.append(self.SUB_SHELL_COMMAND_SET % param)
                    elif config.get("action", "") in ['delete']:
                        cmd_list.append(self.SUB_SHELL_COMMAND_DEL % param)
                    else:
                        _msg = ("<<<Host %s action failed:%s.>>>" %
                                (host_config.get("ip"), config))
                        LOG.error(_msg)
                        raise webob.exc.HTTPServerError(explanation=_msg)
                else:
                    _msg = ("<<<Host %s file_format failed:%s.>>>" %
                            (host_config.get("ip"), config))
                    LOG.error(_msg)
                    raise webob.exc.HTTPServerError(explanation=_msg)
            return cmd_list

        config_cmd_list = get_config_cmd_list(host_config)
        try:
            for config_cmd in config_cmd_list:
                clush_cmd = self.CLUSH_CMD % {
                    'management_ip': host_config.get("ip"),
                    'sub_command': config_cmd}
                LOG.info("clush_cmd: %s", clush_cmd)
                subprocess.check_output(
                    clush_cmd, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            msg = ("<<<Host %s excute clush failed:%s.>>>" %
                   (host_config.get("ip"), e.output.strip()))
            LOG.error(msg)
            raise webob.exc.HTTPServerError(explanation=msg)
        else:
            msg = ("<<<Complete to push configs for host %s.>>>" %
                   host_config.get("ip"))
            LOG.info(msg)

    def _openstack_get_config(self, host_ip, template_configs):
        """
        Get all config items on one host
        :param host_ip:
        :param config_set:
        :return:
        """
        if not host_ip or not template_configs:
            LOG.debug('<<<FUN:_openstack_get_config input params invalid.>>>')
            return

        for config in template_configs:
            cmd = self.SUB_COMMAND_GET % {'config_file': config['config_file'],
                                          'section': config['section'],
                                          'key': config['key']}

            clush_cmd = self.CLUSH_CMD % {'management_ip': host_ip,
                                          'sub_command': cmd}
            try:
                result = subprocess.check_output(clush_cmd, shell=True,
                                                 stderr=subprocess.STDOUT)
                value = result[result.index(':') + 1:-1].strip()
            except subprocess.CalledProcessError as e:
                msg = ("<<<Host %s execute clush failed:%s.>>>" % (
                    host_ip, e.output.strip()))
                LOG.error(msg)
                if e.returncode not in IGNORE_ERROR_CODE:
                    raise webob.exc.HTTPBadRequest(explanation=msg)
            except Exception:
                msg = "<<<Failed to get value from clush result.>>>"
                LOG.exception(msg)
                raise webob.exc.HTTPBadRequest(explanation=msg)
            else:
                msg = ("<<<Success to get value: %s from host %s.>>>" %
                       (value, host_ip))
                LOG.info(msg)
                config.update({'host_value': value})
        return template_configs

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
        restart_failed_services = {}
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

            failed_service = self._service_restart(role_info['service_name'],
                                                   host_management_ip)
            if failed_service:
                if host_management_ip not in restart_failed_services:
                    restart_failed_services.update({host_management_ip: []})
                restart_failed_services[host_management_ip].extend(
                    failed_service)

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

        if restart_failed_services:
            raise HTTPBadRequest("Services '%s' restart failed" %
                                 str(restart_failed_services))

    def _host_service_restart(self, host_ip, components_name):
        params = {'limit': '200', 'filters': {}}
        try:
            services = registry.get_services_detail(self.context,
                                                    **params)
            components = registry.get_components_detail(self.context,
                                                        **params)
        except exception.Invalid as e:
            raise HTTPBadRequest(explanation=e.msg)

        stop_ha = "clush -S -w %s '%s'" % (host_ip, self.STOP_HA_MANAGE_CMD)
        utils.simple_subprocess_call(stop_ha)

        components_id = [comp['id'] for comp in components
                         for comp_name in components_name
                         if comp['name'] == comp_name]

        restart_failed_service = []
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
                        restart_failed_service.append(service_name)
                        msg = "Service %s restart failed on host '%s'."\
                              % (service_name, host_ip)
                        LOG.error(msg)

        enable_ha = "clush -S -w %s '%s'" % (host_ip,
                                             self.ENABLE_HA_MANAGE_CMD)
        utils.simple_subprocess_call(enable_ha)

        return restart_failed_service

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
        host_detail = daisy_cmn.get_host_detail(self.req, host_id)

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

        host_management_ip = daisy_cmn.get_management_ip(host_detail)

        root_passwd = 'ossdbg1'
        daisy_cmn.trust_me([host_management_ip], root_passwd)

        self._openstack_set_config(host_management_ip, config_set)

        restart_failed_services = []
        node_restart_status = True
        if components_name:
            restart_failed_services.extend(self._host_service_restart(
                host_management_ip, components_name))
        else:
            template_config_id_list = [config['template_config_id']
                                       for config in config_set['config']
                                       if config['template_config_id']]
            services_restart_names, node_restart_names =\
                self.get_template_config_service(template_config_id_list)

            if node_restart_names:
                node_restart_status = self.node_restart(host_management_ip)
            elif services_restart_names:
                ovdk_config = [config for config in config_set['config']
                               if "ovdk" in config.get('config_file', "")]
                if ovdk_config:
                    self._service_restart(["ovdk"], host_management_ip)
                restart_failed_services.extend(self._service_restart(
                    services_restart_names, host_management_ip))

        all_config_sets = []
        for config in config_set['config']:
            config['running_version'] = config['config_version']
            all_config_sets.append(config_set)
            registry.update_configs_metadata_by_role_hosts(self.context,
                                                           all_config_sets)

        if restart_failed_services:
            raise HTTPBadRequest("Services '%s' restart failed on %s" %
                                 (','.join(restart_failed_services),
                                  host_management_ip))
        if not node_restart_status:
            raise HTTPBadRequest("Node '%s' restart failed" %
                                 host_management_ip)

    def _force_host_origin_config(self, host_config):
        is_restart_node = False
        services = set()
        for config in host_config.get('config_set', []):
            if config.get('force_type', '') in ['node']:
                is_restart_node = True
                break
            elif config.get('force_type', '') in ['service']:
                for service in config.get("services", []):
                    services.add(service)
        if is_restart_node:
            # restart node failed
            if not self.node_restart(host_config.get("ip")):
                LOG.error("Node '%s' restart failed" %
                          host_config.get("ip"))
                raise HTTPBadRequest("Node '%s' restart failed" %
                                     host_config.get("ip"))
        else:
            if self._service_restart_4_origin_config(services,
                                                     host_config.get("ip")):
                LOG.error("Services '%s' restart failed on %s" %
                          (','.join(services), host_config.get("ip")))
                raise HTTPBadRequest("Services '%s' restart failed on %s" %
                                     (','.join(services),
                                      host_config.get("ip")))

    def _check_valid_host_origin_config(self, host_config):
        def _check_config_action_valid(action):
            if action not in ['add', 'delete', 'set']:
                _exec_msg = "action field must be add/delete/set.%s" % action
                raise exception.Invalid(_exec_msg)

        def _check_config_force_type_valid(force_type):
            if force_type and force_type not in ['service', 'node', 'none']:
                _exec_msg = "force_type field must be service/node.%s" %\
                            force_type
                raise exception.Invalid(_exec_msg)

        def _check_config_file_valid(config_file):
            if not config_file:
                _exec_msg = "config_file field must be not empty."
                raise exception.Invalid(_exec_msg)

        def _check_config_key_valid(key):
            if not key:
                _exec_msg = "key field must be not empty."
                raise exception.Invalid(_exec_msg)

        def _check_config_file_format(file_format):
            if file_format not in ['SKV', 'others']:
                _exec_msg = "file_format field must be SKV/others."
                raise exception.Invalid(_exec_msg)

        def _check_config_skv_format_valid(in_config):
            if in_config.get("section") is None:
                _exec_msg = "section field must be not empty"
                raise exception.Invalid(_exec_msg)
            if in_config.get('action') in ['set'] and\
                    not in_config.get("value"):
                _exec_msg = "value field must be not empty"
                raise exception.Invalid(_exec_msg)

        def _check_config_others_format_valid(in_config):
            if in_config.get('action') in ['add', 'set']:
                if not in_config.get("value"):
                    _exec_msg = "value field must be not empty"
                    raise exception.Invalid(_exec_msg)
                if not in_config.get("separator"):
                    _exec_msg = "separator field must be not empty"
                    raise exception.Invalid(_exec_msg)

        if not host_config.get("ip"):
            _msg = "ip is not valid."
            raise exception.Invalid(_msg)
        if not host_config.get("config_set"):
            _msg = "config set is not valid."
            raise exception.Invalid(_msg)
        for config in host_config.get('config_set', []):
            _check_config_action_valid(config.get("action"))
            _check_config_force_type_valid(config.get("force_type"))
            _check_config_file_valid(config.get("config_file"))
            _check_config_key_valid(config.get("key"))
            _check_config_file_format(config.get("file_format"))
            if config.get("file_format") in ['SKV']:
                _check_config_skv_format_valid(config)
            else:
                _check_config_others_format_valid(config)

    def push_origin_config_to_host(self, host_config):
        root_passwd = 'ossdbg1'
        # check host config
        self._check_valid_host_origin_config(host_config)
        daisy_cmn.trust_me([host_config["ip"]], root_passwd)
        # push host config
        self._push_origin_config_to_host(host_config)
        # restart host or service
        self._force_host_origin_config(host_config)

    def _service_restart_4_origin_config(self, services, host_ip):
        """  """
        stop_ha = "clush -S -w %s '%s'" % (host_ip, self.STOP_HA_MANAGE_CMD)
        utils.simple_subprocess_call(stop_ha)

        restart_failed_service = []
        for service in services:
            active_service = "clush -S -w %s 'systemctl is-active\
                             %s'" % (host_ip, service)
            if 0 == utils.simple_subprocess_call(active_service):
                restart_service = "clush -S -w %s 'systemctl restart\
                                  %s'" % (host_ip, service)
                LOG.info("Restart service %s after pushing config"
                         % service)
                if 0 != utils.simple_subprocess_call(restart_service):
                    restart_failed_service.append(service)
                    msg = "Service %s restart failed on host '%s'."\
                          % (service, host_ip)
                    LOG.error(msg)
        enable_ha = "clush -S -w %s '%s'" % (host_ip,
                                             self.ENABLE_HA_MANAGE_CMD)
        utils.simple_subprocess_call(enable_ha)
        return restart_failed_service

    def _service_restart(self, services_name, host_ip):
        """  """
        stop_ha = "clush -S -w %s '%s'" % (host_ip, self.STOP_HA_MANAGE_CMD)
        utils.simple_subprocess_call(stop_ha)

        restart_failed_service = []
        for service in services_name:
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
                        restart_failed_service.append(service_name)
                        msg = "Service %s restart failed on host '%s'."\
                              % (service_name, host_ip)
                        LOG.error(msg)

        enable_ha = "clush -S -w %s '%s'" % (host_ip,
                                             self.ENABLE_HA_MANAGE_CMD)
        utils.simple_subprocess_call(enable_ha)
        return restart_failed_service

    def get_host_configs(self, host_id, template_configs):
        """
        Pull config from remote host.
        :param configs: template config list
        :param host_ip: host ip
        :param host_password: host password, default is 'ossdbg1'
        :return configs
        """
        host_detail = daisy_cmn.get_host_detail(self.req, host_id)
        host_management_ip = daisy_cmn.get_management_ip(host_detail)
        daisy_cmn.trust_me([host_management_ip], host_detail['root_pwd'])
        return self._openstack_get_config(host_management_ip, template_configs)

    def get_template_config_service(self, template_config_id_list):
        services_restart_names = set()
        node_restart_names = set()
        for template_config_id in template_config_id_list:
            template_config_detail = registry.get_template_config_metadata(
                self.context, template_config_id)
            for service in template_config_detail.get('services', []):
                if not service.get('service_name'):
                    continue
                if service.get('force_type') in ['service']:
                    services_restart_names.add(service['service_name'])
                elif service.get('force_type') in ['node']:
                    node_restart_names.add(service['service_name'])
        return services_restart_names, node_restart_names

    def node_restart(self, host_ip):
        """restart remote host"""
        cmd = 'reboot'
        restart_node_cmd = self.CLUSH_CMD % {'management_ip': host_ip,
                                             'sub_command': cmd}
        LOG.info("Restart host %s after pushing config" % host_ip)
        if 0 != utils.simple_subprocess_call(restart_node_cmd):
            LOG.error("Restart host %s failed." % host_ip)
            return False
        return True
