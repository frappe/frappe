# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""
Syncs a database table to the `DocType` (metadata)

.. note:: This module is only used internally

"""
import re
import os
import frappe
from frappe import _
from frappe.utils import cstr, cint

class InvalidColumnName(frappe.ValidationError): pass

type_map = {
	'Currency':		('decimal', '18,6')
	,'Int':			('int', '11')
	,'Float':		('decimal', '18,6')
	,'Percent':		('decimal', '18,6')
	,'Check':		('int', '1')
	,'Small Text':	('text', '')
	,'Long Text':	('longtext', '')
	,'Code':		('longtext', '')
	,'Text Editor':	('longtext', '')
	,'Date':		('date', '')
	,'Datetime':	('datetime', '6')
	,'Time':		('time', '6')
	,'Text':		('text', '')
	,'Data':		('varchar', '255')
	,'Link':		('varchar', '255')
	,'Dynamic Link':('varchar', '255')
	,'Password':	('varchar', '255')
	,'Select':		('varchar', '255')
	,'Read Only':	('varchar', '255')
	,'Attach':		('varchar', '255')
	,'Attach Image':('varchar', '255')
}

default_columns = ['name', 'creation', 'modified', 'modified_by', 'owner',
	'docstatus', 'parent', 'parentfield', 'parenttype', 'idx']

default_shortcuts = ['_Login', '__user', '_Full Name', 'Today', '__today', "now", "Now"]

def updatedb(dt):
	"""
	Syncs a `DocType` to the table
	   * creates if required
	   * updates columns
	   * updates indices
	"""
	res = frappe.db.sql("select ifnull(issingle, 0) from tabDocType where name=%s", (dt,))
	if not res:
		raise Exception, 'Wrong doctype "%s" in updatedb' % dt

	if not res[0][0]:
		frappe.db.commit()
		tab = DbTable(dt, 'tab')
		tab.sync()
		frappe.db.begin()

class DbTable:
	def __init__(self, doctype, prefix = 'tab'):
		self.doctype = doctype
		self.name = prefix + doctype
		self.columns = {}
		self.current_columns = {}

		# lists for change
		self.add_column = []
		self.change_type = []

		self.add_index = []
		self.drop_index = []

		self.set_default = []

		# load
		self.get_columns_from_docfields()

	def sync(self):
		if not self.name in DbManager(frappe.db).get_tables_list(frappe.db.cur_db_name):
			self.create()
		else:
			self.alter()

	def create(self):
		add_text = ''

		# columns
		column_defs = self.get_column_definitions()
		if column_defs: add_text += ',\n'.join(column_defs) + ',\n'

		# index
		index_defs = self.get_index_definitions()
		if index_defs: add_text += ',\n'.join(index_defs) + ',\n'

		# create table
		frappe.db.sql("""create table `%s` (
			name varchar(255) not null primary key,
			creation datetime(6),
			modified datetime(6),
			modified_by varchar(255),
			owner varchar(255),
			docstatus int(1) default '0',
			parent varchar(255),
			parentfield varchar(255),
			parenttype varchar(255),
			idx int(8),
			%sindex parent(parent))
			ENGINE=InnoDB
			ROW_FORMAT=COMPRESSED
			CHARACTER SET=utf8mb4
			COLLATE=utf8mb4_unicode_ci""" % (self.name, add_text))

	def get_column_definitions(self):
		column_list = [] + default_columns
		ret = []
		for k in self.columns.keys():
			if k not in column_list:
				d = self.columns[k].get_definition()
				if d:
					ret.append('`'+ k+ '` ' + d)
					column_list.append(k)
		return ret

	def get_index_definitions(self):
		ret = []
		for key, col in self.columns.items():
			if col.set_index and col.fieldtype in type_map and \
					type_map.get(col.fieldtype)[0] not in ('text', 'longtext'):
				ret.append('index `' + key + '`(`' + key + '`)')
		return ret

	def get_columns_from_docfields(self):
		"""
			get columns from docfields and custom fields
		"""
		fl = frappe.db.sql("SELECT * FROM tabDocField WHERE parent = %s", self.doctype, as_dict = 1)
		precisions = {}

		if not frappe.flags.in_install:
			custom_fl = frappe.db.sql("""\
				SELECT * FROM `tabCustom Field`
				WHERE dt = %s AND docstatus < 2""", (self.doctype,), as_dict=1)
			if custom_fl: fl += custom_fl

			# get precision from property setters
			for ps in frappe.get_all("Property Setter", fields=["field_name", "value"],
				filters={"doc_type": self.doctype, "doctype_or_field": "DocField", "property": "precision"}):
					precisions[ps.field_name] = ps.value

		for f in fl:
			self.columns[f['fieldname']] = DbColumn(self, f['fieldname'],
				f['fieldtype'], f.get('length'), f.get('default'), f.get('search_index'),
				f.get('options'), f.get('unique'), precisions.get(f['fieldname']) or f.get('precision'))

	def get_columns_from_db(self):
		self.show_columns = frappe.db.sql("desc `%s`" % self.name)
		for c in self.show_columns:
			self.current_columns[c[0]] = {'name': c[0],
				'type':c[1], 'index':c[3]=="MUL", 'default':c[4], "unique":c[3]=="UNI"}

	# GET foreign keys
	def get_foreign_keys(self):
		fk_list = []
		txt = frappe.db.sql("show create table `%s`" % self.name)[0][1]
		for line in txt.split('\n'):
			if line.strip().startswith('CONSTRAINT') and line.find('FOREIGN')!=-1:
				try:
					fk_list.append((line.split('`')[3], line.split('`')[1]))
				except IndexError:
					pass

		return fk_list

	# Drop foreign keys
	def drop_foreign_keys(self):
		if not self.drop_foreign_key:
			return

		fk_list = self.get_foreign_keys()

		# make dictionary of constraint names
		fk_dict = {}
		for f in fk_list:
			fk_dict[f[0]] = f[1]

		# drop
		for col in self.drop_foreign_key:
			frappe.db.sql("set foreign_key_checks=0")
			frappe.db.sql("alter table `%s` drop foreign key `%s`" % (self.name, fk_dict[col.fieldname]))
			frappe.db.sql("set foreign_key_checks=1")

	def alter(self):
		self.get_columns_from_db()
		for col in self.columns.values():
			col.build_for_alter_table(self.current_columns.get(col.fieldname, None))

		query = []

		for col in self.add_column:
			query.append("add column `{}` {}".format(col.fieldname, col.get_definition()))

		for col in self.change_type:
			query.append("change `{}` `{}` {}".format(col.fieldname, col.fieldname, col.get_definition()))

		for col in self.add_index:
			# if index key not exists
			if not frappe.db.sql("show index from `%s` where key_name = %s" %
					(self.name, '%s'), col.fieldname):
				query.append("add index `{}`(`{}`)".format(col.fieldname, col.fieldname))

		for col in self.drop_index:
			if col.fieldname != 'name': # primary key
				# if index key exists
				if frappe.db.sql("""show index from `{0}`
					where key_name=%s
					and Non_unique=%s""".format(self.name), (col.fieldname, 1 if col.unique else 0)):
					query.append("drop index `{}`".format(col.fieldname))

		for col in self.set_default:
			if col.fieldname=="name":
				continue

			if not col.default:
				col_default = "null"
			else:
				col_default = '"{}"'.format(col.default.replace('"', '\\"'))

			query.append('alter column `{}` set default {}'.format(col.fieldname, col_default))

		if query:
			try:
				frappe.db.sql("alter table `{}` {}".format(self.name, ", ".join(query)))
			except Exception, e:
				# sanitize
				if e.args[0]==1060:
					frappe.throw(str(e))
				else:
					raise e

class DbColumn:
	def __init__(self, table, fieldname, fieldtype, length, default,
		set_index, options, unique, precision):
		self.table = table
		self.fieldname = fieldname
		self.fieldtype = fieldtype
		self.length = length
		self.set_index = set_index
		self.default = default
		self.options = options
		self.unique = unique
		self.precision = precision

	def get_definition(self, with_default=1):
		column_def = get_definition(self.fieldtype, self.precision)

		if not column_def:
			return column_def

		if self.default and (self.default not in default_shortcuts) \
			and not self.default.startswith(":") and column_def not in ('text', 'longtext'):
			column_def += ' default "' + self.default.replace('"', '\"') + '"'

		if self.unique and (column_def not in ('text', 'longtext')):
			column_def += ' unique'

		return column_def

	def build_for_alter_table(self, current_def):
		column_def = get_definition(self.fieldtype)

		# no columns
		if not column_def:
			return

		# to add?
		if not current_def:
			self.fieldname = validate_column_name(self.fieldname)
			self.table.add_column.append(self)
			return

		# type
		if (current_def['type'] != column_def) or (self.unique and not current_def['unique'] \
			and column_def in ('text', 'longtext')):
			self.table.change_type.append(self)

		else:
			# index
			if (current_def['index'] and not self.set_index):
				self.table.drop_index.append(self)

			if (current_def['unique'] and not self.unique) and not (column_def in ('text', 'longtext')):
				self.table.drop_index.append(self)

			if (not current_def['index'] and self.set_index) and not (column_def in ('text', 'longtext')):
				self.table.add_index.append(self)

			# default
			if (self.default_changed(current_def) \
				and (self.default not in default_shortcuts) \
				and not cstr(self.default).startswith(":") \
				and not (column_def in ['text','longtext'])):
				self.table.set_default.append(self)

	def default_changed(self, current_def):
		if "decimal" in current_def['type']:
			return self.default_changed_for_decimal(current_def)
		else:
			return current_def['default'] != self.default

	def default_changed_for_decimal(self, current_def):
		try:
			if current_def['default'] in ("", None) and self.default in ("", None):
				# both none, empty
				return False

			elif current_def['default'] in ("", None):
				try:
					# check if new default value is valid
					float(self.default)
					return True
				except ValueError:
					return False

			elif self.default in ("", None):
				# new default value is empty
				return True

			else:
				# NOTE float() raise ValueError when "" or None is passed
				return float(current_def['default'])!=float(self.default)
		except TypeError:
			return True

class DbManager:
	"""
	Basically, a wrapper for oft-used mysql commands. like show tables,databases, variables etc...

	#TODO:
		0.  Simplify / create settings for the restore database source folder
		0a. Merge restore database and extract_sql(from frappe_server_tools).
		1. Setter and getter for different mysql variables.
		2. Setter and getter for mysql variables at global level??
	"""
	def __init__(self,db):
		"""
		Pass root_conn here for access to all databases.
		"""
 		if db:
 			self.db = db


	def get_variables(self,regex):
		"""
		Get variables that match the passed pattern regex
		"""
		return list(self.db.sql("SHOW VARIABLES LIKE '%s'"%regex))

	def get_table_schema(self,table):
		"""
		Just returns the output of Desc tables.
		"""
		return list(self.db.sql("DESC `%s`"%table))


	def get_tables_list(self,target=None):
		"""get list of tables"""
		if target:
			self.db.use(target)

		return [t[0] for t in self.db.sql("SHOW TABLES")]

	def create_user(self, user, password, host):
		#Create user if it doesn't exist.
		try:
			if password:
				self.db.sql("CREATE USER '%s'@'%s' IDENTIFIED BY '%s';" % (user[:16], host, password))
			else:
				self.db.sql("CREATE USER '%s'@'%s';" % (user[:16], host))
		except Exception:
			raise

	def delete_user(self, target, host):
	# delete user if exists
		try:
			self.db.sql("DROP USER '%s'@'%s';" % (target, host))
		except Exception, e:
			if e.args[0]==1396:
				pass
			else:
				raise

	def create_database(self,target):
		if target in self.get_database_list():
			self.drop_database(target)

		self.db.sql("CREATE DATABASE IF NOT EXISTS `%s` ;" % target)

	def drop_database(self,target):
		self.db.sql("DROP DATABASE IF EXISTS `%s`;"%target)

	def grant_all_privileges(self, target, user, host):
		self.db.sql("GRANT ALL PRIVILEGES ON `%s`.* TO '%s'@'%s';" % (target, user, host))

	def grant_select_privilges(self, db, table, user, host):
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
		os.system("mysql -u %s -p%s -h%s %s < %s" % \
			(esc(user), esc(password), esc(frappe.db.host), esc(target), source))

	def drop_table(self,table_name):
		"""drop table if exists"""
		if not table_name in self.get_tables_list():
			return

		self.db.sql("DROP TABLE IF EXISTS %s "%(table_name))

def validate_column_name(n):
	n = n.replace(' ','_').strip().lower()
	special_characters = re.findall("[\W]", n, re.UNICODE)
	if special_characters:
		special_characters = ", ".join('"{0}"'.format(c) for c in special_characters)
		frappe.throw(_("Fieldname {0} cannot have special characters like {1}").format(cstr(n), special_characters), InvalidColumnName)
	return n

def remove_all_foreign_keys():
	frappe.db.sql("set foreign_key_checks = 0")
	frappe.db.commit()
	for t in frappe.db.sql("select name from tabDocType where ifnull(issingle,0)=0"):
		dbtab = DbTable(t[0])
		try:
			fklist = dbtab.get_foreign_keys()
		except Exception, e:
			if e.args[0]==1146:
				fklist = []
			else:
				raise

		for f in fklist:
			frappe.db.sql("alter table `tab%s` drop foreign key `%s`" % (t[0], f[1]))

def get_definition(fieldtype, precision=None):
	d = type_map.get(fieldtype)

	if not d:
		return

	ret = d[0]
	if d[1]:
		length = d[1]
		if fieldtype in ["Float", "Currency", "Percent"] and cint(precision) > 6:
			length = '18,9'
		ret += '(' + length + ')'

	return ret

def add_column(doctype, column_name, fieldtype, precision=None):
	frappe.db.commit()
	frappe.db.sql("alter table `tab%s` add column %s %s" % (doctype,
		column_name, get_definition(fieldtype, precision)))
