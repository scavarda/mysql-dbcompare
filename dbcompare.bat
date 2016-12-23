REM MySQL Utilities mysqldbcompare.exe version 1.6.0 alpha
REM http://dev.mysql.com/doc/mysql-utilities/1.4/en/mysqldbcompare.html

REM Those objects considered in the database include tables, views, triggers, procedures, functions, and events

REM --run-all-tests: run all tests regardless of their end state

REM [Check existence of objects in both databases    --skip-object-compare  ]
REM The test for objects in both databases identifies those objects missing from one or another database. The remaining tests apply only to those objects that appear in both databases. To skip this test, use the --skip-object-compare option. That can be useful when there are known missing objects among the databases. 

REM [Compare object definitions    --skip-diff  ]
REM The definitions (the CREATE statements) are compared and differences are presented. To skip this test, use the --skip-diff option. That can be useful when there are object name differences only that you want to ignore. 

REM [Check table row counts   --skip-row-count  ]
REM This check ensures that both tables have the same number of rows. This does not ensure that the table data is consistent. It is merely a cursory check to indicate possible missing rows in one table or the other. The data consistency check identifies the missing rows. To skip this test, use the --skip-row-count option.

REM [Check table data consistency    --skip-checksum-table   --skip-data-check  ]
REM This check identifies both changed rows as well as missing rows from one or another of the tables in the databases. Changed rows are displayed as a diff-style report with the format chosen (GRID by default) and missing rows are also displayed using the format chosen. This check is divided in two steps: first the full table checksum is compared between the tables, then if this step fails (or is skipped) the algorithm to find rows differences is executed. To skip the preliminary checksum table step in this test, use the --skip-checksum-table option. To skip this full test, use the --skip-data-check option.


REM =============================================================================================================================================
REM                                              CONFIGURAZIONI PERSONALIZZATE                                                                   
REM =============================================================================================================================================


REM PYTHON_MODE=1 execute python script, PYTHON_MODE=0 execute .exe application
SET PYTHON_MODE=1

SET BATCH_FOLDER=%~dp0
SET DATE_NOW=%DATE:~6,4%-%DATE:~3,2%-%DATE:~0,2%
SET TIME_NOW=%TIME:~0,2%-%TIME:~3,2%-%TIME:~6,2%
SET MYSQL_UTILITIES_DIRECTORY=%BATCH_FOLDER%mysql-utilities-1.6.0
SET MYSQLDBCOMPARE="C:\Program Files (x86)\MySQL\MySQL Utilities 1.6.0a\mysqldbcompare.exe"

SET FILENAME="%BATCH_FOLDER%diff\diff_1.6 schema1-schema2 (%DATE_NOW%__%TIME_NOW%).sql"


SET SERVER_1=root:root@database.local:3306
SET SCHEMA_1=db1name

SET SERVER_2=root:root@database.remote:3306
SET SCHEMA_2=db2name


REM =============================================================================================================================================
REM                                              MYSQL_DB_COMPARE CONFIGURATION                                                               
REM =============================================================================================================================================


REM CHANGE_FOR_SERVER: to see the transformation for transforming object definitions on server1 to match the corresponding definitions on server2, use --changes-for=server1
REM CHANGE_FOR_SERVER: to see the transformation for transforming object definitions on server2 to match the corresponding definitions on server1, use --changes-for=server2
SET CHANGE_FOR_SERVER=--changes-for=server2



REM --show-reverse: Produce a transformation report containing the SQL statements to conform the object definitions specified in reverse.
SET SHOW_REVERSE=--show-reverse
SET SHOW_REVERSE=



REM --disable-binary-logging: If binary logging is enabled, disable it during the operation to prevent comparison operations from being written to the binary log. Note: Disabling binary logging requires the SUPER privilege
SET DISABLE_BINARY_LOGGING=--disable-binary-logging
REM SET DISABLE_BINARY_LOGGING=



REM [ --difftype ]
REM unified (default): Display unified format output.
REM context:           Display context format output.
REM differ:            Display differ-style format output.
REM sql:               Display SQL transformation statement output.
SET DIFF_TYPE=--difftype=unified 
SET DIFF_TYPE=--difftype=context
SET DIFF_TYPE=--difftype=differ
SET DIFF_TYPE=--difftype=sql
SET DIFF_TYPE=

SET DIFF_TYPE=--difftype=differ



REM [ --format ]
REM grid (default): Display output in grid or table format like that of the mysql client command-line tool.
REM csv:            Display output in comma-separated values format.
REM tab:            Display output in tab-separated format.
REM vertical:       Display output in single-column format like that of the \G command for the mysql client command-line tool.
SET FORMAT=--format=grid 
SET FORMAT=--format=csv
SET FORMAT=--format=tab
SET FORMAT=--format=vertical
SET FORMAT=

REM SET FORMAT=--format=differ



REM --quiet: Do not print anything. Return only an exit code of success or failure. 
SET QUIET=--quiet
SET QUIET=



REM [SKIP TESTS]
REM --skip-checksum-table: Skip the CHECKSUM TABLE step in the data consistency check.
REM --skip-data-check: Skip the data consistency check.
REM --skip-diff: Skip the object definition difference check.
REM --skip-object-compare: Skip the object comparison check.
REM --skip-row-count: Skip the row count check.
REM --skip-table-options: Skip check of all table options (e.g., AUTO_INCREMENT, ENGINE, CHARSET, etc.).

REM SET SKIP_TESTS=--skip-checksum-table --skip-data-check --skip-diff --skip-object-compare --skip-row-count --skip-table-options
SET SKIP_TESTS=--skip-row-count --skip-data-check --skip-table-options
REM SET SKIP_TESTS=



REM --character-set=<charset> Sets the client character set. The default is retrieved from the server variable character_set_client.
REM --compact: Compacts the output by reducing the number of control lines that are displayed in the diff results. This option should be used together with one of the following difference types: unified or context. It is most effective when used with the unified difference type and the grid format.



IF %PYTHON_MODE% == 1 GOTO :PYTHON_COMMAND
IF %PYTHON_MODE% == 0 GOTO :EXE_COMMAND

:PYTHON_COMMAND
  CD "%MYSQL_UTILITIES_DIRECTORY%\scripts"
  SET PYTHONPATH=%MYSQL_UTILITIES_DIRECTORY%
  python mysqldbcompare.py --server1=%SERVER_1% --server2=%SERVER_2% %DISABLE_BINARY_LOGGING% %DIFF_TYPE% %FORMAT% --run-all-tests %QUIET% %SKIP_TESTS% %CHANGE_FOR_SERVER% %SHOW_REVERSE% %SCHEMA_1%:%SCHEMA_2% >%FILENAME%
  GOTO :FINE
:END

:EXE_COMMAND
  %MYSQLDBCOMPARE% --server1=%SERVER_1% --server2=%SERVER_2% %DISABLE_BINARY_LOGGING% %DIFF_TYPE% %FORMAT% --run-all-tests %QUIET% %SKIP_TESTS% %CHANGE_FOR_SERVER% %SHOW_REVERSE% %SCHEMA_1%:%SCHEMA_2% >%FILENAME%
  GOTO :FINE
:END


:FINE
REM %MYSQLDBCOMPARE% --version
:END

pause