#!/usr/bin/env python
#
# Copyright (c) 2011, 2014, Oracle and/or its affiliates. All rights reserved.
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

"""
This file contains the operations to perform database consistency checking
on two databases.
"""

from mysql.utilities.common.tools import check_python_version

# Check Python version compatibility
check_python_version()

import os
import re
import sys

from mysql.utilities.exception import UtilError, FormatError
from mysql.utilities.command.dbcompare import database_compare
from mysql.utilities.common.ip_parser import parse_connection
from mysql.utilities.common.dbcompare import DEFAULT_SPAN_KEY_SIZE
from mysql.utilities.common.pattern_matching import REGEXP_OBJ_NAME
from mysql.utilities.common.tools import check_connector_python
from mysql.utilities.common.messages import (PARSE_ERR_DB_PAIR,
                                             PARSE_ERR_DB_PAIR_EXT,
                                             PARSE_ERR_DB_MISSING_CMP,
                                             PARSE_ERR_SPAN_KEY_SIZE_TOO_LOW)
from mysql.utilities.common.options import (add_difftype, add_verbosity,
                                            check_verbosity,
                                            add_changes_for, add_reverse,
                                            add_format_option,
                                            add_character_set_option,
                                            add_ssl_options, get_ssl_dict,
                                            setup_common_options,
                                            check_password_security)
from mysql.utilities.common.sql_transform import (is_quoted_with_backticks,
                                                  remove_backtick_quoting,
                                                  quote_with_backticks)


# Constants
NAME = "MySQL Utilities - mysqldbcompare "
DESCRIPTION = "mysqldbcompare - compare databases for consistency"
USAGE = "%prog --server1=user:pass@host:port:socket " + \
        "--server2=user:pass@host:port:socket db1:db2"
PRINT_WIDTH = 75

# Check for connector/python
if not check_connector_python():
    sys.exit(1)

