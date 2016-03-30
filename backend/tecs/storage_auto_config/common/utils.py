import subprocess
import random
import shlex
import signal
import time
import os
import logging


LOG = logging.getLogger()
formatter = "%(asctime)s %(name)s %(levelname)s %(message)s"
logging.basicConfig(format=formatter,
                    filename="storage_auto_config.log",
                    filemode="a",
                    level=logging.DEBUG)
stream_log = logging.StreamHandler()
stream_log.setLevel(logging.DEBUG)
stream_log.setFormatter(logging.Formatter(formatter))
LOG.addHandler(stream_log)


def print_or_raise(msg, exc=None):
    if not exc:
        LOG.debug(msg)
    else:
        if isinstance(exc, Exception):
            LOG.error(msg)
            raise exc
        elif issubclass(exc, Exception):
            raise exc(msg)


class ScriptInnerError(Exception):
    def __init__(self, message=None):
        super(ScriptInnerError, self).__init__(message)


class UnknownArgumentError(Exception):
    def __init__(self, message=None):
        super(UnknownArgumentError, self).__init__(message)


class NoRootWrapSpecified(Exception):
    def __init__(self, message=None):
        super(NoRootWrapSpecified, self).__init__(message)


class ProcessExecutionError(Exception):
    def __init__(self, stdout=None, stderr=None, exit_code=None, cmd=None,
                 description=None):
        self.exit_code = exit_code
        self.stderr = stderr
        self.stdout = stdout
        self.cmd = cmd
        self.description = description

        if description is None:
            description = "Unexpected error while running command."
        if exit_code is None:
            exit_code = '-'
        message = ("%s\nCommand: %s\nExit code: %s\nStdout: %r\nStderr: %r"
                   % (description, cmd, exit_code, stdout, stderr))
        super(ProcessExecutionError, self).__init__(message)


def execute(cmd, **kwargs):
    """Helper method to shell out and execute a command through subprocess.

    Allows optional retry.s

    :param cmd:             Passed to subprocess.Popen.
    :type cmd:              string
    TODO:param process_input: Send to opened process.
    :type proces_input:     string
    TODO:param check_exit_code: Single bool, int, or list of allowed exit
                            codes.  Defaults to [0].  Raise
                            :class:`ProcessExecutionError` unless
                            program exits with one of these code.
    :type check_exit_code:  boolean, int, or [int]
    :param delay_on_retry:  True | False. Defaults to True. If set to True,
                            wait a short amount of time before retrying.
    :type delay_on_retry:   boolean
    :param attempts:        How many times to retry cmd.
    :type attempts:         int
    TODO:param run_as_root: True | False. Defaults to False. If set to True,
                            the command is prefixed by the command specified
                            in the root_helper kwarg.
    :type run_as_root:      boolean
    :param root_helper:     command to prefix to commands called with
                            run_as_root=True
    :type root_helper:      string
    TODO:param shell:           whether or not there should be a shell used to
                            execute this command. Defaults to false.
    :type shell:            boolean
    :param loglevel:        log level for execute commands.
    :type loglevel:         int.  (Should be logging.DEBUG or logging.INFO)
    :returns:               (stdout, stderr) from process execution
    :raises:                :class:`UnknownArgumentError` on
                            receiving unknown arguments
    :raises:                :class:`ProcessExecutionError`
    """
    def _subprocess_setup():
        # Python installs a SIGPIPE handler by default.
        # This is usually not what non-Python subprocesses expect.
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    # stdin
    process_input = kwargs.pop('process_input', None)
    check_exit_code = kwargs.pop('check_exit_code', [0])
    ignore_exit_code = False
    delay_on_retry = kwargs.pop('delay_on_retry', True)
    attempts = kwargs.pop('attempts', 1)
    run_as_root = kwargs.pop('run_as_root', False)
    root_helper = kwargs.pop('root_helper', '')
    shell = kwargs.pop('shell', True)
    silent = kwargs.pop('silent', False)
    # loglevel = kwargs.pop('loglevel', logging.DEBUG)

    if isinstance(check_exit_code, bool):
        ignore_exit_code = not check_exit_code
        check_exit_code = [0]
    elif isinstance(check_exit_code, int):
        check_exit_code = [check_exit_code]

    if kwargs:
        raise UnknownArgumentError(
            'Got unknown keyword args to utils.execute: %r' % kwargs)

    if run_as_root and hasattr(os, 'geteuid') and os.geteuid() != 0:
        if not root_helper:
            raise NoRootWrapSpecified(
                message=('Command requested root, but did not specify a root '
                         'helper.'))
        cmd = shlex.split(root_helper) + list(cmd)

    while attempts > 0:
        attempts -= 1
        try:
            if not silent:
                print_or_raise('Running cmd (subprocess): %s' % cmd)

            # windows
            if os.name == 'nt':
                preexec_fn = None
                close_fds = False
            else:
                preexec_fn = _subprocess_setup
                close_fds = True

            obj = subprocess.Popen(cmd,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   close_fds=close_fds,
                                   preexec_fn=preexec_fn,
                                   shell=shell)

            if process_input is not None:
                result = obj.communicate(process_input)
            else:
                result = obj.communicate()
            obj.stdin.close()
            _returncode = obj.returncode
            if not silent:
                print_or_raise('Result was %s' % _returncode)
            if not ignore_exit_code and _returncode not in check_exit_code:
                (stdout, stderr) = result
                raise ProcessExecutionError(exit_code=_returncode,
                                            stdout=stdout,
                                            stderr=stderr,
                                            cmd=cmd)
                                            # cmd=sanitized_cmd)
            return result
        except ProcessExecutionError:
            if not attempts:
                raise
            else:
                if not silent:
                    print_or_raise('%r failed. Retrying.' % cmd)
                if delay_on_retry:
                    time.sleep(random.randint(20, 200) / 100.0)
        finally:
            time.sleep(0)


def get_available_data_ip(media_ips):
    unavailable_ip = []
    for media_ip in media_ips:
        try:
            execute("ping -c 1 -W 2 %s" % media_ip)
        except ProcessExecutionError:
            unavailable_ip.append(media_ip)
            continue
    return list(set(media_ips) - set(unavailable_ip)), unavailable_ip


def clear_host_iscsi_resource():
    out, err = execute("iscsiadm -m node", check_exit_code=[0, 21])
    if not out:
        return

    sd_ips_list = map(lambda x: x.split(":3260")[0], out.split("\n")[:-1])
    if not sd_ips_list:
        return

    valid_ips, invalid_ips = get_available_data_ip(sd_ips_list)
    clear_resource = ""
    for ip in invalid_ips:
        logout_session = "iscsiadm -m node -p %s -u;" % ip
        del_node = "iscsiadm -m node -p %s -o delete;" % ip
        # manual_startup = "iscsiadm -m node -p %s -o update -n node.startup "
        #                  "-v manual;" % ip
        clear_resource += (logout_session + del_node)
    execute(clear_resource, check_exit_code=[0, 21], silent=True)
    # _execute("multipath -F")


def config_computer():
    # remove exist iscsi resource
    clear_host_iscsi_resource()
    config_multipath()


def config_multipath():
    if os.path.exists("/etc/multipath.conf"):
        execute("echo y|mv /etc/multipath.conf /etc/multipath.conf.bak",
                check_exit_code=[0, 1])

    execute("cp -p base/multipath.conf /etc/")
    execute("systemctl enable multipathd.service;"
            "systemctl restart multipathd.service")
