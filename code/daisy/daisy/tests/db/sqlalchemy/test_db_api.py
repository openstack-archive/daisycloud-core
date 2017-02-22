from daisy.common import exception
from daisy.context import RequestContext
from daisy.db.sqlalchemy import api
from daisy import test
from daisy.tests import test_utils
import mock
from oslo_db.sqlalchemy import session
from oslo_db.sqlalchemy.session import Query
import webob


class FakeFetchoneValue(object):
    """
    fake fatchone().value()
    """

    def __init__(self, value):
        self.value = value

    def values(self):
        return list(self.value)


class FakeExecute(object):
    """
    fake session, return different result
    """

    def __init__(self, sql_query):
        self.sql_query = sql_query
        self.cluster_id = '1ac45b6c-08a7-44ad-8732-64d919841af0'
        self.network_id = '636b8ccd-61cd-4d8b-af54-7ce5deb9a0fb'
        self.sql_network_plane_cidr = \
            "select networks.cidr from networks" + \
            "                               where networks.name" + \
            "='PUBLICAPI' and networks.cluster_id='" + self.cluster_id + \
            "' and networks.deleted=0"
        self.sql_all_network_plane_info = \
            "select networks.id,networks.cidr," + \
            "                                 networks.name from " + \
            "networks where                                  " + \
            "networks.cluster_id='" + self.cluster_id + \
            "' and networks.deleted=0"
        self.roles_info_sql = \
            "select roles.db_vip,roles.glance_vip," + \
            "                                 roles.vip, roles.public_vip " + \
            "from roles where                                  " + \
            "roles.cluster_id='" + self.cluster_id + "' and roles.deleted=0"
        self.sql_ip = \
            "select assigned_networks.ip from assigned_networks" + \
            "                  where assigned_networks.deleted=0 and      " + \
            "            assigned_networks.network_id='" + self.network_id + \
            "' order by assigned_networks.ip"

    def fetchone(self):
        """
        return different result based on sql_querl
        sql_query looks like "select * from hosts;"
        """
        # import pdb;pdb.set_trace()
        if self.sql_query == self.sql_network_plane_cidr:
            query_network_plane_cidr = ('10.43.203.1/24',)
            return FakeFetchoneValue(query_network_plane_cidr)

        return ""

    def fetchall(self):
        # import pdb;pdb.set_trace()
        if self.sql_query == self.roles_info_sql:
            roles_vip_list = \
                [
                    (None, None, None, None),
                    (None, None, '162.160.1.200', None),
                    ('162.160.1.200', '162.160.1.200', '162.160.1.200',
                     '10.43.203.90')
                ]
            roles_vip = [FakeFetchoneValue(vip) for vip in roles_vip_list]
            return roles_vip
        if self.sql_query == self.sql_ip:
            query_ip_list = [('10.43.203.132',), ('10.43.203.139',),
                             ('10.43.203.90',), ]
            query_ip_list = [FakeFetchoneValue(ip) for ip in query_ip_list]
            return query_ip_list
        if self.sql_query == self.sql_all_network_plane_info:
            query_all_network_plane_info = \
                [
                    ('024af6b6-5897-4521-b339-79de06d6e6f6',
                     '',
                     'fdfdf'),
                    ('239640af-893e-46f5-be01-a7f8a3974086',
                     '162.162.1.1/24',
                     'STORAGE'),
                    ('3a8977fc-ca66-4c74-8ceb-acae91b6eb76',
                     '99.99.1.1/24',
                     'DEPLOYMENT'),
                    ('5aa012ad-2020-4ca9-bfa3-823f6b91ab0b',
                     '162.161.1.1/24',
                     'heartbeat161'),
                    ('636b8ccd-61cd-4d8b-af54-7ce5deb9a0fb',
                     '10.43.203.1/24',
                     'PUBLICAPI'),
                    ('a4e357b1-ce27-4fdd-9913-ff182ca5e00d',
                     '',
                     'physnet1'),
                    ('aa1f981f-c591-48c5-bf56-f359d28a8a75',
                     '162.160.1.1/24',
                     'MANAGEMENT'),
                    ('c47d9973-4651-4c61-afef-ca5346c13f25',
                     '162.165.1.1/24',
                     'fdfdffd'),
                    ('cb1f4d4c-2a28-4dde-91a8-7cb966f758d8',
                     '192.170.1.1/24',
                     'EXTERNAL')
                ]
            query_all_network_plane_info = \
                [FakeFetchoneValue(np) for np in query_all_network_plane_info]
            return query_all_network_plane_info
        return ''


class FakeSession(object):
    """
    fake session, return different result
    """

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        return

    def execute(self, sql_query=None):
        """
        return different result based on sql_querl
        sql_query looks like "select * from hosts;"
        """
        return FakeExecute(sql_query)

    def begin(self):
        return self

    def query(self, *args):
        return Query(args)


class DottableDict(dict):

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.__dict__ = self

    def allow_dotting(self, state=True):
        if state:
            self.__dict__ = self
        else:
            self.__dict__ = dict()
