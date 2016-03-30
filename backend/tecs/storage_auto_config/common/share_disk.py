
from utils import *


class BaseShareDisk():
    instance = None

    def __init__(self):
        self._PROTOCOL_MAPPING = {
            'ISCSI': ISCSIShareDisk,
            'CEPH': CEPHShareDisk
        }
        self.instance_mapping = {}

    def __get_protocol_instance(self, protocol_type):
        if not protocol_type or \
           protocol_type not in self._PROTOCOL_MAPPING.keys():
            print_or_raise("Protocol type '%s' is not valid." % protocol_type,
                           ScriptInnerError)

        protocol_instance = self.instance_mapping.get(protocol_type,
                                                      BaseShareDisk)
        if isinstance(protocol_instance,
                      self._PROTOCOL_MAPPING[protocol_type]):
            return protocol_instance
        else:
            self.instance_mapping.update(
                {protocol_type: self._PROTOCOL_MAPPING[protocol_type]()})
            return self.instance_mapping[protocol_type]

    @classmethod
    def single_instance(cls):
        if not BaseShareDisk.instance:
            BaseShareDisk.instance = BaseShareDisk()
        return BaseShareDisk.instance

    def deploy_share_disk(self, item, host_name):
        protocol_instance = self.__get_protocol_instance(
            item.get('protocol_type', 'ISCSI'))
        protocol_instance.deploy_share_disk(item, host_name)


