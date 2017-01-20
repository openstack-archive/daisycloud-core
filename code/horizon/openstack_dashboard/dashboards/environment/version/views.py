#
#   Copyright ZTE
#   Daisy Tools Dashboard
#

import os
import json
import logging
import hashlib
import statvfs
import time
import datetime

from django import http
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.utils.translation import ungettext_lazy
from django.core.urlresolvers import reverse_lazy
from horizon import forms
from horizon import tables
from horizon import messages
from horizon import exceptions

from openstack_dashboard import api

LOG = logging.getLogger(__name__)


def get_version_path(file_type=None):
    if file_type and file_type == "zenic":
        return getattr(settings, 'DAISY_ZENIC_VER_PATH',
                       "/var/lib/daisy/zenic/")
    return getattr(settings, 'DAISY_VER_PATH',
                   "/var/lib/daisy/kolla/")


def delete_version_file(version_file_name, file_type=None):
    ver_path = get_version_path(file_type)
    for item in os.listdir(ver_path):
        if item != version_file_name:
            continue

        full_path = os.path.join(ver_path, item)
        if os.path.isfile(full_path):
            os.remove(full_path)


class VersionFilterAction(tables.FilterAction):
    def filter(self, table, versions, filter_string):
        pass


class DeleteVersion(tables.DeleteAction):
    help_text = _("This action cannot be undone. If system version is "
                  "deleted, the corresponding patch version will be "
                  "automatically deleted.")

    @staticmethod
    def action_present(count):
        return ungettext_lazy(
            u"Remove Version",
            u"Remove Versions",
            count
        )

    @staticmethod
    def action_past(count):
        return ungettext_lazy(
            u"Removed Version",
            u"Removed Versions",
            count
        )

    def _allowed(self, request, datum):
        if datum and datum["version_status"] == "used":
            return False
        return True

    def delete(self, request, version_id):
        try:
            # refer to get_object_id()
            version_info = version_id.split(",")
            if len(version_info) != 2:
                msg = _("Invalid version delete parameter: %s") % version_id
                raise exceptions.WorkflowValidationError(msg)
            if version_info[-1] == "system":
                version = api.daisy.version_get(request, version_info[0])
                # First step to delete the patch version files
                if hasattr(version, "version_patch"):
                    for patch in version.version_patch:
                        delete_version_file(patch["name"], version.type)
                        api.daisy.version_patch_delete(request, patch["id"])
                # Second step to delete system version file
                delete_version_file(version.name, version.type)
                api.daisy.version_delete(request, version.id)
            elif version_info[-1] == "patch":
                patch = api.daisy.version_patch_get(request, version_info[0])
                version = api.daisy.version_get(request, patch.version_id)
                delete_version_file(patch.name, version.type)
                api.daisy.version_patch_delete(request, patch.id)
            else:
                msg = _("Invalid version type: %s") % version_info[-1]
                raise exceptions.WorkflowValidationError(msg)
        except Exception as e:
            messages.error(request, e)
            LOG.error('Delete file failed! %s' % e)


class UpdateVersion(tables.LinkAction):
    name = "update_version"
    verbose_name = _("Update version")
    url = "horizon:environment:version:update_version"
    classes = ("ajax-modal", )

    def allowed(self, request, datum):
        if datum["version_status"] == "used":
            return False
        return True


def get_file_type(version_detail):
    file_type = ""

    if version_detail["file_type"] == "unknown":
        file_type = _("unknown")
    else:
        file_type = version_detail["file_type"]

    return file_type


def get_version_type(version_detail):
    version_type = ""

    if version_detail["version_type"] == "system":
        version_type = _("system")
    elif version_detail["version_type"] == "patch":
        version_type = _("patch")

    return version_type


def get_version_status(version_detail):
    version_status = ""

    if version_detail["version_status"] == "used":
        version_status = _("used")
    elif version_detail["version_status"] == "unused":
        version_status = _("unused")

    return version_status


def get_file_size(version_detail):
    file_size = version_detail["file_size"]

    if version_detail["file_size"] > 1024 * 1024 * 1024:
        file_size = "%.2f" % (float(version_detail["file_size"]) /
                              (1024 * 1024 * 1024)) + " GB"
    elif version_detail["file_size"] > 1024 * 1024:
        file_size = "%.2f" % (float(version_detail["file_size"]) /
                              (1024 * 1024)) + " MB"
    elif version_detail["file_size"] > 1024:
        file_size = "%.0f" % (float(version_detail["file_size"]) /
                              1024) + " KB"
    else:
        file_size = "<1 KB"

    return file_size


