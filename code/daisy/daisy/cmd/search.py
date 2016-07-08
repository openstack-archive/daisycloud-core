#!/usr/bin/env python

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 OpenStack Foundation
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

"""
Glance Catalog Search Server
"""

import os
import sys

import eventlet

from daisy.common import utils
from oslo_config import cfg
from oslo_log import log as logging
import osprofiler.notifier
import osprofiler.web

from daisy.common import config
from daisy.common import exception
from daisy.common import wsgi
from daisy import notifier

# Monkey patch socket, time, select, threads
eventlet.patcher.monkey_patch(socket=True, time=True, select=True,
                              thread=True, os=True)

# If ../glance/__init__.py exists, add ../ to Python search path, so that
# it will override what happens to be installed in /usr/(local/)lib/python...
possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
if os.path.exists(os.path.join(possible_topdir, 'glance', '__init__.py')):
    sys.path.insert(0, possible_topdir)


CONF = cfg.CONF
CONF.import_group("profiler", "daisy.common.wsgi")
logging.register_options(CONF)

KNOWN_EXCEPTIONS = (RuntimeError,
                    exception.WorkerCreationFailure)


def fail(e):
    global KNOWN_EXCEPTIONS
    return_code = KNOWN_EXCEPTIONS.index(type(e)) + 1
    sys.stderr.write("ERROR: %s\n" % utils.exception_to_str(e))
    sys.exit(return_code)


def main():
    try:
        config.parse_args()
        wsgi.set_eventlet_hub()
        logging.setup(CONF, 'glance')

        if cfg.CONF.profiler.enabled:
            _notifier = osprofiler.notifier.create("Messaging",
                                                   notifier.messaging, {},
                                                   notifier.get_transport(),
                                                   "glance", "search",
                                                   cfg.CONF.bind_host)
            osprofiler.notifier.set(_notifier)
        else:
            osprofiler.web.disable()

        server = wsgi.Server()
        server.start(config.load_paste_app('glance-search'),
                     default_port=9393)
        server.wait()
    except KNOWN_EXCEPTIONS as e:
        fail(e)


if __name__ == '__main__':
    main()
