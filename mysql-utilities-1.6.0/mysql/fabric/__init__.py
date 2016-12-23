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
"""MySQL Fabric library
"""
import os

# Version info as a tuple (major, minor, patch, extra)
__version_info__ = (1, 5, 2, "")

# MySQL Fabric version:
# `PEP-386 <http://www.python.org/dev/peps/pep-0386>`__ format
__version__ = "{0}.{1}.{2}{3}".format(*__version_info__)

# Connector Python version info as a tuple (major, minor, patch, extra)
__cpy_version_info__ = (2, 0, 0, "")

# Connector Python version:
# `PEP-386 <http://www.python.org/dev/peps/pep-0386>`__ format
__cpy_version__ = "{0}.{1}.{2}{3}".format(*__cpy_version_info__)

def check_connector():
    """Check if the connector is properly configured and
    has the required version.
    """
    from mysql.fabric.errors import (
        ConfigurationError
    )

    try:
        import mysql.connector as cpy
        if cpy.version.VERSION < __cpy_version_info__:
            path = os.path.dirname(cpy.__file__)
            raise ConfigurationError(
                "Looked for mysql.connector at ({path}). Connector has "
                "({cpy_ver}) version but ({required_ver}) or later version "
                "is required.".format(path=path, cpy_ver=cpy.version.VERSION,
                required_ver=__cpy_version_info__)
            )
    except ImportError as error:
        import mysql
        path = os.path.dirname(mysql.__file__)
        raise ConfigurationError(
            "Tried to look for mysql.connector at ({path}). Connector not "
            "installed. Error ({error}).".format(path=path, error=error)
        )