class VersionTable(tables.DataTable):
    version_name = tables.Column("version_name",
                                 verbose_name=_("Version name"))
    file_type = tables.Column(get_file_type,
                              verbose_name=_("File type"))
    version_no = tables.Column("version_no",
                               verbose_name=_("Version No"),
                               hidden=True)
    version_type = tables.Column(get_version_type,
                                 verbose_name=_("Version type"))
    version_status = tables.Column(get_version_status,
                                   verbose_name=_("Version status"))
    upload_time = tables.Column("upload_time",
                                verbose_name=_("Upload time"))
    file_size = tables.Column(get_file_size,
                              verbose_name=_("File size"))
    check_sum = tables.Column("check_sum",
                              verbose_name=_("Check sum"),
                              hidden=True)
    corresponding_version = tables.Column("corresponding_version",
                                          verbose_name=_("Corresponding "
                                                         "system version"))
    description = tables.Column("description",
                                verbose_name=_("Description"))

    def get_object_id(self, datum):
        return datum["id"] + "," + datum["version_type"]

    class Meta:
        name = "version_list"
        verbose_name = _("VersionList")
        multi_select = True
        table_actions = (VersionFilterAction, DeleteVersion)
        row_actions = (DeleteVersion, UpdateVersion)


def get_local_time(created_at):
    now_stamp = time.time()
    loc_time = datetime.datetime.fromtimestamp(now_stamp)
    utc_time = datetime.datetime.utcfromtimestamp(now_stamp)
    loc_dt = datetime.datetime.strptime(created_at,
                                        "%Y-%m-%dT%H:%M:%S.000000")
    loc_dt += loc_time - utc_time
    return loc_dt.strftime("%Y-%m-%d %H:%M:%S")


class VersionView(tables.DataTableView):
    table_class = VersionTable
    template_name = "environment/version/index.html"

    def get_data(self):
        versions = api.daisy.version_list(self.request)
        version_lists = [c for c in versions]
        version_lists.reverse()

        ret_versions = []
        for version in version_lists:
            ret_versions.append({
                "id": version.id,
                "file_type": version.type,
                "version_no": version.version,
                "version_type": "system",
                "version_name": version.name,
                "corresponding_version": "-",
                "file_size": version.size,
                "version_status": version.status,
                "check_sum": version.checksum,
                "upload_time": get_local_time(version.created_at),
                "description": version.description
            })
            if hasattr(version, "version_patch"):
                version.version_patch.reverse()
                for patch in version.version_patch:
                    ret_versions.append({
                        "id": patch["id"],
                        "file_type": version.type,
                        "version_no": version.version,
                        "version_type": "patch",
                        "version_name": patch["name"],
                        "corresponding_version": version.name,
                        "file_size": patch["size"],
                        "version_status": patch["status"],
                        "check_sum": patch["checksum"],
                        "upload_time": get_local_time(patch["created_at"]),
                        "description": patch["description"]
                    })
        return ret_versions

    def get_context_data(self, **kwargs):
        context = super(VersionView, self).get_context_data(**kwargs)
        backend_types = api.daisy.backend_types_get(self.request)
        backend_types_dict = backend_types.to_dict()
        if len(backend_types_dict['default_backend_types']) == 0:
            context['hide_templates'] = True
        clusters = api.daisy.cluster_list(self.request)
        context['clusters'] = [c for c in clusters]
        context['is_version'] = True
        return context


def generate_file_md5(file_path):
    if not os.path.isfile(file_path):
        return ''

    stat = os.stat(file_path)
    file = open(file_path, 'rb')
    md5_obj = hashlib.md5()
    while True:
        seg = file.read(stat.st_blksize)
        if not seg:
            break
        md5_obj.update(seg)
    file.close()

    return md5_obj.hexdigest()


def get_version_file_names(request):
    versions = api.daisy.version_list(request)
    version_lists = [c for c in versions]
    version_lists.reverse()

    ret_file_names = []
    for version in version_lists:
        ret_file_names.append(version.name)
        if hasattr(version, "version_patch"):
            for patch in version.version_patch:
                ret_file_names.append(patch["name"])

    return ret_file_names


