# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

# called from wnf.py
# lib/wnf.py --install [rootpassword] [dbname] [source]

from __future__ import unicode_literals

import os, sys, json
import webnotes
import webnotes.db
import getpass

from webnotes.model.db_schema import DbManager
from webnotes.model.sync import sync_for
from webnotes.utils import cstr

class Installer:
	def __init__(self, root_login, root_password=None, db_name=None, site=None, site_config=None):
		make_conf(db_name, site=site, site_config=site_config)
		self.site = site
		
		self.make_connection(root_login, root_password)

		webnotes.local.conn = self.conn
		webnotes.local.session = webnotes._dict({'user':'Administrator'})
	
		self.dbman = DbManager(self.conn)
		
	def make_connection(self, root_login, root_password):
		if root_login:
			if not root_password:
				root_password = webnotes.conf.get("root_password") or None
			
			if not root_password:
				root_password = getpass.getpass("MySQL root password: ")
			
		self.root_password = root_password
		self.conn = webnotes.db.Database(user=root_login, password=root_password)
		
	def install(self, db_name, source_sql=None, admin_password = 'admin', verbose=0,
		force=0):
		
		if force or (db_name not in self.dbman.get_database_list()):
			# delete user (if exists)
			self.dbman.delete_user(db_name)
		else:
			raise Exception("Database %s already exists" % (db_name,))

		# create user and db
		self.dbman.create_user(db_name, webnotes.conf.db_password)
			
		if verbose: print "Created user %s" % db_name
	
		# create a database
		self.dbman.create_database(db_name)
		if verbose: print "Created database %s" % db_name
		
		# grant privileges to user
		self.dbman.grant_all_privileges(db_name, db_name)
		if verbose: print "Granted privileges to user %s and database %s" % (db_name, db_name)

		# flush user privileges
		self.dbman.flush_privileges()
		
		# close root connection
		self.conn.close()

		webnotes.connect(db_name=db_name, site=self.site)
		self.dbman = DbManager(webnotes.conn)
		
		# import in db_name
		if verbose: print "Starting database import..."

		# get the path of the sql file to import
		if not source_sql:
			source_sql = os.path.join(os.path.dirname(webnotes.__file__), "..", 
				'conf', 'Framework.sql')

		self.dbman.restore_database(db_name, source_sql, db_name, webnotes.conf.db_password)
		if verbose: print "Imported from database %s" % source_sql
		
		self.create_auth_table()

		# fresh app
		if 'Framework.sql' in source_sql:
			if verbose: print "Installing app..."
			self.install_app(verbose=verbose)

		# update admin password
		self.update_admin_password(admin_password)
		
		# create public folder
		from webnotes.install_lib import setup_public_folder
		setup_public_folder.make(site=self.site)
		
		if not self.site:
			from webnotes.build import bundle
			bundle(False)
					
		return db_name
		
	def install_app(self, verbose=False):
		sync_for("lib", force=True, sync_everything=True, verbose=verbose)
		self.import_core_docs()

		try:
			from startup import install
		except ImportError, e:
			install = None

		if os.path.exists("app"):
			sync_for("app", force=True, sync_everything=True, verbose=verbose)

		if os.path.exists(os.path.join("app", "startup", "install_fixtures")):
			install_fixtures()

		# build website sitemap
		from website.doctype.website_sitemap_config.website_sitemap_config import build_website_sitemap_config
		build_website_sitemap_config()

		if verbose: print "Completing App Import..."
		install and install.post_import()
		if verbose: print "Updating patches..."
		self.set_all_patches_as_completed()
		self.assign_all_role_to_administrator()

	def update_admin_password(self, password):
		from webnotes.auth import _update_password
		webnotes.conn.begin()
		_update_password("Administrator", webnotes.conf.get("admin_password") or password)
		webnotes.conn.commit()
	
	def import_core_docs(self):
		install_docs = [
			# profiles
			{'doctype':'Profile', 'name':'Administrator', 'first_name':'Administrator', 
				'email':'admin@localhost', 'enabled':1},
			{'doctype':'Profile', 'name':'Guest', 'first_name':'Guest',
				'email':'guest@localhost', 'enabled':1},

			# userroles
			{'doctype':'UserRole', 'parent': 'Administrator', 'role': 'Administrator', 
				'parenttype':'Profile', 'parentfield':'user_roles'},
			{'doctype':'UserRole', 'parent': 'Guest', 'role': 'Guest', 
				'parenttype':'Profile', 'parentfield':'user_roles'},
				
			{'doctype': "Role", "role_name": "Report Manager"}
		]
		
		webnotes.conn.begin()
		for d in install_docs:
			bean = webnotes.bean(d)
			bean.insert()
		webnotes.conn.commit()
	
	def set_all_patches_as_completed(self):
		try:
			from patches.patch_list import patch_list
		except ImportError, e:
			print "No patches to update."
			return
		
		for patch in patch_list:
			webnotes.doc({
				"doctype": "Patch Log",
				"patch": patch
			}).insert()
		webnotes.conn.commit()
		
	def assign_all_role_to_administrator(self):
		webnotes.bean("Profile", "Administrator").get_controller().add_roles(*webnotes.conn.sql_list("""
			select name from tabRole"""))
		webnotes.conn.commit()

	def create_auth_table(self):
		webnotes.conn.sql_ddl("""create table if not exists __Auth (
			`user` VARCHAR(180) NOT NULL PRIMARY KEY,
			`password` VARCHAR(180) NOT NULL
			) ENGINE=InnoDB DEFAULT CHARSET=utf8""")
		
