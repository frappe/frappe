-- Core Elements to install WNFramework
-- To be called from install.py


--
-- Table structure for table `tabDocField`
--

DROP TABLE IF EXISTS `tabDocField`;
CREATE TABLE `tabDocField` (
  `name` varchar(255) NOT NULL,
  `creation` datetime(6) DEFAULT NULL,
  `modified` datetime(6) DEFAULT NULL,
  `modified_by` varchar(255) DEFAULT NULL,
  `owner` varchar(255) DEFAULT NULL,
  `docstatus` int(1) NOT NULL DEFAULT 0,
  `parent` varchar(255) DEFAULT NULL,
  `parentfield` varchar(255) DEFAULT NULL,
  `parenttype` varchar(255) DEFAULT NULL,
  `idx` int(8) NOT NULL DEFAULT 0,
  `fieldname` varchar(255) DEFAULT NULL,
  `label` varchar(255) DEFAULT NULL,
  `oldfieldname` varchar(255) DEFAULT NULL,
  `fieldtype` varchar(255) DEFAULT NULL,
  `oldfieldtype` varchar(255) DEFAULT NULL,
  `options` text,
  `search_index` int(1) NOT NULL DEFAULT 0,
  `hidden` int(1) NOT NULL DEFAULT 0,
  `set_only_once` int(1) NOT NULL DEFAULT 0,
  `print_hide` int(1) NOT NULL DEFAULT 0,
  `report_hide` int(1) NOT NULL DEFAULT 0,
  `reqd` int(1) NOT NULL DEFAULT 0,
  `bold` int(1) NOT NULL DEFAULT 0,
  `collapsible` int(1) NOT NULL DEFAULT 0,
  `unique` int(1) NOT NULL DEFAULT 0,
  `no_copy` int(1) NOT NULL DEFAULT 0,
  `allow_on_submit` int(1) NOT NULL DEFAULT 0,
  `trigger` varchar(255) DEFAULT NULL,
  `collapsible_depends_on` text,
  `depends_on` text,
  `permlevel` int(11) NOT NULL DEFAULT 0,
  `ignore_user_permissions` int(1) NOT NULL DEFAULT 0,
  `width` varchar(255) DEFAULT NULL,
  `print_width` varchar(255) DEFAULT NULL,
  `default` text,
  `description` text,
  `in_filter` int(1) NOT NULL DEFAULT 0,
  `in_list_view` int(1) NOT NULL DEFAULT 0,
  `read_only` int(1) NOT NULL DEFAULT 0,
  `precision` varchar(255) DEFAULT NULL,
  `length` int(11) NOT NULL DEFAULT 0,
  PRIMARY KEY (`name`),
  KEY `parent` (`parent`),
  KEY `label` (`label`),
  KEY `fieldtype` (`fieldtype`),
  KEY `fieldname` (`fieldname`)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


--
-- Table structure for table `tabDocPerm`
--

DROP TABLE IF EXISTS `tabDocPerm`;
CREATE TABLE `tabDocPerm` (
  `name` varchar(255) NOT NULL,
  `creation` datetime(6) DEFAULT NULL,
  `modified` datetime(6) DEFAULT NULL,
  `modified_by` varchar(255) DEFAULT NULL,
  `owner` varchar(255) DEFAULT NULL,
  `docstatus` int(1) NOT NULL DEFAULT 0,
  `parent` varchar(255) DEFAULT NULL,
  `parentfield` varchar(255) DEFAULT NULL,
  `parenttype` varchar(255) DEFAULT NULL,
  `idx` int(8) NOT NULL DEFAULT 0,
  `permlevel` int(11) DEFAULT '0',
  `role` varchar(255) DEFAULT NULL,
  `match` varchar(255) DEFAULT NULL,
  `read` int(1) NOT NULL DEFAULT 1,
  `write` int(1) NOT NULL DEFAULT 1,
  `create` int(1) NOT NULL DEFAULT 1,
  `submit` int(1) NOT NULL DEFAULT 0,
  `cancel` int(1) NOT NULL DEFAULT 0,
  `delete` int(1) NOT NULL DEFAULT 1,
  `amend` int(1) NOT NULL DEFAULT 0,
  `report` int(1) NOT NULL DEFAULT 1,
  `export` int(1) NOT NULL DEFAULT 1,
  `import` int(1) NOT NULL DEFAULT 0,
  `share` int(1) NOT NULL DEFAULT 1,
  `print` int(1) NOT NULL DEFAULT 1,
  `email` int(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`name`),
  KEY `parent` (`parent`)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `tabDocType`
--

DROP TABLE IF EXISTS `tabDocType`;
CREATE TABLE `tabDocType` (
  `name` varchar(255) NOT NULL DEFAULT '',
  `creation` datetime(6) DEFAULT NULL,
  `modified` datetime(6) DEFAULT NULL,
  `modified_by` varchar(255) DEFAULT NULL,
  `owner` varchar(255) DEFAULT NULL,
  `docstatus` int(1) NOT NULL DEFAULT 0,
  `parent` varchar(255) DEFAULT NULL,
  `parentfield` varchar(255) DEFAULT NULL,
  `parenttype` varchar(255) DEFAULT NULL,
  `idx` int(8) NOT NULL DEFAULT 0,
  `search_fields` varchar(255) DEFAULT NULL,
  `issingle` int(1) NOT NULL DEFAULT 0,
  `istable` int(1) NOT NULL DEFAULT 0,
  `module` varchar(255) DEFAULT NULL,
  `app` varchar(255) DEFAULT NULL,
  `autoname` varchar(255) DEFAULT NULL,
  `name_case` varchar(255) DEFAULT NULL,
  `title_field` varchar(255) DEFAULT NULL,
  `sort_field` varchar(255) DEFAULT NULL,
  `sort_order` varchar(255) DEFAULT NULL,
  `description` text,
  `colour` varchar(255) DEFAULT NULL,
  `read_only` int(1) NOT NULL DEFAULT 0,
  `in_create` int(1) NOT NULL DEFAULT 0,
  `menu_index` int(11) DEFAULT NULL,
  `parent_node` varchar(255) DEFAULT NULL,
  `smallicon` varchar(255) DEFAULT NULL,
  `allow_copy` int(1) NOT NULL DEFAULT 0,
  `allow_rename` int(1) NOT NULL DEFAULT 0,
  `allow_import` int(1) NOT NULL DEFAULT 0,
  `hide_toolbar` int(1) NOT NULL DEFAULT 0,
  `hide_heading` int(1) NOT NULL DEFAULT 0,
  `max_attachments` int(11) NOT NULL DEFAULT 0,
  `print_outline` varchar(255) DEFAULT NULL,
  `read_only_onload` int(1) NOT NULL DEFAULT 0,
  `in_dialog` int(1) NOT NULL DEFAULT 0,
  `document_type` varchar(255) DEFAULT NULL,
  `icon` varchar(255) DEFAULT NULL,
  `tag_fields` varchar(255) DEFAULT NULL,
  `subject` varchar(255) DEFAULT NULL,
  `_last_update` varchar(32) DEFAULT NULL,
  `default_print_format` varchar(255) DEFAULT NULL,
  `is_submittable` int(1) NOT NULL DEFAULT 0,
  `_user_tags` varchar(255) DEFAULT NULL,
  `custom` int(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`name`),
  KEY `parent` (`parent`)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `tabSeries`
--

DROP TABLE IF EXISTS `tabSeries`;
CREATE TABLE `tabSeries` (
  `name` varchar(100) DEFAULT NULL,
  `current` int(10) NOT NULL DEFAULT 0
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


--
-- Table structure for table `tabSessions`
--

DROP TABLE IF EXISTS `tabSessions`;
CREATE TABLE `tabSessions` (
  `user` varchar(255) DEFAULT NULL,
  `sid` varchar(255) DEFAULT NULL,
  `sessiondata` longtext,
  `ipaddress` varchar(16) DEFAULT NULL,
  `lastupdate` datetime(6) DEFAULT NULL,
  `device` varchar(255) DEFAULT 'desktop',
  `status` varchar(20) DEFAULT NULL,
  KEY `sid` (`sid`)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


--
-- Table structure for table `tabSingles`
--

DROP TABLE IF EXISTS `tabSingles`;
CREATE TABLE `tabSingles` (
  `doctype` varchar(255) DEFAULT NULL,
  `field` varchar(255) DEFAULT NULL,
  `value` text,
  KEY `singles_doctype_field_index` (`doctype`, `field`)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `__Auth`
--

DROP TABLE IF EXISTS `__Auth`;
CREATE TABLE `__Auth` (
  `user` VARCHAR(255) NOT NULL PRIMARY KEY,
  `password` VARCHAR(255) NOT NULL,
  KEY `user` (`user`)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `tabFile`
--

DROP TABLE IF EXISTS `tabFile`;
CREATE TABLE `tabFile` (
  `name` varchar(255) NOT NULL,
  `creation` datetime(6) DEFAULT NULL,
  `modified` datetime(6) DEFAULT NULL,
  `modified_by` varchar(255) DEFAULT NULL,
  `owner` varchar(255) DEFAULT NULL,
  `docstatus` int(1) NOT NULL DEFAULT 0,
  `parent` varchar(255) DEFAULT NULL,
  `parentfield` varchar(255) DEFAULT NULL,
  `parenttype` varchar(255) DEFAULT NULL,
  `idx` int(8) NOT NULL DEFAULT 0,
  `file_name` varchar(255) DEFAULT NULL,
  `file_url` varchar(255) DEFAULT NULL,
  `module` varchar(255) DEFAULT NULL,
  `attached_to_name` varchar(255) DEFAULT NULL,
  `file_size` int(11) NOT NULL DEFAULT 0,
  `attached_to_doctype` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`name`),
  KEY `parent` (`parent`),
  KEY `attached_to_name` (`attached_to_name`),
  KEY `attached_to_doctype` (`attached_to_doctype`)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `tabDefaultValue`
--

DROP TABLE IF EXISTS `tabDefaultValue`;
CREATE TABLE `tabDefaultValue` (
  `name` varchar(255) NOT NULL,
  `creation` datetime(6) DEFAULT NULL,
  `modified` datetime(6) DEFAULT NULL,
  `modified_by` varchar(255) DEFAULT NULL,
  `owner` varchar(255) DEFAULT NULL,
  `docstatus` int(1) NOT NULL DEFAULT 0,
  `parent` varchar(255) DEFAULT NULL,
  `parentfield` varchar(255) DEFAULT NULL,
  `parenttype` varchar(255) DEFAULT NULL,
  `idx` int(8) NOT NULL DEFAULT 0,
  `defvalue` text,
  `defkey` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`name`),
  KEY `parent` (`parent`),
  KEY `defaultvalue_parent_defkey_index` (`parent`,`defkey`)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