def upload_version(request):
    try:
        file_type = request.POST.get("file_type")
        file_position = request.POST.get("file_position")
        version_type = request.POST.get("version_type")

        version_path = get_version_path(file_type)
        if version_type == "patch":
            correspond_file = request.POST.get("correspond_file")
            if correspond_file is None:
                msg = _("Please select corresponding system version file")
                raise exceptions.WorkflowValidationError(msg)
        version_file = request.FILES.get("version_file")
        description = request.POST.get("description")

        version_file_name = ""
        if file_position == 'local':
            if version_file is not None:
                version_file_name = version_file.name
                # Upload file
                destination = open(version_path + version_file_name, 'wb+')
                for chunk in version_file.chunks():
                    destination.write(chunk)
                destination.close()
            else:
                msg = _("Please select version file")
                raise exceptions.WorkflowValidationError(msg)
        elif file_position == 'server':
            version_file_name = request.POST.get("select_server_file")
        else:
            msg = _("Unsupported original file location")
            raise exceptions.WorkflowValidationError(msg)

        # Add version information
        file_size = os.path.getsize(version_path + version_file_name)
        check_sum = generate_file_md5(version_path + version_file_name)
        if version_type == "system":
            api.daisy.version_add(request,
                                  type=file_type,
                                  name=version_file_name,
                                  size=file_size,
                                  checksum=check_sum,
                                  description=description)
            messages.success(request, _('Upload system version file success!'))
        elif version_type == "patch":
            api.daisy.version_patch_add(request,
                                        name=version_file_name,
                                        size=file_size,
                                        checksum=check_sum,
                                        version_id=correspond_file,
                                        description=description)
            messages.success(request, _('Upload patch version file success!'))
        else:
            msg = _("Unsupported version type")
            raise exceptions.WorkflowValidationError(msg)
    except Exception, e:
        messages.error(request, e)
        LOG.error('Upload file failed! %s' % e)

    url = reverse('horizon:environment:version:index')
    response = http.HttpResponseRedirect(url)
    return response


def get_appointed_system_versions(request):
    data = json.loads(request.body)

    ret_system_version_list = []
    versions = api.daisy.version_list(request,
                                      filters={"type": data["file_type"]})
    version_lists = [c for c in versions]
    version_lists.reverse()
    for version in version_lists:
        ret_system_version_list.append({
            "version_id": version.id,
            "version_name": version.name
        })

    return http.HttpResponse(json.dumps(ret_system_version_list),
                             content_type="application/json")


def get_headstrong_server_files(request):
    version_path = get_version_path()
    file_names = get_version_file_names(request)

    server_file_types = [".bin", ".iso"]
    ret_headstrong_files = []
    for item in os.listdir(version_path):
        full_path = os.path.join(version_path, item)
        file_extension = os.path.splitext(full_path)[1]

        if os.path.isfile(full_path) \
                and item not in file_names \
                and file_extension.lower() in server_file_types:
            ret_headstrong_files.append({
                "version_id": "",
                "version_name": item
            })

    return http.HttpResponse(json.dumps(ret_headstrong_files),
                             content_type="application/json")


def get_version_file_types(request):
    versions = api.daisy.version_list(request)
    version_lists = [c for c in versions]
    version_lists.reverse()

    ret_file_types = []
    for version in version_lists:
        if version.type not in ret_file_types:
            ret_file_types.append(version.type)

    return http.HttpResponse(json.dumps(ret_file_types),
                             content_type="application/json")


def get_appointed_patch_files(request):
    data = json.loads(request.body)

    ret_patch_version_list = []
    versions = api.daisy.version_list(request)
    version_lists = [c for c in versions]
    for version in version_lists:
        if version.id == data["system_file"]:
            if hasattr(version, "version_patch"):
                version.version_patch.reverse()
                for patch in version.version_patch:
                    ret_patch_version_list.append({
                        "version_id": patch["id"],
                        "version_name": patch["name"]})
                break

    return http.HttpResponse(json.dumps(ret_patch_version_list),
                             content_type="application/json")


