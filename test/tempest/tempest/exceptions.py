# Copyright 2012 OpenStack Foundation
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

import testtools

# zfl add : get related opencos log
import re
import traceback
import time
from tempest_lib.common.utils import misc


# zfl add a decorator to show func's exec time
def exectime(func): 
    def newfunc(*args, **args2): 
        t0 = time.time()
        f = func(*args, **args2)
        print "\n\n@====exectime====%.3fs taken for {%s}\n\n" % (time.time() - t0, func.__name__)
        return f
    return newfunc
# zfl add end


class TempestException(Exception):
    """
    Base Tempest Exception

    To correctly use this class, inherit from it and define
    a 'message' property. That message will get printf'd
    with the keyword arguments provided to the constructor.
    """
    message = "An unknown exception occurred"

    def __init__(self, *args, **kwargs):
        super(TempestException, self).__init__()
        try:
            self._error_string = self.message % kwargs
        except Exception:
            # at least get the core message out if something happened
            self._error_string = self.message
        if len(args) > 0:
            # If there is a non-kwarg parameter, assume it's the error
            # message or reason description and tack it on to the end
            # of the exception message
            # Convert all arguments into their string representations...
            args = ["%s" % arg for arg in args]
            self._error_string = (self._error_string +
                                  "\nDetails: %s" % '\n'.join(args))

    def __str__(self):
        # zfl add : get related opencos log
            try:
                # zfl for debug only: stop and reserve
                # if issubclass(type(self),SSHTimeout):
                #     import time
                #     time.sleep(999999999)
                # zfl for debug only: stop and reserve end

                self.get_log = True
                log_obj = misc.GetOpenCosLog()
                pattern1 = re.compile(r'\w+-\w+-\w+-\w+-\w+')
                sresult = pattern1.findall(self._error_string)
                obj_type = ""
                if 'server' in self._error_string.lower():
                    obj_type = "server"
                if sresult:
                    log_result = log_obj.get_opencos_log(sresult,
                                                         obj_type=obj_type)
                else:
                    log_result = log_obj.get_opencos_log([],
                                                         obj_type=obj_type)
                    log_result = "\n--------- <logs>\n" + log_result
                self._error_string = self._error_string +
                                     "\n\n\n===possible log ===" +
                                     log_result +
                                     "\n\n===possiblelog end===\n\n\n"
            except Exception as e:
                  print "ZTE ===zfl : error ==" , e
                  traceback.print_exc()
#        else:
#            print "\n========zfl,exception call __str__ again"
        
        #zfl add end: get related opencos log      
            return self._error_string

class RestClientException(TempestException,
                          testtools.TestCase.failureException):
    pass


class InvalidConfiguration(TempestException):
    message = "Invalid Configuration"


class InvalidCredentials(TempestException):
    message = "Invalid Credentials"


class InvalidServiceTag(TempestException):
    message = "Invalid service tag"


class InvalidIdentityVersion(TempestException):
    message = "Invalid version %(identity_version) of the identity service"


class TimeoutException(TempestException):
    message = "Request timed out"


class BuildErrorException(TempestException):
    message = "Server %(server_id)s failed to build and is in ERROR status"


class ImageKilledException(TempestException):
    message = "Image %(image_id)s 'killed' while waiting for '%(status)s'"


class AddImageException(TempestException):
    message = "Image %(image_id)s failed to become ACTIVE in the allotted time"


class EC2RegisterImageException(TempestException):
    message = ("Image %(image_id)s failed to become 'available' "
               "in the allotted time")


class VolumeBuildErrorException(TempestException):
    message = "Volume %(volume_id)s failed to build and is in ERROR status"


class SnapshotBuildErrorException(TempestException):
    message = "Snapshot %(snapshot_id)s failed to build and is in ERROR status"


class VolumeBackupException(TempestException):
    message = "Volume backup %(backup_id)s failed and is in ERROR status"


class StackBuildErrorException(TempestException):
    message = ("Stack %(stack_identifier)s is in %(stack_status)s status "
               "due to '%(stack_status_reason)s'")


class StackResourceBuildErrorException(TempestException):
    message = ("Resource %(resource_name)s in stack %(stack_identifier)s is "
               "in %(resource_status)s status due to "
               "'%(resource_status_reason)s'")


class AuthenticationFailure(TempestException):
    message = ("Authentication with user %(user)s and password "
               "%(password)s failed auth using tenant %(tenant)s.")


class EndpointNotFound(TempestException):
    message = "Endpoint not found"


class ImageFault(TempestException):
    message = "Got image fault"


class IdentityError(TempestException):
    message = "Got identity error"


class SSHTimeout(TempestException):
    message = ("Connection to the %(host)s via SSH timed out.\n"
               "User: %(user)s, Password: %(password)s")


class SSHExecCommandFailed(TempestException):
    """Raised when remotely executed command returns nonzero status."""
    message = ("Command '%(command)s', exit status: %(exit_status)d, "
               "Error:\n%(strerror)s")


class ServerUnreachable(TempestException):
    message = "The server is not reachable via the configured network"


class TearDownException(TempestException):
    message = "%(num)d cleanUp operation failed"


class RFCViolation(RestClientException):
    message = "RFC Violation"


class InvalidHttpSuccessCode(RestClientException):
    message = "The success code is different than the expected one"


class BadRequest(RestClientException):
    message = "Bad request"


class ResponseWithNonEmptyBody(RFCViolation):
    message = ("RFC Violation! Response with %(status)d HTTP Status Code "
               "MUST NOT have a body")


class ResponseWithEntity(RFCViolation):
    message = ("RFC Violation! Response with 205 HTTP Status Code "
               "MUST NOT have an entity")


class InvalidHTTPResponseHeader(RestClientException):
    message = "HTTP response header is invalid"


class InvalidStructure(TempestException):
    message = "Invalid structure of table with details"


class CommandFailed(Exception):
    def __init__(self, returncode, cmd, output, stderr):
        super(CommandFailed, self).__init__()
        self.returncode = returncode
        self.cmd = cmd
        self.stdout = output
        self.stderr = stderr

    def __str__(self):
        return ("Command '%s' returned non-zero exit status %d.\n"
                "stdout:\n%s\n"
                "stderr:\n%s" % (self.cmd,
                                 self.returncode,
                                 self.stdout,
                                 self.stderr))
