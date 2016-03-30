
import subprocess
import daisy.registry.client.v1.api as registry
from daisy.api.backends.tecs import config
from oslo_log import log as logging
import webob.exc

LOG = logging.getLogger(__name__)
CONFIG_MAP = {
    'cinder_config': '/etc/cinder/cinder.conf',
    'cinder_api_paste_ini': '/etc/cinder/api-paste.ini',
    'glance_api_config': '/etc/glance/glance-api.conf',
    'glance_api_paste_ini': '/etc/glance/glance-api-paste.ini',
    }

class config_clushshell():
    """ Class for clush backend."""
    def __init__(self, req, role_id):
        if not req and not role_id:
            LOG.error("<<<config_clushshell:push_config input params is invalid.>>>")
            return

        self.context = req.context
        self.role_id = role_id

        self.CLUSH_CMD = "clush -S -w %(management_ip)s \"%(sub_command)s\""
        self.SUB_COMMAND = "openstack-config --set %(config_file)s %(section)s %(key)s %(value)s"

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

        sub_command_by_one_host = []
        for config in config_set['config']:
            if config['config_version'] == config['running_version']:
                continue

            config_file = registry.get_config_file_metadata(self.context, config['config_file_id'])
            sub_command_by_one_host.append(
                self.SUB_COMMAND % \
                {'config_file':config_file['name'] ,'section':config['section'],
                 'key':config['key'], 'value':config['value']})

        try:
            sub_command_by_one_host = ";".join(sub_command_by_one_host)
            clush_cmd = self.CLUSH_CMD % {'management_ip':host_ip, 'sub_command':sub_command_by_one_host}
            subprocess.check_output(clush_cmd, shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            msg = ("<<<Host %s excute clush failed:%s!>>>" % (host_ip, e.output.strip()))
            LOG.exception(msg)
            raise webob.exc.HTTPServerError(explanation=msg)
        else:
            msg = ("<<<Host %s excute clush successful!>>>" % host_ip)
            LOG.info(msg)
            config['running_version'] = config['config_version']

    def push_config(self):
        """
        Push config to remote host.
        :param req: http req
        :param role_id: host role id
        :return:
        """
        self.role_info = registry.get_role_metadata(self.context, self.role_id)
        if not self.role_info or not self.role_info.get('config_set_id'):
            LOG.error("<<<config_clushshell:push_config,get_role_metadata failed.>>>")
            return

        config_set = registry.get_config_set_metadata(self.context, self.role_info['config_set_id'])
        if not config_set or not config_set.has_key('config'):
            LOG.info("<<<config_clushshell:push_config,get_config_set_metadata failed.>>>")
            return

        config_set['config'] = \
            [config for config in config_set['config']
             if config.has_key('config_version') and config.has_key('running_version')
             and config['config_version'] != config['running_version']]

        if not config_set['config']:
            LOG.info('<<<No config need to be modified, within the scope of the hosts in role_id:%s.>>>' %
                     self.role_id)
            return

        self.role_hosts = registry.get_role_host_metadata(self.context, self.role_id)
        current_count = 0
        all_host_config_sets = []
        for role_host in self.role_hosts:
            host = registry.get_host_metadata(self.context, role_host['host_id'])
            #change by 10166727--------start-------------
            host_ip=[]
            for interface in host['interfaces']:
                find_flag=interface['ip'].find(':')
                if find_flag<0:
                    host_ip=[interface['ip']]
                else:
                    ip_list_tmp=interface['ip'].split(",")
                    for ip_list in ip_list_tmp:
                        if ip_list.split(':')[0] == "MANAGEMENT":
                            host_ip=[str(ip_list.split(':')[1])]
            #change by 10166727--------end---------------
            if not host_ip:
                continue
            host_ip = host_ip[0]

            if 0 != subprocess.call('/var/lib/daisy/tecs/trustme.sh %s %s' % (host_ip, 'ossdbg1'),
                                    shell=True,
                                    stderr=subprocess.STDOUT):
                raise Exception("trustme.sh error!")
            if not config_set.has_key("config"):
                continue

            self._openstack_set_config(host_ip, config_set)
            all_host_config_sets.append(config_set)
            registry.update_configs_metadata_by_role_hosts(self.context, all_host_config_sets)

            LOG.debug("Update config for host:%s successfully!" % host_ip)

            self._host_service_restart(host_ip)
            current_count +=1
            self.role_info['config_set_update_progress'] = round(current_count*1.0/len(self.role_hosts), 2)*100
            registry.update_role_metadata(self.context, self.role_id, self.role_info)

    def _host_service_restart(self,host_ip):
        """  """
        for service in self.role_info['service_name']:
            for service_detail_name in config.service_map.get(service).split(','):
                cmd = ""
                if self.role_info['name'] == "CONTROLLER_HA":
                    cmd = "clush -S -w %s [ `systemctl is-active %s` != 'active' ] && systemctl restart  %s" % \
                    (host_ip, service_detail_name, service_detail_name)
                else:
                    cmd = "clush -S -w %s systemctl restart %s" % (host_ip, service_detail_name)
                if 0 != subprocess.call(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE):
                    LOG.error("Service %s restart failed in host:%s." % (service_detail_name, host_ip))

    