class ISCSIShareDisk(BaseShareDisk):
    _LV_DEFAULT_NAME = {
        'glance': ("VolGroupHAImage", "lvHAImage", 254),
        'db': ("VolGroupHAMysql", "lvHAMysql", 253),
        'db_backup': ("VolGroupHABakMysql", "lvHABakMysql", 252),
        'mongodb': ("VolGroupHAMongodb", "lvHAMongodb", 251),
    }

    def _get_iscsi_configs(self, record_list):
        raid_config = {}
        for record in record_list:
            discovery_media_ip = record.split(" ")[0].split(":")[0]
            discovery_media_iqn = record.split(" ")[1]
            try:
                execute("ping -c 1 -W 2 %s" % discovery_media_ip)
            except ProcessExecutionError:
                execute("iscsiadm -m node -T %s -p %s -o delete" %
                        (discovery_media_iqn, discovery_media_ip),
                        check_exit_code=[0, 1])
                continue

            if discovery_media_ip in raid_config.get(discovery_media_iqn, []):
                execute("iscsiadm -m node -T %s -p %s -R" %
                        (discovery_media_iqn, discovery_media_ip),
                        check_exit_code=[0, 1])

            elif discovery_media_iqn in raid_config.keys():
                raid_config[discovery_media_iqn] += [discovery_media_ip]
            else:
                raid_config[discovery_media_iqn] = [discovery_media_ip]

        print_or_raise("Raid config is:\n%s" % str(raid_config))
        return raid_config

    def _lv_reentrant_check(
            self, vg_name, lv_name, iscsi_session_setup, lun=None,
            data_ips=[]):
        """
        Check if share disk operation is reentrant.
        :return:True,continue follow action; False, do nothing.
        """
        lv_device_path = "/dev/%s/%s" % (vg_name, lv_name)
        if not os.path.exists(lv_device_path):
            return True

        if not iscsi_session_setup:
            exist_volumes = \
                [sd for sd in self._ls_sd_path() if "-lun-" + lun in sd
                 for ip in data_ips if "ip-" + ip in sd]
            if not exist_volumes:
                print_or_raise("Lvm %s is exist, but no sd device match!" %
                               lv_device_path, ScriptInnerError)

        return False

    def _lv_rollback(self, lv, vg, block_device):
        try:
            execute("lvremove -y -ff /dev/%s/%s" % (lv, vg),
                    check_exit_code=[0, 1, 5])
            execute("vgremove -y -ff %s" % vg, check_exit_code=[0, 1, 5])
            execute("pvremove -y -ff %s" % block_device,
                    check_exit_code=[0, 1, 5])
        except Exception as e:
            print_or_raise("Rollback lvm resource failed!", e)

    def _establish_iscsi_session(self, available_data_ips):
         # discovery
        discovery_ret = ""
        for ip in available_data_ips:
            out, err = execute(
                "iscsiadm -m discovery -t st -p %s:3260" % ip)
            discovery_ret += out
            # if('0' != err) or ('0\n' != err ) or err:
            #     print_or_raise("Discovery ip:%s failed,continue.." % ip)

        if not discovery_ret:
            print_or_raise("No discovery record!", ScriptInnerError)

        record_list = list(set(discovery_ret.split('\n')[:-1]))
        print_or_raise(
            "Discovery successful! Record:\n%s" % "\n".join(record_list))

        # get iqn and ip like {iqn1: ip1, iqn2:ip2}
        raid_config = self._get_iscsi_configs(record_list)

        # auto config & login
        login_cmd = \
            lambda x, y: "iscsiadm -m node -T %s -p %s:3260 -l" % (x, y)
        auto_cmd = \
            lambda x, y: "iscsiadm -m node -T %s -p %s -o update -n " \
                         "node.startup -v automatic" % (x, y)
        login = []
        auto_config = []
        for index in range(len(raid_config.keys())):
            k = raid_config.keys()[index]
            v = raid_config[k]
            login += map(login_cmd, [k] * len(v), v)
            auto_config += map(auto_cmd, [k] * len(v), v)
        execute(";".join(login))
        execute(";".join(auto_config))
        print_or_raise("Login successful!")
        return raid_config

    def _modify_host_iqn(self, host_name):
        # modify host IQN
        host_iqn, err = execute("cat /etc/iscsi/initiatorname.iscsi")
        md5_str, err = execute("echo -n %s | openssl md5" % host_name)
        host_iqn = host_iqn.split("=")[1].strip()
        wish_iqn = "iqn.opencos.rh:" + md5_str.split("=")[1].strip()
        if wish_iqn != host_iqn:
            print_or_raise(
                "The host iqn is:%s, but wish iqn is %s, it will be modified."
                % (host_iqn, wish_iqn))
            with open("/etc/iscsi/initiatorname.iscsi", "w") as fp:
                fp.write("InitiatorName=" + wish_iqn + "\n")
            execute("systemctl restart iscsid.service")

    def _ls_sd_path(self):
        out, err = execute("ls /dev/disk/by-path")
        return out.split("\n")[:-1]

    def _find_multipath_by_sd(self, iqns, lun_id):
        sd_path = []
        attemps = 0
        while not sd_path:
            sd_path = \
                [sd for sd in self._ls_sd_path()
                 if filter(lambda complex_sd_path: complex_sd_path in sd,
                 [iqn + "-lun-" + str(lun_id) for iqn in iqns])]
            attemps += 1

            if attemps == 5:
                execute("iscsiadm -m node -R")
            elif attemps > 10:
                print_or_raise(
                    "After login successful,"
                    "there is no local sd device match with block device.",
                    ScriptInnerError)

            time.sleep(2)

        sd_path = "/dev/disk/by-path/" + sd_path[0]
        sd_real_path = os.path.realpath(sd_path)

        attemps = 0
        multipath_path = ""
        while not os.path.exists(multipath_path):
            multipath_device, err = execute("multipath -l %s" % sd_real_path)
            # if not multipath_device or ('0' != err) or ('0\n' != err) or err:
            #     continue

            multipath_path = "/dev/mapper/" + \
                             multipath_device.split("\n")[0].split(" ")[0]
            attemps += 1

            if attemps > 5:
                print_or_raise(
                    "No multipath match with local sd device:%s." %
                    sd_real_path,
                    ScriptInnerError)
            time.sleep(2)

        return multipath_path

    def _create_lv_by_multipath_device(
            self, multipath, vg_name, lv_name, size, fs_type):
        try:
            # create lvm base on block device
            execute("pvcreate -y -ff %s" % multipath,
                    check_exit_code=[0, 1, 5])
            execute("vgcreate -y -ff %s %s" % (vg_name, multipath),
                    check_exit_code=[0, 1, 5])

            if size == -1:
                lvcreate = "lvcreate -W y -l 100%%FREE -n %s %s" % \
                           (lv_name, vg_name)
            else:
                lvcreate = "lvcreate -W y -L %sG -n %s %s" % \
                           (round(size * 0.95, 2), lv_name, vg_name)
            execute(lvcreate, check_exit_code=[0, 1, 5])
            execute("pvscan --cache --activate ay")

            # make filesystem
            execute("mkfs.%s /dev/%s/%s" % (fs_type, vg_name, lv_name))
        except Exception as e:
            self._lv_rollback(lv_name, vg_name, multipath)
            print_or_raise("LVM create failed, resource has been rollbacked.",
                           e)

    def deploy_share_disk(self, item, host_name):
        config_computer()
        self._modify_host_iqn(host_name)
        service = item['service']
        if service not in ['glance', 'db', 'db_backup', 'mongodb']:
            print_or_raise("Service name '%s' is not valid." % service)

        # check ip
        available_data_ips, invalid_ips = \
            get_available_data_ip(item['data_ips'])
        if not available_data_ips:
            print_or_raise("No valid data ips,please check.", ScriptInnerError)

        raid_config = self._establish_iscsi_session(available_data_ips)

        lv_config = item.get('lvm_config', None)
        vg_name = lv_config.get('vg_name', self._LV_DEFAULT_NAME[service][0])
        lv_name = lv_config.get('lv_name', self._LV_DEFAULT_NAME[service][1])
        if not self._lv_reentrant_check(vg_name, lv_name, True):
            return

        multipath = self._find_multipath_by_sd(
            raid_config.keys(),
            item.get('lun', self._LV_DEFAULT_NAME[service][2]))

        self._create_lv_by_multipath_device(multipath,
                                            vg_name,
                                            lv_name,
                                            lv_config.get('size', -1),
                                            lv_config.get('fs_type', 'ext4'))


