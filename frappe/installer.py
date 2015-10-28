# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# called from wnf.py
# lib/wnf.py --install [rootpassword] [dbname] [source]

from __future__ import unicode_literals

import os, json, sys
import frappe
import frappe.database
import getpass
import importlib
from frappe.model.db_schema import DbManager
from frappe.model.sync import sync_for
from frappe.utils.fixtures import sync_fixtures
from frappe.website import render, statics

def install_db(root_login="root", root_password=None, db_name=None, source_sql=None,
	admin_password=None, verbose=True, force=0, site_config=None, reinstall=False):
	make_conf(db_name, site_config=site_config)
	frappe.flags.in_install_db = True
	if reinstall:
		frappe.connect(db_name=db_name)
		dbman = DbManager(frappe.local.db)
		dbman.create_database(db_name)

	else:
		frappe.local.db = make_connection(root_login, root_password)
		frappe.local.session = frappe._dict({'user':'Administrator'})
		create_database_and_user(force, verbose)

	frappe.conf.admin_password = frappe.conf.admin_password or admin_password

	frappe.connect(db_name=db_name)
	check_if_ready_for_barracuda()
	import_db_from_sql(source_sql, verbose)
	remove_missing_apps()

	create_auth_table()
	frappe.flags.in_install_db = False

def get_current_host():
	return frappe.db.sql("select user()")[0][0].split('@')[1]

def create_database_and_user(force, verbose):
	db_name = frappe.local.conf.db_name
	dbman = DbManager(frappe.local.db)
	if force or (db_name not in dbman.get_database_list()):
		dbman.delete_user(db_name, get_current_host())
		dbman.drop_database(db_name)
	else:
		raise Exception("Database %s already exists" % (db_name,))

	dbman.create_user(db_name, frappe.conf.db_password, get_current_host())
	if verbose: print "Created user %s" % db_name

	dbman.create_database(db_name)
	if verbose: print "Created database %s" % db_name

	dbman.grant_all_privileges(db_name, db_name, get_current_host())
	dbman.flush_privileges()
	if verbose: print "Granted privileges to user %s and database %s" % (db_name, db_name)

	# close root connection
	frappe.db.close()

def create_auth_table():
	frappe.db.sql_ddl("""create table if not exists __Auth (
		`user` VARCHAR(180) NOT NULL PRIMARY KEY,
		`password` VARCHAR(180) NOT NULL
		) ENGINE=InnoDB DEFAULT CHARSET=utf8""")

def import_db_from_sql(source_sql, verbose):
	if verbose: print "Starting database import..."
	db_name = frappe.conf.db_name
	if not source_sql:
		source_sql = os.path.join(os.path.dirname(frappe.__file__), 'data', 'Framework.sql')
	DbManager(frappe.local.db).restore_database(db_name, source_sql, db_name, frappe.conf.db_password)
	if verbose: print "Imported from database %s" % source_sql

def make_connection(root_login, root_password):
	if root_login:
		if not root_password:
			root_password = frappe.conf.get("root_password") or None

		if not root_password:
			root_password = getpass.getpass("MySQL root password: ")
	return frappe.database.Database(user=root_login, password=root_password)

def install_app(name, verbose=False, set_as_patched=True):
	frappe.clear_cache()
	app_hooks = frappe.get_hooks(app_name=name)
	installed_apps = frappe.get_installed_apps()

	# install pre-requisites
	if app_hooks.required_apps:
		for app in app_hooks.required_apps:
			install_app(app)

	frappe.flags.in_install = name
	frappe.clear_cache()

	if name not in frappe.get_all_apps(with_frappe=True):
		raise Exception("App not in apps.txt")

	if name in installed_apps:
		frappe.msgprint("App {0} already installed".format(name))
		return

	print "Installing {0}...".format(name)

	if name != "frappe":
		frappe.only_for("System Manager")

	for before_install in app_hooks.before_install or []:
		frappe.get_attr(before_install)()

	if name != "frappe":
		add_module_defs(name)

	sync_for(name, force=True, sync_everything=True, verbose=verbose)

	add_to_installed_apps(name)

	if set_as_patched:
		set_all_patches_as_completed(name)

	for after_install in app_hooks.after_install or []:
		frappe.get_attr(after_install)()

	print "Installing fixtures..."
	sync_fixtures(name)

	frappe.flags.in_install = False

def add_to_installed_apps(app_name, rebuild_website=True):
	installed_apps = frappe.get_installed_apps()
	if not app_name in installed_apps:
		installed_apps.append(app_name)
		frappe.db.set_global("installed_apps", json.dumps(installed_apps))
		frappe.db.commit()
		post_install(rebuild_website)

def remove_from_installed_apps(app_name):
	installed_apps = frappe.get_installed_apps()
	if app_name in installed_apps:
		installed_apps.remove(app_name)
		frappe.db.set_global("installed_apps", json.dumps(installed_apps))
		frappe.db.commit()
		if frappe.flags.in_install:
			post_install()

