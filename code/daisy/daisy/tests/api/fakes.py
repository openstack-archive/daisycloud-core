# Copyright 2010 OpenStack Foundation
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

import uuid

import routes
import webob
import webob.dec
import webob.request

from daisy.common import wsgi
from daisy import context

class FakeRouter(wsgi.Router):

    def __init__(self, ext_mgr=None):
        pass

    @webob.dec.wsgify
    def __call__(self, req):
        res = webob.Response()
        res.status = '200'
        res.headers['X-Test-Success'] = 'True'
        return res

class FakeRequestContext(context.RequestContext):

    def __init__(self, *args, **kwargs):
        kwargs['auth_token'] = kwargs.get('auth_token', 'fake_auth_token')
        return super(FakeRequestContext, self).__init__(*args, **kwargs)


class HTTPRequest(webob.Request):

    @classmethod
    def blank(cls, *args, **kwargs):
        kwargs['base_url'] = 'http://localhost:29292/v1'
        use_admin_context = kwargs.pop('use_admin_context', False)
        out = wsgi.Request.blank(*args, **kwargs)
        out.context = FakeRequestContext(
            'fake_user',
            'fake',
            is_admin=use_admin_context)
        return out


class TestRouter(wsgi.Router):

    def __init__(self, controller):
        mapper = routes.Mapper()
        mapper.resource("test",
                        "tests",
                        controller=wsgi.Resource(controller))
        super(TestRouter, self).__init__(mapper)


