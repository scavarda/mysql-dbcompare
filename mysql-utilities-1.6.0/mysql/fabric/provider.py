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
"""Define interfaces to register/unregister accounts to access cloud
providers.
"""
import logging

from mysql.fabric import (
    persistence as _persistence,
)

from mysql.fabric.providers import (
    get_provider_manager,
    get_provider_idx,
    get_provider_type,
)

_LOGGER = logging.getLogger(__name__)

_CREATE_PROVIDER = (
    "CREATE TABLE providers "
    "(provider_id VARCHAR(256) NOT NULL, "
    "type INT NOT NULL, "
    "username VARCHAR(100) NOT NULL, "
    "password VARCHAR(128) NOT NULL, "
    "url VARCHAR(256) NOT NULL, "
    "tenant VARCHAR(100) NOT NULL, "
    "default_image VARCHAR(256), "
    "default_flavor VARCHAR(256), "
    "CONSTRAINT pk_provider_id PRIMARY KEY (provider_id))"
)

_QUERY_PROVIDER = (
    "SELECT provider_id, type, username, password, url, tenant, "
    "default_image, default_flavor FROM providers WHERE provider_id = %s"
)

_QUERY_PROVIDERS = (
    "SELECT provider_id, type, username, password, url, tenant, "
    "default_image, default_flavor FROM providers"
)

_INSERT_PROVIDER = (
    "INSERT INTO providers(provider_id, type, username, password, url, tenant, "
    "default_image, default_flavor) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)"
)

_REMOVE_PROVIDER = (
    "DELETE from providers WHERE provider_id = %s "
)

class Provider(_persistence.Persistable):
    """Define a provider class which is responsible for registering/
    unregistering accounts to access cloud providers.

    A cloud provider, or simply a provider, is uniquely identified by
    a string indentifier and accessed through an access point or URL.
    To authenticate requests to the provider, a user and password are
    defined and mapped to a tenant account.

    It is also possible to define a default image and default virtual
    machine template, also known as flavor, to be used if the
    information is not provided when a machine is created.

    :param provider_id: Provider's Id.
    :rtype provider_id: string
    :param provider_type: Provider's type such as OpenStack, Amazon, etc.
    :rtype provider_type: string
    :param username: User name to access the provider.
    :param password: Password to access the provider.
    :param url: Provider's access point or address.
    :param tenant: Provider's tenant.
    :param default_image: Default image's name.
    :param default_flaovr: Default flavor's name.
    """
    def __init__(self, provider_id=None, provider_type=None, username=None,
                 password=None, url=None, tenant=None, default_image=None,
                 default_flavor=None, row=None):
        """Constructor for the Provider.
        """
        super(Provider, self).__init__()

        if row is not None:
            assert provider_id is None
            assert provider_type is None
            assert username is None
            assert password is None
            assert url is None
            assert tenant is None
            provider_id, provider_idx, username, password, url, tenant, \
                default_image, default_flavor = row
            provider_type = get_provider_type(provider_idx)

        assert provider_id is not None
        assert provider_type is not None
        assert username is not None
        assert password is not None
        assert url is not None
        assert tenant is not None

        self.__provider_id = provider_id
        self.__provider_idx = get_provider_idx(provider_type)
        self.__username = username
        self.__password = password
        self.__url = url
        self.__tenant = tenant
        self.__default_image = default_image
        self.__default_flavor = default_flavor

    def __eq__(self, other):
        """Two providers are equal if they have the same id.
        """
        return isinstance(other, Provider) and \
               self.__provider_id == other.provider_id

    def __hash__(self):
        """A provider is hashable through its id.
        """
        return hash(self.__provider_id)

    @property
    def provider_id(self):
        """Return the provider's id.
        """
        return self.__provider_id

    @property
    def provider_type(self):
        """Return the provider's type.
        """
        return get_provider_type(self.__provider_idx)

    @property
    def username(self):
        """Return the username's id.
        """
        return self.__username

    @property
    def password(self):
        """Return the provider's password.
        """
        return self.__password

    @property
    def url(self):
        """Return the provider's url.
        """
        return self.__url

    @property
    def tenant(self):
        """Return the provider's tenant.
        """
        return self.__tenant

    @property
    def default_image(self):
        """Return the provider's default image.
        """
        return self.__default_image

    @property
    def default_flavor(self):
        """Return the provider's defautl flavor.
        """
        return self.__default_flavor

    @staticmethod
    def create(persister=None):
        """Create the objects(tables) that will store the provier information
        into the state store.

        :param persister: Object to access the state store.
        :raises: DatabaseError If the table already exists.
        """
        persister.exec_stmt(_CREATE_PROVIDER)

    @staticmethod
    def fetch(provider_id, persister=None):
        """Return a provider object corresponding to the provider's id.

        :param provider_id: Id of the provider that will be returned.
        :param persister: Object to access the state store.
        :return: Provider that corresponds to the id or None if it does
                 not exist.
        """
        cur = persister.exec_stmt(_QUERY_PROVIDER,
            {"fetch" : False, "raw" : False, "params":(provider_id, )}
        )
        row = cur.fetchone()
        if row:
            return Provider(row=row)

    @staticmethod
    def providers(persister=None):
        """Return a set provider objects.

        :param persister: Object to access the state store.
        :return: Set of providers.
        """
        cur = persister.exec_stmt(_QUERY_PROVIDERS,
            {"fetch" : False, "raw" : False}
        )

        rows = cur.fetchall()
        for row in rows:
            yield Provider(row=row)

    @staticmethod
    def add(provider, persister=None):
        """Write a provider object into the state store.

        :param provider: A reference to a provider.
        :param persister: Object to access the state store.
        """
        persister.exec_stmt(_INSERT_PROVIDER,
            {"params": (
                provider.provider_id,
                get_provider_idx(provider.provider_type),
                provider.username,
                provider.password,
                provider.url,
                provider.tenant,
                provider.default_image,
                provider.default_flavor
              )
            }
        )

    @staticmethod
    def remove(provider, persister=None):
        """Remove a provider object from the state store.

        :param provider: A reference to a provider.
        :param persister: Object to access the state store.
        """
        persister.exec_stmt(
            _REMOVE_PROVIDER, {"params": (provider.provider_id, )}
        )

    def get_provider_manager(self):
        """Return a reference to the provider manager.
        """
        return get_provider_manager(self.provider_type)

    def as_dict(self):
        """Return the object as a dictionary.
        Note that the password is omitted from the output for
        security reasons.
        """
        dictionary = {
            "id" : self.__provider_id,
            "type" : get_provider_type(self.__provider_idx),
            "username" : self.__username,
            "url" : self.__url,
            "tenant" : self.__tenant,
            "default_image" : self.__default_image \
                if self.__default_image else "",
            "default_flavor" : self.__default_flavor \
                if self.__default_flavor else ""
        }
        return dictionary
