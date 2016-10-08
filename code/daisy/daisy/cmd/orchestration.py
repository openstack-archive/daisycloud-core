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
Reference implementation server for Daisy orchestration
"""

import os
import sys
import eventlet
from oslo_config import cfg
from oslo_log import log as logging
from daisy.common import exception
from daisy.common import config
from oslo_service import loopingcall
from daisy.orchestration import manager
import six

# Monkey patch socket and time
eventlet.patcher.monkey_patch(all=False, socket=True, time=True, thread=True)

# If ../glance/__init__.py exists, add ../ to Python search path, so that
# it will override what happens to be installed in /usr/(local/)lib/python...
possible_topdir = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                   os.pardir,
                                   os.pardir))
if os.path.exists(os.path.join(possible_topdir, 'daisy', '__init__.py')):
    sys.path.insert(0, possible_topdir)


CONF = cfg.CONF
scale_opts = [
    cfg.StrOpt('auto_scale_interval', default=60,
               help='Number of seconds between two '
                    'checkings to compute auto scale status'),
]
CONF.register_opts(scale_opts, group='orchestration')
logging.register_options(CONF)


def fail(returncode, e):
    sys.stderr.write("ERROR: %s\n" % six.text_type(e))


def main():
    try:
        config.parse_args()
        logging.setup(CONF, 'daisy')
        timer = loopingcall.FixedIntervalLoopingCall(
            manager.OrchestrationManager.find_auto_scale_cluster)
        timer.start(float(CONF.orchestration.auto_scale_interval)).wait()
    except exception.WorkerCreationFailure as e:
        fail(2, e)
    except RuntimeError as e:
        fail(1, e)

if __name__ == '__main__':
    main()
