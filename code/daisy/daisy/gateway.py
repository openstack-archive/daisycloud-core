# Copyright 2012 OpenStack Foundation
# Copyright 2013 IBM Corp.
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
import glance_store
from oslo_log import log as logging

from daisy.api import authorization
from daisy.api import policy
from daisy.api import property_protections
from daisy.common import exception
from daisy.common import property_utils
from daisy.common import store_utils
import daisy.db
import daisy.domain
import daisy.location
import daisy.notifier
import daisy.quota
try:
    import daisy.search
    daisy_search = daisy.search
except ImportError:
    daisy_search = None


LOG = logging.getLogger(__name__)


class Gateway(object):
    def __init__(self, db_api=None, store_api=None, notifier=None,
                 policy_enforcer=None, es_api=None):
        self.db_api = db_api or daisy.db.get_api()
        self.store_api = store_api or glance_store
        self.store_utils = store_utils
        self.notifier = notifier or daisy.notifier.Notifier()
        self.policy = policy_enforcer or policy.Enforcer()
        if es_api:
            self.es_api = es_api
        else:
            self.es_api = daisy_search.get_api() if daisy_search else None

    def get_image_factory(self, context):
        image_factory = daisy.domain.ImageFactory()
        store_image_factory = daisy.location.ImageFactoryProxy(
            image_factory, context, self.store_api, self.store_utils)
        quota_image_factory = daisy.quota.ImageFactoryProxy(
            store_image_factory, context, self.db_api, self.store_utils)
        policy_image_factory = policy.ImageFactoryProxy(
            quota_image_factory, context, self.policy)
        notifier_image_factory = daisy.notifier.ImageFactoryProxy(
            policy_image_factory, context, self.notifier)
        if property_utils.is_property_protection_enabled():
            property_rules = property_utils.PropertyRules(self.policy)
            pif = property_protections.ProtectedImageFactoryProxy(
                notifier_image_factory, context, property_rules)
            authorized_image_factory = authorization.ImageFactoryProxy(
                pif, context)
        else:
            authorized_image_factory = authorization.ImageFactoryProxy(
                notifier_image_factory, context)
        return authorized_image_factory

    def get_image_member_factory(self, context):
        image_factory = daisy.domain.ImageMemberFactory()
        quota_image_factory = daisy.quota.ImageMemberFactoryProxy(
            image_factory, context, self.db_api, self.store_utils)
        policy_member_factory = policy.ImageMemberFactoryProxy(
            quota_image_factory, context, self.policy)
        authorized_image_factory = authorization.ImageMemberFactoryProxy(
            policy_member_factory, context)
        return authorized_image_factory

    def get_repo(self, context):
        image_repo = daisy.db.ImageRepo(context, self.db_api)
        store_image_repo = daisy.location.ImageRepoProxy(
            image_repo, context, self.store_api, self.store_utils)
        quota_image_repo = daisy.quota.ImageRepoProxy(
            store_image_repo, context, self.db_api, self.store_utils)
        policy_image_repo = policy.ImageRepoProxy(
            quota_image_repo, context, self.policy)
        notifier_image_repo = daisy.notifier.ImageRepoProxy(
            policy_image_repo, context, self.notifier)
        if property_utils.is_property_protection_enabled():
            property_rules = property_utils.PropertyRules(self.policy)
            pir = property_protections.ProtectedImageRepoProxy(
                notifier_image_repo, context, property_rules)
            authorized_image_repo = authorization.ImageRepoProxy(
                pir, context)
        else:
            authorized_image_repo = authorization.ImageRepoProxy(
                notifier_image_repo, context)

        return authorized_image_repo

    def get_task_factory(self, context):
        task_factory = daisy.domain.TaskFactory()
        policy_task_factory = policy.TaskFactoryProxy(
            task_factory, context, self.policy)
        notifier_task_factory = daisy.notifier.TaskFactoryProxy(
            policy_task_factory, context, self.notifier)
        authorized_task_factory = authorization.TaskFactoryProxy(
            notifier_task_factory, context)
        return authorized_task_factory

    def get_task_repo(self, context):
        task_repo = daisy.db.TaskRepo(context, self.db_api)
        policy_task_repo = policy.TaskRepoProxy(
            task_repo, context, self.policy)
        notifier_task_repo = daisy.notifier.TaskRepoProxy(
            policy_task_repo, context, self.notifier)
        authorized_task_repo = authorization.TaskRepoProxy(
            notifier_task_repo, context)
        return authorized_task_repo

    def get_task_stub_repo(self, context):
        task_stub_repo = daisy.db.TaskRepo(context, self.db_api)
        policy_task_stub_repo = policy.TaskStubRepoProxy(
            task_stub_repo, context, self.policy)
        notifier_task_stub_repo = daisy.notifier.TaskStubRepoProxy(
            policy_task_stub_repo, context, self.notifier)
        authorized_task_stub_repo = authorization.TaskStubRepoProxy(
            notifier_task_stub_repo, context)
        return authorized_task_stub_repo

    def get_task_executor_factory(self, context):
        task_repo = self.get_task_repo(context)
        image_repo = self.get_repo(context)
        image_factory = self.get_image_factory(context)
        return daisy.domain.TaskExecutorFactory(task_repo,
                                                 image_repo,
                                                 image_factory)

    def get_metadef_namespace_factory(self, context):
        ns_factory = daisy.domain.MetadefNamespaceFactory()
        policy_ns_factory = policy.MetadefNamespaceFactoryProxy(
            ns_factory, context, self.policy)
        notifier_ns_factory = daisy.notifier.MetadefNamespaceFactoryProxy(
            policy_ns_factory, context, self.notifier)
        authorized_ns_factory = authorization.MetadefNamespaceFactoryProxy(
            notifier_ns_factory, context)
        return authorized_ns_factory

    def get_metadef_namespace_repo(self, context):
        ns_repo = daisy.db.MetadefNamespaceRepo(context, self.db_api)
        policy_ns_repo = policy.MetadefNamespaceRepoProxy(
            ns_repo, context, self.policy)
        notifier_ns_repo = daisy.notifier.MetadefNamespaceRepoProxy(
            policy_ns_repo, context, self.notifier)
        authorized_ns_repo = authorization.MetadefNamespaceRepoProxy(
            notifier_ns_repo, context)
        return authorized_ns_repo

    def get_metadef_object_factory(self, context):
        object_factory = daisy.domain.MetadefObjectFactory()
        policy_object_factory = policy.MetadefObjectFactoryProxy(
            object_factory, context, self.policy)
        notifier_object_factory = daisy.notifier.MetadefObjectFactoryProxy(
            policy_object_factory, context, self.notifier)
        authorized_object_factory = authorization.MetadefObjectFactoryProxy(
            notifier_object_factory, context)
        return authorized_object_factory

    def get_metadef_object_repo(self, context):
        object_repo = daisy.db.MetadefObjectRepo(context, self.db_api)
        policy_object_repo = policy.MetadefObjectRepoProxy(
            object_repo, context, self.policy)
        notifier_object_repo = daisy.notifier.MetadefObjectRepoProxy(
            policy_object_repo, context, self.notifier)
        authorized_object_repo = authorization.MetadefObjectRepoProxy(
            notifier_object_repo, context)
        return authorized_object_repo

    def get_metadef_resource_type_factory(self, context):
        resource_type_factory = daisy.domain.MetadefResourceTypeFactory()
        policy_resource_type_factory = policy.MetadefResourceTypeFactoryProxy(
            resource_type_factory, context, self.policy)
        notifier_resource_type_factory = (
            daisy.notifier.MetadefResourceTypeFactoryProxy(
                policy_resource_type_factory, context, self.notifier)
        )
        authorized_resource_type_factory = (
            authorization.MetadefResourceTypeFactoryProxy(
                notifier_resource_type_factory, context)
        )
        return authorized_resource_type_factory

    def get_metadef_resource_type_repo(self, context):
        resource_type_repo = daisy.db.MetadefResourceTypeRepo(
            context, self.db_api)
        policy_object_repo = policy.MetadefResourceTypeRepoProxy(
            resource_type_repo, context, self.policy)
        notifier_object_repo = daisy.notifier.MetadefResourceTypeRepoProxy(
            policy_object_repo, context, self.notifier)
        authorized_object_repo = authorization.MetadefResourceTypeRepoProxy(
            notifier_object_repo, context)
        return authorized_object_repo

    def get_metadef_property_factory(self, context):
        prop_factory = daisy.domain.MetadefPropertyFactory()
        policy_prop_factory = policy.MetadefPropertyFactoryProxy(
            prop_factory, context, self.policy)
        notifier_prop_factory = daisy.notifier.MetadefPropertyFactoryProxy(
            policy_prop_factory, context, self.notifier)
        authorized_prop_factory = authorization.MetadefPropertyFactoryProxy(
            notifier_prop_factory, context)
        return authorized_prop_factory

    def get_metadef_property_repo(self, context):
        prop_repo = daisy.db.MetadefPropertyRepo(context, self.db_api)
        policy_prop_repo = policy.MetadefPropertyRepoProxy(
            prop_repo, context, self.policy)
        notifier_prop_repo = daisy.notifier.MetadefPropertyRepoProxy(
            policy_prop_repo, context, self.notifier)
        authorized_prop_repo = authorization.MetadefPropertyRepoProxy(
            notifier_prop_repo, context)
        return authorized_prop_repo

    def get_metadef_tag_factory(self, context):
        tag_factory = daisy.domain.MetadefTagFactory()
        policy_tag_factory = policy.MetadefTagFactoryProxy(
            tag_factory, context, self.policy)
        notifier_tag_factory = daisy.notifier.MetadefTagFactoryProxy(
            policy_tag_factory, context, self.notifier)
        authorized_tag_factory = authorization.MetadefTagFactoryProxy(
            notifier_tag_factory, context)
        return authorized_tag_factory

    def get_metadef_tag_repo(self, context):
        tag_repo = daisy.db.MetadefTagRepo(context, self.db_api)
        policy_tag_repo = policy.MetadefTagRepoProxy(
            tag_repo, context, self.policy)
        notifier_tag_repo = daisy.notifier.MetadefTagRepoProxy(
            policy_tag_repo, context, self.notifier)
        authorized_tag_repo = authorization.MetadefTagRepoProxy(
            notifier_tag_repo, context)
        return authorized_tag_repo

    def get_catalog_search_repo(self, context):
        if self.es_api is None:
            # TODO(mriedem): Make this a separate exception or change to
            # warning/error logging in Liberty once we're past string freeze.
            # See bug 1441764.
            LOG.debug('The search and index services are not available. '
                      'Ensure you have the necessary prerequisite '
                      'dependencies installed like elasticsearch to use these '
                      'services.')
            raise exception.ServiceUnavailable()
        search_repo = daisy.search.CatalogSearchRepo(context, self.es_api)
        policy_search_repo = policy.CatalogSearchRepoProxy(
            search_repo, context, self.policy)
        return policy_search_repo