if __name__ == '__main__':
    # Setup the command parser
    parser = setup_common_options(os.path.basename(sys.argv[0]),
                                  DESCRIPTION, USAGE, server=False)

    # Connection information for the source server
    parser.add_option("--server1", action="store", dest="server1",
                      type="string", default="root@localhost:3306",
                      help="connection information for first server in "
                           "the form: <user>[:<password>]@<host>[:<port>]"
                           "[:<socket>] or <login-path>[:<port>][:<socket>].")

    # Connection information for the destination server
    parser.add_option("--server2", action="store", dest="server2",
                      type="string", default=None,
                      help="connection information for second server in "
                           "the form: <user>[:<password>]@<host>[:<port>]"
                           "[:<socket>] or <login-path>[:<port>][:<socket>].")

    # Add character set option
    add_character_set_option(parser)

    # Output format
    add_format_option(parser, "display the output in either grid (default), "
                              "tab, csv, or vertical format", "grid")

    # Add skips
    parser.add_option("--skip-checksum-table", action="store_true",
                      dest="no_checksum_table",
                      help="skip CHECKSUM TABLE step in data consistency "
                           "check.")

    parser.add_option("--skip-object-compare", action="store_true",
                      dest="no_object_check",
                      help="skip object comparison step.")

    parser.add_option("--skip-row-count", action="store_true",
                      dest="no_row_count",
                      help="skip row count step.")

    parser.add_option("--skip-diff", action="store_true",
                      dest="no_diff",
                      help="skip the object diff step.")

    parser.add_option("--skip-data-check", action="store_true",
                      dest="no_data",
                      help="skip data consistency check.")

    # Skip check of table options.
    parser.add_option("--skip-table-options", action="store_true",
                      dest="skip_tbl_opts",
                      help="skip check of all table options (e.g., "
                           "AUTO_INCREMENT, ENGINE, CHARSET, etc.).")

    # Add display width option
    parser.add_option("--width", action="store", dest="width",
                      type="int", help="display width",
                      default=PRINT_WIDTH)

    # run-all-tests mode
    parser.add_option("-a", "--run-all-tests", action="store_true",
                      dest="run_all_tests",
                      help="do not abort when a diff test fails")

    # Add compact option for resulting diff
    parser.add_option("-c", "--compact", action="store_true",
                      dest="compact", help="compact output from a diff.")

    # turn off binlog mode
    parser.add_option("--disable-binary-logging", action="store_true",
                      default=False, dest="toggle_binlog",
                      help="turn binary logging off during operation if "
                           "enabled (SQL_LOG_BIN=1). Note: may require SUPER "
                           "privilege. Prevents compare operations from being "
                           "written to the binary log.")

    # add the span key option
    parser.add_option(
        "--span-key-size", action="store", default=DEFAULT_SPAN_KEY_SIZE,
        type="int", dest="span_key_size",
        help="changes the size of the key used for compare table contents. A "
             "higher value can help to get more accurate results comparing "
             "large databases, but may slow the algorithm. Default value is "
             "{0}.".format(DEFAULT_SPAN_KEY_SIZE)
    )

    # add the use indexes option
    parser.add_option(
        "--use-indexes", action="store", type="string", default='',
        dest="use_indexes",
        help="for each table, indicate which index to use as if were a "
             "primary key (each of his columns must not allow null values)."
    )

    # Add verbosity and quiet (silent) mode
    add_verbosity(parser, True)

    # Add difftype option
    add_difftype(parser, True)

    # Add the direction (changes-for)
    add_changes_for(parser)

    # Add show reverse option
    add_reverse(parser)

    # Add ssl options
    add_ssl_options(parser)

    # Now we process the rest of the arguments.
    opt, args = parser.parse_args()

    # Check security settings
    check_password_security(opt, args, "# ")

    # Warn if quiet and verbosity are both specified
    check_verbosity(opt)

    # check unique keys
    ukey_regexp = re.compile(r'(?:(?:;){{0,1}}{0}\.{0})'
                             ''.format(REGEXP_OBJ_NAME))

    db_idxes_l = None

    # Split the table names considering backtick quotes
    if opt.use_indexes:
        grp = ukey_regexp.findall(opt.use_indexes)
        if not grp:
            parser.error("Can't parse the specified --use-indexes argument {0}"
                         "".format(opt.use_indexes))
        db_idxes_l = []
        for table, index in grp:
            table_uc = (table if is_quoted_with_backticks(table)
                        else quote_with_backticks(table))
            index_uc = (index if is_quoted_with_backticks(index)
                        else quote_with_backticks(index))
            db_idxes_l.append((table_uc, index_uc))

    # Set options for database operations.
    options = {
        "quiet": opt.quiet,
        "verbosity": opt.verbosity,
        "difftype": opt.difftype,
        "run_all_tests": opt.run_all_tests,
        "width": opt.width,
        "no_checksum_table": opt.no_checksum_table,
        "no_object_check": opt.no_object_check,
        "no_diff": opt.no_diff,
        "no_row_count": opt.no_row_count,
        "no_data": opt.no_data,
        "format": opt.format,
        "toggle_binlog": opt.toggle_binlog,
        "changes-for": opt.changes_for,
        "reverse": opt.reverse,
        "span_key_size": opt.span_key_size,
        "skip_table_opts": opt.skip_tbl_opts,
        "charset": opt.charset,
        "use_indexes": db_idxes_l,
        "compact": opt.compact
    }

    # Add ssl options to options instead of connection.
    options.update(get_ssl_dict(opt))

    # Parse server connection values
    server2_values = None
    try:
        server1_values = parse_connection(opt.server1, None, options)
    except FormatError:
        _, err, _ = sys.exc_info()
        parser.error("Server1 connection values invalid: %s." % err)
    except UtilError:
        _, err, _ = sys.exc_info()
        parser.error("Server1 connection values invalid: %s." % err.errmsg)

    if opt.server2:
        try:
            server2_values = parse_connection(opt.server2, None, options)
        except FormatError:
            _, err, _ = sys.exc_info()
            parser.error("Server2 connection values invalid: %s." % err)
        except UtilError:
            _, err, _ = sys.exc_info()
            parser.error("Server2 connection values invalid: %s." % err.errmsg)

    # Check for arguments
    if len(args) == 0:
        parser.error(PARSE_ERR_DB_MISSING_CMP)

    if opt.span_key_size and opt.span_key_size < DEFAULT_SPAN_KEY_SIZE:
        parser.error(
            PARSE_ERR_SPAN_KEY_SIZE_TOO_LOW.format(
                s_value=opt.span_key_size, default=DEFAULT_SPAN_KEY_SIZE))
    # Operations to perform:
    # 1) databases exist
    # 2) check object counts
    # 3) check object differences
    # 4) check row counts among the tables
    # 5) check table data consistency

    res = True
    check_failed = False
    arg_regexp = re.compile(r'{0}(?:(?:\:){0})?'.format(REGEXP_OBJ_NAME))
    for db in args:
        # Split the database names considering backtick quotes
        grp = arg_regexp.match(db)
        if not grp:
            parser.error(PARSE_ERR_DB_PAIR.format(db_pair=db,
                                                  db1_label='db1',
                                                  db2_label='db2'))
        parts = grp.groups()
        matched_size = len(parts[0])
        if not parts[1]:
            parts = (parts[0], parts[0])
        else:
            # add 1 for the separator ':'
            matched_size = matched_size + 1
            matched_size = matched_size + len(parts[1])
        # Verify if the size of the databases matched by the REGEX is equal
        # to the initial specified string. In general, this identifies the
        # missing use of backticks.
        if matched_size != len(db):
            parser.error(PARSE_ERR_DB_PAIR_EXT.format(db_pair=db,
                                                      db1_label='db1',
                                                      db2_label='db2',
                                                      db1_value=parts[0],
                                                      db2_value=parts[1]))

        # Remove backtick quotes (handled later)
        db1 = remove_backtick_quoting(parts[0]) \
            if is_quoted_with_backticks(parts[0]) else parts[0]
        db2 = remove_backtick_quoting(parts[1]) \
            if is_quoted_with_backticks(parts[1]) else parts[1]

        try:
            res = database_compare(server1_values, server2_values,
                                   db1, db2, options)
            print
        except UtilError:
            _, e, _ = sys.exc_info()
            print("ERROR: %s" % e.errmsg)
            sys.exit(1)

        if not res:
            check_failed = True

        if check_failed and not opt.run_all_tests:
            break

    if not opt.quiet:
        print
        if check_failed:
            print("# Database consistency check failed.")
        else:
            sys.stdout.write("# Databases are consistent")
            if (opt.no_object_check or opt.no_diff or
               opt.no_row_count or opt.no_data or opt.skip_tbl_opts):
                sys.stdout.write(" given skip options specified")
            print(".")
        print("#\n# ...done")

    if check_failed:
        sys.exit(1)

    sys.exit()
