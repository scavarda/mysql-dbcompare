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
"""This module provides the necessary means to interact with an OpenStack
provider and has the MachineManager class as the main entry point.
"""
import logging
import time
import functools
import uuid as _uuid
import json

try:
    from novaclient import client

    from novaclient.exceptions import (
        UnsupportedVersion,
        CommandError,
        AuthorizationFailure,
        NoUniqueMatch,
        AuthSystemNotFound,
        NoTokenLookupException,
        EndpointNotFound,
        AmbiguousEndpoints,
        ConnectionRefused,
        ClientException,
    )
except:
    pass

from mysql.fabric import (
    errors as _errors,
)

from mysql.fabric.providers import (
    AbstractMachineManager,
)

from mysql.fabric.machine import (
    Machine,
)

_LOGGER = logging.getLogger(__name__)

SEARCH_PROPERTIES = {
    'mindisk' : ('minDisk', int),
    'minram' : ('minRam', int),
    'ram' : ('ram', int),
    'vcpus' : ('vcpus', int),
    'swap' : ('swap', int),
    'disk' : ('disk', int),
    'rxtx_factor' : ('rxtx_factor', float),
}

def preprocess_meta(meta):
    """Preprocess parameters that will be used to search for resources in
    the cloud.

    This is necessary because the parameters are strings and some of them
    need to be converted to integers or floats. Besides the parameter names
    are case sensitive and must be changed.
    """
    proc_meta = {}
    for key, value in meta.iteritems():
        key = key.lower()
        if key in SEARCH_PROPERTIES:
            key, convert = SEARCH_PROPERTIES[key]
            try:
                value = convert(value)
            except ValueError as error:
                raise _errors.MachineError(error)
        proc_meta[key] = value
    return proc_meta

def find_resource(meta, finder):
    """Find a resource based on some meta information.
    """
    proc_meta = preprocess_meta(meta)
    resources = finder(**proc_meta)
    if not resources:
        raise _errors.ConfigurationError(
            "There is no image with the requested properties: %s" %
            (proc_meta, )
        )
    elif len(resources) > 1:
        _LOGGER.warning(
            "There are more than one image with the requested properties: "
            "(%s). Using (%s).", proc_meta, resources[0]
        )
    _LOGGER.info("Using resource (%s).", resources[0])
    return resources[0]

def catch_exception(function):
    """Catch exception and throw an MachineError.
    """
    @functools.wraps(function)
    def wrapper_catch_exception(*args, **kwargs):
        """Wrapper to catch OpenStack exceptions.
        """
        try:
            return function(*args, **kwargs)
        except (UnsupportedVersion, CommandError, AuthorizationFailure,
                NoUniqueMatch, AuthSystemNotFound, NoTokenLookupException,
                EndpointNotFound, AmbiguousEndpoints, ConnectionRefused,
                ClientException) as error:
            raise _errors.MachineError(error)
    return wrapper_catch_exception

def keep_waiting(obj, get_info, status):
    """Keep pooling until the status changes.
    Note that this function does not fetch detailed information when there
    is an error and this needs to be improved.
    """
    while obj.status in status:
        time.sleep(5)
        obj = get_info(obj.id)
    if obj.status != 'ACTIVE':
        raise _errors.MachineError(
            "Unexpected status (%s) when valid statuses were (%s). "
            "Error creating resource (%)." % (obj.status, status, str(obj.id))
        )

def configure_provider():
    """Configure the OpenStack Provider.
    """
    import novaclient.client
    return ("OPENSTACK", MachineManager, 2)

