# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

"""
	Create a database from scratch (wip)
"""

class DatabaseInstance:

	def __init__(self, conn = None,db_name = None):
		self.conn = conn
		self.db_name = db_name
		
		
#	def setup(self):
#		self.create_db_and_user()
#		self.create_base_tables()
#		self.import_system_module()
#		self.setup_users()
		
	def create_db_and_user(self):
		import webnotes.defs
		
		# create user and db
		self.conn.sql("CREATE USER '%s'@'localhost' IDENTIFIED BY '%s'" % (self.db_name, webnotes.defs.db_password))
		self.conn.sql("CREATE DATABASE IF NOT EXISTS `%s` ;" % self.db_name)
		self.conn.sql("GRANT ALL PRIVILEGES ON `%s` . * TO '%s'@'localhost';" % (self.db_name, self.db_name))
		self.conn.sql("FLUSH PRIVILEGES")
		self.conn.sql("SET GLOBAL TRANSACTION ISOLATION LEVEL READ COMMITTED;")
		self.conn.sql("USE %s"%self.db_name)
		
		
	
		
	
	def create_base_tables(self):
		self.create_singles()
		self.create_sessions()
		self.create_doctypecache()
		self.create_role()
		self.create_docfield()
		self.create_docperm()
		self.create_docformat()
		self.create_doctype()

	def import_system_module(self):
		docs = [
			['DocType','Role']
			,['Role','Administrator']
			,['Role','Guest']
			,['Role','All']
			,['DocType','DocPerm']
			,['DocType','DocFormat']
			,['DocType','DocField']
			,['DocType','DocType']
			,['DocType','DefaultValue']
			,['DocType','Profile']
			,['DocType','UserRole']
		]
		
		# import in sequence
		for d in docs:
			import_module.import_from_files(record_list=[['System',d[0],d[1]]])
		
		# import all
		import_module.import_from_files([['System']])
			

	# singles
	# ------------------------------------------------------

	def create_singles(self):
		self.conn.sql("DROP TABLE IF EXISTS `tabSingles`")
		self.conn.sql("""CREATE TABLE `tabSingles` (
		  `doctype` varchar(40) default NULL,
		  `field` varchar(40) default NULL,
		  `value` text,
		  KEY `doctype` (`doctype`)
		) ENGINE=InnoDB DEFAULT CHARSET=latin1;""")
	
	# sessions
	# ------------------------------------------------------

	def create_sessions(self):
		self.conn.sql("DROP TABLE IF EXISTS `tabSessions`;")
		self.conn.sql("""CREATE TABLE `tabSessions` (
		  `user` varchar(40) default NULL,
		  `sid` varchar(120) default NULL,
		  `sessiondata` longtext,
		  `ipaddress` varchar(16) default NULL,
		  `lastupdate` datetime default NULL
		) ENGINE=MyISAM DEFAULT CHARSET=latin1;""")

	# doc type cache
	# ------------------------------------------------------

	def create_doctypecache(self):
		self.conn.sql("DROP TABLE IF EXISTS `__DocTypeCache`")
		self.conn.sql("create table `__DocTypeCache` (name VARCHAR(120), modified DATETIME, content TEXT, server_code_compiled TEXT)")
		self.conn.sql("""
		create table `__SessionCache` (user VARCHAR(120), country VARCHAR(120), cache LONGTEXT)
		""")
		
		

	# Role
	# ------------------------------------------------------

	def create_role(self):
		self.conn.sql("DROP TABLE IF EXISTS `tabRole`")
		self.conn.sql("""CREATE TABLE `tabRole` (
		  `name` varchar(120) NOT NULL,
		  `creation` datetime default NULL,
		  `modified` datetime default NULL,
		  `modified_by` varchar(40) default NULL,
		  `owner` varchar(40) default NULL,
		  `docstatus` int(1) default '0',
		  `parent` varchar(120) default NULL,
		  `parentfield` varchar(120) default NULL,
		  `parenttype` varchar(120) default NULL,
		  `idx` int(8) default NULL,
		  `role_name` varchar(180) default NULL,
		  `module` varchar(180) default NULL,
		  PRIMARY KEY  (`name`),
		  KEY `parent` (`parent`)
		) ENGINE=InnoDB DEFAULT CHARSET=latin1;""")

	# DocField
	# ------------------------------------------------------

	def create_docfield(self):
		self.conn.sql("DROP TABLE IF EXISTS `tabDocField`")
		self.conn.sql("""CREATE TABLE `tabDocField` (
		  `name` varchar(120) NOT NULL,
		  `creation` datetime default NULL,
		  `modified` datetime default NULL,
		  `modified_by` varchar(40) default NULL,
		  `owner` varchar(40) default NULL,
		  `docstatus` int(1) default '0',
		  `parent` varchar(120) default NULL,
		  `parentfield` varchar(120) default NULL,
		  `parenttype` varchar(120) default NULL,
		  `idx` int(8) default NULL,
		  `fieldname` varchar(180) default NULL,
		  `label` varchar(180) default NULL,
		  `oldfieldname` varchar(180) default NULL,
		  `fieldtype` varchar(180) default NULL,
		  `oldfieldtype` varchar(180) default NULL,
		  `options` text,
		  `search_index` int(3) default NULL,
		  `hidden` int(3) default NULL,
		  `print_hide` int(3) default NULL,
		  `report_hide` int(3) default NULL,
		  `reqd` int(3) default NULL,
		  `no_copy` int(3) default NULL,
		  `allow_on_submit` int(3) default NULL,
		  `trigger` varchar(180) default NULL,
		  `depends_on` varchar(180) default NULL,
		  `permlevel` int(3) default NULL,
		  `width` varchar(180) default NULL,
		  `default` text,
		  `description` text,
		  `colour` varchar(180) default NULL,
		  `icon` varchar(180) default NULL,
		  `in_filter` int(3) default NULL,
		  PRIMARY KEY  (`name`),
		  KEY `parent` (`parent`),
		  KEY `label` (`label`),
		  KEY `fieldtype` (`fieldtype`),
		  KEY `fieldname` (`fieldname`)
		) ENGINE=InnoDB DEFAULT CHARSET=latin1;""")

	# DocPerm
	# ------------------------------------------------------

	def create_docperm(self):
		self.conn.sql("DROP TABLE IF EXISTS `tabDocPerm`")
		self.conn.sql("""CREATE TABLE `tabDocPerm` (
		  `name` varchar(120) NOT NULL,
		  `creation` datetime default NULL,
		  `modified` datetime default NULL,
		  `modified_by` varchar(40) default NULL,
		  `owner` varchar(40) default NULL,
		  `docstatus` int(1) default '0',
		  `parent` varchar(120) default NULL,
		  `parentfield` varchar(120) default NULL,
		  `parenttype` varchar(120) default NULL,
		  `idx` int(8) default NULL,
		  `permlevel` int(11) default NULL,
		  `role` varchar(180) default NULL,
		  `match` varchar(180) default NULL,
		  `read` int(3) default NULL,
		  `write` int(3) default NULL,
		  `create` int(3) default NULL,
		  `submit` int(3) default NULL,
		  `cancel` int(3) default NULL,
		  `amend` int(3) default NULL,
		  `execute` int(3) default NULL,
		  PRIMARY KEY  (`name`),
		  KEY `parent` (`parent`)
		) ENGINE=InnoDB DEFAULT CHARSET=latin1;""")
		
	# DocFormat
	# ------------------------------------------------------

	def create_docformat(self):
		self.conn.sql("DROP TABLE IF EXISTS `tabDocFormat`")
		self.conn.sql("""CREATE TABLE `tabDocFormat` (
		  `name` varchar(120) NOT NULL,
		  `creation` datetime default NULL,
		  `modified` datetime default NULL,
		  `modified_by` varchar(40) default NULL,
		  `owner` varchar(40) default NULL,
		  `docstatus` int(1) default '0',
		  `parent` varchar(120) default NULL,
		  `parentfield` varchar(120) default NULL,
		  `parenttype` varchar(120) default NULL,
		  `idx` int(8) default NULL,
		  `format` varchar(180) default NULL,
		  PRIMARY KEY  (`name`),
		  KEY `parent` (`parent`)
		) ENGINE=InnoDB DEFAULT CHARSET=latin1;""")

	# DocType
	# ------------------------------------------------------

	def create_doctype(self):
		self.conn.sql("DROP TABLE IF EXISTS `tabDocType`")
		self.conn.sql("""CREATE TABLE `tabDocType` (
		  `name` varchar(180) NOT NULL default '',
		  `creation` datetime default NULL,
		  `modified` datetime default NULL,
		  `modified_by` varchar(40) default NULL,
		  `owner` varchar(180) default NULL,
		  `docstatus` int(1) default '0',
		  `parent` varchar(120) default NULL,
		  `parentfield` varchar(120) default NULL,
		  `parenttype` varchar(120) default NULL,
		  `idx` int(8) default NULL,
		  `search_fields` varchar(180) default NULL,
		  `issingle` int(1) default NULL,
		  `istable` int(1) default NULL,
		  `version` int(11) default NULL,
		  `module` varchar(180) default NULL,
		  `autoname` varchar(180) default NULL,
		  `name_case` varchar(180) default NULL,
		  `description` text,
		  `colour` varchar(180) default NULL,
		  `read_only` int(1) default NULL,
		  `in_create` int(1) default NULL,
		  `show_in_menu` int(3) default NULL,
		  `menu_index` int(11) default NULL,
		  `parent_node` varchar(180) default NULL,
		  `smallicon` varchar(180) default NULL,
		  `allow_print` int(1) default NULL,
		  `allow_email` int(1) default NULL,
		  `allow_copy` int(1) default NULL,
		  `allow_rename` int(1) default NULL,
		  `hide_toolbar` int(1) default NULL,
		  `hide_heading` int(1) default NULL,
		  `allow_attach` int(1) default NULL,
		  `use_template` int(1) default NULL,
		  `max_attachments` int(11) default NULL,
		  `section_style` varchar(180) default NULL,
		  `client_script` text,
		  `client_script_core` text,
		  `server_code` text,
		  `server_code_core` text,
		  `server_code_compiled` text,
		  `client_string` text,
		  `server_code_error` varchar(180) default NULL,
		  `print_outline` varchar(180) default NULL,
		  `dt_template` text,
		  `is_transaction_doc` int(1) default NULL,
		  `change_log` text,
		  `read_only_onload` int(1) default NULL,
		  PRIMARY KEY  (`name`),
		  KEY `parent` (`parent`)
		) ENGINE=InnoDB DEFAULT CHARSET=latin1;""")
		
	def create_module_def(self):
		self.conn.sql("DROP TABLE IF EXISTS `tabModule Def`")
		self.conn.sql("CREATE TABLE `tabModule Def` (`name` varchar(120) NOT NULL, `creation` datetime default NULL, `modified` datetime 					default NULL,`modified_by` varchar(40) default NULL,`owner` varchar(40) default NULL,`docstatus` int(1) default '0',  					`parent` varchar(120) default NULL,`parentfield` varchar(120) default NULL, `parenttype` varchar(120) default NULL,				`idx` int(8) default NULL,`module_name` varchar(180) default NULL,`doctype_list` text,				 PRIMARY KEY  (`name`), KEY `parent` (`parent`)) ENGINE=InnoDB")


	def post_cleanup(self):
		self.conn.sql("use %s;" % self.db_name)
		self.conn.sql("update tabProfile set password = password('admin') where name='Administrator'")
		self.conn.sql("update tabDocType set server_code_compiled = NULL")	
