# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import eventlet
eventlet.monkey_patch(thread=False)

import argparse
import functools
import json
import logging
import sys

import flask

from logging import handlers
from ironic_discoverd import conf
from ironic_discoverd import firewall
from ironic_discoverd import introspect
from ironic_discoverd import node_cache
from ironic_discoverd import process
from ironic_discoverd import utils


app = flask.Flask(__name__)
LOG = logging.getLogger('ironic_discoverd.main')
fh = handlers.RotatingFileHandler(
    '/var/log/ironic/discoverd.log',
    'a', maxBytes=2*1024*1024, backupCount=5)
formatter = logging.Formatter(
    '%(asctime)-12s:%(name)s:%(levelname)s:%(message)s')
fh.setFormatter(formatter)
LOG.addHandler(fh)


def convert_exceptions(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except utils.Error as exc:
            return str(exc), exc.http_code

    return wrapper


@app.route('/v1/continue', methods=['POST'])
@convert_exceptions
def api_continue():
    data = flask.request.get_json(force=True)
    LOG.debug("/v1/continue got JSON %s", data)

    data_name = data.pop('data_name')
    if 'os_status' in data.keys():
        os_status = data.pop('os_status')
    else:
        os_status = None
    if 'ipmi_address' in data.keys():
        ipmi_addr = data.pop('ipmi_address')
    else:
        ipmi_addr = None
    if 'hostname' in data.keys():
        hostname = data.pop('hostname')
    else:
        hostname = None
    if data_name == "baremetal_source":
        process.write_data_to_daisy(data, ipmi_addr, os_status, hostname)
    return json.dumps(""), 200, {'Content-Type': 'applications/json'}


def periodic_update(period):  # pragma: no cover
    while True:
        LOG.debug('Running periodic update of filters')
        try:
            firewall.update_filters()
        except Exception:
            LOG.exception('Periodic update failed')
        eventlet.greenthread.sleep(period)


def periodic_clean_up(period):  # pragma: no cover
    while True:
        LOG.debug('Running periodic clean up of node cache')
        try:
            if node_cache.clean_up():
                firewall.update_filters()
        except Exception:
            LOG.exception('Periodic clean up of node cache failed')
        eventlet.greenthread.sleep(period)


def config_shim(args):
    """Make new argument parsing method backwards compatible."""
    if len(args) == 2 and args[1][0] != '-':
        return ['--config-file', args[1]]


def init():
    if conf.getboolean('discoverd', 'authenticate'):
        utils.add_auth_middleware(app)
    else:
        LOG.warning('Starting unauthenticated, please check configuration')

    node_cache.init()

    if conf.getboolean('discoverd', 'manage_firewall'):
        firewall.init()
        period = conf.getint('discoverd', 'firewall_update_period')
        eventlet.greenthread.spawn_n(periodic_update, period)

    if conf.getint('discoverd', 'timeout') > 0:
        period = conf.getint('discoverd', 'clean_up_period')
        eventlet.greenthread.spawn_n(periodic_clean_up, period)
    else:
        LOG.warning('Timeout is disabled in configuration')


def main():  # pragma: no cover
    old_args = config_shim(sys.argv)
    parser = argparse.ArgumentParser(description='''Hardware introspection
                                                 service for OpenStack Ironic.
                                                 ''')
    parser.add_argument('--config-file', dest='config', required=True)
    # if parse_args is passed None it uses sys.argv instead.
    args = parser.parse_args(old_args)

    conf.read(args.config)
    debug = conf.getboolean('discoverd', 'debug')

    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    for third_party in ('urllib3.connectionpool',
                        'keystonemiddleware.auth_token',
                        'requests.packages.urllib3.connectionpool'):
        logging.getLogger(third_party).setLevel(logging.WARNING)
    logging.getLogger('ironicclient.common.http').setLevel(
        logging.INFO if debug else logging.ERROR)

    if old_args:
        LOG.warning('"ironic-discoverd <config-file>" syntax is deprecated use'
                    ' "ironic-discoverd --config-file <config-file>" instead')

    init()
    app.run(debug=debug,
            host=conf.get('discoverd', 'listen_address'),
            port=conf.getint('discoverd', 'listen_port'))
