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

"""Command interface for working with events and procedures. It provides the
necessary means to trigger an event, to get details on a procedure and wait
until procedures finish their execution.
"""
import uuid as _uuid

from mysql.fabric import (
    events as _events,
    executor as _executor,
    errors as _errors,
)

from mysql.fabric.command import (
    Command,
    CommandResult,
    ResultSet,
)

class Trigger(Command):
    """Trigger an event.
    """
    group_name = "event"
    command_name = "trigger"

    def execute(self, event, locks, *args, **kwargs):
        """Trigger the execution of an event.

        :param event: Event's identification.
        :type event: String
        :param args: Event's non-keyworded arguments.
        :param kwargs: Event's keyworded arguments.

        :return: :class:`CommandResult` instance with UUID of the
                 procedures that were triggered.

        """

        lockable_objects = set()
        for lock in locks.split(","):
            lockable_objects.add(lock.strip())

        rset = ResultSet(names=['uuid'], types=[str])

        # Trigger the event and add the UUID of all procedures queued
        # to the result.
        for proc in _events.trigger(event, lockable_objects, *args, **kwargs):
            rset.append_row([str(proc.uuid)])

        return CommandResult(None, results=rset)

class WaitForProcedures(Command):
    """Wait until procedures, which are identified through their uuid in a
    list and separated by comma, finish their execution. If a procedure is
    not found an error is returned.
    """
    group_name = "event"
    command_name = "wait_for_procedures"

    def execute(self, proc_uuids):
        """Wait until a set of procedures uniquely identified by their uuids
        finish their execution.

        However, before starting waiting, the function checks if the procedures
        exist. If one of the procedures is not found, the following exception
        is raised :class:`~mysql.fabric.errors.ProcedureError`.

        :param proc_uuids: Iterable with procedures' uuids.
        """
        procs = []
        it_proc_uuids = proc_uuids.split(",")
        for proc_uuid in it_proc_uuids:
            proc_uuid = _uuid.UUID(proc_uuid.strip())
            procedure = _executor.Executor().get_procedure(proc_uuid)
            if not procedure:
                raise _errors.ProcedureError("Procedure (%s) was not found." %
                                             (proc_uuid, ))
            procs.append(procedure)

        for procedure in procs:
            procedure.wait()

        return CommandResult(None)