class MachineManager(AbstractMachineManager):
    """Manage an Openstack Machine.

    Note that SSL is not supported yet and this needs to be improved.
    """
    @catch_exception
    def __init__(self, provider, version="1.1"):
        """Constructor for MachineManager object.
        """
        super(MachineManager, self).__init__(provider, version)
        credentials = {
            'username' : self.provider.username,
            'api_key' : self.provider.password,
            'auth_url' : self.provider.url,
            'project_id' : self.provider.tenant
        }
        self.__cs = client.Client(self.version, **credentials)

    @catch_exception
    def create_machines(self, parameters, wait_spawning):
        """Create an Openstack Machine.
        """
        # Make a copy of the parameters as it will be changed.
        parameters = parameters.copy()

        # Retrieve image's reference.
        parameters['image'] = \
           find_resource(parameters['image'], self.__cs.images.findall)

        # Retrieve flavor's reference.
        parameters['flavor'] = \
           find_resource(parameters['flavor'], self.__cs.flavors.findall)

        # Retrieve network information using private_network and
        # public_network paramaters.
        public_network = None
        if parameters['private_network']:
            nics = []
            nic = self.__cs.networks.find(label=parameters['private_network'])
            nics.append({'net-id' : nic.id})
            parameters['nics'] = nics
        if parameters['public_network']:
            public_network = parameters['public_network']
        del parameters['private_network']
        del parameters['public_network']
        del parameters['private_nics']
        del parameters['public_nics']

        # Set the config_drive parameter so that the cloud-init can run.
        parameters['config_drive'] = True

        # Make sure that a resource object is returned.
        parameters['return_raw'] = False

        # Create machines.
        machines = []
        number_machines = parameters['number_machines']
        del parameters['number_machines']
        for n_machine in range(number_machines):
            name = str(_uuid.uuid4())
            machine = self.__cs.servers.create(name=name, **parameters)
            machines.append(machine)

        # Wait until the machine is alive and kicking.
        if wait_spawning:
            for machine in machines:
                keep_waiting(
                    machine, self.__cs.servers.get, ('QUEUED', 'BUILD')
                )

        ret = []
        for machine in machines:
            if public_network:
                self.assign_public_ip(machine, public_network)
            machine = self.__cs.servers.get(machine.id)
            ret.append(self.format_machine(machine))

        return ret

    @catch_exception
    def search_machines(self, generic_filters, meta_filters):
        """Return machines based on the provided filters.
        """
        _LOGGER.debug(
            "Searching for machines using generic filters (%s) and "
            "meta filters (%s).", generic_filters, meta_filters
        )

        match = []
        for machine in self.__cs.servers.findall(**generic_filters):
            checked = []
            for key, value in machine.metadata.iteritems():
                if key in meta_filters:
                    checked.append(meta_filters[key] == value)
            if checked and all(checked):
                match.append(machine)

        _LOGGER.debug("Found machines (%s).", match)

        ret = []
        for machine in match:
            ret.append(self.format_machine(machine))
        return ret

    @catch_exception
    def get_machine(self, machine_uuid):
        """Return a reference to an OpenStack Machine.
        """
        return self.__cs.servers.get(machine_uuid)

    @catch_exception
    def destroy_machine(self, machine_uuid):
        """Destroy an OpenStack Machine.
        """
        machine = self.get_machine(machine_uuid)
        self.remove_public_ip(machine)
        self.destroy_snapshot(machine_uuid)
        machine.delete()

    @catch_exception
    def assign_public_ip(self, machine, pool):
        """Assign a public IP address to an OpenStack Machine.
        """
        floating_ip = self.__cs.floating_ips.create(pool=pool)
        machine.add_floating_ip(floating_ip)
        _LOGGER.info(
            "Associated elastic ip (%s) to machine (%s).", floating_ip.ip,
            str(machine.id)
        )
        return floating_ip.ip

    @catch_exception
    def remove_public_ip(self, machine):
        """Remove all public IP addresses from an OpenStack Machine.
        """
        floating_ips = \
            self.__cs.floating_ips.findall(**{'instance_id' : machine.id})
        for floating_ip in floating_ips:
            machine.remove_floating_ip(floating_ip)
            floating_ip.delete()

    @catch_exception
    def create_snapshot(self, machine_uuid, wait_spawning):
        """Create a snapshot from an OpenStack Machine
.
        """
        machine = self.__cs.servers.get(machine_uuid)
        snapshot_name = "-".join(["snapshot", machine_uuid, str(time.time())])
        snapshot_id = machine.create_image(snapshot_name)
        if wait_spawning:
            image = self.__cs.images.get(snapshot_id)
            keep_waiting(image, self.__cs.images.get, ('QUEUED', 'SAVING'))
        return snapshot_name

    @catch_exception
    def destroy_snapshot(self, machine_uuid):
        """Destroy a snapshot associated to an OpenStack Machine.
        """
        images = self.__cs.images.list()
        snapshot_name = "-".join(["snapshot", machine_uuid])
        for image in images:
            if snapshot_name in image.name:
                image.delete()

    def format_machine(self, machine):
        """Format machine data.

        :param machine: Reference to a machine.
        """
        addresses = json.dumps(machine.networks)

        av_host = "-"
        try:
            av_host = getattr(machine, "OS-EXT-SRV-ATTR:hypervisor_hostname")
        except AttributeError:
            pass

        av_zone = "-"
        try:
            av_zone = getattr(machine, "OS-EXT-AZ:availability_zone")
        except AttributeError:
            pass

        new = Machine(uuid=_uuid.UUID(machine.id),
            provider_id=self.provider.provider_id,
            av_zone=":".join([av_zone, av_host]),
            addresses=addresses
        )
        return new