def make_conf(db_name=None, db_password=None, site=None, site_config=None):
	try:
		from werkzeug.exceptions import NotFound
		import conf
		
		try:
			webnotes.init(site=site)
		except NotFound:
			pass
		
		if not site and webnotes.conf.site:
			site = webnotes.conf.site
			
		if site:
			# conf exists and site is specified, create site_config.json
			make_site_config(site, db_name, db_password, site_config)
		elif os.path.exists("conf.py"):
			print "conf.py exists"
		else:
			# pyc file exists but py doesn't
			raise ImportError
			
	except ImportError:
		if site:
			raise Exception("conf.py does not exist")
		else:
			# create conf.py
			with open(os.path.join("lib", "conf", "conf.py"), "r") as confsrc:
				with open("conf.py", "w") as conftar:
					conftar.write(confsrc.read() % get_conf_params(db_name, db_password))
	
	webnotes.destroy()
	webnotes.init(site=site)
						
def make_site_config(site, db_name=None, db_password=None, site_config=None):
	import conf
	if not getattr(conf, "sites_dir", None):
		raise Exception("sites_dir missing in conf.py")
		
	site_path = os.path.join(conf.sites_dir, site)
	
	if not os.path.exists(site_path):
		os.mkdir(site_path)
	
	site_file = os.path.join(site_path, "site_config.json")
	
	if not os.path.exists(site_file):
		if not (site_config and isinstance(site_config, dict)):
			site_config = get_conf_params(db_name, db_password)
		
		with open(site_file, "w") as f:
			f.write(json.dumps(site_config, indent=1, sort_keys=True))
			
def get_conf_params(db_name=None, db_password=None):
	if not db_name:
		db_name = raw_input("Database Name: ")
		if not db_name:
			raise Exception("Database Name Required")
	
	if not db_password:
		from webnotes.utils import random_string
		db_password = random_string(16)
	
	return {"db_name": db_name, "db_password": db_password}
	
def install_fixtures():
	print "Importing install fixtures..."
	for basepath, folders, files in os.walk(os.path.join("app", "startup", "install_fixtures")):
		for f in files:
			f = cstr(f)
			if f.endswith(".json"):
				print "Importing " + f
				with open(os.path.join(basepath, f), "r") as infile:
					webnotes.bean(json.loads(infile.read())).insert_or_update()
					webnotes.conn.commit()

			if f.endswith(".csv"):
				from core.page.data_import_tool.data_import_tool import import_file_by_path
				import_file_by_path(os.path.join(basepath, f), ignore_links = True, overwrite=True)
				webnotes.conn.commit()
					
	if os.path.exists(os.path.join("app", "startup", "install_fixtures", "files")):
		if not os.path.exists(os.path.join("public", "files")):
			os.makedirs(os.path.join("public", "files"))
		os.system("cp -r %s %s" % (os.path.join("app", "startup", "install_fixtures", "files", "*"), 
			os.path.join("public", "files")))
