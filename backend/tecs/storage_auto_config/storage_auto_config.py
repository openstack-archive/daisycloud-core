###############################################################################
#   Author: CG
#   Description:
#   1.The script should be copied to the host, before running.
#   2.The script is not thread safe.
#   3.Example for script call:
#     [config share disk]:
#         python storage_auto_config share_disk <host_pxe_mac>,
#     we use host_pxe_mac to generate host IQN by md5 and write it to
#     '/etc/iscsi/initiatorname.iscsi'
#     [config cinder]: python storage_auto_config cinder_conf 10.43.177.129,
#     the second parameter for cinder_config is cinder <host_ip>.
#       If the backend is CEPH,you should call the following command:
#       python storage_auto_config glance_rbd_conf at glance node &
#       python storage_auto_config nova_rbd_conf at nova node.
#     [config multipath]:python storage_auto_config check_multipath.
#   4.Before run script,the cinder.json and control.json  file
#     must be  must be config.
###############################################################################
import sys
import uuid
import traceback
from common.utils import *
from common.cinder_conf import BaseConfig, CEPHBackendConfig
from common.share_disk import BaseShareDisk

try:
    import simplejson as json
except ImportError:
    import json


def _set_config_file(file, section, key, value):
    set_config = BaseConfig.SET_CONFIG.format(
        config_file=file,
        section=section,
        key=key,
        value=value)
    execute(set_config)


def config_share_disk(config, host_name):
    # deploy share_disk
    for item in config:
        BaseShareDisk.single_instance().deploy_share_disk(item, host_name)


def config_cinder(config, cinder_host_ip=""):
    # config xml and cinder.conf
    for config in config['disk_array']:
        # load disk array global config
        backends = config['backend']
        for item in backends.items():
            BaseConfig.single_instance().config_backend(
                item,
                management_ips=config.get('management_ips', []),
                data_ips=config.get('data_ips', []),
                user_name=config.get('user_name', []),
                user_pwd=config.get('user_pwd', []),
                cinder_host_ip=cinder_host_ip)

    # config multipath
    config_computer()

    # enable config
    execute("systemctl restart openstack-cinder-volume.service")


def config_nova_with_rbd(config):
    # config xml and cinder.conf
    for config in config['disk_array']:
        # load disk array global config
        backends = config['backend']
        for key, value in backends.items():
            if value.get('volume_driver') == 'CEPH':
                uuid_instance = uuid.uuid3(uuid.NAMESPACE_DNS, "zte.com.cn")
                uuid_str = uuid_instance.urn.split(":")[2]
                _set_config_file(CEPHBackendConfig.NOVA_CONF_FILE,
                                 'libvirt',
                                 'images_type',
                                 'rbd')
                _set_config_file(CEPHBackendConfig.NOVA_CONF_FILE,
                                 'libvirt',
                                 'rbd_secret_uuid',
                                 uuid_str)
                return

    # enable config
    execute("systemctl restart openstack-nova-compute.service")


def config_glance_with_rbd(config):
    # config xml and cinder.conf
    for config in config['disk_array']:
        # load disk array global config
        backends = config['backend']
        for key, value in backends.items():
            if value.get('volume_driver') == 'CEPH':
                _set_config_file(CEPHBackendConfig.GLANCE_API_CONF_FILE,
                                 'DEFAULT',
                                 'show_image_direct_url',
                                 'True')
                _set_config_file(CEPHBackendConfig.GLANCE_API_CONF_FILE,
                                 'glance_store',
                                 'default_store',
                                 'rbd')
                return

    # enable config
    execute("systemctl restart openstack-glance-api.service")


def _launch_script():
    def subcommand_launcher(args, valid_args_len, json_path, oper_type):
        if len(args) < valid_args_len:
            print_or_raise("Too few parameter is given,please check.",
                           ScriptInnerError)

        with open(json_path, "r") as fp_json:
            params = json.load(fp_json)

        print_or_raise("-----Begin config %s, params is %s.-----" %
                       (oper_type, params))
        return params

    oper_type = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if oper_type == "share_disk":
            share_disk_config = \
                subcommand_launcher(sys.argv, 3, "base/control.json",
                                    oper_type)
            config_share_disk(share_disk_config, sys.argv[2])
        elif oper_type == "cinder_conf":
            cinder_backend_config = subcommand_launcher(sys.argv, 3,
                                                        "base/cinder.json",
                                                        oper_type)
            config_cinder(cinder_backend_config, sys.argv[2])
        elif oper_type == "nova_rbd_conf":
            nova_rbd_config = subcommand_launcher(sys.argv, 1,
                                                  "base/cinder.json",
                                                  oper_type)
            config_nova_with_rbd(nova_rbd_config)
        elif oper_type == "glance_rbd_conf":
            glance_rbd_config = subcommand_launcher(sys.argv, 1,
                                                    "base/cinder.json",
                                                    oper_type)
            config_glance_with_rbd(glance_rbd_config)
        elif oper_type == "check_multipath":
            print_or_raise("-----Begin config %s.-----")
            config_computer()
        elif oper_type == "debug":
            pass
        else:
            print_or_raise("Script operation is not given,such as:share_disk,"
                           "cinder_conf,nova_rbd_conf,glance_rbd_conf,"
                           "check_multipath.", ScriptInnerError)
    except Exception as e:
        print_or_raise("----------Operation %s is Failed.----------\n"
                       "Exception call chain as follow,%s" %
                       (oper_type, traceback.format_exc()))
        raise e
    else:
        print_or_raise("----------Operation %s is done!----------" %
                       oper_type)


if __name__ == "__main__":
    _launch_script()