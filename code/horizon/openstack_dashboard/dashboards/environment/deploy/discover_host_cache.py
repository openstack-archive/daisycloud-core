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


def clean_cache():
    cache.set("discover_host_cache", None)


def get_cache():
    wizard_context = cache.get("discover_host_cache", None)
    return wizard_context


def set_cache(discover_host_result):
    cache.set("discover_host_cache", discover_host_result)
    LOG.info("UUUUUUUUUUUUUUU %s" % get_cache())