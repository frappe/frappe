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

# called from wnf.py
# lib/wnf.py --install [rootpassword] [dbname] [source]

from __future__ import unicode_literals

import os, sys
import webnotes, conf
import webnotes.db
import getpass
from webnotes.model.db_schema import DbManager
from webnotes.model.sync import sync_for

class Installer:
	def __init__(self, root_login, root_password=None):
		if root_login:
			if not root_password:
				root_password = getattr(conf, "root_password", None)
			if not root_password:
				root_password = getpass.getpass("MySQL root password: ")
			
		self.root_password = root_password
		
		self.conn = webnotes.db.Database(user=root_login, password=root_password)
		webnotes.conn=self.conn
		webnotes.session= webnotes._dict({'user':'Administrator'})
		self.dbman = DbManager(self.conn)

	def import_from_db(self, target, source_path='', password = 'admin', verbose=0):
		"""
		a very simplified version, just for the time being..will eventually be deprecated once the framework stabilizes.
		"""		
		# delete user (if exists)
		self.dbman.delete_user(target)

		# create user and db
		self.dbman.create_user(target, 
			hasattr(conf, 'db_password') and conf.db_password or password)
			
		if verbose: print "Created user %s" % target
	
		# create a database
		self.dbman.create_database(target)
		if verbose: print "Created database %s" % target
		
		# grant privileges to user
		self.dbman.grant_all_privileges(target,target)
		if verbose: print "Granted privileges to user %s and database %s" % (target, target)

		# flush user privileges
		self.dbman.flush_privileges()

		self.conn.use(target)
		
		# import in target
		if verbose: print "Starting database import..."

		# get the path of the sql file to import
		source_given = True
		if not source_path:
			source_given = False
			source_path = os.path.join(os.path.sep.join(os.path.abspath(webnotes.__file__).split(os.path.sep)[:-3]), 'data', 'Framework.sql')

		self.dbman.restore_database(target, source_path, self.root_password)
		if verbose: print "Imported from database %s" % source_path

		# fresh app
		if 'Framework.sql' in source_path:
			print "Installing app..."
			self.install_app()

		# update admin password
		self.update_admin_password(password)
		return target
		
	def install_app(self):
		try:
			from startup import install
		except ImportError, e:
			print "No app install found"

		sync_for("lib", force=True, sync_everything=True)
		self.import_core_docs()
		install.pre_import()
		sync_for("app", force=True, sync_everything=True)
		print "Completing App Import..."
		install.post_import()
		print "Updating patches..."
		self.set_all_patches_as_completed()

	def update_admin_password(self, password):
		from webnotes.auth import update_password
		webnotes.conn.begin()
		update_password("Administrator", getattr(conf, "admin_password", password))
		webnotes.conn.commit()
		
	def import_core_docs(self):
		install_docs = [
			{'doctype':'Module Def', 'name': 'Core', 'module_name':'Core'},

			# roles
			{'doctype':'Role', 'role_name': 'Administrator', 'name': 'Administrator'},
			{'doctype':'Role', 'role_name': 'All', 'name': 'All'},
			{'doctype':'Role', 'role_name': 'System Manager', 'name': 'System Manager'},
			{'doctype':'Role', 'role_name': 'Report Manager', 'name': 'Report Manager'},
			{'doctype':'Role', 'role_name': 'Guest', 'name': 'Guest'},

			# profiles
			{'doctype':'Profile', 'name':'Administrator', 'first_name':'Administrator', 
				'email':'admin@localhost', 'enabled':1},
			{'doctype':'Profile', 'name':'Guest', 'first_name':'Guest',
				'email':'guest@localhost', 'enabled':1},

			# userroles
			{'doctype':'UserRole', 'parent': 'Administrator', 'role': 'Administrator', 
				'parenttype':'Profile', 'parentfield':'userroles'},
			{'doctype':'UserRole', 'parent': 'Guest', 'role': 'Guest', 
				'parenttype':'Profile', 'parentfield':'userroles'}
		]
		
		webnotes.conn.begin()
		for d in install_docs:
			doc = webnotes.doc(fielddata=d)
			doc.insert()
		webnotes.conn.commit()
	
	def set_all_patches_as_completed(self):
		try:
			from patches.patch_list import patch_list
		except ImportError, e:
			print "No patches to update."
			return
		
		webnotes.conn.begin()
		for patch in patch_list:
			webnotes.doc({
				"doctype": "Patch Log",
				"patch": patch
			}).insert()
		webnotes.conn.commit()
			