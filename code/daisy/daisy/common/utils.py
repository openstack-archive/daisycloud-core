# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2014 SoftLayer Technologies, Inc.
# Copyright 2015 Mirantis, Inc
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
System-level utilities and helper functions.
"""

import errno
from functools import reduce

try:
    from eventlet import sleep
except ImportError:
    from time import sleep
from eventlet.green import socket

import functools
import os
import platform
import re
import subprocess
import sys
import uuid

from OpenSSL import crypto
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import encodeutils
from oslo_utils import excutils
from oslo_utils import netutils
from oslo_utils import strutils
import six
from webob import exc

from daisy.common import exception
from daisy import i18n

CONF = cfg.CONF

LOG = logging.getLogger(__name__)
_ = i18n._
_LE = i18n._LE

FEATURE_BLACKLIST = ['content-length', 'content-type', 'x-image-meta-size']

# Whitelist of v1 API headers of form x-image-meta-xxx
IMAGE_META_HEADERS = ['x-image-meta-location', 'x-image-meta-size',
                      'x-image-meta-is_public', 'x-image-meta-disk_format',
                      'x-image-meta-container_format', 'x-image-meta-name',
                      'x-image-meta-status', 'x-image-meta-copy_from',
                      'x-image-meta-uri', 'x-image-meta-checksum',
                      'x-image-meta-created_at', 'x-image-meta-updated_at',
                      'x-image-meta-deleted_at', 'x-image-meta-min_ram',
                      'x-image-meta-min_disk', 'x-image-meta-owner',
                      'x-image-meta-store', 'x-image-meta-id',
                      'x-image-meta-protected', 'x-image-meta-deleted',
                      'x-image-meta-virtual_size']

DAISY_TEST_SOCKET_FD_STR = 'DAISY_TEST_SOCKET_FD'

DISCOVER_DEFAULTS = {
    'listen_port': '5050',
    'ironic_url': 'http://127.0.0.1:6385/v1',
}


def chunkreadable(iter, chunk_size=65536):
    """
    Wrap a readable iterator with a reader yielding chunks of
    a preferred size, otherwise leave iterator unchanged.

    :param iter: an iter which may also be readable
    :param chunk_size: maximum size of chunk
    """
    return chunkiter(iter, chunk_size) if hasattr(iter, 'read') else iter


def chunkiter(fp, chunk_size=65536):
    """
    Return an iterator to a file-like obj which yields fixed size chunks

    :param fp: a file-like object
    :param chunk_size: maximum size of chunk
    """
    while True:
        chunk = fp.read(chunk_size)
        if chunk:
            yield chunk
        else:
            break


def cooperative_iter(iter):
    """
    Return an iterator which schedules after each
    iteration. This can prevent eventlet thread starvation.

    :param iter: an iterator to wrap
    """
    try:
        for chunk in iter:
            sleep(0)
            yield chunk
    except Exception as err:
        with excutils.save_and_reraise_exception():
            msg = _LE("Error: cooperative_iter exception %s") % err
            LOG.error(msg)


def cooperative_read(fd):
    """
    Wrap a file descriptor's read with a partial function which schedules
    after each read. This can prevent eventlet thread starvation.

    :param fd: a file descriptor to wrap
    """
    def readfn(*args):
        result = fd.read(*args)
        sleep(0)
        return result
    return readfn


MAX_COOP_READER_BUFFER_SIZE = 134217728  # 128M seems like a sane buffer limit


class CooperativeReader(object):

    """
    An eventlet thread friendly class for reading in image data.

    When accessing data either through the iterator or the read method
    we perform a sleep to allow a co-operative yield. When there is more than
    one image being uploaded/downloaded this prevents eventlet thread
    starvation, ie allows all threads to be scheduled periodically rather than
    having the same thread be continuously active.
    """

    def __init__(self, fd):
        """
        :param fd: Underlying image file object
        """
        self.fd = fd
        self.iterator = None
        # NOTE(markwash): if the underlying supports read(), overwrite the
        # default iterator-based implementation with cooperative_read which
        # is more straightforward
        if hasattr(fd, 'read'):
            self.read = cooperative_read(fd)
        else:
            self.iterator = None
            self.buffer = ''
            self.position = 0

    def read(self, length=None):
        """Return the requested amount of bytes, fetching the next chunk of
        the underlying iterator when needed.

        This is replaced with cooperative_read in __init__ if the underlying
        fd already supports read().
        """
        if length is None:
            if len(self.buffer) - self.position > 0:
                # if no length specified but some data exists in buffer,
                # return that data and clear the buffer
                result = self.buffer[self.position:]
                self.buffer = ''
                self.position = 0
                return str(result)
            else:
                # otherwise read the next chunk from the underlying iterator
                # and return it as a whole. Reset the buffer, as subsequent
                # calls may specify the length
                try:
                    if self.iterator is None:
                        self.iterator = self.__iter__()
                    return self.iterator.next()
                except StopIteration:
                    return ''
                finally:
                    self.buffer = ''
                    self.position = 0
        else:
            result = bytearray()
            while len(result) < length:
                if self.position < len(self.buffer):
                    to_read = length - len(result)
                    chunk = self.buffer[self.position:self.position + to_read]
                    result.extend(chunk)

                    # This check is here to prevent potential OOM issues if
                    # this code is called with unreasonably high values of read
                    # size. Currently it is only called from the HTTP clients
                    # of Glance backend stores, which use httplib for data
                    # streaming, which has readsize hardcoded to 8K, so this
                    # check should never fire. Regardless it still worths to
                    # make the check, as the code may be reused somewhere else.
                    if len(result) >= MAX_COOP_READER_BUFFER_SIZE:
                        raise exception.LimitExceeded()
                    self.position += len(chunk)
                else:
                    try:
                        if self.iterator is None:
                            self.iterator = self.__iter__()
                        self.buffer = self.iterator.next()
                        self.position = 0
                    except StopIteration:
                        self.buffer = ''
                        self.position = 0
                        return str(result)
            return str(result)

    def __iter__(self):
        return cooperative_iter(self.fd.__iter__())


class LimitingReader(object):

    """
    Reader designed to fail when reading image data past the configured
    allowable amount.
    """

    def __init__(self, data, limit):
        """
        :param data: Underlying image data object
        :param limit: maximum number of bytes the reader should allow
        """
        self.data = data
        self.limit = limit
        self.bytes_read = 0

    def __iter__(self):
        for chunk in self.data:
            self.bytes_read += len(chunk)
            if self.bytes_read > self.limit:
                raise exception.ImageSizeLimitExceeded()
            else:
                yield chunk

    def read(self, i):
        result = self.data.read(i)
        self.bytes_read += len(result)
        if self.bytes_read > self.limit:
            raise exception.ImageSizeLimitExceeded()
        return result


def image_meta_to_http_headers(image_meta):
    """
    Returns a set of image metadata into a dict
    of HTTP headers that can be fed to either a Webob
    Request object or an httplib.HTTP(S)Connection object

    :param image_meta: Mapping of image metadata
    """
    headers = {}
    for k, v in image_meta.items():
        if v is not None:
            if k == 'properties':
                for pk, pv in v.items():
                    if pv is not None:
                        headers["x-image-meta-property-%s"
                                % pk.lower()] = six.text_type(pv)
            else:
                headers["x-image-meta-%s" % k.lower()] = six.text_type(v)
    return headers


def get_image_meta_from_headers(response):
    """
    Processes HTTP headers from a supplied response that
    match the x-image-meta and x-image-meta-property and
    returns a mapping of image metadata and properties

    :param response: Response to process
    """
    result = {}
    properties = {}

    if hasattr(response, 'getheaders'):  # httplib.HTTPResponse
        headers = response.getheaders()
    else:  # webob.Response
        headers = response.headers.items()

    for key, value in headers:
        key = str(key.lower())
        if key.startswith('x-image-meta-property-'):
            field_name = key[len('x-image-meta-property-'):].replace('-', '_')
            properties[field_name] = value or None
        elif key.startswith('x-image-meta-'):
            field_name = key[len('x-image-meta-'):].replace('-', '_')
            if 'x-image-meta-' + field_name not in IMAGE_META_HEADERS:
                msg = _("Bad header: %(header_name)s") % {'header_name': key}
                raise exc.HTTPBadRequest(msg, content_type="text/plain")
            result[field_name] = value or None
    result['properties'] = properties

    for key, nullable in [('size', False), ('min_disk', False),
                          ('min_ram', False), ('virtual_size', True)]:
        if key in result:
            try:
                result[key] = int(result[key])
            except ValueError:
                if nullable and result[key] == str(None):
                    result[key] = None
                else:
                    extra = (_("Cannot convert image %(key)s '%(value)s' "
                               "to an integer.")
                             % {'key': key, 'value': result[key]})
                    raise exception.InvalidParameterValue(value=result[key],
                                                          param=key,
                                                          extra_msg=extra)
            if result[key] < 0 and result[key] is not None:
                extra = (_("Image %(key)s must be >= 0 "
                           "('%(value)s' specified).")
                         % {'key': key, 'value': result[key]})
                raise exception.InvalidParameterValue(value=result[key],
                                                      param=key,
                                                      extra_msg=extra)

    for key in ('is_public', 'deleted', 'protected'):
        if key in result:
            result[key] = strutils.bool_from_string(result[key])
    return result


def get_host_meta(response):
    result = {}
    for key, value in response.json.items():
        result[key] = value
    return result


def get_cluster_meta(response):
    result = {}
    for key, value in response.json.items():
        result[key] = value
    return result


def get_component_meta(response):
    result = {}
    for key, value in response.json.items():
        result[key] = value
    return result


def get_service_meta(response):
    result = {}
    for key, value in response.json.items():
        result[key] = value
    return result


def get_template_meta(response):
    result = {}
    for key, value in response.json.items():
        result[key] = value
    return result


def get_role_meta(response):
    result = {}
    for key, value in response.json.items():
        result[key] = value
    return result


def get_config_file_meta(response):
    result = {}
    for key, value in response.json.items():
        result[key] = value
    return result


def get_config_set_meta(response):
    result = {}
    for key, value in response.json.items():
        result[key] = value
    return result


def get_config_meta(response):
    result = {}
    for key, value in response.json.items():
        result[key] = value
    return result


def get_network_meta(response):
    result = {}
    for key, value in response.json.items():
        result[key] = value
    return result


def get_dict_meta(response):
    result = {}
    for key, value in response.json.items():
        result[key] = value
    return result


def create_mashup_dict(image_meta):
    """
    Returns a dictionary-like mashup of the image core properties
    and the image custom properties from given image metadata.

    :param image_meta: metadata of image with core and custom properties
    """

    def get_items():
        for key, value in six.iteritems(image_meta):
            if isinstance(value, dict):
                for subkey, subvalue in six.iteritems(
                        create_mashup_dict(value)):
                    if subkey not in image_meta:
                        yield subkey, subvalue
            else:
                yield key, value

    return dict(get_items())


def safe_mkdirs(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def safe_remove(path):
    try:
        os.remove(path)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


class PrettyTable(object):

    """Creates an ASCII art table for use in bin/glance

    Example:

        ID  Name              Size         Hits
        --- ----------------- ------------ -----
        122 image                       22     0
    """

    def __init__(self):
        self.columns = []

    def add_column(self, width, label="", just='l'):
        """Add a column to the table

        :param width: number of characters wide the column should be
        :param label: column heading
        :param just: justification for the column, 'l' for left,
                     'r' for right
        """
        self.columns.append((width, label, just))

    def make_header(self):
        label_parts = []
        break_parts = []
        for width, label, _ in self.columns:
            # NOTE(sirp): headers are always left justified
            label_part = self._clip_and_justify(label, width, 'l')
            label_parts.append(label_part)

            break_part = '-' * width
            break_parts.append(break_part)

        label_line = ' '.join(label_parts)
        break_line = ' '.join(break_parts)
        return '\n'.join([label_line, break_line])

    def make_row(self, *args):
        row = args
        row_parts = []
        for data, (width, _, just) in zip(row, self.columns):
            row_part = self._clip_and_justify(data, width, just)
            row_parts.append(row_part)

        row_line = ' '.join(row_parts)
        return row_line

    @staticmethod
    def _clip_and_justify(data, width, just):
        # clip field to column width
        clipped_data = str(data)[:width]

        if just == 'r':
            # right justify
            justified = clipped_data.rjust(width)
        else:
            # left justify
            justified = clipped_data.ljust(width)

        return justified


def get_terminal_size():

    def _get_terminal_size_posix():
        import fcntl
        import struct
        import termios

        height_width = None

        try:
            height_width = struct.unpack('hh', fcntl.ioctl(sys.stderr.fileno(),
                                                           termios.TIOCGWINSZ,
                                                           struct.pack(
                                                               'HH', 0, 0)))
        except Exception:
            pass

        if not height_width:
            try:
                p = subprocess.Popen(['stty', 'size'],
                                     shell=False,
                                     stdout=subprocess.PIPE,
                                     stderr=open(os.devnull, 'w'))
                result = p.communicate()
                if p.returncode == 0:
                    return tuple(int(x) for x in result[0].split())
            except Exception:
                pass

        return height_width

    def _get_terminal_size_win32():
        try:
            from ctypes import create_string_buffer
            from ctypes import windll
            handle = windll.kernel32.GetStdHandle(-12)
            csbi = create_string_buffer(22)
            res = windll.kernel32.GetConsoleScreenBufferInfo(handle, csbi)
        except Exception:
            return None
        if res:
            import struct
            unpack_tmp = struct.unpack("hhhhHhhhhhh", csbi.raw)
            (bufx, bufy, curx, cury, wattr,
             left, top, right, bottom, maxx, maxy) = unpack_tmp
            height = bottom - top + 1
            width = right - left + 1
            return (height, width)
        else:
            return None

    def _get_terminal_size_unknownOS():
        raise NotImplementedError

    func = {'posix': _get_terminal_size_posix,
            'win32': _get_terminal_size_win32}

    height_width = func.get(platform.os.name, _get_terminal_size_unknownOS)()

    if height_width is None:
        raise exception.Invalid()

    for i in height_width:
        if not isinstance(i, int) or i <= 0:
            raise exception.Invalid()

    return height_width[0], height_width[1]


def mutating(func):
    """Decorator to enforce read-only logic"""
    @functools.wraps(func)
    def wrapped(self, req, *args, **kwargs):
        if req.context.read_only:
            msg = "Read-only access"
            LOG.debug(msg)
            raise exc.HTTPForbidden(msg, request=req,
                                    content_type="text/plain")
        return func(self, req, *args, **kwargs)
    return wrapped


def setup_remote_pydev_debug(host, port):
    error_msg = _LE('Error setting up the debug environment. Verify that the'
                    ' option pydev_worker_debug_host is pointing to a valid '
                    'hostname or IP on which a pydev server is listening on'
                    ' the port indicated by pydev_worker_debug_port.')

    try:
        try:
            from pydev import pydevd
        except ImportError:
            import pydevd

        pydevd.settrace(host,
                        port=port,
                        stdoutToServer=True,
                        stderrToServer=True)
        return True
    except Exception:
        with excutils.save_and_reraise_exception():
            LOG.exception(error_msg)


def validate_key_cert(key_file, cert_file):
    try:
        error_key_name = "private key"
        error_filename = key_file
        with open(key_file, 'r') as keyfile:
            key_str = keyfile.read()
        key = crypto.load_privatekey(crypto.FILETYPE_PEM, key_str)

        error_key_name = "certificate"
        error_filename = cert_file
        with open(cert_file, 'r') as certfile:
            cert_str = certfile.read()
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_str)
    except IOError as ioe:
        raise RuntimeError(_("There is a problem with your %(error_key_name)s "
                             "%(error_filename)s.  Please verify it."
                             "  Error: %(ioe)s") %
                           {'error_key_name': error_key_name,
                            'error_filename': error_filename,
                            'ioe': ioe})
    except crypto.Error as ce:
        raise RuntimeError(_("There is a problem with your %(error_key_name)s "
                             "%(error_filename)s.  Please verify it. OpenSSL"
                             " error: %(ce)s") %
                           {'error_key_name': error_key_name,
                            'error_filename': error_filename,
                            'ce': ce})

    try:
        data = str(uuid.uuid4())
        digest = CONF.digest_algorithm
        if digest == 'sha1':
            LOG.warn('The FIPS (FEDERAL INFORMATION PROCESSING STANDARDS)'
                     ' state that the SHA-1 is not suitable for'
                     ' general-purpose digital signature applications (as'
                     ' specified in FIPS 186-3) that require 112 bits of'
                     ' security. The default value is sha1 in Kilo for a'
                     ' smooth upgrade process, and it will be updated'
                     ' with sha256 in next release(L).')
        out = crypto.sign(key, data, digest)
        crypto.verify(cert, out, data, digest)
    except crypto.Error as ce:
        raise RuntimeError(_("There is a problem with your key pair.  "
                             "Please verify that cert %(cert_file)s and "
                             "key %(key_file)s belong together.  OpenSSL "
                             "error %(ce)s") % {'cert_file': cert_file,
                                                'key_file': key_file,
                                                'ce': ce})


def get_test_suite_socket():
    global DAISY_TEST_SOCKET_FD_STR
    if DAISY_TEST_SOCKET_FD_STR in os.environ:
        fd = int(os.environ[DAISY_TEST_SOCKET_FD_STR])
        sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
        sock = socket.SocketType(_sock=sock)
        sock.listen(CONF.backlog)
        del os.environ[DAISY_TEST_SOCKET_FD_STR]
        os.close(fd)
        return sock
    return None


def is_uuid_like(val):
    """Returns validation of a value as a UUID.

    For our purposes, a UUID is a canonical form string:
    aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
    """
    try:
        return str(uuid.UUID(val)) == val
    except (TypeError, ValueError, AttributeError):
        return False


def is_valid_hostname(hostname):
    """Verify whether a hostname (not an FQDN) is valid."""
    return re.match('^[a-zA-Z0-9-]+$', hostname) is not None


def is_valid_fqdn(fqdn):
    """Verify whether a host is a valid FQDN."""
    return re.match('^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', fqdn) is not None


def parse_valid_host_port(host_port):
    """
    Given a "host:port" string, attempts to parse it as intelligently as
    possible to determine if it is valid. This includes IPv6 [host]:port form,
    IPv4 ip:port form, and hostname:port or fqdn:port form.

    Invalid inputs will raise a ValueError, while valid inputs will return
    a (host, port) tuple where the port will always be of type int.
    """

    try:
        try:
            host, port = netutils.parse_host_port(host_port)
        except Exception:
            raise ValueError(_('Host and port "%s" is not valid.') % host_port)

        if not netutils.is_valid_port(port):
            raise ValueError(_('Port "%s" is not valid.') % port)

        # First check for valid IPv6 and IPv4 addresses, then a generic
        # hostname. Failing those, if the host includes a period, then this
        # should pass a very generic FQDN check. The FQDN check for letters at
        # the tail end will weed out any hilariously absurd IPv4 addresses.

        if not (netutils.is_valid_ipv6(host) or netutils.is_valid_ipv4(host) or
                is_valid_hostname(host) or is_valid_fqdn(host)):
            raise ValueError(_('Host "%s" is not valid.') % host)

    except Exception as ex:
        raise ValueError(_('%s '
                           'Please specify a host:port pair, where host is an '
                           'IPv4 address, IPv6 address, hostname, or FQDN. If '
                           'using an IPv6 address, enclose it in brackets '
                           'separately from the port (i.e., '
                           '"[fe80::a:b:c]:9876").') % ex)

    return (host, int(port))


def exception_to_str(exc):
    try:
        error = six.text_type(exc)
    except UnicodeError:
        try:
            error = str(exc)
        except UnicodeError:
            error = ("Caught '%(exception)s' exception." %
                     {"exception": exc.__class__.__name__})
    return encodeutils.safe_encode(error, errors='ignore')


try:
    REGEX_4BYTE_UNICODE = re.compile(u'[\U00010000-\U0010ffff]')
except re.error:
    # UCS-2 build case
    REGEX_4BYTE_UNICODE = re.compile(u'[\uD800-\uDBFF][\uDC00-\uDFFF]')


def no_4byte_params(f):
    """
    Checks that no 4 byte unicode characters are allowed
    in dicts' keys/values and string's parameters
    """
    def wrapper(*args, **kwargs):

        def _is_match(some_str):
            return (isinstance(some_str, unicode) and
                    REGEX_4BYTE_UNICODE.findall(some_str) != [])

        def _check_dict(data_dict):
            # a dict of dicts has to be checked recursively
            for key, value in data_dict.iteritems():
                if isinstance(value, dict):
                    _check_dict(value)
                else:
                    if _is_match(key):
                        msg = _("Property names can't contain 4 byte unicode.")
                        raise exception.Invalid(msg)
                    if _is_match(value):
                        msg = (_("%s can't contain 4 byte unicode characters.")
                               % key.title())
                        raise exception.Invalid(msg)

        for data_dict in [arg for arg in args if isinstance(arg, dict)]:
            _check_dict(data_dict)
        # now check args for str values
        for arg in args:
            if _is_match(arg):
                msg = _("Param values can't contain 4 byte unicode.")
                raise exception.Invalid(msg)
        # check kwargs as well, as params are passed as kwargs via
        # registry calls
        _check_dict(kwargs)
        return f(*args, **kwargs)
    return wrapper


def stash_conf_values():
    """
    Make a copy of some of the current global CONF's settings.
    Allows determining if any of these values have changed
    when the config is reloaded.
    """
    conf = {}
    conf['bind_host'] = CONF.bind_host
    conf['bind_port'] = CONF.bind_port
    conf['tcp_keepidle'] = CONF.cert_file
    conf['backlog'] = CONF.backlog
    conf['key_file'] = CONF.key_file
    conf['cert_file'] = CONF.cert_file

    return conf


def get_host_min_mac(host_interfaces):
    if not isinstance(host_interfaces, list):
        host_interfaces = eval(host_interfaces)
    macs = [interface['mac'] for interface in host_interfaces
            if interface['type'] == 'ether' and interface['mac']]
    min_mac = min(macs)
    return min_mac


def ip_into_int(ip):
    """
    Switch ip string to decimalism integer..
    :param ip: ip string
    :return: decimalism integer
    """
    return reduce(lambda x, y: (x << 8) + y, map(int, ip.split('.')))


def is_ip_in_cidr(ip, cidr):
    """
    Check ip is in cidr
    :param ip: Ip will be checked, like:192.168.1.2.
    :param cidr: Ip range,like:192.168.0.0/24.
    :return: If ip in cidr, return True, else return False.
    """
    network = cidr.split('/')
    mask = ~(2**(32 - int(network[1])) - 1)
    return (ip_into_int(ip) & mask) == (ip_into_int(network[0]) & mask)


def is_ip_in_ranges(ip, ip_ranges):
    """
    Check ip is in range
    : ip: Ip will be checked, like:192.168.1.2.
    : ip_ranges : Ip ranges, like:
                    [{'start':'192.168.0.10', 'end':'192.168.0.20'}
                    {'start':'192.168.0.50', 'end':'192.168.0.60'}]
    :return: If ip in ip_ranges, return True, else return False.
    """
    for ip_range in ip_ranges:
        start_ip_int = ip_into_int(ip_range['start'])
        end_ip_int = ip_into_int(ip_range['end'])
        ip_int = ip_into_int(ip)
        if ip_int >= start_ip_int and ip_int <= end_ip_int:
            return True

    return False


def get_dvs_interfaces(host_interfaces):
    dvs_interfaces = []
    if not isinstance(host_interfaces, list):
        host_interfaces = eval(host_interfaces)
    for interface in host_interfaces:
        if not isinstance(interface, dict):
            interface = eval(interface)
        if ('vswitch_type' in interface and
                interface['vswitch_type'] == 'dvs'):
            dvs_interfaces.append(interface)

    return dvs_interfaces


def get_clc_pci_info(pci_info):
    clc_pci = []
    flag1 = 'Intel Corporation Coleto Creek PCIe Endpoint'
    flag2 = '8086:0435'
    for pci in pci_info:
        if flag1 in pci or flag2 in pci:
            clc_pci.append(pci.split()[0])
    return clc_pci


def cpu_str_to_list(spec):
    """Parse a CPU set specification.

    :param spec: cpu set string eg "1-4,^3,6"

    Each element in the list is either a single
    CPU number, a range of CPU numbers, or a
    caret followed by a CPU number to be excluded
    from a previous range.

    :returns: a set of CPU indexes
    """

    cpusets = []
    if not spec:
        return cpusets

    cpuset_ids = set()
    cpuset_reject_ids = set()
    for rule in spec.split(','):
        rule = rule.strip()
        # Handle multi ','
        if len(rule) < 1:
            continue
        # Note the count limit in the .split() call
        range_parts = rule.split('-', 1)
        if len(range_parts) > 1:
            # So, this was a range; start by converting the parts to ints
            try:
                start, end = [int(p.strip()) for p in range_parts]
            except ValueError:
                raise exception.Invalid(_("Invalid range expression %r")
                                        % rule)
            # Make sure it's a valid range
            if start > end:
                raise exception.Invalid(_("Invalid range expression %r")
                                        % rule)
            # Add available CPU ids to set
            cpuset_ids |= set(range(start, end + 1))
        elif rule[0] == '^':
            # Not a range, the rule is an exclusion rule; convert to int
            try:
                cpuset_reject_ids.add(int(rule[1:].strip()))
            except ValueError:
                raise exception.Invalid(_("Invalid exclusion "
                                          "expression %r") % rule)
        else:
            # OK, a single CPU to include; convert to int
            try:
                cpuset_ids.add(int(rule))
            except ValueError:
                raise exception.Invalid(_("Invalid inclusion "
                                          "expression %r") % rule)

    # Use sets to handle the exclusion rules for us
    cpuset_ids -= cpuset_reject_ids
    cpusets = list(cpuset_ids)
    cpusets.sort()
    return cpusets


def cpu_list_to_str(cpu_list):
    """Parse a CPU list to string.

    :param cpu_list: eg "[1,2,3,4,6,7]"

    :returns: a string of CPU ranges, eg 1-4,6,7
    """
    spec = ''
    if not cpu_list:
        return spec

    cpu_list.sort()
    count = 0
    group_cpus = []
    tmp_cpus = []
    for cpu in cpu_list:
        if count == 0:
            init = cpu
            tmp_cpus.append(cpu)
        else:
            if cpu == (init + count):
                tmp_cpus.append(cpu)
            else:
                group_cpus.append(tmp_cpus)
                tmp_cpus = []
                count = 0
                init = cpu
                tmp_cpus.append(cpu)
        count += 1

    group_cpus.append(tmp_cpus)

    for group in group_cpus:
        if len(group) > 2:
            group_spec = ("%s-%s" % (group[0], group[0]+len(group)-1))
        else:
            group_str = [str(num) for num in group]
            group_spec = ','.join(group_str)
        if spec:
            spec += ',' + group_spec
        else:
            spec = group_spec

    return spec


def simple_subprocess_call(cmd):
    return_code = subprocess.call(cmd,
                                  shell=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
    return return_code


def translate_quotation_marks_for_shell(orig_str):
    translated_str = ''
    quotation_marks = '"'
    quotation_marks_count = orig_str.count(quotation_marks)
    if quotation_marks_count > 0:
        replace_marks = '\\"'
        translated_str = orig_str.replace(quotation_marks, replace_marks)
    else:
        translated_str = orig_str
    return translated_str


def get_numa_node_cpus(host_cpu):
    numa = {}
    if 'numa_node0' in host_cpu:
        numa['numa_node0'] = cpu_str_to_list(host_cpu['numa_node0'])
    if 'numa_node1' in host_cpu:
        numa['numa_node1'] = cpu_str_to_list(host_cpu['numa_node1'])
    return numa


def get_numa_node_from_cpus(numa, str_cpus):
    numa_nodes = []

    cpu_list = cpu_str_to_list(str_cpus)
    for cpu in cpu_list:
        if cpu in numa['numa_node0']:
            numa_nodes.append(0)
        if cpu in numa['numa_node1']:
            numa_nodes.append(1)

    numa_nodes = list(set(numa_nodes))
    numa_nodes.sort()
    return numa_nodes
