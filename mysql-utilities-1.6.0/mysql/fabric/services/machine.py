#
# Copyright (c) 2014 Oracle and/or its affiliates. All rights reserved.
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
"""Provide the necessary interface to manage virtual machine instances.
"""
import logging
import uuid as _uuid

from mysql.fabric.command import (
    ProcedureCommand,
    Command,
    ResultSet,
    CommandResult,
)

from mysql.fabric import (
    events as _events,
    errors as _errors,
)

from mysql.fabric.machine import (
    Machine,
)

from mysql.fabric.services.provider import (
    _retrieve_provider,
)

from mysql.fabric.node import (
    FabricNode,
)

_LOGGER = logging.getLogger(__name__)

reserved_meta = (
    'mysql-fabric', 'mysql-fabric-version', 'mysql-fabric-uuid',
    'mysql-fabric-group', 'mysql-fabric-machine-group-uuid'
)

CREATE_INSTANCE = _events.Event()
class CreateMachine(ProcedureCommand):
    """Create a virtual machine instance:

        mysqlfabric machine create provider --image name=image-mysql \
        --flavor name=vm-template --meta db=mysql --meta version=5.6

        mysqlfabric machine create provider --image name=image-mysql \
        --flavor name=vm-template --security_groups grp_fabric, grp_ham

    Options that accept a list are defined by providing the same option
    multiple times in the command-line. The image, flavor, files, meta
    and scheduler_hints are those which might be defined multiple times.
    Note the the security_groups option might be defined only once but
    it accept a string with a list of security groups.
    """
    group_name = "machine"
    command_name = "create"

    def execute(self, provider_id, image=None, flavor=None,
        number_machines=1, availability_zone=None, key_name=None,
        security_groups=None, private_network=None, public_network=None,
        userdata=None, swap=None, scheduler_hints=None, meta=None,
        skip_store=False, wait_spawning=True, synchronous=True):
        """Create a machine.

        :param provider_id: Provider's Id.
        :param image: Image's properties (e.g. name=image-mysql).
        :rtype image: list of key/value pairs
        :param flavor: Flavor's properties (e.g. name=vm-template).
        :rtype flavor: list of key/value pairs
        :param number_machines: Number of machines to be created.
        :rtype number_machines: integer
        :param availability_zone: Name of availability zone.
        :rtype availability_zone: string
        :param key_name: Name of the key previously created.
        :rtype key_name: string
        :param security_groups: Security groups to have access to the
                                machine(s).
        :rtype security_groups: string with a list of security groups
        :param private_network: Name of the private network where the
                                machine(s) will be placed to.
        :rtype key_name: string
        :param public_network: Name of the public network which will provide
                               a public address.
        :rtype key_name: string
        :param userdata: Script that to be used to configure the machine(s).
        :rtype userdata: path to a file
        :param swap: Size of the swap space in megabyte.
        :rtype swap: integer
        :param scheduler_hints: Information on which host(s) the machine(s) will
                                be created in.
        :rtype scheduler_hints: list of key/value pairs
        :param meta: Metadata on the machine(s).
        :rtype meta: list of key/value pairs
        :param skip_store: Do not store information on machine(s) into the
                           state store. Default is False.
        :param wait_spwaning: Whether one should wait until the provider
                              finishes its task or not.
        :param synchronous: Whether one should wait until the execution finishes
                            or not.
        """
        parameters = {
            'image' : image,
            'flavor' : flavor,
            'number_machines' : number_machines,
            'availability_zone' : availability_zone,
            'key_name' : key_name,
            'security_groups' : security_groups,
            'private_network' : private_network,
            'public_network' : public_network,
            'userdata' : userdata,
            'swap' : swap,
            'block_device' : None,
            'scheduler_hints' : scheduler_hints,
            'private_nics' : None,
            'public_nics' : None,
            'meta' : meta
        }
        machine_group_uuid = str(_uuid.uuid4())
        procedures = _events.trigger(
            CREATE_INSTANCE, self.get_lockable_objects(), provider_id,
            parameters, machine_group_uuid, skip_store, wait_spawning
        )
        return self.wait_for_procedures(procedures, synchronous)

    def generate_options(self):
        """Make some options accept multiple values.
        """
        super(CreateMachine, self).generate_options()
        options = ["image", "flavor", "files", "meta", "scheduler_hints"]
        for option in self.command_options:
            if option['dest'] in options:
                option['action'] = "append"

