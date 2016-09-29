import mock
import webob
from daisy.common import exception
from oslo_db.sqlalchemy.session import Query
from daisy.context import RequestContext
from daisy.db.sqlalchemy import api
from daisy import test


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
            query_ip_list = [('10.43.203.132',), ('10.43.203.139',)]
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


class TestSqlalchemyApi(test.TestCase):

    def setUp(self):
        super(TestSqlalchemyApi, self).setUp()
        self.req = webob.Request.blank('/')
        self.req.context = RequestContext(is_admin=True, user='fake user',
                                          tenant='fake tenant')

    def test_exclude_public_vip(self):
        cluster_id = '1ac45b6c-08a7-44ad-8732-64d919841af0'
        network_plane_name = 'PUBLICAPI'
        session = FakeSession()

        available_ip_list = api.get_ip_with_equal_cidr(
            cluster_id, network_plane_name, session, exclude_ips=[])
        public_vip = '10.43.203.90'

        self.assertIn(public_vip, available_ip_list)

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