class CEPHShareDisk(BaseShareDisk):
    def __init__(self):
        self.monitor_ip = ''
        self.monitor_passwd = ''

    def deploy_share_disk(self, item, host_name):
        self.monitor_ip = item.get('monitor_ip', '')
        self.monitor_passwd = item.get('monitor_passwd', '')
        rbd_pool = item['rbd_config']['rbd_pool']
        rbd_img = item['rbd_config']['rbd_volume']
        img_size = int(item['rbd_config']['size'])*1024
        fs_type = item['rbd_config'].get('fs_type', 'ext4')
        cmd_create = 'sshpass -p %s ssh %s rbd create -p %s --size %s  %s ' % \
                     (self.monitor_passwd,
                      self.monitor_ip,
                      rbd_pool,
                      img_size,
                      rbd_img)
        cmd_query = 'sshpass -p %s ssh %s rbd ls -l %s' % (
            self.monitor_passwd, self.monitor_ip,  rbd_pool)
        image_in_monitor = []
        print_or_raise("Create image %s in pool %s at monitor %s." %
                       (rbd_img, rbd_pool, self.monitor_ip))
        try:
            out, err = execute(cmd_query)
            if out:
                for line in out.splitlines():
                    image_in_monitor.append(line.split()[0])
                if rbd_img not in image_in_monitor:
                    execute(cmd_create)
        except Exception as e:
            print_or_raise("Query pool %s in monitor error or create image %s "
                           "in pool %s." % (rbd_pool, rbd_img, rbd_pool), e)
        execute("systemctl stop rbdmap")
        rbd_map = '%s/%s id=admin,' \
                  'keyring=/etc/ceph/ceph.client.admin.keyring' % (rbd_pool,
                                                                   rbd_img)
        rbd_map_need_to_write = True
        print_or_raise("Write rbdmap.")
        with open("/etc/ceph/rbdmap", "a+") as fp:
            for line in fp:
                if line == rbd_map + "\n":
                    rbd_map_need_to_write = False
            if rbd_map_need_to_write is True:
                fp.write(rbd_map + "\n")
                execute("chmod 777 /etc/ceph/rbdmap")
        execute("systemctl enable rbdmap")
        execute("systemctl start rbdmap")
        execute("mkfs.%s /dev/rbd/%s/%s" % (fs_type, rbd_pool, rbd_img))