DESTROY_INSTANCE = _events.Event()
class MachineDestroy(ProcedureCommand):
    """Destroy a virtual machine instance.
    """
    group_name = "machine"
    command_name = "destroy"

    def execute(self, provider_id, machine_uuid, force=False,
                skip_store=False, synchronous=True):
        """Destroy a machine.

        :param provider_id: Provider's Id.
        :param machine_uuid: Machine's uuid.
        :param force: Ignore errors while accessing the cloud provider.
        :param skip_store: Proceed anyway if there is no information on
                           the machine in the state store. Default is False.
        :param synchronous: Whether one should wait until the execution finishes
                            or not.
        :return: Tuple with job's uuid and status.
        """
        procedures = _events.trigger(
            DESTROY_INSTANCE, self.get_lockable_objects(), provider_id,
            machine_uuid, force, skip_store
        )
        return self.wait_for_procedures(procedures, synchronous)

class MachineLookup(Command):
    """Return information on existing machine(s) created by a provider.
    """
    group_name = "machine"
    command_name = "list"

    def execute(self, provider_id, generic_filters=None, meta_filters=None,
                skip_store=False):
        """Return information on existing machine(s).

        :param provider_id: Provider's Id.
        :param generic_filters: Filter returned machines by some properites
                                but metadata properties.
        :param meta_filters: Filter returned machines by metadata properties.
        :param skip_store: Proceed anyway if there is no information on
                           the machine in the state store. Default is False.
        """
        rset = ResultSet(
            names=('uuid', 'provider_id', 'av_zone', 'addresses'),
            types=(str, str, str, str)
        )

        if not skip_store:
            if generic_filters or meta_filters:
                raise _errors.ConfigurationError(
                    "Filters are only supported when the 'skip_store' option "
                    "is set."
                )
            provider = _retrieve_provider(provider_id)
            for mc in Machine.machines(provider.provider_id):
                rset.append_row(
                    (str(mc.uuid), mc.provider_id, mc.av_zone, mc.addresses)
                )
        else:
            generic_filters, meta_filters = \
                _preprocess_filters(generic_filters, meta_filters)
            manager = _retrieve_manager(provider_id)
            for mc in manager.search_machines(generic_filters, meta_filters):
                rset.append_row(
                    (str(mc.uuid), mc.provider_id, mc.av_zone, mc.addresses)
                )

        return CommandResult(None, results=rset)

    def generate_options(self):
        """Make some options accept multiple values.
        """
        super(MachineLookup, self).generate_options()
        options = ["generic_filters", "meta_filters"]
        for option in self.command_options:
            if option['dest'] in options:
                option['action'] = "append"


CREATE_SNAPSHOT = _events.Event()
class SnapshotCreate(ProcedureCommand):
    """Create a snapshot image from a machine.
    """
    group_name = "snapshot"
    command_name = "create"

    def execute(self, provider_id, machine_uuid, skip_store=False,
                wait_spawning=True, synchronous=True):
        """Create a snapshot image from a machine.

        :param provider_id: Provider's Id.
        :param machine_uuid: Machine's uuid.
        :param skip_store: Proceed anyway if there is no information on
                           the machine in the state store. Default is False.
        :param wait_spwaning: Whether one should wait until the provider
                              finishes its task or not.
        :param synchronous: Whether one should wait until the execution finishes
                            or not.
        :return: Tuple with job's uuid and status.
        """
        procedures = _events.trigger(
            CREATE_SNAPSHOT, self.get_lockable_objects(), provider_id,
            machine_uuid, skip_store, wait_spawning
        )
        return self.wait_for_procedures(procedures, synchronous)

