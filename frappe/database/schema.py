from __future__ import unicode_literals

import re
import os
import frappe

from frappe import _
from frappe.utils import cstr, cint

VARCHAR_LEN = 140
OPTIONAL_COLUMNS = ["_user_tags", "_comments", "_assign", "_liked_by"]
DEFAULT_SHORTCUTS = ['_Login', '__user', '_Full Name', 'Today', '__today', "now", "Now"]
STANDARD_VARCHAR_COLUMNS = ('name', 'owner', 'modified_by', 'parent', 'parentfield', 'parenttype')
DEFAULT_COLUMNS = ['name', 'creation', 'modified', 'modified_by', 'owner', 'docstatus', 'parent',
	'parentfield', 'parenttype', 'idx']

class InvalidColumnName(frappe.ValidationError): pass

def validate_column_name(n):
	special_characters = re.findall(r"[\W]", n, re.UNICODE)
	if special_characters:
		special_characters = ", ".join('"{0}"'.format(c) for c in special_characters)
		frappe.throw(_("Fieldname {0} cannot have special characters like {1}").format(
			frappe.bold(cstr(n)), special_characters), frappe.db.InvalidColumnName)
	return n

def validate_column_length(fieldname):
	""" In MySQL maximum column length is 64 characters,
		ref: https://dev.mysql.com/doc/refman/5.5/en/identifiers.html"""

	if len(fieldname) > 64:
		frappe.throw(_("Fieldname is limited to 64 characters ({0})").format(fieldname))

def get_definition(fieldtype, precision=None, length=None):
	d = frappe.db.type_map.get(fieldtype)

	# convert int to long int if the length of the int is greater than 11
	if fieldtype == "Int" and length and length>11:
		d = frappe.db.type_map.get("Long Int")

	if not d:
		return

	coltype = d[0]
	size = None
	if d[1]:
		size = d[1]

	if size:
		if fieldtype in ["Float", "Currency", "Percent"] and cint(precision) > 6:
			size = '21,9'

		if coltype == "varchar" and length:
			size = length

	if size is not None:
		coltype = "{coltype}({size})".format(coltype=coltype, size=size)

	return coltype

def add_column(doctype, column_name, fieldtype, precision=None):
	if column_name in frappe.db.get_table_columns(doctype):
		# already exists
		return

	frappe.db.commit()
	frappe.db.sql("alter table `tab%s` add column %s %s" % (doctype,
		column_name, get_definition(fieldtype, precision)))

class DbManager:
	"""
	Basically, a wrapper for oft-used mysql commands. like show tables,databases, variables etc...

	#TODO:
		0.  Simplify / create settings for the restore database source folder
		0a. Merge restore database and extract_sql(from frappe_server_tools).
		1. Setter and getter for different mysql variables.
		2. Setter and getter for mysql variables at global level??
	"""
	def __init__(self, db):
		"""
		Pass root_conn here for access to all databases.
		"""
		if db:
			self.db = db

	def get_current_host(self):
		return self.db.sql("select user()")[0][0].split('@')[1]

	def get_variables(self,regex):
		"""
		Get variables that match the passed pattern regex
		"""
		return list(self.db.sql("SHOW VARIABLES LIKE '%s'"%regex))

	def create_user(self, user, password, host=None):
		#Create user if it doesn't exist.
		if not host:
			host = self.get_current_host()

		if password:
			self.db.sql("CREATE USER '%s'@'%s' IDENTIFIED BY '%s';" % (user[:16], host, password))
		else:
			self.db.sql("CREATE USER '%s'@'%s';" % (user[:16], host))

	def delete_user(self, target, host=None):
		if not host:
			host = self.get_current_host()
		try:
			self.db.sql("DROP USER '%s'@'%s';" % (target, host))
		except Exception as e:
			if e.args[0]==1396:
				pass
			else:
				raise

	def create_database(self,target):
		if target in self.get_database_list():
			self.drop_database(target)

		self.db.sql("CREATE DATABASE `%s` ;" % target)

	def drop_database(self,target):
		self.db.sql("DROP DATABASE IF EXISTS `%s`;"%target)

	def grant_all_privileges(self, target, user, host=None):
		if not host:
			host = self.get_current_host()

		self.db.sql("GRANT ALL PRIVILEGES ON `%s`.* TO '%s'@'%s';" % (target,
			user, host))

	def grant_select_privilges(self, db, table, user, host=None):
		if not host:
			host = self.get_current_host()

		if table:
			self.db.sql("GRANT SELECT ON %s.%s to '%s'@'%s';" % (db, table, user, host))
		else:
			self.db.sql("GRANT SELECT ON %s.* to '%s'@'%s';" % (db, user, host))

	def flush_privileges(self):
		self.db.sql("FLUSH PRIVILEGES")

	def get_database_list(self):
		"""get list of databases"""
		return [d[0] for d in self.db.sql("SHOW DATABASES")]

	def restore_database(self,target,source,user,password):
		from frappe.utils import make_esc
		esc = make_esc('$ ')

		from distutils.spawn import find_executable
		pipe = find_executable('pv')
		if pipe:
			pipe   = '{pipe} {source} |'.format(
				pipe   = pipe,
				source = source
			)
			source = ''
		else:
			pipe   = ''
			source = '< {source}'.format(source = source)

		if pipe:
			print('Creating Database...')

		command = '{pipe} mysql -u {user} -p{password} -h{host} {target} {source}'.format(
			pipe = pipe,
			user = esc(user),
			password = esc(password),
			host     = esc(frappe.db.host),
			target   = esc(target),
			source   = source
		)
		os.system(command)

	def drop_table(self,table_name):
		"""drop table if exists"""
		if not table_name in frappe.db.get_tables:
			return

		self.db.sql("DROP TABLE IF EXISTS %s "%(table_name))
