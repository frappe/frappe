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
Syncs a database table to the `DocType` (metadata)

.. note:: This module is only used internally

"""
import os
import webnotes

type_map = {
	'currency':		('decimal', '18,6')
	,'int':			('int', '11')
	,'float':		('decimal', '18,6')
	,'check':		('int', '1')
	,'small text':	('text', '')
	,'long text':	('longtext', '')
	,'code':		('text', '')
	,'text editor':	('text', '')
	,'date':		('date', '')
	,'time':		('time', '')
	,'text':		('text', '')
	,'data':		('varchar', '180')
	,'link':		('varchar', '180')
	,'password':	('varchar', '180')
	,'select':		('varchar', '180')
	,'read only':	('varchar', '180')
	,'blob':		('longblob', '')
}

default_columns = ['name', 'creation', 'modified', 'modified_by', 'owner', 'docstatus', 'parent',\
	 'parentfield', 'parenttype', 'idx']

default_shortcuts = ['_Login', '__user', '_Full Name', 'Today', '__today']


from webnotes.utils import cint

# -------------------------------------------------
# Class database table
# -------------------------------------------------

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

	def create(self):
		add_text = ''
		
		# columns
		t = self.get_column_definitions()
		if t: add_text += ',\n'.join(self.get_column_definitions()) + ',\n'
		
		# index
		t = self.get_index_definitions()
		if t: add_text += ',\n'.join(self.get_index_definitions()) + ',\n'
	
		# create table
		webnotes.conn.sql("""create table `%s` (
			name varchar(120) not null primary key, 
			creation datetime,
			modified datetime,
			modified_by varchar(40), 
			owner varchar(40),
			docstatus int(1) default '0', 
			parent varchar(120),
			parentfield varchar(120), 
			parenttype varchar(120), 
			idx int(8),
			%sindex parent(parent)) 
			ENGINE=InnoDB 
			CHARACTER SET=utf8""" % (self.name, add_text))

	def get_columns_from_docfields(self):
		"""
			get columns from docfields and custom fields
		"""
		fl = webnotes.conn.sql("SELECT * FROM tabDocField WHERE parent = '%s'" % self.doctype, as_dict = 1)
		
		try:
			custom_fl = webnotes.conn.sql("""\
				SELECT * FROM `tabCustom Field`
				WHERE dt = %s AND docstatus < 2""", self.doctype, as_dict=1)
			if custom_fl: fl += custom_fl
		except Exception, e:
			if e.args[0]!=1146: # ignore no custom field
				raise e

		for f in fl:
			self.columns[f['fieldname']] = DbColumn(self, f['fieldname'],
					f['fieldtype'], f.get('length'), f.get('default'),
					f.get('search_index'), f.get('options'))
	
	def get_columns_from_db(self):
		self.show_columns = webnotes.conn.sql("desc `%s`" % self.name)
		for c in self.show_columns:
			self.current_columns[c[0]] = {'name': c[0], 'type':c[1], 'index':c[3], 'default':c[4]}
	
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
		for k in self.columns.keys():
			if type_map.get(self.columns[k].fieldtype) and type_map.get(self.columns[k].fieldtype.lower())[0] not in ('text', 'blob'):
				ret.append('index `' + k + '`(`' + k + '`)')
		return ret


	# GET foreign keys
	def get_foreign_keys(self):
		fk_list = []
		txt = webnotes.conn.sql("show create table `%s`" % self.name)[0][1]
		for line in txt.split('\n'):
			if line.strip().startswith('CONSTRAINT') and line.find('FOREIGN')!=-1:
				try:
					fk_list.append((line.split('`')[3], line.split('`')[1]))
				except IndexError, e:
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
			webnotes.conn.sql("set foreign_key_checks=0")
			webnotes.conn.sql("alter table `%s` drop foreign key `%s`" % (self.name, fk_dict[col.fieldname]))
			webnotes.conn.sql("set foreign_key_checks=1")
		
	def sync(self):
		if not self.name in DbManager(webnotes.conn).get_tables_list(webnotes.conn.cur_db_name):
			self.create()
		else:
			self.alter()
	
	def alter(self):
		self.get_columns_from_db()
		for col in self.columns.values():
			col.check(self.current_columns.get(col.fieldname, None))

		for col in self.add_column:
			webnotes.conn.sql("alter table `%s` add column `%s` %s" % (self.name, col.fieldname, col.get_definition()))

		for col in self.change_type:
			webnotes.conn.sql("alter table `%s` change `%s` `%s` %s" % (self.name, col.fieldname, col.fieldname, col.get_definition()))

		for col in self.add_index:
			webnotes.conn.sql("alter table `%s` add index `%s`(`%s`)" % (self.name, col.fieldname, col.fieldname))

		for col in self.drop_index:
			if col.fieldname != 'name': # primary key
				webnotes.conn.sql("alter table `%s` drop index `%s`" % (self.name, col.fieldname))


		for col in self.set_default:
			webnotes.conn.sql("alter table `%s` alter column `%s` set default %s" % (self.name, col.fieldname, '%s'), col.default)


# -------------------------------------------------
# Class database column
# -------------------------------------------------

class DbColumn:
	def __init__(self, table, fieldname, fieldtype, length, default, set_index, options):
		self.table = table
		self.fieldname = fieldname
		self.fieldtype = fieldtype
		self.length = length
		self.set_index = set_index
		self.default = default
		self.options = options

	def get_definition(self, with_default=1):
		d = type_map.get(self.fieldtype.lower())

		if not d:
			return
			
		ret = d[0]
		if d[1]:
			ret += '(' + d[1] + ')'
		if with_default and self.default and (self.default not in default_shortcuts) \
			and d[0] not in ['text', 'longblob']:
			ret += ' default "' + self.default.replace('"', '\"') + '"'
		return ret
		
	def check(self, current_def):
		column_def = self.get_definition(0)

		# no columns
		if not column_def:
			return
		
		# to add?
		if not current_def:
			self.fieldname = validate_column_name(self.fieldname)
			self.table.add_column.append(self)
			return

		# type
		if current_def['type'] != column_def:
			self.table.change_type.append(self)
		
		# index
		else:
			if (current_def['index'] and not self.set_index):
				self.table.drop_index.append(self)
			
			if (not current_def['index'] and self.set_index and not (column_def in ['text','blob'])):
				self.table.add_index.append(self)
		
		# default
		if (self.default and (current_def['default'] != self.default) and (self.default not in default_shortcuts) and not (column_def in ['text','blob'])):
			self.table.set_default.append(self)


class DbManager:
	"""
	Basically, a wrapper for oft-used mysql commands. like show tables,databases, variables etc... 

	#TODO:
		0.  Simplify / create settings for the restore database source folder 
		0a. Merge restore database and extract_sql(from webnotes_server_tools).
		1. Setter and getter for different mysql variables.
		2. Setter and getter for mysql variables at global level??
	"""	
	def __init__(self,conn):
		"""
		Pass root_conn here for access to all databases.
		"""
 		if conn:
 			self.conn = conn
		

	def get_variables(self,regex):
		"""
		Get variables that match the passed pattern regex
		"""
		return list(self.conn.sql("SHOW VARIABLES LIKE '%s'"%regex))
			
	def get_table_schema(self,table):
		"""
		Just returns the output of Desc tables.
		"""
		return list(self.conn.sql("DESC `%s`"%table))
		
			
	def get_tables_list(self,target=None):
		"""get list of tables"""
		if target:
			self.conn.use(target)
		
		return [t[0] for t in self.conn.sql("SHOW TABLES")]

	def create_user(self,user,password):
		#Create user if it doesn't exist.
		try:
			if password:
				self.conn.sql("CREATE USER '%s'@'localhost' IDENTIFIED BY '%s';" % (user[:16], password))
			else:
				self.conn.sql("CREATE USER '%s'@'localhost';"%user[:16])
		except Exception, e:
			raise e


	def delete_user(self,target):
	# delete user if exists
		try:
			self.conn.sql("DROP USER '%s'@'localhost';" % target)
		except Exception, e:
			if e.args[0]==1396:
				pass
			else:
				raise e

	def create_database(self,target):
		if target in self.get_database_list():
			self.drop_database(target)

		self.conn.sql("CREATE DATABASE IF NOT EXISTS `%s` ;" % target)

	def drop_database(self,target):
		try:
			self.conn.sql("DROP DATABASE IF EXISTS `%s`;"%target)
		except Exception,e:
			raise e

	def grant_all_privileges(self,target,user):
		try:
			self.conn.sql("GRANT ALL PRIVILEGES ON `%s` . * TO '%s'@'localhost';" % (target, user))
		except Exception,e:
			raise e

	def grant_select_privilges(self,db,table,user):
		try:
			if table:
				self.conn.sql("GRANT SELECT ON %s.%s to '%s'@'localhost';" % (db,table,user))
			else:
				self.conn.sql("GRANT SELECT ON %s.* to '%s'@'localhost';" % (db,user))
		except Exception,e:
			raise e

	def flush_privileges(self):
		try:
			self.conn.sql("FLUSH PRIVILEGES")
		except Exception,e:
			raise e


	def get_database_list(self):
		"""get list of databases"""
		return [d[0] for d in self.conn.sql("SHOW DATABASES")]

	def restore_database(self,target,source,root_password):		
		from webnotes.utils import make_esc
		esc = make_esc('$ ')
		
		try:
			ret = os.system("mysql -u root -p%s %s < %s" % \
				(esc(root_password), esc(target), source))
		except Exception,e:
			raise e

	def drop_table(self,table_name):
		"""drop table if exists"""
		if not table_name in self.get_tables_list():
			return
		try:
			self.conn.sql("DROP TABLE IF EXISTS %s "%(table_name))
		except Exception,e:
			raise e	

	def set_transaction_isolation_level(self,scope='SESSION',level='READ COMMITTED'):
		#Sets the transaction isolation level. scope = global/session
		try:
			self.conn.sql("SET %s TRANSACTION ISOLATION LEVEL %s"%(scope,level))
		except Exception,e:
			raise e



# -------------------------------------------------
# validate column name to be code-friendly
# -------------------------------------------------

def validate_column_name(n):
	n = n.replace(' ','_').strip().lower()
	import re
	if re.search("[\W]", n):
		webnotes.msgprint('err:%s is not a valid fieldname.<br>A valid name must contain letters / numbers / spaces.<br><b>Tip: </b>You can change the Label after the fieldname has been set' % n)
		raise Exception
	return n

# -------------------------------------------------
# sync table - called from form.py
# -------------------------------------------------

def updatedb(dt, archive=0):
	"""
	Syncs a `DocType` to the table
	   * creates if required
	   * updates columns
	   * updates indices
	"""
	res = webnotes.conn.sql("select ifnull(issingle, 0) from tabDocType where name=%s", dt)
	if not res:
		raise Exception, 'Wrong doctype "%s" in updatedb' % dt
	
	if not res[0][0]:
		webnotes.conn.commit()
		tab = DbTable(dt, archive and 'arc' or 'tab')
		tab.sync()
		webnotes.conn.begin()

# patch to remove foreign keys
# ----------------------------

def remove_all_foreign_keys():
	webnotes.conn.sql("set foreign_key_checks = 0")
	webnotes.conn.commit()
	for t in webnotes.conn.sql("select name from tabDocType where ifnull(issingle,0)=0"):
		dbtab = webnotes.model.db_schema.DbTable(t[0])
		try:
			fklist = dbtab.get_foreign_keys()
		except Exception, e:
			if e.args[0]==1146:
				fklist = []
			else:
				raise e
				
		for f in fklist:
			webnotes.conn.sql("alter table `tab%s` drop foreign key `%s`" % (t[0], f[1]))
