
import uuid
from utils import *
from xml.etree.ElementTree import ElementTree, Element


class BaseConfig():
    _CINDER_CONF_PATH = "/etc/cinder/cinder.conf"
    SET_CONFIG = \
        "openstack-config --set {config_file} {section} {key} {value}"
    GET_CONFIG = \
        "openstack-config --get {config_file} {section} {key}"
    instance = None

    def __init__(self):
        self._BACKEND_MAPPING = {
            'KS3200_IPSAN': ZTEBackendConfig,
            'KS3200_FCSAN': ZTEBackendConfig,
            'FUJISTU_ETERNUS': FUJISTUBackendConfig,
            'LVM': None,
            'CEPH': CEPHBackendConfig,
        }
        self.instance_mapping = {}

    def __get_backend_instance(self, backend_type):
        if not backend_type or \
           backend_type not in self._BACKEND_MAPPING.keys():
            print_or_raise("Volume driver type '%s' is not valid." %
                           backend_type,
                           ScriptInnerError)

        backend_instance = self.instance_mapping.get(backend_type, BaseConfig)
        if isinstance(backend_instance, self._BACKEND_MAPPING[backend_type]):
            return backend_instance
        else:
            self.instance_mapping.update(
                {backend_type: self._BACKEND_MAPPING[backend_type]()})
            return self.instance_mapping[backend_type]

    @classmethod
    def single_instance(cls):
        if not BaseConfig.instance:
            BaseConfig.instance = BaseConfig()
        return BaseConfig.instance

    def _construct_particular_cinder_data(self, backend, backend_data):
        print_or_raise("Backend _construct_particular_cinder_data method no "
                       "implement!", ScriptInnerError)

    def _write_xml(self, fp_xml, **backend_device_args):
        self.backend_instance._write_xml(fp_xml, **backend_device_args)

    def _construct_commonality_cinder_data(self, backend, backend_data):
        backend_pools, xml_path = \
            self.backend_instance._construct_particular_cinder_data(
                backend, backend_data)

        backend_data['volume_backend_name'] = \
            backend_data.pop('volume_type')

        set_backend = lambda x, y: self.SET_CONFIG.format(
            config_file=self._CINDER_CONF_PATH,
            section=backend,
            key=x, value=y)

        backend_config_list = list()
        backend_config_list += map(
            set_backend, backend_data.keys(), backend_data.values())

        get_bakcends = \
            self.GET_CONFIG.format(config_file=self._CINDER_CONF_PATH,
                                    section="DEFAULT",
                                    key="enabled_backends")
        out, err = execute(get_bakcends, check_exit_code=[0, 1])
        exist_backends = out.split("\n")[0] if out else ""
        enabled_backends = \
            exist_backends if backend in exist_backends else \
            "%s" % backend if not out else "%s,%s" % \
                                           (exist_backends, backend)
        set_bakcends = \
            self.SET_CONFIG.format(config_file=self._CINDER_CONF_PATH,
                                    section="DEFAULT",
                                    key="enabled_backends",
                                    value=enabled_backends)

        # write to cinder.conf
        config_set_all = set_bakcends + ";" + ";".join(backend_config_list)
        execute(config_set_all)

        return backend_pools, xml_path

    def is_needed_generate_backend_xml(self, backend_driver):
        if backend_driver in ['KS3200_IPSAN', 'KS3200_FCSAN',
                              'FUJISTU_ETERNUS']:
            return True
        else:
            return False

    def config_backend(self, backend_cinder_args, **backend_device_args):
        """
        Config outer interface,for public flow.
        :param backend_device_args: device config
        :param backend_cinder_args: backend config
        :return:
        """
        backend_data = backend_cinder_args[1]
        backend_driver = backend_data.get('volume_driver', None)
        self.backend_instance = self.__get_backend_instance(backend_driver)

        # config cinder.conf
        backend_pools, xml_path = \
            self._construct_commonality_cinder_data(backend_cinder_args[0],
                                                    backend_data)

        # config xml
        if self.is_needed_generate_backend_xml(backend_driver):
            backend_device_args.update({'pools': backend_pools})
            with open(xml_path, "w+") as fp_xml:
                self._write_xml(fp_xml, **backend_device_args)
                execute("chown cinder:cinder %s" % xml_path)

    def update_xml_node(self, element_obj, node_path, content):
        node_list = element_obj.findall(node_path)
        if node_list:
            node_list[0].text = content
        else:
            new_element = Element(node_path.split('/')[-1])
            new_element.text = content
            parent_node = element_obj.findall(node_path.split('/')[0])
            parent_node[0].append(new_element)


