# Copyright 2010-2011 OpenStack Foundation
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

from oslo_log import log as logging
import webob.exc

from daisy.common import exception
from daisy.common import utils
from daisy.common import wsgi
import daisy.db
from daisy import i18n


LOG = logging.getLogger(__name__)
_ = i18n._
_LI = i18n._LI
_LW = i18n._LW


class Controller(object):

    def __init__(self):
        self.db_api = daisy.db.get_api()

    def get_cluster_hosts(self, req, cluster_id, host_id=None):
        """
        Get the members of an cluster.
        """
        try:
            self.db_api.cluster_get(req.context, cluster_id)
        except exception.NotFound:
            msg = _("Project %(id)s not found") % {'id': cluster_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound(msg)
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LW("Access denied to cluster %(id)s but returning"
                      " 'not found'") % {'id': cluster_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound()

        members = self.db_api.cluster_host_member_find(
            req.context, cluster_id=cluster_id, host_id=host_id)
        msg = "Returning member list for cluster %(id)s" % {'id': cluster_id}
        LOG.debug(msg)
        return dict(members=make_member_list(members,
                                             host_id='host_id'))

    @utils.mutating
    def update_all(self, req, image_id, body):
        """
        Replaces the members of the image with those specified in the
        body.  The body is a dict with the following format::

            {"memberships": [
                {"member_id": <MEMBER_ID>,
                 ["can_share": [True|False]]}, ...
            ]}
        """
        self._check_can_access_image_members(req.context)

        # Make sure the image exists
        try:
            image = self.db_api.image_get(req.context, image_id)
        except exception.NotFound:
            msg = _("Image %(id)s not found") % {'id': image_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound(msg)
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LW("Access denied to image %(id)s but returning"
                      " 'not found'") % {'id': image_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound()

        # Can they manipulate the membership?
        if not self.is_image_sharable(req.context, image):
            msg = (_LW("User lacks permission to share image %(id)s") %
                   {'id': image_id})
            LOG.warn(msg)
            msg = _("No permission to share that image")
            raise webob.exc.HTTPForbidden(msg)

        # Get the membership list
        try:
            memb_list = body['memberships']
        except Exception as e:
            # Malformed entity...
            msg = _LW("Invalid membership association specified for "
                      "image %(id)s") % {'id': image_id}
            LOG.warn(msg)
            msg = (_("Invalid membership association: %s") %
                   utils.exception_to_str(e))
            raise webob.exc.HTTPBadRequest(explanation=msg)

        add = []
        existing = {}
        # Walk through the incoming memberships
        for memb in memb_list:
            try:
                datum = dict(image_id=image['id'],
                             member=memb['member_id'],
                             can_share=None)
            except Exception as e:
                # Malformed entity...
                msg = _LW("Invalid membership association specified for "
                          "image %(id)s") % {'id': image_id}
                LOG.warn(msg)
                msg = (_("Invalid membership association: %s") %
                       utils.exception_to_str(e))
                raise webob.exc.HTTPBadRequest(explanation=msg)

            # Figure out what can_share should be
            if 'can_share' in memb:
                datum['can_share'] = bool(memb['can_share'])

            # Try to find the corresponding membership
            members = self.db_api.image_member_find(req.context,
                                                    image_id=datum['image_id'],
                                                    member=datum['member'])
            try:
                member = members[0]
            except IndexError:
                # Default can_share
                datum['can_share'] = bool(datum['can_share'])
                add.append(datum)
            else:
                # Are we overriding can_share?
                if datum['can_share'] is None:
                    datum['can_share'] = members[0]['can_share']

                existing[member['id']] = {
                    'values': datum,
                    'membership': member,
                }

        # We now have a filtered list of memberships to add and
        # memberships to modify.  Let's start by walking through all
        # the existing image memberships...
        existing_members = self.db_api.image_member_find(req.context,
                                                         image_id=image['id'])
        for member in existing_members:
            if member['id'] in existing:
                # Just update the membership in place
                update = existing[member['id']]['values']
                self.db_api.image_member_update(req.context,
                                                member['id'],
                                                update)
            else:
                # Outdated one; needs to be deleted
                self.db_api.image_member_delete(req.context, member['id'])

        # Now add the non-existent ones
        for memb in add:
            self.db_api.image_member_create(req.context, memb)

        # Make an appropriate result
        msg = (_LI("Successfully updated memberships for image %(id)s") %
               {'id': image_id})
        LOG.info(msg)
        return webob.exc.HTTPNoContent()

    @utils.mutating
    def update(self, req, image_id, id, body=None):
        """
        Adds a membership to the image, or updates an existing one.
        If a body is present, it is a dict with the following format::

            {"member": {
                "can_share": [True|False]
            }}

        If "can_share" is provided, the member's ability to share is
        set accordingly.  If it is not provided, existing memberships
        remain unchanged and new memberships default to False.
        """
        self._check_can_access_image_members(req.context)

        # Make sure the image exists
        try:
            image = self.db_api.image_get(req.context, image_id)
        except exception.NotFound:
            msg = _("Image %(id)s not found") % {'id': image_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound(msg)
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LW("Access denied to image %(id)s but returning"
                      " 'not found'") % {'id': image_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound()

        # Can they manipulate the membership?
        if not self.is_image_sharable(req.context, image):
            msg = (_LW("User lacks permission to share image %(id)s") %
                   {'id': image_id})
            LOG.warn(msg)
            msg = _("No permission to share that image")
            raise webob.exc.HTTPForbidden(msg)

        # Determine the applicable can_share value
        can_share = None
        if body:
            try:
                can_share = bool(body['member']['can_share'])
            except Exception as e:
                # Malformed entity...
                msg = _LW("Invalid membership association specified for "
                          "image %(id)s") % {'id': image_id}
                LOG.warn(msg)
                msg = (_("Invalid membership association: %s") %
                       utils.exception_to_str(e))
                raise webob.exc.HTTPBadRequest(explanation=msg)

        # Look up an existing membership...
        members = self.db_api.image_member_find(req.context,
                                                image_id=image_id,
                                                member=id)
        if members:
            if can_share is not None:
                values = dict(can_share=can_share)
                self.db_api.image_member_update(req.context,
                                                members[0]['id'],
                                                values)
        else:
            values = dict(image_id=image['id'], member=id,
                          can_share=bool(can_share))
            self.db_api.image_member_create(req.context, values)

        msg = (_LI("Successfully updated a membership for image %(id)s") %
               {'id': image_id})
        LOG.info(msg)
        return webob.exc.HTTPNoContent()

    @utils.mutating
    def delete(self, req, image_id, id):
        """
        Removes a membership from the image.
        """
        self._check_can_access_image_members(req.context)

        # Make sure the image exists
        try:
            image = self.db_api.image_get(req.context, image_id)
        except exception.NotFound:
            msg = _("Image %(id)s not found") % {'id': image_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound(msg)
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LW("Access denied to image %(id)s but returning"
                      " 'not found'") % {'id': image_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound()

        # Can they manipulate the membership?
        if not self.is_image_sharable(req.context, image):
            msg = (_LW("User lacks permission to share image %(id)s") %
                   {'id': image_id})
            LOG.warn(msg)
            msg = _("No permission to share that image")
            raise webob.exc.HTTPForbidden(msg)

        # Look up an existing membership
        members = self.db_api.image_member_find(req.context,
                                                image_id=image_id,
                                                member=id)
        if members:
            self.db_api.image_member_delete(req.context, members[0]['id'])
        else:
            msg = ("%(id)s is not a member of image %(image_id)s" %
                   {'id': id, 'image_id': image_id})
            LOG.debug(msg)
            msg = _("Membership could not be found.")
            raise webob.exc.HTTPNotFound(explanation=msg)

        # Make an appropriate result
        msg = (_LI("Successfully deleted a membership from image %(id)s") %
               {'id': image_id})
        LOG.info(msg)
        return webob.exc.HTTPNoContent()

    @utils.mutating
    def add_cluster_host(self, req, cluster_id, host_id, body=None):
        """
        Adds a host to cluster.
        """

        # Make sure the cluster exists
        try:
            self.db_api.cluster_get(req.context, cluster_id)
        except exception.NotFound:
            msg = _("Project %(id)s not found") % {'id': cluster_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound(msg)
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LW("Access denied to cluster %(id)s but returning"
                      " 'not found'") % {'id': cluster_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound()

        # Make sure the host exists
        try:
            self.db_api.host_get(req.context, host_id)
        except exception.NotFound:
            msg = _("Host %(id)s not found") % {'id': host_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound(msg)
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LW("Access denied to host %(id)s but returning"
                      " 'not found'") % {'id': host_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound()

        # Look up an existing membership...
        members = self.db_api.cluster_host_member_find(req.context,
                                                       cluster_id=cluster_id,
                                                       host_id=host_id)
        if members:
            msg = (_LI("Project %(cluster_id)s has host %(host_id)s "
                       "membership already!") %
                   {'cluster_id': cluster_id, 'host_id': host_id})
        else:
            values = dict(cluster_id=cluster_id, host_id=host_id)
            self.db_api.cluster_host_member_create(req.context, values)

        msg = (_LI("Successfully added a host %(host_id)s to cluster %("
                   "cluster_id)s") %
               {'host_id': host_id, 'cluster_id': cluster_id})
        LOG.info(msg)
        return webob.exc.HTTPNoContent()

    @utils.mutating
    def delete_cluster_host(self, req, cluster_id, host_id):
        """
        Removes a host from cluster.
        """
        # Make sure the cluster exists
        try:
            self.db_api.cluster_get(req.context, cluster_id)
        except exception.NotFound:
            msg = _("Project %(id)s not found") % {'id': cluster_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound(msg)
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LW("Access denied to cluster %(id)s but returning"
                      " 'not found'") % {'id': cluster_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound()

        # Make sure the host exists
        try:
            self.db_api.host_get(req.context, host_id)
        except exception.NotFound:
            msg = _("Host %(id)s not found") % {'id': host_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound(msg)
        except exception.Forbidden:
            # If it's private and doesn't belong to them, don't let on
            # that it exists
            msg = _LW("Access denied to host %(id)s but returning"
                      " 'not found'") % {'id': host_id}
            LOG.warn(msg)
            raise webob.exc.HTTPNotFound()

        # Look up an existing membership
        members = self.db_api.cluster_host_member_find(req.context,
                                                       cluster_id=cluster_id,
                                                       host_id=host_id)
        if members:
            self.db_api.cluster_host_member_delete(
                req.context, members[0]['id'])
        else:
            msg = ("%(host_id)s is not a member of cluster %(cluster_id)s" %
                   {'host_id': host_id, 'cluster_id': cluster_id})
            LOG.debug(msg)
            msg = _("Membership could not be found.")
            raise webob.exc.HTTPNotFound(explanation=msg)

        # Make an appropriate result
        msg = (_LI("Successfully deleted a host %(host_id)s from cluster %("
                   "cluster_id)s") %
               {'host_id': host_id, 'cluster_id': cluster_id})
        LOG.info(msg)
        return webob.exc.HTTPNoContent()

    def default(self, req, *args, **kwargs):
        """This will cover the missing 'show' and 'create' actions"""
        LOG.debug("The method %s is not allowed for this resource" %
                  req.environ['REQUEST_METHOD'])
        raise webob.exc.HTTPMethodNotAllowed(
            headers=[('Allow', 'PUT, DELETE')])

    def get_host_clusters(self, req, host_id):
        """
        Retrieves clusters shared with the given host.
        """
        try:
            members = self.db_api.cluster_host_member_find(
                req.context, host_id=host_id)
        except exception.NotFound:
            msg = _LW("Host %(id)s not found") % {'id': host_id}
            LOG.warn(msg)
            msg = _("Membership could not be found.")
            raise webob.exc.HTTPBadRequest(explanation=msg)

        msg = "Returning list of clusters shared with host %(id)s" % {
            'id': host_id}
        LOG.debug(msg)
        return dict(multi_clusters=make_member_list(members,
                                                    cluster_id='cluster_id'))


def make_member_list(members, **attr_map):
    """
    Create a dict representation of a list of members which we can use
    to serialize the members list.  Keyword arguments map the names of
    optional attributes to include to the database attribute.
    """

    def _fetch_memb(memb, attr_map):
        return dict([(k, memb[v])
                     for k, v in attr_map.items() if v in memb.keys()])

    # Return the list of members with the given attribute mapping
    return [_fetch_memb(memb, attr_map) for memb in members]


def create_resource():
    """Image members resource factory method."""
    deserializer = wsgi.JSONRequestDeserializer()
    serializer = wsgi.JSONResponseSerializer()
    return wsgi.Resource(Controller(), deserializer, serializer)