def remove_app(app_name, dry_run=False):
	"""Delete app and all linked to the app's module with the app."""

	if not dry_run:
		confirm = raw_input("All doctypes (including custom), modules related to this app will be deleted. Are you sure you want to continue (y/n) ? ")
		if confirm!="y":
			return

	from frappe.utils.backups import scheduled_backup
	print "Backing up..."
	scheduled_backup(ignore_files=True)

	# remove modules, doctypes, roles
	for module_name in frappe.get_module_list(app_name):
		for doctype in frappe.get_list("DocType", filters={"module": module_name},
			fields=["name", "issingle"]):
			print "removing {0}...".format(doctype.name)
			# drop table

			if not dry_run:
				if not doctype.issingle:
					frappe.db.sql("drop table `tab{0}`".format(doctype.name))
				frappe.delete_doc("DocType", doctype.name)

		print "removing Module {0}...".format(module_name)
		if not dry_run:
			frappe.delete_doc("Module Def", module_name)

	remove_from_installed_apps(app_name)

def post_install(rebuild_website=False):
	if rebuild_website:
		render.clear_cache()
		statics.sync().start()

	init_singles()
	frappe.db.commit()
	frappe.clear_cache()

def set_all_patches_as_completed(app):
	patch_path = os.path.join(frappe.get_pymodule_path(app), "patches.txt")
	if os.path.exists(patch_path):
		for patch in frappe.get_file_items(patch_path):
			frappe.get_doc({
				"doctype": "Patch Log",
				"patch": patch
			}).insert()
		frappe.db.commit()

def init_singles():
	singles = [single['name'] for single in frappe.get_all("DocType", filters={'issingle': True})]
	for single in singles:
		if not frappe.db.get_singles_dict(single):
			doc = frappe.new_doc(single)
			doc.flags.ignore_mandatory=True
			doc.flags.ignore_validate=True
			doc.save()

def make_conf(db_name=None, db_password=None, site_config=None):
	site = frappe.local.site
	make_site_config(db_name, db_password, site_config)
	sites_path = frappe.local.sites_path
	frappe.destroy()
	frappe.init(site, sites_path=sites_path)

def make_site_config(db_name=None, db_password=None, site_config=None):
	frappe.create_folder(os.path.join(frappe.local.site_path))
	site_file = get_site_config_path()

	if not os.path.exists(site_file):
		if not (site_config and isinstance(site_config, dict)):
			site_config = get_conf_params(db_name, db_password)

		with open(site_file, "w") as f:
			f.write(json.dumps(site_config, indent=1, sort_keys=True))

def update_site_config(key, value):
	"""Update a value in site_config"""
	with open(get_site_config_path(), "r") as f:
		site_config = json.loads(f.read())

	# int
	try:
		value = int(value)
	except ValueError:
		pass

	# boolean
	if value in ("False", "True"):
		value = eval(value)

	# remove key if value is None
	if value == "None":
		if key in site_config:
			del site_config[key]
	else:
		site_config[key] = value

	with open(get_site_config_path(), "w") as f:
		f.write(json.dumps(site_config, indent=1, sort_keys=True))

def get_site_config_path():
	return os.path.join(frappe.local.site_path, "site_config.json")

def get_conf_params(db_name=None, db_password=None):
	if not db_name:
		db_name = raw_input("Database Name: ")
		if not db_name:
			raise Exception("Database Name Required")

	if not db_password:
		from frappe.utils import random_string
		db_password = random_string(16)

	return {"db_name": db_name, "db_password": db_password}

def make_site_dirs():
	site_public_path = os.path.join(frappe.local.site_path, 'public')
	site_private_path = os.path.join(frappe.local.site_path, 'private')
	for dir_path in (
			os.path.join(site_private_path, 'backups'),
			os.path.join(site_public_path, 'files'),
			os.path.join(frappe.local.site_path, 'task-logs')):
		if not os.path.exists(dir_path):
			os.makedirs(dir_path)
	locks_dir = frappe.get_site_path('locks')
	if not os.path.exists(locks_dir):
			os.makedirs(locks_dir)

def add_module_defs(app):
	modules = frappe.get_module_list(app)
	for module in modules:
		d = frappe.new_doc("Module Def")
		d.app_name = app
		d.module_name = module
		d.save(ignore_permissions=True)

def remove_missing_apps():
	apps = ('frappe_subscription', 'shopping_cart')
	installed_apps = json.loads(frappe.db.get_global("installed_apps") or "[]")
	for app in apps:
		if app in installed_apps:
			try:
				importlib.import_module(app)

			except ImportError:
				installed_apps.remove(app)
				frappe.db.set_global("installed_apps", json.dumps(installed_apps))

def check_if_ready_for_barracuda():
	mariadb_variables = frappe._dict(frappe.db.sql("""show variables"""))
	for key, value in {
			"innodb_file_format": "Barracuda",
			"innodb_file_per_table": "ON",
			"innodb_large_prefix": "ON",
			"character_set_server": "utf8mb4",
			"collation_server": "utf8mb4_unicode_ci"
		}.items():

		if mariadb_variables.get(key) != value:
			print "="*80
			print "Please add this to MariaDB's my.cnf and restart MariaDB before proceeding"
			print
			print expected_config_for_barracuda
			print "="*80
			sys.exit(1)
			# raise Exception, "MariaDB needs to be configured!"

expected_config_for_barracuda = """[mysqld]
innodb-file-format=barracuda
innodb-file-per-table=1
innodb-large-prefix=1
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
"""