class ZTEBackendConfig(BaseConfig):
    _DEFAULT_USERNAME = "admin"
    _DEFAULT_USERPWD = "admin"
    _DEFAULT_XML_FILE_PREFIX = "cinder_zte_conf_file"
    _DEFAULT_XML_TEMPLATE_PATH = "/etc/cinder/cinder_zte_conf.xml"
    _ISCSI_DRIVER = 'cinder.volume.drivers.zte.zte_ks.ZteISCSIDriver'
    _FC_DRIVER = 'cinder.volume.drivers.zte.zte_ks.ZteFCDriver'

    def _construct_particular_cinder_data(self, backend, backend_data):
        # construct commonality data in cinder.conf
        backend_data['volume_driver'] = \
            self._ISCSI_DRIVER \
            if "KS3200_IPSAN" == backend_data['volume_driver'] \
            else self._FC_DRIVER
        backend_data[self._DEFAULT_XML_FILE_PREFIX] = \
            backend_data.pop('backend_config_file') \
            if backend_data.get('backend_config_file', None) \
            else "/etc/cinder/%s_%s.xml" % (self._DEFAULT_XML_FILE_PREFIX,
                                            backend)
        backend_data['use_multipath_for_image_xfer'] = \
            backend_data.get('multipath_tool', True)
        backend_pools = backend_data.pop('pools')

        return backend_pools, backend_data[self._DEFAULT_XML_FILE_PREFIX]

    def _write_xml(self, fp, **backend_device_args):
        if not os.path.exists(self._DEFAULT_XML_TEMPLATE_PATH):
            print_or_raise("XML file template %s not exists,can't load defult "
                           "params." % self._DEFAULT_XML_TEMPLATE_PATH,
                           ScriptInnerError)

        mgnt_ips = backend_device_args['management_ips']
        user_name = backend_device_args['user_name']
        user_pwd = backend_device_args['user_pwd']
        cinder_host_ip = backend_device_args['cinder_host_ip']
        pools = backend_device_args['pools']
        xml_fp = fp

        tree = ElementTree()
        elements = tree.parse(self._DEFAULT_XML_TEMPLATE_PATH)
        for index in range(len(mgnt_ips)):
            self.update_xml_node(
                elements,
                "Storage/ControllerIP" + str(index), mgnt_ips[index])

        if cinder_host_ip:
            self.update_xml_node(elements, "Storage/LocalIP", cinder_host_ip)
        self.update_xml_node(elements, "Storage/UserName", user_name)
        self.update_xml_node(elements, "Storage/UserPassword", user_pwd)

        # del all StoragePool and StorageVd node
        pool_parent_node = elements.findall("LUN")
        pool_child_nodes = elements.findall("LUN/StoragePool")
        vd_child_nodes = elements.findall("LUN/StorageVd")
        map(pool_parent_node[0].remove, pool_child_nodes + vd_child_nodes)

        # add StoragePool node base on pools
        for pool in pools:
            element = Element("StoragePool")
            element.text = pool
            element.tail = "\n\t"
            pool_parent_node[0].insert(0, element)

        tree.write(xml_fp, encoding="utf-8", xml_declaration=True)


