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

from horizon.tables import actions


class OperateRegionAction(actions.LinkAction):
    def __init__(self, attrs=None, **kwargs):
        super(OperateRegionAction, self).__init__(**kwargs)
        self.verbose_name = kwargs.get('verbose_name', self.name.title())
        self.action_type = kwargs.get('action_type', "operate_region")
        self.icon = kwargs.get('icon', None)


class AutofillAction(actions.LinkAction):
    def __init__(self, attrs=None, **kwargs):
        super(AutofillAction, self).__init__(**kwargs)
        self.verbose_name = kwargs.get('verbose_name', self.name.title())
        self.action_type = kwargs.get('action_type', "auto_fill")


class ManuallyAssignRoleAction(actions.LinkAction):
    def __init__(self, attrs=None, **kwargs):
        super(ManuallyAssignRoleAction, self).__init__(**kwargs)
        self.verbose_name = kwargs.get('verbose_name', self.name.title())
        self.action_type = kwargs.get('action_type', "manually_assign_role")
        self.icon = kwargs.get('icon', None)
