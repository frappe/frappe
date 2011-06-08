-- Core Elements to install WNFramework
-- To be called from install.py


--
-- Table structure for table `__DocTypeCache`
--

DROP TABLE IF EXISTS `__DocTypeCache`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `__DocTypeCache` (
  `name` varchar(120) DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `content` text
) ENGINE=MyISAM DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `__SessionCache`
--

DROP TABLE IF EXISTS `__SessionCache`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `__SessionCache` (
  `user` varchar(120) DEFAULT NULL,
  `country` varchar(120) DEFAULT NULL,
  `cache` longtext
) ENGINE=MyISAM DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;



--
-- Table structure for table `tabDocField`
--

DROP TABLE IF EXISTS `tabDocField`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tabDocField` (
  `name` varchar(120) NOT NULL,
  `creation` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `modified_by` varchar(40) DEFAULT NULL,
  `owner` varchar(40) DEFAULT NULL,
  `docstatus` int(1) DEFAULT '0',
  `parent` varchar(120) DEFAULT NULL,
  `parentfield` varchar(120) DEFAULT NULL,
  `parenttype` varchar(120) DEFAULT NULL,
  `idx` int(8) DEFAULT NULL,
  `fieldname` varchar(180) DEFAULT NULL,
  `label` varchar(180) DEFAULT NULL,
  `oldfieldname` varchar(180) DEFAULT NULL,
  `fieldtype` varchar(180) DEFAULT NULL,
  `oldfieldtype` varchar(180) DEFAULT NULL,
  `options` text,
  `search_index` int(3) DEFAULT NULL,
  `hidden` int(3) DEFAULT NULL,
  `print_hide` int(3) DEFAULT NULL,
  `report_hide` int(3) DEFAULT NULL,
  `reqd` int(3) DEFAULT NULL,
  `no_copy` int(3) DEFAULT NULL,
  `allow_on_submit` int(3) DEFAULT NULL,
  `trigger` varchar(180) DEFAULT NULL,
  `depends_on` varchar(180) DEFAULT NULL,
  `permlevel` int(3) DEFAULT NULL,
  `width` varchar(180) DEFAULT NULL,
  `default` text,
  `description` text,
  `colour` varchar(180) DEFAULT NULL,
  `icon` varchar(180) DEFAULT NULL,
  `in_filter` int(3) DEFAULT NULL,
  PRIMARY KEY (`name`),
  KEY `parent` (`parent`),
  KEY `label` (`label`),
  KEY `fieldtype` (`fieldtype`),
  KEY `fieldname` (`fieldname`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tabDocFormat`
--

DROP TABLE IF EXISTS `tabDocFormat`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tabDocFormat` (
  `name` varchar(120) NOT NULL,
  `creation` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `modified_by` varchar(40) DEFAULT NULL,
  `owner` varchar(40) DEFAULT NULL,
  `docstatus` int(1) DEFAULT '0',
  `parent` varchar(120) DEFAULT NULL,
  `parentfield` varchar(120) DEFAULT NULL,
  `parenttype` varchar(120) DEFAULT NULL,
  `idx` int(8) DEFAULT NULL,
  `format` varchar(180) DEFAULT NULL,
  PRIMARY KEY (`name`),
  KEY `parent` (`parent`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tabDocPerm`
--

DROP TABLE IF EXISTS `tabDocPerm`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tabDocPerm` (
  `name` varchar(120) NOT NULL,
  `creation` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `modified_by` varchar(40) DEFAULT NULL,
  `owner` varchar(40) DEFAULT NULL,
  `docstatus` int(1) DEFAULT '0',
  `parent` varchar(120) DEFAULT NULL,
  `parentfield` varchar(120) DEFAULT NULL,
  `parenttype` varchar(120) DEFAULT NULL,
  `idx` int(8) DEFAULT NULL,
  `permlevel` int(11) DEFAULT NULL,
  `role` varchar(180) DEFAULT NULL,
  `match` varchar(180) DEFAULT NULL,
  `read` int(3) DEFAULT NULL,
  `write` int(3) DEFAULT NULL,
  `create` int(3) DEFAULT NULL,
  `submit` int(3) DEFAULT NULL,
  `cancel` int(3) DEFAULT NULL,
  `amend` int(3) DEFAULT NULL,
  `execute` int(3) DEFAULT NULL,
  PRIMARY KEY (`name`),
  KEY `parent` (`parent`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tabDocType`
