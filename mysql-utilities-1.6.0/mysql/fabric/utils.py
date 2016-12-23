#
# Copyright (c) 2013,2014, Oracle and/or its affiliates. All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#

"""Define features that can be used throughout the code.
"""

import os
import sys
import inspect
import ctypes
import re
import datetime
import uuid

TTL = 0
VERSION_TOKEN = 0
FABRIC_UUID = uuid.UUID('5ca1ab1e-a007-feed-f00d-cab3fe13249e')

class SingletonMeta(type):
    """Define a Singleton.
    This Singleton class can be used as follows::

      class MyClass(object):
        __metaclass__ = SingletonMeta
      ...
    """
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMeta, cls).__call__(*args,
                                                                     **kwargs)
        return cls._instances[cls]


class Singleton(object):
    """Define a Singleton.
    This Singleton class can be used as follows::

      class MyClass(Singleton):
      ...
    """
    __metaclass__ = SingletonMeta

def _do_fork():
    """Create a process.
    """
    try:
        if os.fork() > 0:
            sys.exit(0)
    except OSError, error:
        sys.stderr.write("fork failed with errno %d: %s\n" %
                         (error.errno, error.strerror))
        sys.exit(1)

def daemonize(stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
    """Standard procedure for daemonizing a process.

    This process daemonizes the current process and put it in the
    background. When daemonized, logs are written to syslog.

    [1] Python Cookbook by Martelli, Ravenscropt, and Ascher.
    """
    _do_fork()
    os.chdir("/")        # The current directory might be removed.
    os.umask(0)
    os.setsid()
    _do_fork()
    sys.stdout.flush()
    sys.stderr.flush()
    sin = file(stdin, 'r')
    sout = file(stdout, 'a+')
    serr = file(stderr, 'a+', 0)
    os.dup2(sin.fileno(), sys.stdin.fileno())
    os.dup2(sout.fileno(), sys.stdout.fileno())
    os.dup2(serr.fileno(), sys.stdin.fileno())


def async_raise(tid, exctype):
    """Raise an exception within the context of a thread.

    :param tid: Thread Id.
    :param exctype: Exception class.
    :raises: exctype.
    """
    if not inspect.isclass(exctype):
        raise TypeError("Only types can be raised (not instances).")

    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(tid), ctypes.py_object(exctype)
        )

    if res == 0:
        raise ValueError("Invalid thread id.")
    elif res != 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid), None)
        raise SystemError("Failed to throw an exception.")

def split_dump_pattern(pattern):
    """Split a comma separated string of patterns, into a list of patterns.

    :param pattern: A comma separated string of patterns.
    """
    regex = re.compile('\s*,\s*')
    return regex.split(pattern)

def split_database_table(fully_qualified_table_name):
    """Split a fully qualified table name, which is the database name
    followed by the table name (database_name.table_name).

    :param fully_qualified_table_name: The fully qualified table name.
    """
    return fully_qualified_table_name.split('.')

def wrap_output(output):
    """Used to wrap the the output in a standard format:
    (FABRIC_UUID, VERSION_TOKEN, TTL).

    :param output: The output that needs to be wrapped.
    :return: the "output" parameter is returned in the following four
             tuple format.
    """
    return (FABRIC_UUID, VERSION_TOKEN, TTL, output)

def get_time():
    """Get current time using datetime.utcnow().
    """
    return datetime.datetime.utcnow().replace(microsecond=0)

def get_time_delta(delta):
    """Transform a value provided through the parameter delta into a
    timedelta object.

    :param delta: Delta value in seconds.
    """
    return datetime.timedelta(seconds=delta)

def get_time_from_timestamp(timestamp):
    """Return a utc time from a timestemp().
    """
    return datetime.datetime.utcfromtimestamp(timestamp).replace(microsecond=0)

def get_group_lower_bound_list(input_string):
    """Get the list of GROUP IDs and the LBs from the input string.

    :param input_string: String input by the user containing delimited
                         group ids and LBs.
    """
    group_id_list = []
    lower_bound_list = []
    group_id_lower_bound_list = input_string.replace(' ', '').split(",")
    for item in group_id_lower_bound_list:
        group_id = None
        lower_bound = None
        if item.find("/") != -1:
            group_id, lower_bound = item.split("/")
        else:
            group_id = item
        if group_id is not None:
            group_id_list.append(group_id)
        if lower_bound is not None:
            lower_bound_list.append(lower_bound)
    return group_id_list, lower_bound_list

def dequote(value):
    """Removes single, double or backtick quotes around the value.

    If the value is  "spam", spam without quotes will be returned. Similar
    with single and backtick quotes. If quotes do not match, or the first
    character is not single, double or backtick, the value is returned
    unchanged.

    If value is not a string, the value is simply returned.

    :param value: A string.
    :return: A string with quotes removed.
    """
    if not isinstance(value, basestring):
        return value

    if value[0] in '\'"`' and value[-1] == value[0]:
        return value[1:-1]
    return value

def check_number_threads(increasing=0):
    """Check the number of threads that are running and whether the maximum
    number of connections in the state store is configured accordingly.

    :param increasing: Whether you want to increase the number of threads and
                       how many threads. Default is zero.

    It raises a ConfigurationError exception if the number of connections is
    too small.
    """
    from mysql.fabric import (
        errors as _errors,
        executor as _executor,
        persistence as _persistence,
        services as _services,
        server as _server,
    )

    n_sessions = _services.ServiceManager().get_number_sessions()
    n_executors = _executor.Executor().get_number_executors()
    n_failure_detectors = len(_server.Group.groups_by_status(_server.Group.ACTIVE))
    n_controls = 1
    persister = _persistence.current_persister()
    max_allowed_connections = persister.max_allowed_connections()
    if (n_sessions +  n_executors + n_controls + n_failure_detectors +\
        increasing) > (max_allowed_connections - 1):
        raise _errors.ConfigurationError(
            "Too many threads requested. Session threads (%s), Executor "
            "threads (%s), Control threads (%s) and Failure Detector threads "
            "(%s). The maximum number of threads allowed is (%s). Increase "
            "the maximum number of connections in the state store in order "
            "to increase this limit." % (n_sessions, n_executors, n_controls,
            n_failure_detectors, max_allowed_connections - 1)
         )