class FUJISTUBackendConfig(BaseConfig):
    _DEFAULT_USERNAME = "root"
    _DEFAULT_USERPWD = "root"
    _DEFAULT_XML_FILE_PREFIX = "cinder_eternus_config_file"
    _DEFAULT_XML_TEMPLATE_PATH = \
        "/etc/cinder/cinder_fujitsu_eternus_dx.xml"
    FUJISTU_DRIVER = \
        "cinder.volume.drivers.fujitsu.eternus_dx_iscsi.FJDXISCSIDriver"

    def _construct_particular_cinder_data(self, backend, backend_data):
        # construct commonality data in cinder.conf
        backend_data['volume_driver'] = self.FUJISTU_DRIVER
        backend_data[self._DEFAULT_XML_FILE_PREFIX] = \
            backend_data.pop('backend_config_file') \
            if backend_data.get('backend_config_file', None) \
            else "/etc/cinder/%s_%s.xml" % (self._DEFAULT_XML_FILE_PREFIX,
                                            backend)
        backend_data['use_multipath_for_image_xfer'] = \
            backend_data.get('multipath_tool', True)
        backend_data['use_fujitsu_image_volume'] = \
            backend_data.get('use_fujitsu_image_volume', True)
        backend_data['fujitsu_min_image_volume_per_storage'] = \
            backend_data.get('fujitsu_min_image_volume_per_storage', 1)
        backend_data['fujitsu_image_management_dir'] = \
            backend_data.get('fujitsu_image_management_dir',
                             '/var/lib/glance/conversion')
        backend_pools = backend_data.pop('pools')

        return backend_pools, backend_data[self._DEFAULT_XML_FILE_PREFIX]

    def _write_xml(self, fp, **backend_device_args):
        if not os.path.exists(self._DEFAULT_XML_TEMPLATE_PATH):
            print_or_raise("XML file template %s not exists,can't load defult "
                           "params." % self._DEFAULT_XML_TEMPLATE_PATH,
                           ScriptInnerError)

        mgnt_ip = backend_device_args['management_ips'][0]
        data_ips = backend_device_args['data_ips']
        user_name = backend_device_args['user_name']
        user_pwd = backend_device_args['user_pwd']
        pool = backend_device_args['pools'][0]
        xml_fp = fp

        tree = ElementTree()
        elements = tree.parse(self._DEFAULT_XML_TEMPLATE_PATH)
        self.update_xml_node(elements, "EternusIP", mgnt_ip)
        self.update_xml_node(elements, "EternusUser", user_name)
        self.update_xml_node(elements, "EternusPassword", user_pwd)
        self.update_xml_node(elements, "EternusPool", pool)
        self.update_xml_node(elements, "EternusSnapPool", pool)

        root = tree.getroot()
        map(root.remove, root.findall("EternusISCSIIP"))
        for ip in data_ips:
            element = Element("EternusISCSIIP")
            element.text = ip
            element.tail = "\n"
            root.insert(4, element)
            # root.append(element)

        tree.write(xml_fp, encoding="utf-8", xml_declaration=True)


class CEPHBackendConfig(BaseConfig):
    NOVA_CONF_FILE = "/etc/nova/nova.conf"
    GLANCE_API_CONF_FILE = "/etc/glance/glance-api.conf"
    _RBD_STORE_USER = "cinder"
    _RBD_POOL = "volumes"
    _RBD_MAX_CLONE_DEPTH = 5
    _RBD_FLATTEN_VOLUME_FROM_SNAPSHOT = "False"
    _RBD_CEPH_CONF = "/etc/ceph/ceph.conf"
    _RBD_DRIVER = 'cinder.volume.drivers.rbd.RBDDriver'

    def _construct_particular_cinder_data(self, backend, backend_data):
        backend_data['volume_driver'] = self._RBD_DRIVER
        backend_data['rbd_pool'] = self._RBD_POOL
        backend_data['rbd_max_clone_depth'] = self._RBD_MAX_CLONE_DEPTH
        backend_data['rbd_flatten_volume_from_snapshot'] = \
            self._RBD_FLATTEN_VOLUME_FROM_SNAPSHOT
        backend_data['rbd_ceph_conf'] = self._RBD_CEPH_CONF
        uuid_instance = uuid.uuid3(uuid.NAMESPACE_DNS, "zte.com.cn")
        backend_data['rbd_secret_uuid'] = uuid_instance.urn.split(":")[2]
        return [], []
