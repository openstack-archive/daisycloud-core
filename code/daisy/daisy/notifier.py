# Copyright 2011, OpenStack Foundation
# Copyright 2012, Red Hat, Inc.
# Copyright 2013 IBM Corp.
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

from oslo_config import cfg
from oslo_log import log as logging
import oslo_messaging

from daisy import i18n

_ = i18n._
_LE = i18n._LE

notifier_opts = [
    cfg.StrOpt('default_publisher_id', default="image.localhost",
               help='Default publisher_id for outgoing notifications.'),
    cfg.ListOpt('disabled_notifications', default=[],
                help='List of disabled notifications. A notification can be '
                     'given either as a notification type to disable a single '
                     'event, or as a notification group prefix to disable all '
                     'events within a group. Example: if this config option '
                     'is set to ["image.create", "metadef_namespace"], then '
                     '"image.create" notification will not be sent after '
                     'image is created and none of the notifications for '
                     'metadefinition namespaces will be sent.'),
]

CONF = cfg.CONF
CONF.register_opts(notifier_opts)

LOG = logging.getLogger(__name__)


def get_transport():
    return oslo_messaging.get_notification_transport(CONF)


class Notifier(object):
    """Uses a notification strategy to send out messages about events."""

    def __init__(self):
        publisher_id = CONF.default_publisher_id
        self._transport = get_transport()
        self._notifier = oslo_messaging.Notifier(self._transport,
                                                 publisher_id=publisher_id)

    def warn(self, event_type, payload):
        self._notifier.warn({}, event_type, payload)

    def info(self, event_type, payload):
        self._notifier.info({}, event_type, payload)

    def error(self, event_type, payload):
        self._notifier.error({}, event_type, payload)