DESTROY_SNAPSHOT = _events.Event()
class SnapshotDestroy(ProcedureCommand):
    """Destroy snapshot images associated to a machine.
    """
    group_name = "snapshot"
    command_name = "destroy"

    def execute(self, provider_id, machine_uuid, skip_store=False,
                synchronous=True):
        """Destroy snapshot images associated to a machine.

        :param provider_id: Provider's Id.
        :param machine_uuid: Machine's uuid.
        :param skip_store: Proceed anyway if there is no information on
                           the machine in the state store. Default is False.
        :param wait_spwaning: Whether one should wait until the provider
                              finishes its task or not.
        :param synchronous: Whether one should wait until the execution finishes
                            or not.
        :return: Tuple with job's uuid and status.
        """
        procedures = _events.trigger(
            DESTROY_SNAPSHOT, self.get_lockable_objects(), provider_id,
            machine_uuid, skip_store
        )
        return self.wait_for_procedures(procedures, synchronous)

@_events.on_event(CREATE_INSTANCE)
def _create_machine(provider_id, parameters, machine_group_uuid,
                     skip_store, wait_spawning):
    """Create a machine.
    """
    manager = _retrieve_manager(provider_id)

    _preprocess_paramaters(parameters, machine_group_uuid, manager.provider)
    machines = manager.create_machines(parameters, wait_spawning)

    _LOGGER.debug("Created machine(s) (%s).", machines)

    if not skip_store:
        for machine in machines:
            Machine.add(machine)

    return [machine.as_dict() for machine in machines]

@_create_machine.undo
def _undo_create_machine(provider_id, parameters, machine_group_uuid,
                          skip_store, wait_spawning):
    """Remove machines already created if there is an error.
    """
    generic_filters = {}
    meta_filters = {
        'mysql-fabric-machine-group-uuid' : machine_group_uuid
    }
    manager = _retrieve_manager(provider_id)
    for machine in manager.search_machines(generic_filters, meta_filters):
        manager.destroy_machine(str(machine.uuid))

@_events.on_event(DESTROY_INSTANCE)
def _destroy_machine(provider_id, machine_uuid, force, skip_store):
    """Destroy a machine.
    """
    machine = _retrieve_machine(provider_id, machine_uuid, skip_store)
    if machine:
        Machine.remove(machine)
    manager = _retrieve_manager(provider_id)
    try:
        manager.destroy_machine(machine_uuid)
    except _errors.MachineError:
        if not force:
            raise

    _LOGGER.debug("Destroyed machine (%s).", machine)

@_events.on_event(CREATE_SNAPSHOT)
def _create_snapshot(provider_id, machine_uuid, skip_store, wait_spawning):
    """Create a snapshot.
    """
    _retrieve_machine(provider_id, machine_uuid, skip_store)
    manager = _retrieve_manager(provider_id)
    return manager.create_snapshot(machine_uuid, wait_spawning)

@_events.on_event(DESTROY_SNAPSHOT)
def _destroy_snapshot(provider_id, machine_uuid, skip_store):
    """Destroy a snapshot.
    """
    _retrieve_machine(provider_id, machine_uuid, skip_store)
    manager = _retrieve_manager(provider_id)
    return manager.destroy_snapshot(machine_uuid)

def _retrieve_machine(provider_id, machine_uuid, skip_store):
    """Return a machine object from an id.
    """
    machine = Machine.fetch(machine_uuid)

    if not machine and not skip_store:
        raise _errors.MachineError(
            "Machine (%s) does not exist." % (machine_uuid, )
        )

    if machine and machine.provider_id != provider_id:
        raise _errors.MachineError(
            "Machine (%s) does not belong to provider (%s)." %
            (machine_uuid, provider_id)
        )

    return machine

def _retrieve_manager(provider_id):
    """Retrive the manager for a provider.
    """
    provider = _retrieve_provider(provider_id)
    MachineManager = provider.get_provider_manager()
    return MachineManager(provider)

def _kv_to_dict(meta):
    """Transform a list with key/value strings into a dictionary.
    """
    try:
        return dict(m.split("=", 1) for m in meta)
    except ValueError:
        raise _errors.MachineError("Invalid parameter (%s)." % (meta, ))