ip_ranges = [
    {'start': '112.18.1.2',
     'cidr': '112.18.1.1/24',
     'end': '112.18.1.5',
     'gateway': '112.18.1.2'
     },
    {
        'start': '112.18.1.15',
        'cidr': '112.18.1.1/24',
        'end': '112.18.1.15',
        'gateway': '112.18.1.1'
    },
]


class TestSqlalchemyApi(test.TestCase):

    def setUp(self):
        super(TestSqlalchemyApi, self).setUp()
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=False, user='fake user',
                                          tenant='fake tenant')

    # def test_exclude_public_vip(self):
    #     cluster_id = '1ac45b6c-08a7-44ad-8732-64d919841af0'
    #     network_plane_name = 'PUBLICAPI'
    #     session = FakeSession()

    #     available_ip_list = api.get_ip_with_equal_cidr(
    #         cluster_id, network_plane_name, session, exclude_ips=[])
    #     public_vip = '10.43.203.90'

    #     self.assertIn(public_vip, available_ip_list)

    @mock.patch('daisy.db.sqlalchemy.models.ConfigService.save')
    @mock.patch('daisy.db.sqlalchemy.models.TemplateService.save')
    @mock.patch('daisy.db.sqlalchemy.models.TemplateConfig.save')
    @mock.patch('oslo_db.sqlalchemy.session.Query.delete')
    @mock.patch('daisy.db.sqlalchemy.api.get_session')
    def test_template_config_import(self, mock_do_sesison, mock_do_delete,
                                    mock_do_config_save, mock_do_service_save,
                                    mock_do_config_service_save):
        def mock_sesison(*args, **kwargs):
            return FakeSession()

        def mock_delete(*args, **kwargs):
            pass

        def mock_config_save(*args, **kwargs):
            pass

        def mock_service_save(*args, **kwargs):
            pass

        def mock_config_service_save(*args, **kwargs):
            pass

        values = {u'template': u'{"001": {"ch_desc": "test", "en_desc": '
                               u'"test", "suggested_range": {}, "name": '
                               u'"test_config", "data_type": "string", '
                               u'"length": "256", "service": {"test_service": '
                               u'{"force_type": "None"}}, "section_name": '
                               u'"DEFAULT", "data_check_script": "", '
                               u'"config_file": "/home/test.conf", '
                               u'"default_value": ""}}'}

        mock_do_sesison.side_effect = mock_sesison
        mock_do_delete.side_effect = mock_delete
        mock_do_config_save.side_effect = mock_config_save
        mock_do_service_save.side_effect = mock_service_save
        mock_do_config_service_save.side_effect = mock_config_service_save
        api.template_config_import(self.req.context, values)

    @mock.patch('daisy.db.sqlalchemy.models.TemplateFuncConfigs.save')
    @mock.patch('daisy.db.sqlalchemy.models.TemplateFunc.save')
    @mock.patch('oslo_db.sqlalchemy.session.Query.delete')
    @mock.patch('daisy.db.sqlalchemy.api.get_session')
    def test_template_func_import(self, mock_do_sesison,
                                  mock_do_delete,
                                  mock_do_func_save,
                                  mock_do_func_config_save):
        def mock_sesison(*args, **kwargs):
            return FakeSession()

        def mock_delete(*args, **kwargs):
            pass

        def mock_func_save(*args, **kwargs):
            pass

        def mock_func_config_save(*args, **kwargs):
            pass

        values = {u'template': u'{"001": {"ch_decs": "test", "en_decs": '
                               u'"test", "config": {"001": "test_config"}, '
                               u'"name": "test_func", "dataCheckScript": ""}}'}
        mock_do_sesison.side_effect = mock_sesison
        mock_do_delete.side_effect = mock_delete
        mock_do_func_save.side_effect = mock_func_save
        mock_do_func_config_save.side_effect = mock_func_config_save
        api.template_func_import(self.req.context, values)

    def test_check_assigned_ip_in_ip_range(self):
        assigned_ip = ['192.168.2.1', '192.168.2.6', '192.168.2.7',
                       '192.168.2.8', '192.168.2.9']
        ip_range = [{u'end': u'192.168.2.42', u'start': u'192.168.2.2'}]
        ssh_host_ip = set(['10.42.223.52', '192.168.2.1'])

        self.assertEqual(None, api.check_assigned_ip_in_ip_range(assigned_ip,
                                                                 ip_range,
                                                                 ssh_host_ip))

    def test_check_assigned_ip_in_ip_range_with_ip_in_range(self):
        assigned_ip = ['192.168.2.6', '192.168.2.7',
                       '192.168.2.8', '192.168.2.9']
        ip_range = [{u'end': u'192.168.2.42', u'start': u'192.168.2.2'}]
        ssh_host_ip = set()

        self.assertEqual(None, api.check_assigned_ip_in_ip_range(assigned_ip,
                                                                 ip_range,
                                                                 ssh_host_ip))

    def test_check_assigned_ip_in_ip_range_with_ip_not_in_range(self):
        assigned_ip = ['192.168.2.1', '192.168.2.6', '192.168.2.7',
                       '192.168.2.8', '192.168.2.9']
        ip_range = [{u'end': u'192.168.2.42', u'start': u'192.168.2.2'}]
        ssh_host_ip = set()

        self.assertRaises(exception.Forbidden,
                          api.check_assigned_ip_in_ip_range, assigned_ip,
                          ip_range, ssh_host_ip)

    @mock.patch('daisy.db.sqlalchemy.api.host_get_all')
    def test_change_host_name_with_empty(self, mock_do_host_get_all):
        def mock_host_get_all(*args, **kwargs):
            return [
                {
                    'id': u'f9b3aa0b-43c6-437a-9243-e7d141d22114',
                    'name': u'abcddd'
                },
                {
                    'id': u'bad3f85a-aa2a-429e-b941-7f2d8312dc2a',
                    'name': u'abcd'
                },
                {
                    'id': u'b3ea6edc-8758-41e6-9b5b-ebfea2622c06',
                    'name': u'abcdddd'
                },
                {
                    'id': u'840b92ab-7e79-4a7d-be0a-5e735e0a836e',
                    'name': u''
                }
            ]

        values = {
            u'vcpu_pin_set': u'',
            u'interfaces': u"[]",
            u'isolcpus': None,
            u'os_cpus': u'',
            u'cluster': u'5ed9fd4c-5c97-46f8-af79-786f98c70b2a',
            u'dvs_cpus': u'',
            u'dvs_high_cpuset': u'',
            u'pci_high_cpuset': u''
        }
        mangement_ip = "192.168.1.6"

        class Foo(object):
            id = "840b92ab-7e79-4a7d-be0a-5e735e0a836e"
            name = ''
            os_status = "init"
        mock_do_host_get_all.side_effect = mock_host_get_all
        api.change_host_name(self.req.context, values, mangement_ip, Foo())
        self.assertEqual('host-192-168-1-6', values["name"])

    @mock.patch('daisy.db.sqlalchemy.api.host_get_all')
    def test_change_host_name_with_assign(self, mock_do_host_get_all):
        def mock_host_get_all(*args, **kwargs):
            return [
                {
                    'id': u'f9b3aa0b-43c6-437a-9243-e7d141d22114',
                    'name': u'abcddd'
                },
                {
                    'id': u'bad3f85a-aa2a-429e-b941-7f2d8312dc2a',
                    'name': u'abcd'
                },
                {
                    'id': u'b3ea6edc-8758-41e6-9b5b-ebfea2622c06',
                    'name': u'abcdddd'
                },
                {
                    'id': u'840b92ab-7e79-4a7d-be0a-5e735e0a836e',
                    'name': u''
                }
            ]

        values = {
            u'vcpu_pin_set': u'',
            u'interfaces': u"[]",
            u'isolcpus': None,
            u'os_cpus': u'',
            u'cluster': u'5ed9fd4c-5c97-46f8-af79-786f98c70b2a',
            u'dvs_cpus': u'',
            u'dvs_high_cpuset': u'',
            u'pci_high_cpuset': u''
        }
        mangement_ip = "192.168.1.6"

        class Foo(object):
            id = "840b92ab-7e79-4a7d-be0a-5e735e0a836e"
            name = 'host-1'
            os_status = "init"
        mock_do_host_get_all.side_effect = mock_host_get_all
        api.change_host_name(self.req.context, values, mangement_ip, Foo())
        self.assertEqual(None, values.get("name", None))

    @mock.patch('daisy.db.sqlalchemy.api.host_get_all')
    def test_change_host_name_with_conflict(self, mock_do_host_get_all):
        def mock_host_get_all(*args, **kwargs):
            return [
                {
                    'id': u'f9b3aa0b-43c6-437a-9243-e7d141d22114',
                    'name': u'host-192-168-1-6'
                },
                {
                    'id': u'bad3f85a-aa2a-429e-b941-7f2d8312dc2a',
                    'name': u'host-192-168-1-6'
                },
                {
                    'id': u'b3ea6edc-8758-41e6-9b5b-ebfea2622c06',
                    'name': u'host-192-168-1-6',
                },
                {
                    'id': u'840b92ab-7e79-4a7d-be0a-5e735e0a836e',
                    'name': u'',
                }
            ]

        values = {
            u'vcpu_pin_set': u'',
            u'interfaces': u"[]",
            u'isolcpus': None,
            u'os_cpus': u'',
            u'cluster': u'5ed9fd4c-5c97-46f8-af79-786f98c70b2a',
            u'dvs_cpus': u'',
            u'dvs_high_cpuset': u'',
            u'pci_high_cpuset': u''
        }
        mangement_ip = "192.168.1.6"

        class Foo(object):
            id = "840b92ab-7e79-4a7d-be0a-5e735e0a836e"
            os_status = "init"
        mock_do_host_get_all.side_effect = mock_host_get_all
        self.assertRaises(exception.Duplicate,
                          api.change_host_name, self.req.context, values,
                          mangement_ip, Foo())

    @mock.patch('daisy.db.sqlalchemy.api.get_session')
    def test_network_get_all_with_cluster_id_in_filters(self, mock_do_sesison):
        filters_value = {
            'deleted': False,
            u'cluster_id': u'a0ed9c30-afd3-4bba-bf0f-12ed44e42332'}
        limit_value = 25
        sort_key_value = ['created_at']
        sort_dir_value = ['desc']

        api.network_get_all(self.req.context, filters=filters_value,
                            limit=limit_value, sort_key=sort_key_value,
                            sort_dir=sort_dir_value)

    def test__delete_host_fields(self):
        delete_fields = ['config_set_id',
                         'vcpu_pin_set',
                         'dvs_high_cpuset',
                         'pci_high_cpuset',
                         'os_cpus',
                         'dvs_cpus',
                         'dvs_config_type',
                         'dvsc_cpus',
                         'dvsp_cpus',
                         'dvsv_cpus',
                         'dvsblank_cpus',
                         'flow_mode',
                         'virtio_queue_size',
                         'dvs_config_desc']
        values = {'os_status': 'init'}
        host_ref_dict = {'os_status': 'active'}
        host_ref = test_utils.DottableDict(host_ref_dict)
        host_ref.allow_dotting()
        api._delete_host_fields(host_ref, values)
        for field in delete_fields:
            self.assertEqual(values[field], None)
        self.assertEqual(values['isolcpus'], None)

        values = {'os_status': 'active', 'isolcpus': '1,2'}
        api._delete_host_fields(host_ref, values)
        for field in delete_fields:
            self.assertEqual(values[field], None)
        self.assertEqual(values['isolcpus'], '1,2')

        values = {'isolcpus': '1,2'}
        host_ref_dict = {'os_status': 'active'}
        host_ref = test_utils.DottableDict(host_ref_dict)
        host_ref.allow_dotting()
        api._delete_host_fields(host_ref, values)
        for field in delete_fields:
            self.assertEqual(values[field], None)
        self.assertEqual(values['isolcpus'], '1,2')

        values = {'isolcpus': '1,2'}
        host_ref_dict = {'os_status': 'init'}
        host_ref = test_utils.DottableDict(host_ref_dict)
        host_ref.allow_dotting()
        api._delete_host_fields(host_ref, values)
        for field in delete_fields:
            self.assertEqual(values[field], None)
        self.assertEqual(values['isolcpus'], None)

    def test__cluster_update_without_public_vip(self):
        cluster_add_values = {u'name': u'provider',
                              u'use_dns': u'1',
                              u'networking_parameters': u"{u'base_mac': u''}",
                              u'public_vip': u'10.43.203.199',
                              u'target_systems': u'os+tecs'}

        cluster_update_values = {u'name': u'provider_update',
                                 u'use_dns': u'1',
                                 u'networking_parameters':
                                     u"{u'base_mac': u'',\
                                        u'net_l23_provider': None,\
                                        u'segmentation_type': u'ovs'}"}
        cluster_add__info = api.cluster_add(self.req.context,
                                            cluster_add_values)
        cluster_id = cluster_add__info.__dict__['id']
        cluster_update_info = api.cluster_update(self.req.context,
                                                 cluster_id,
                                                 cluster_update_values)
        cluster_name = cluster_update_info.__dict__['name']
        public_vip = cluster_update_info.__dict__['public_vip']
        self.assertEqual(cluster_name, 'provider_update')
        self.assertEqual(public_vip, '10.43.203.199')
        api.cluster_destroy(self.req.context, cluster_id)

    def test__cluster_update_with_public_vip(self):
        cluster_add_values = {u'name': u'provider',
                              u'use_dns': u'1',
                              u'networking_parameters': u"{u'base_mac': u''}",
                              u'public_vip': u'10.43.203.199',
                              u'target_systems': u'os+tecs'}
        cluster_update_values = {u'name': u'provider_update',
                                 u'use_dns': u'1',
                                 u'networking_parameters':
                                     u"{u'base_mac': u'',\
                                        u'net_l23_provider': None,\
                                        u'segmentation_type': u'ovs',\
                                        u'public_vip': u'10.43.203.200'}"}
        cluster_add__info = api.cluster_add(self.req.context,
                                            cluster_add_values)
        cluster_id = cluster_add__info.__dict__['id']
        cluster_update_info = api.cluster_update(self.req.context,
                                                 cluster_id,
                                                 cluster_update_values)
        cluster_name = cluster_update_info.__dict__['name']
        public_vip = cluster_update_info.__dict__['public_vip']
        self.assertEqual(cluster_name, 'provider_update')
        self.assertEqual(public_vip, '10.43.203.200')
        api.cluster_destroy(self.req.context, cluster_id)

    def test_discover_host_get_by_host_id(self):
        host_id = u'a0d0b8fd-be4e-4540-b047-bc9cc07339b9'
        discover_host_id = u'ad858b51-d976-4b88-bcdd-1ffc8dffe8e4'
        discover_host1 = {'status': u'DISCOVERY_SUCCESSFUL',
                          'ip': u'192.168.1.10',
                          'passwd': u'ossdbg1',
                          'mac': u'90:e2:ba:c4:3f:b8',
                          'host_id': host_id,
                          'message': u'discover host for 192.168.1.10!',
                          'id': discover_host_id}
        api.discover_host_add(self.req.context, discover_host1)
        discover_hosts = api.discover_host_get_by_host_id(
            self.req.context, host_id)
        self.assertEqual(len(discover_hosts), 1)
        self.assertEqual(discover_hosts[0]['host_id'], host_id)
        api.discover_host_destroy(self.req.context, discover_host_id)

    def test_host_destroy(self):
        host_id = u'9692370d-7378-4ef8-9e21-1afe5cd1564a'
        discover_host_id = u'9692370d-7378-4ef8-9e21-1afe5cd15644'
        host_meta = {
            u'name': u'host-192-168-1-102',
            u'description': u'default',
            u'discover_mode': u'SSH',
            u'dmi_uuid': u'574775DC-0000-1000-0000-744AA400B807',
            u'id': host_id,
            u'interfaces': unicode([{u'bond_type': None,
                                     u'ip': u'10.43.203.44',
                                     u'is_deployment': False,
                                     u'mac': u'a0:36:9f:91:85:a9',
                                     u'max_speed': u'1000baseT/Full',
                                     u'name': u'ens8f1.900',
                                     u'netmask': u'255.255.254.0'}]),
        }
        discover_host = {'status': u'DISCOVERY_SUCCESSFUL',
                         'ip': u'10.43.203.44',
                         'passwd': u'ossdbg1',
                         'mac': u'a0:36:9f:91:85:a9',
                         'host_id': host_id,
                         'message': u'discover host for 10.43.203.44!',
                         'id': discover_host_id}

        api.host_add(self.req.context, host_meta)
        api.discover_host_add(self.req.context, discover_host)
        api.host_destroy(self.req.context, host_id)
        self.assertRaises(exception.NotFound,
                          api.host_get,
                          self.req.context,
                          host_id)
        self.assertRaises(exception.NotFound,
                          api.discover_host_get,
                          self.req.context,
                          discover_host_id)

    def test_get_assigned_networks_by_network_id(self):
        network_id = u'1'
        assigned_networks = api.get_assigned_networks_by_network_id(
            self.req.context, network_id)
        self.assertEqual(assigned_networks, [])

    @mock.patch('daisy.db.sqlalchemy.api.get_used_ip_in_dataplan_net')
    def test_get_ip_with_equal_cidr(self, fake_used_ip):
        fake_used_ip.return_value = ['112.18.1.15', '112.18.1.16']
        network_values = {
            'cluster_id': '737adb89-ee6f-4642-8196-9ee6926fbe50',
            'cidr': '112.18.1.1/25',
                    'gateway': '112.18.1.1',
                    'vlan_id': None,
                    'ip_ranges': str(ip_ranges),
                    'name': 'physnet1',
                    'segmentation_type': 'vxlan',
                    'physnet_name': 'physnet_enp2s0',
                    'type': 'default',
                    'network_type': 'DATAPLANE',
        }
        network_info = api.network_add(self.req.context, network_values)
        network_id = network_info.__dict__['id']
        # print network_info
        cluster_id = '737adb89-ee6f-4642-8196-9ee6926fbe50'
        network_plane_name = 'physnet1'
        session = api.get_session()
        get_ips = api.get_ip_with_equal_cidr(
            cluster_id, network_plane_name, session, exclude_ips=[])
        self.assertEqual(['112.18.1.15', '112.18.1.16'], get_ips)

    @mock.patch('daisy.db.sqlalchemy.api.get_used_ip_in_dataplan_net')
    def test_get_ip_with_equal_cidr_nomarl(self, fake_used_ip):
        fake_used_ip.return_value = ['112.18.1.15', '112.18.1.16']
        network_values = {
            'cluster_id': '737adb89-ee6f-4642-8196-9ee6926fbe50',
            'cidr': '112.18.1.1/25',
                    'gateway': '112.18.1.1',
                    'vlan_id': None,
                    'ip_ranges': str(ip_ranges),
                    'capability': 'high',
                    'name': 'STORAGE',
                    'type': 'default',
                    'network_type': 'STORAGE',
        }
        network_info = api.network_add(self.req.context, network_values)
        cluster_id = '737adb89-ee6f-4642-8196-9ee6926fbe50'
        network_plane_name = 'STORAGE'
        session = api.get_session()
        get_ips = api.get_ip_with_equal_cidr(
            cluster_id, network_plane_name, session, exclude_ips=[])
        self.assertEqual([], get_ips)

    def test_get_used_ip_in_dataplan_net(self):
        network_values = {
            'cluster_id': '737adb89-ee6f-4642-8196-9ee6926fbe50',
            'cidr': '112.18.1.1/25',
                    'gateway': '112.18.1.1',
                    'ip_ranges': str(ip_ranges),
                    'name': 'physnet1',
                    'segmentation_type': 'vxlan',
                    'physnet_name': 'physnet_enp2s0',
                    'type': 'default',
                    'network_type': 'DATAPLANE',
        }
        network_info = api.network_add(self.req.context, network_values)
        network_id = network_info.__dict__['id']
        # print network_info
        cluster_id = '737adb89-ee6f-4642-8196-9ee6926fbe50'
        network_plane_name = 'physnet1'
        session = api.get_session()
        get_ips = api.get_used_ip_in_dataplan_net(network_id, session)
        self.assertEqual([], get_ips)

    def test_according_to_cidr_distribution_ip(self):
        network_values = {
            'cluster_id': '737adb89-ee6f-4642-8196-9ee6926fbe50',
            'cidr': '112.18.1.2/25',
                    'gateway': '112.18.1.1',
                    'ip_ranges': str(ip_ranges),
                    'name': 'physnet1',
                    'segmentation_type': 'vxlan',
                    'physnet_name': 'physnet_enp2s0',
                    'type': 'default',
                    'network_type': 'DATAPLANE',
        }
        network_info = api.network_add(self.req.context, network_values)
        network_id = network_info.__dict__['id']

        cluster_id = '737adb89-ee6f-4642-8196-9ee6926fbe50'
        network_plane_name = 'physnet1'
        session = api.get_session()
        distribution_ip1 = api.according_to_cidr_distribution_ip(
            cluster_id, network_plane_name, session)
        # gateway = '112.18.1.2'
        self.assertEqual('112.18.1.3', distribution_ip1)

    def test_get_network_ip_range(self):
        network_values = {
            'cluster_id': '737adb89-ee6f-4642-8196-9ee6926fbe50',
            'cidr': '112.18.1.2/25',
                    'gateway': '112.18.1.1',
                    'ip_ranges': str(ip_ranges),
                    'name': 'physnet1',
                    'segmentation_type': 'vxlan',
                    'physnet_name': 'physnet_enp2s0',
                    'type': 'default',
                    'network_type': 'DATAPLANE',
        }
        network_info = api.network_add(self.req.context, network_values)
        network_id = network_info.__dict__['id']
        ip_ranges_sorted = api.get_network_ip_range(
            self.req.context, network_id)
        actual_ip_ranges = \
            [(u'112.18.1.2', u'112.18.1.5', u'112.18.1.1/24', u'112.18.1.2'),
             (u'112.18.1.15', u'112.18.1.15', u'112.18.1.1/24', u'112.18.1.1')]
        self.assertEqual(actual_ip_ranges, ip_ranges_sorted)

    def test_network_get_all(self):
        network_values = {
            'cluster_id': '737adb89-ee6f-4642-8196-9ee6926fbe50',
            'cidr': '112.18.1.2/25',
                    'gateway': '112.18.1.1',
                    'ip_ranges': str(ip_ranges),
                    'name': 'physnet1',
                    'segmentation_type': 'vxlan',
                    'physnet_name': 'physnet_enp2s0',
                    'type': 'default',
                    'network_type': 'DATAPLANE',
        }
        network_info = api.network_add(self.req.context, network_values)
        networks = api.network_get_all(self.req.context)

        self.assertEqual(network_values['cluster_id'],
                         networks[0]['cluster_id'])
        self.assertEqual(network_values['cidr'], networks[0]['cidr'])

    def test__network_update(self):
        network_values = {
            'cluster_id': '737adb89-ee6f-4642-8196-9ee6926fbe50',
            'cidr': '112.18.1.2/25',
                    'gateway': '112.18.1.1',
                    'ip_ranges': str(ip_ranges),
                    'name': 'physnet1',
                    'segmentation_type': 'vxlan',
                    'physnet_name': 'physnet_enp2s0',
                    'type': 'default',
                    'network_type': 'DATAPLANE',
        }
        network_info = api.network_add(self.req.context, network_values)
        network_id = network_info.__dict__['id']
        update_info = {'cidr': '112.18.1.2/24',
                       'gateway': '112.18.1.10',
                       'ip_ranges': str(ip_ranges)}
        update_networks = \
            api._network_update(self.req.context, update_info, network_id)
        self.assertEqual(update_info['cidr'], update_networks['cidr'])

    @mock.patch('daisy.db.sqlalchemy.api.get_session')
    def test_version_get_all(self, mock_do_sesison):
        def mock_sesison(*args, **kwargs):
            return FakeSession()
        version_values = {'id': '1', 'status': 'used'}
        filters_value = {
            'deleted': False,
            'cluster_id': u'a0ed9c30-afd3-4bba-bf0f-12ed44e42332'}
        limit_value = 25
        sort_key_value = ['created_at']
        sort_dir_value = ['desc']
        mock_do_sesison.side_effect = mock_sesison

        class User(object):
            def __init__(self, id, status):
                self.id = id
                self.status = status

            def to_dict(self):
                return {'id': self.id, 'status': self.status}

        user = User(id='1', status='used')
        Query.all = mock.Mock(return_value=[user])
        session.query = mock.Mock(return_value=version_values)
        versions = api.version_get_all(self.req.context,
                                       filters=filters_value,
                                       limit=limit_value,
                                       sort_key=sort_key_value,
                                       sort_dir=sort_dir_value)
        self.assertEqual(version_values['id'], versions[0]['id'])

    def test_get_host_interface_vf_info(self):
        self.assertRaises(exception.NotFound,
                          api._get_host_interface_vf_info,
                          self.req.context, None)

    @mock.patch('daisy.db.sqlalchemy.models.HostInterface.save')
    def test_update_host_interface_vf_info(self, mock_host_interface_save):
        session = FakeSession()
        host_id = "9692370d-7378-4ef8-9e21-1afe5cd1564a"
        pf_interface_id = "d1e5ce54-f96d-41da-8f28-4535918660b7"
        vf_values = "[{'name':'ens301','index':0}]"
        mock_host_interface_save.return_value = None
        api._update_host_interface_vf_info(self.req.context, host_id,
                                           pf_interface_id, vf_values, session)
        self.assertTrue(mock_host_interface_save.called)

        vf_values = "[{'name':'bond0_0','slaves':'enp3s0 enp3s1','index':0}]"
        mock_host_interface_save.return_value = None
        api._update_host_interface_vf_info(self.req.context, host_id,
                                           pf_interface_id, vf_values, session)
        self.assertTrue(mock_host_interface_save.called)

    def test_add_host_interface_vf(self):
        host_id = u'9692370d-7378-4ef8-9e21-1afe5cd1566c'
        host_meta = {
            u'name': u'host-192-168-1-102',
            u'description': u'default',
            u'discover_mode': u'SSH',
            u'dmi_uuid': u'574775DC-0000-1000-0000-744AA400B807',
            u'id': host_id,
            u'interfaces': unicode([{u'bond_type': None,
                                     u'ip': u'10.43.203.44',
                                     u'is_deployment': False,
                                     u'mac': u'a0:36:9f:91:85:a9',
                                     u'max_speed': u'1000baseT/Full',
                                     u'name': u'ens8f1.900',
                                     u'netmask': u'255.255.254.0',
                                     u'vf': [
                                         {'name': 'ens301', 'index': 0}]}]),
        }

        api.host_add(self.req.context, host_meta)
        ret = api.host_interfaces_get_all(self.req.context)
        self.assertEqual(ret[0]["host_id"], host_id)
        api.host_destroy(self.req.context, host_id)

    def test_update_host_interface_vf(self):
        host_id = u'9692370d-7378-4ef8-9e21-1afe5cd1566c'
        host_meta = {
            u'name': u'host-192-168-1-102',
            u'description': u'default',
            u'discover_mode': u'SSH',
            u'dmi_uuid': u'574775DC-0000-1000-0000-744AA400B807',
            u'id': host_id,
            u'interfaces': unicode([{u'bond_type': None,
                                     u'ip': u'10.43.203.44',
                                     u'is_deployment': False,
                                     u'mac': u'a0:36:9f:91:85:a9',
                                     u'max_speed': u'1000baseT/Full',
                                     u'name': u'ens8f1.900',
                                     u'netmask': u'255.255.254.0',
                                     u'vf': [
                                         {'name': 'ens301', 'index': 0}]}]),
        }

        update_meta = {
            u'interfaces': unicode([{u'bond_type': None,
                                     u'ip': u'10.43.203.44',
                                     u'is_deployment': False,
                                     u'mac': u'a0:36:9f:91:85:a9',
                                     u'max_speed': u'1000baseT/Full',
                                     u'name': u'ens8f1.900',
                                     u'netmask': u'255.255.254.0',
                                     u'vf': [
                                         {'name': 'ens301', 'index': 1}]}]),
        }

        api.host_add(self.req.context, host_meta)
        api.host_update(self.req.context, host_id, update_meta)
        ret = api.host_interfaces_get_all(self.req.context)
        self.assertEqual(ret[0]["host_id"], host_id)
        api.host_destroy(self.req.context, host_id)

    def test_according_to_cidr_distribution_ip_without_cidr(self):
        ip_ranges = [{'start': '112.18.1.2', 'end': '112.18.1.5', }, ]
        network_values = {
            'cluster_id': '737adb89-ee6f-4642-8196-9ee6926fbe50',
            'cidr': '112.18.1.2/25',
                    'gateway': '112.18.1.1',
                    'ip_ranges': str(ip_ranges),
                    'name': 'physnet1',
                    'segmentation_type': 'vxlan',
                    'physnet_name': 'physnet_enp2s0',
                    'type': 'default',
                    'network_type': 'DATAPLANE',
        }
        network_info = api.network_add(self.req.context, network_values)
        network_id = network_info.__dict__['id']

        cluster_id = '737adb89-ee6f-4642-8196-9ee6926fbe50'
        network_plane_name = 'physnet1'
        session = api.get_session()
        distribution_ip1 = api.according_to_cidr_distribution_ip(
            cluster_id, network_plane_name, session)
        self.assertEqual('112.18.1.2', distribution_ip1)

    def test_according_to_cidr_distribution_ip_without_ip(self):
        network_values = {
            'cluster_id': '737adb89-ee6f-4642-8196-9ee6926fbe50',
            'cidr': None,
            'gateway': None,
            'name': 'physnet1',
                    'segmentation_type': 'vxlan',
                    'physnet_name': 'physnet_enp2s0',
                    'type': 'default',
                    'network_type': 'DATAPLANE',
        }
        network_info = api.network_add(self.req.context, network_values)
        network_id = network_info.__dict__['id']

        cluster_id = '737adb89-ee6f-4642-8196-9ee6926fbe50'
        network_plane_name = 'physnet1'
        session = api.get_session()
        self.assertRaises(exception.Forbidden,
                          api.according_to_cidr_distribution_ip, cluster_id,
                          network_plane_name, session)

    def test_according_to_cidr_distribution_ip_from_net_cidr(self):
        network_values = {
            'cluster_id': '737adb89-ee6f-4642-8196-9ee6926fbe50',
            'cidr': '112.18.1.2/25',
                    'gateway': '112.18.1.1',
                    'name': 'physnet1',
                    'segmentation_type': 'vxlan',
                    'physnet_name': 'physnet_enp2s0',
                    'type': 'default',
                    'network_type': 'DATAPLANE',
        }
        network_info = api.network_add(self.req.context, network_values)
        network_id = network_info.__dict__['id']

        cluster_id = '737adb89-ee6f-4642-8196-9ee6926fbe50'
        network_plane_name = 'physnet1'
        session = api.get_session()
        distribution_ip1 = api.according_to_cidr_distribution_ip(
            cluster_id, network_plane_name, session)
        self.assertEqual('112.18.1.2', distribution_ip1)

    def test_according_to_cidr_distribution_ip_from_range_cidr(self):
        ip_ranges = [
            {'start': None,
             'cidr': '112.18.1.1/24',
                     'end': None,
                     'gateway': '112.18.1.2'
             }, ]
        network_values = {
            'cluster_id': '737adb89-ee6f-4642-8196-9ee6926fbe50',
            'cidr': '112.18.1.2/25',
                    'gateway': '112.18.1.1',
                    'ip_ranges': str(ip_ranges),
                    'name': 'physnet1',
                    'segmentation_type': 'vxlan',
                    'physnet_name': 'physnet_enp2s0',
                    'type': 'default',
                    'network_type': 'DATAPLANE',
        }
        network_info = api.network_add(self.req.context, network_values)
        network_id = network_info.__dict__['id']

        cluster_id = '737adb89-ee6f-4642-8196-9ee6926fbe50'
        network_plane_name = 'physnet1'
        session = api.get_session()
        distribution_ip1 = api.according_to_cidr_distribution_ip(
            cluster_id, network_plane_name, session)
        self.assertEqual('112.18.1.1', distribution_ip1)

    def test_check_ip_ranges(self):
        ip_ranges = ('12.1.1.10', '12.1.1.15', '12.1.1.1/24', '12.1.1.1')
        check_result = api.check_ip_ranges(ip_ranges, [])
        self.assertEqual('12.1.1.10', check_result[1])

    def test_sort_ip_ranges_with_cidr(self):
        ip_ranges = \
            [('12.1.1.10', '12.1.1.10', '12.1.1.1/24', '12.1.1.1'),
             ('16.168.1.100', '16.168.1.100', '16.168.1.10/24', '16.168.1.1'),
             ('17.168.1.10', '17.168.1.10', '17.168.1.1/24', '17.168.1.1'),
             ('5.5.5.5', '5.5.5.5', '5.5.5.1/24', '5.5.5.1')]
        sorted_ip_ranges = api.sort_ip_ranges_with_cidr(ip_ranges)
        # print 'sorted_ip_ranges:', sorted_ip_ranges
        self.assertEqual(('5.5.5.5', '5.5.5.5', '5.5.5.1/24', '5.5.5.1'),
                         sorted_ip_ranges[0])
        self.assertEqual(('12.1.1.10', '12.1.1.10', '12.1.1.1/24', '12.1.1.1'),
                         sorted_ip_ranges[1])

    def test_sort_ip_ranges_with_cidr_no_startip(self):
        ip_ranges = \
            [('12.1.1.10', '12.1.1.10', '12.1.1.1/24', '12.1.1.1'),
             ('16.168.1.100', '16.168.1.100', '16.168.1.10/24', '16.168.1.1'),
             (None, None, '17.168.1.1/24', '17.168.1.1'),
             ('5.5.5.5', '5.5.5.5', '5.5.5.1/24', '5.5.5.1')]
        sorted_ip_ranges = api.sort_ip_ranges_with_cidr(ip_ranges)
        # print 'sorted_ip_ranges:', sorted_ip_ranges
        self.assertEqual(('5.5.5.5', '5.5.5.5', '5.5.5.1/24', '5.5.5.1'),
                         sorted_ip_ranges[0])
        self.assertEqual(('12.1.1.10', '12.1.1.10', '12.1.1.1/24', '12.1.1.1'),
                         sorted_ip_ranges[1])