def check_disk_space_and_file_exist(request):
    data = json.loads(request.body)

    ver_path = get_version_path(data["file_type"])
    vfs = os.statvfs(ver_path)
    disk_free_space = vfs[statvfs.F_BAVAIL] * vfs[statvfs.F_BSIZE]

    ret_msg = []
    # 1. Check file exist or not
    file_names = get_version_file_names(request)
    if data["file_name"] in file_names:
        ret_msg.append("File already exist")
        messages.error(request, _("File already exist"))

    # 2. Check disk space
    disk_space_min = 100 * 1024 * 1024
    # Can't upload files if disk free space is less than 100M
    if disk_free_space < disk_space_min:
        ret_msg.append("Disk free space is less than 100M")
        messages.error(request, _("Disk free space is less than 100M"))
    # Can't upload files if disk free space is less than file size
    if int(data["file_size"]) + disk_space_min > disk_free_space:
        ret_msg.append("Insufficient disk space")
        notice_free = (disk_free_space - disk_space_min) / (1024 * 1024)
        message = _("Insufficient disk space, current free: %dM") % notice_free
        messages.error(request, message)
    # Notice if disk free space is less than 1G
    if disk_free_space < 1024 * 1024 * 1024:
        messages.warning(request, _('Disk space is less than 1G'))

    return http.HttpResponse(json.dumps(ret_msg),
                             content_type="application/json")


def get_appointed_system_packages(request):
    return []


def get_tecs_version_list(request):
    tecs_version_list = []
    versions = api.daisy.version_list(request, filters={"type": "tecs"})
    version_lists = [c for c in versions]
    version_lists.reverse()
    for version in version_lists:
        tecs_version_list.append({
            "version_id": version.id,
            "version_name": version.name
        })

    return tecs_version_list


def check_version_file_exist(request, version_id):
    file_type = ""
    version_name = ""

    version = api.daisy.version_get(request, version_id)
    if version and version.name:
        version_name = version.name
        file_type = version.type
    else:
        patch = api.daisy.version_patch_get(request, version_id)
        if patch and patch.name:
            version = api.daisy.version_get(request, patch.version_id)
            version_name = patch.name
            file_type = version.type
    if not version_name:
        message = _("Version is not found.")
        raise exceptions.ConfigurationError(message)

    if not os.path.exists(get_version_path(file_type) + version_name):
        message = _("Version file is inexistent. %s") % version_name
        raise exceptions.ConfigurationError(message)


