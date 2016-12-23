The patch on "database.py" is for ignoring the check on upper/lowercase table name of the foreign key definitions:

Example:

# TABLE     t_Files                                 FAIL    SKIP    SKIP    
#
# Object definitions differ. (--changes-for=server2)
#

  CREATE TABLE `t_Files` (
    `IDFile` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `FKFormat` int(10) unsigned DEFAULT NULL,
    `FileNameOriginal` varchar(255) NOT NULL,
    `FileName` varchar(255) NOT NULL DEFAULT '',
    `FileSize` bigint(20) unsigned NOT NULL DEFAULT '0',
    `FKRepository` int(10) unsigned NOT NULL DEFAULT '0',
    `InsertDate` datetime DEFAULT NULL,
    `InsertUser` int(10) unsigned NOT NULL DEFAULT '0',
    PRIMARY KEY (`IDFile`),
    KEY `fk_t_Files_t_Formats` (`FKFormat`),
    KEY `FK_t_Files_2` (`FKRepository`),
-   CONSTRAINT `FK_t_Files_2` FOREIGN KEY (`FKRepository`) REFERENCES `t_repositories` (`IDRepository`) ON DELETE CASCADE ON UPDATE CASCADE,
?                                                                        ^
+   CONSTRAINT `FK_t_Files_2` FOREIGN KEY (`FKRepository`) REFERENCES `t_Repositories` (`IDRepository`) ON DELETE CASCADE ON UPDATE CASCADE,
?                                                                        ^
-   CONSTRAINT `fk_t_Files_t_Formats` FOREIGN KEY (`FKFormat`) REFERENCES `t_formats` (`IDFormat`) ON DELETE NO ACTION ON UPDATE NO ACTION
?                                                                            ^
+   CONSTRAINT `fk_t_Files_t_Formats` FOREIGN KEY (`FKFormat`) REFERENCES `t_Formats` (`IDFormat`) ON DELETE NO ACTION ON UPDATE NO ACTION
?                                                                            ^
  )
