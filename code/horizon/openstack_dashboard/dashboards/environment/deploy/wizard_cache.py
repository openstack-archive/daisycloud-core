# Copyright 2015 ZTE Corp.
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


from django.core.cache import cache
import logging
LOG = logging.getLogger(__name__)


def clean_cache(cluster_id):
    cache.set(cluster_id, None)


def get_cache(cluster_id):
    wizard_context = cache.get(cluster_id, None)
    if wizard_context is None:
        wizard_context = {
            "selecthosts": {
                "status": 1
            },
            "osconfig": {
                "status": 0
            },
            "hosts_role_assignment": {
                "status": 0
            },
            "bonding": {
                "status": 0
            },
            "network": {
                "status": 0
            },
            "networkmapping": {
                "status": 0
            },
            "hosts_config": {
                "status": 0
            }
        }
    return wizard_context


def set_cache(cluster_id, step_name, status):
    wizard_context = get_cache(cluster_id)
    wizard_context[step_name]["status"] = status
    cache.set(cluster_id, wizard_context)