--

DROP TABLE IF EXISTS `tabDocType`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tabDocType` (
  `name` varchar(180) NOT NULL DEFAULT '',
  `creation` datetime DEFAULT NULL,
  `modified` datetime DEFAULT NULL,
  `modified_by` varchar(40) DEFAULT NULL,
  `owner` varchar(180) DEFAULT NULL,
  `docstatus` int(1) DEFAULT '0',
  `parent` varchar(120) DEFAULT NULL,
  `parentfield` varchar(120) DEFAULT NULL,
  `parenttype` varchar(120) DEFAULT NULL,
  `idx` int(8) DEFAULT NULL,
  `search_fields` varchar(180) DEFAULT NULL,
  `issingle` int(1) DEFAULT NULL,
  `istable` int(1) DEFAULT NULL,
  `version` int(11) DEFAULT NULL,
  `module` varchar(180) DEFAULT NULL,
  `autoname` varchar(180) DEFAULT NULL,
  `name_case` varchar(180) DEFAULT NULL,
  `description` text,
  `colour` varchar(180) DEFAULT NULL,
  `read_only` int(1) DEFAULT NULL,
  `in_create` int(1) DEFAULT NULL,
  `show_in_menu` int(3) DEFAULT NULL,
  `menu_index` int(11) DEFAULT NULL,
  `parent_node` varchar(180) DEFAULT NULL,
  `smallicon` varchar(180) DEFAULT NULL,
  `allow_print` int(1) DEFAULT NULL,
  `allow_email` int(1) DEFAULT NULL,
  `allow_copy` int(1) DEFAULT NULL,
  `allow_rename` int(1) DEFAULT NULL,
  `hide_toolbar` int(1) DEFAULT NULL,
  `hide_heading` int(1) DEFAULT NULL,
  `allow_attach` int(1) DEFAULT NULL,
  `use_template` int(1) DEFAULT NULL,
  `max_attachments` int(11) DEFAULT NULL,
  `section_style` varchar(180) DEFAULT NULL,
  `client_script` text,
  `client_script_core` text,
  `server_code` text,
  `server_code_core` text,
  `server_code_compiled` text,
  `client_string` text,
  `server_code_error` varchar(180) DEFAULT NULL,
  `print_outline` varchar(180) DEFAULT NULL,
  `dt_template` text,
  `is_transaction_doc` int(1) DEFAULT NULL,
  `change_log` text,
  `read_only_onload` int(1) DEFAULT NULL,
  PRIMARY KEY (`name`),
  KEY `parent` (`parent`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `tabSeries`
--

DROP TABLE IF EXISTS `tabSeries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tabSeries` (
  `name` varchar(40) DEFAULT NULL,
  `current` int(10) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;


--
-- Table structure for table `tabSessions`
--

DROP TABLE IF EXISTS `tabSessions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tabSessions` (
  `user` varchar(40) DEFAULT NULL,
  `sid` varchar(120) DEFAULT NULL,
  `sessiondata` longtext,
  `ipaddress` varchar(16) DEFAULT NULL,
  `lastupdate` datetime DEFAULT NULL,
  `status` varchar(20) DEFAULT NULL
) ENGINE=MyISAM DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;


--
-- Table structure for table `tabSingles`
--

DROP TABLE IF EXISTS `tabSingles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `tabSingles` (
  `doctype` varchar(40) DEFAULT NULL,
  `field` varchar(40) DEFAULT NULL,
  `value` text,
  KEY `doctype` (`doctype`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

