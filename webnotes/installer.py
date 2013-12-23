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

def install_db(root_login="root", root_password=None, db_name=None, source_sql=None,
	admin_password = 'admin', verbose=True, force=0, site_config=None, reinstall=False):
	webnotes.flags.in_install_db = True
	make_conf(db_name, site_config=site_config)
	if reinstall:
		webnotes.connect(db_name=db_name)
		dbman = DbManager(webnotes.local.conn)
		dbman.create_database(db_name)

	else:
		webnotes.local.conn = make_connection(root_login, root_password)
		webnotes.local.session = webnotes._dict({'user':'Administrator'})
		create_database_and_user(force, verbose)

	webnotes.conf.admin_password = admin_password

	webnotes.connect(db_name=db_name)
	import_db_from_sql(source_sql, verbose)
	
	create_auth_table()
	webnotes.flags.in_install_db = False

def create_database_and_user(force, verbose):
	db_name = webnotes.conf.db_name
	dbman = DbManager(webnotes.local.conn)
	if force or (db_name not in dbman.get_database_list()):
		dbman.delete_user(db_name)
	else:
		raise Exception("Database %s already exists" % (db_name,))

	dbman.create_user(db_name, webnotes.conf.db_password)
	if verbose: print "Created user %s" % db_name

	dbman.create_database(db_name)
	if verbose: print "Created database %s" % db_name
	
	dbman.grant_all_privileges(db_name, db_name)
	dbman.flush_privileges()
	if verbose: print "Granted privileges to user %s and database %s" % (db_name, db_name)
	
	# close root connection
	webnotes.conn.close()

def create_auth_table():
	webnotes.conn.sql_ddl("""create table if not exists __Auth (
		`user` VARCHAR(180) NOT NULL PRIMARY KEY,
		`password` VARCHAR(180) NOT NULL
		) ENGINE=InnoDB DEFAULT CHARSET=utf8""")

def import_db_from_sql(source_sql, verbose):
	if verbose: print "Starting database import..."
	db_name = webnotes.conf.db_name
	if not source_sql:
		source_sql = os.path.join(os.path.dirname(webnotes.__file__), 'data', 'Framework.sql')
	DbManager(webnotes.local.conn).restore_database(db_name, source_sql, db_name, webnotes.conf.db_password)
	if verbose: print "Imported from database %s" % source_sql

def make_connection(root_login, root_password):
	if root_login:
		if not root_password:
			root_password = webnotes.conf.get("root_password") or None
		
		if not root_password:
			root_password = getpass.getpass("MySQL root password: ")
	return webnotes.db.Database(user=root_login, password=root_password)

def install_app(name, verbose=False):
	webnotes.flags.in_install_app = True
	webnotes.clear_cache()
	manage = webnotes.get_module(name + ".manage") 
	if hasattr(manage, "before_install"):
		manage.before_install()
	
	sync_for(name, force=True, sync_everything=True, verbose=verbose)

	if hasattr(manage, "after_install"):
		manage.after_install()

	set_all_patches_as_completed(name)
	installed_apps = json.loads(webnotes.conn.get_global("installed_apps") or "[]") or []
	installed_apps.append(name)
	webnotes.conn.set_global("installed_apps", json.dumps(installed_apps))
	webnotes.clear_cache()
	webnotes.conn.commit()
	
	from webnotes.website.doctype.website_sitemap_config.website_sitemap_config import rebuild_website_sitemap_config
	rebuild_website_sitemap_config()

	webnotes.clear_cache()
	webnotes.flags.in_install_app = False
	

def set_all_patches_as_completed(app):
	patch_path = os.path.join(webnotes.get_pymodule_path(app), "patches.txt")
	if os.path.exists(patch_path):
		for patch in webnotes.get_file_items(patch_path):
			webnotes.doc({
				"doctype": "Patch Log",
				"patch": patch
			}).insert()
		webnotes.conn.commit()
		
def make_conf(db_name=None, db_password=None, site_config=None):
	site = webnotes.local.site
	make_site_config(db_name, db_password, site_config)
	webnotes.destroy()
	webnotes.init(site)

def make_site_config(db_name=None, db_password=None, site_config=None):		
	webnotes.create_folder(os.path.join(webnotes.local.site_path))
	site_file = os.path.join(webnotes.local.site_path, "site_config.json")
	
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