class UpdateVersionForm(forms.SelfHandlingForm):

    FILE_TYPE_CHOICES = [
        ("redhat 6.5", "redhat 6.5"),
        ("redhat 7.0", "redhat 7.0"),
        ("suse", "suse"),
        ("centos 7.0", "centos 7.0"),
        ("windows", "windows"),
        ("vplat", "vplat"),
        ("tecs", "tecs"),
        ("zenic", "zenic"),
        ("kolla", "kolla"),
        ("unknown", _("unknown"))]
    VERSION_TYPE_CHOICES = [
        ("system", _("System version")),
        ("patch", _("Patch version"))]

    old_version_id = forms.CharField(widget=forms.HiddenInput())
    old_patch_id = forms.CharField(widget=forms.HiddenInput(),
                                   required=False)
    old_version_type = forms.CharField(widget=forms.HiddenInput())
    old_version_name = forms.CharField(label=_("Version name"),
                                       required=False)
    old_size = forms.CharField(widget=forms.HiddenInput(),
                               required=False)
    old_checksum = forms.CharField(widget=forms.HiddenInput(),
                                   required=False)
    new_file_type = forms.ChoiceField(label=_("File type"),
                                      choices=FILE_TYPE_CHOICES,
                                      initial="redhat 7.0",
                                      required=False)
    new_version_type = forms.ChoiceField(label=_("Version type"),
                                         widget=forms.RadioSelect(),
                                         choices=VERSION_TYPE_CHOICES,
                                         initial="system",
                                         required=False)
    new_correspond_file = forms.ChoiceField(label=_("Corresponding system "
                                                    "version"),
                                            required=False)
    new_description = forms.CharField(label=_("Description"),
                                      widget=forms.Textarea(
                                          attrs={'rows': '3'}),
                                      required=False)

    def __init__(self, request, *args, **kwargs):
        super(UpdateVersionForm, self).__init__(request, *args, **kwargs)
        version_info = kwargs.get('initial', {}).get('version_id').split(",")
        self.fields['old_version_id'].initial = version_info[0]
        self.fields['old_patch_id'].initial = ""
        self.fields['old_version_type'].initial = version_info[1]
        self.fields['new_version_type'].initial = version_info[1]
        self.fields['new_correspond_file'].choices = \
            self.get_system_files(request)
        if version_info[1] == "system":
            version = api.daisy.version_get(request, version_info[0])
            if version:
                self.fields['old_version_name'].initial = version.name
                self.fields['old_size'].initial = version.size
                self.fields['old_checksum'].initial = version.checksum
                self.fields['new_file_type'].initial = version.type
                self.fields['new_description'].initial = version.description
        elif version_info[1] == "patch":
            patch = api.daisy.version_patch_get(request, version_info[0])
            version = api.daisy.version_get(request, patch.version_id)
            self.fields['old_version_id'].initial = version.id
            self.fields['old_patch_id'].initial = version_info[0]
            if version:
                self.fields['old_version_name'].initial = patch.name
                self.fields['old_size'].initial = patch.size
                self.fields['old_checksum'].initial = patch.checksum
                self.fields['new_file_type'].initial = version.type
                self.fields['new_correspond_file'].initial = version.id
                self.fields['new_description'].initial = patch.description

    def get_system_files(self, request):
        versions = api.daisy.version_list(request)
        version_lists = [c for c in versions]
        version_lists.reverse()
        system_file_choices = []
        for version in version_lists:
            system_file_choices.append((version.id, version.name))
        return system_file_choices

    def handle(self, request, data):
        try:
            if data["old_version_type"] == "system":
                if data["new_version_type"] == "system":
                    # system->system
                    api.daisy.version_update(
                        request, data["old_version_id"],
                        type=data["new_file_type"],
                        description=data['new_description'])
                elif data["new_version_type"] == "patch":
                    # system->patch
                    if not data["new_correspond_file"]:
                        msg = _("Corresponding system version is not selected")
                        raise exceptions.WorkflowValidationError(msg)
                    api.daisy.version_patch_add(
                        request,
                        name=data["old_version_name"],
                        size=data["old_size"],
                        checksum=data["old_checksum"],
                        version_id=data["new_correspond_file"],
                        description=data['new_description'])
                    api.daisy.version_delete(request, data["old_version_id"])
                else:
                    msg = _("Invalid version "
                            "type: %s") % data["old_version_type"]
                    raise exceptions.WorkflowValidationError(msg)
            elif data["old_version_type"] == "patch":
                if data["new_version_type"] == "system":
                    # patch->system
                    api.daisy.version_add(request,
                                          type=data["new_file_type"],
                                          name=data["old_version_name"],
                                          size=data["old_size"],
                                          checksum=data["old_checksum"],
                                          description=data['new_description'])
                    api.daisy.version_patch_delete(request,
                                                   data["old_patch_id"])
                elif data["new_version_type"] == "patch":
                    # patch->patch
                    if not data["new_correspond_file"]:
                        msg = _("Corresponding system version is not selected")
                        raise exceptions.WorkflowValidationError(msg)
                    api.daisy.version_patch_update(
                        request, data["old_patch_id"],
                        version_id=data["new_correspond_file"],
                        description=data['new_description'])
                else:
                    msg = _("Invalid version "
                            "type: %s") % data["old_version_type"]
                    raise exceptions.WorkflowValidationError(msg)
            else:
                msg = _("Invalid version type: %s") % data["old_version_type"]
                raise exceptions.WorkflowValidationError(msg)
        except Exception, e:
            messages.error(request, _("Update version failed! %s") % e)
            LOG.error('Update version failed! %s' % e)
            return False

        return True


class UpdateVersionView(forms.ModalFormView):
    form_class = UpdateVersionForm
    template_name = 'environment/version/update_version.html'
    submit_url = "horizon:environment:version:update_version"
    success_url = reverse_lazy('horizon:environment:version:index')

    def get_context_data(self, **kwargs):
        context = super(UpdateVersionView, self).get_context_data(**kwargs)
        context['version_id'] = self.kwargs['version_id']
        return context

    def get_initial(self):
        ret = {'version_id': self.kwargs["version_id"]}
        return ret
=======
    return kolla_version_list
>>>>>>> create cluster can config kolla version