def _preprocess_paramaters(parameters, machine_group_uuid, provider):
    """Process paramaters.
    """
    # 1. Put image parameter in the appropriate format.
    if parameters['image']:
        parameters['image'] = _kv_to_dict(parameters['image'])
    elif provider.default_image:
        parameters['image'] = { 'name' : provider.default_image }
    if not parameters['image']:
        raise _errors.MachineError("No valid image hasn't been found.")

    # 2. Put flavor parameter in the appropriate format.
    if parameters['flavor']:
       parameters['flavor'] = _kv_to_dict(parameters['flavor'])
    elif provider.default_flavor:
       parameters['flavor'] = { 'name' : provider.default_flavor }
    if not parameters['flavor']:
        raise _errors.MachineError("No valid flavor hasn't been found.")

    # 3. Check the parameter number_machines.
    number_machines = parameters['number_machines']
    try:
        number_machines = int(number_machines)
        parameters['number_machines'] = number_machines
    except TypeError:
        number_machines = 1
        parameters['number_machines'] = number_machines
    if number_machines <= 0:
        raise _errors.MachineError(
            "Number of machines must be greater than zero (%s)." %
            (number_machines, )
        )

    # 4. We don't need to check the availability_zone parameter

    # 5. We don't need to check the parameter key_name parameter.

    # 6. Put the security_groups parameter in the appropriate format.
    if parameters['security_groups']:
        security_groups = parameters['security_groups'].split(',')
        parameters['security_groups'] = security_groups

    # 7. Check the private_newtwork parameter.
    private_nics = parameters['private_nics']
    private_network = parameters['private_network']
    if private_network and private_nics:
        raise _errors.ConfigurationError(
            "Can't define both private_network (%s) and private_nics "
            "parameters (%s)." % (private_network, private_nics)
        )

    # 8. Check the public_newtwork parameter.
    public_nics = parameters['public_nics']
    public_network = parameters['public_network']
    if public_network and public_nics:
        raise _errors.ConfigurationError(
            "Can't define both public_network (%s) and public_nics "
            "parameters (%s)." % (public_network, public_nics)
        )

    # 9. Read userdata parameter which must be a path to a file.
    if parameters['userdata']:
        try:
            src = parameters['userdata']
            userdata = open(src)
        except IOError as error:
            raise _errors.ConfigurationError(
                "Can't open '%(src)s': %(exc)s" % {'src': src, 'exc': error}
            )
        parameters['userdata'] = userdata

    # 10. We don't need to check the swap parameter

    # 11. Put the block_device parameter in the appropriate format.
    if parameters['block_device']:
        raise _errors.ConfigurationError(
            "Parameter block_device is not supported yet."
        )

    # 12. Put the scheduler_hints parameter in the appropriate format.
    if parameters['scheduler_hints']:
        parameters['scheduler_hints'] = \
            _kv_to_dict(parameters['scheduler_hints'])

    # 13. Put the private_nics parameter in the appropriate format.
    if parameters['private_nics']:
        raise _errors.ConfigurationError(
            "Parameter private_nics is not supported yet."
        )

    # 14. Put the public_nics parameter in the appropriate format.
    if parameters['public_nics']:
        raise _errors.ConfigurationError(
            "Parameter public_nics is not supported yet."
        )

    # 15. Put meta parameter in the appropriate format.
    reserved_value = (
        'True', str(FabricNode().version), str(FabricNode().uuid),
        str(FabricNode().group_uuid), machine_group_uuid
    )
    assert len(reserved_meta) == len(reserved_value)
    if parameters['meta']:
        parameters['meta'] = _kv_to_dict(parameters['meta'])
        if any([key in reserved_meta for key in parameters['meta'].iterkeys()]):
            raise _errors.ConfigurationError(
                "The meta parameter cannot have key words in the following "
                "list: %s. They are reserved for internal use." %
                (str(reserved_meta), )
            )
    else:
        parameters['meta'] = {}

    meta = dict(zip(reserved_meta, reserved_value))
    parameters['meta'].update(meta)

def _preprocess_filters(generic_filters, meta_filters):
    """Process filters.
    """
    if generic_filters:
        generic_filters = _kv_to_dict(generic_filters)
    else:
        generic_filters = {}

    if meta_filters:
        meta_filters = _kv_to_dict(meta_filters)
    else:
        meta_filters = {}

    for filters in (generic_filters, meta_filters):
        if any([key in reserved_meta for key in filters.iterkeys()]):
            raise _errors.ConfigurationError(
                "The filters option cannot have key words in the following "
                "list: %s. They are reserved for internal use." %
                (str(reserved_meta), )
            )

    meta_filters['mysql-fabric-group'] = str(FabricNode().group_uuid)

    return generic_filters, meta_filters
