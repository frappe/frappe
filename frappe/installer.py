# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import configparser
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from collections import OrderedDict
from contextlib import suppress
from shutil import which

import click
from semantic_version import Version

import frappe
from frappe.defaults import _clear_cache
from frappe.utils import cint, is_git_url
from frappe.utils.dashboard import sync_dashboards
from frappe.utils.synchronization import filelock


def _is_scheduler_enabled(site) -> bool:
	enable_scheduler = False
	try:
		frappe.init(site)
		frappe.connect()
		enable_scheduler = cint(frappe.db.get_single_value("System Settings", "enable_scheduler"))
	except Exception:
		pass
	finally:
		frappe.db.close()

	return bool(enable_scheduler)


def _new_site(
	db_name,
	site,
	db_root_username=None,
	db_root_password=None,
	admin_password=None,
	verbose=False,
	install_apps=None,
	source_sql=None,
	force=False,
	db_password=None,
	db_type=None,
	db_socket=None,
	db_host=None,
	db_port=None,
	db_user=None,
	setup_db=True,
	rollback_callback=None,
	mariadb_user_host_login_scope=None,
):
	"""Install a new Frappe site"""

	from frappe.utils import scheduler

	if not force and os.path.exists(site):
		print(f"Site {site} already exists, use `--force` to proceed anyway")
		sys.exit(1)

	frappe.init(site)

	if not db_name:
		db_name = f"_{frappe.generate_hash(length=16)}"

	try:
		# enable scheduler post install?
		enable_scheduler = _is_scheduler_enabled(site)
	except Exception:
		enable_scheduler = False

	make_site_dirs()
	if rollback_callback:
		rollback_callback.add(lambda: shutil.rmtree(frappe.get_site_path()))

	with filelock("bench_new_site", timeout=1):
		install_db(
			root_login=db_root_username,
			root_password=db_root_password,
			db_name=db_name,
			admin_password=admin_password,
			verbose=verbose,
			source_sql=source_sql,
			force=force,
			db_password=db_password,
			db_type=db_type,
			db_socket=db_socket,
			db_host=db_host,
			db_port=db_port,
			db_user=db_user,
			setup=setup_db,
			rollback_callback=rollback_callback,
			mariadb_user_host_login_scope=mariadb_user_host_login_scope,
		)

		apps_to_install = ["frappe"] + (frappe.conf.get("install_apps") or []) + (list(install_apps or []))

		for app in apps_to_install:
			# NOTE: not using force here for 2 reasons:
			# 	1. It's not really needed here as we've freshly installed a new db
			# 	2. If someone uses a sql file to do restore and that file already had
			# 		installed_apps then it might cause problems as that sql file can be of any previous version(s)
			# 		which might be incompatible with the current version and using force might cause problems.
			# 		Example: the DocType DocType might not have `migration_hash` column which will cause failure in the restore.
			install_app(app, verbose=verbose, set_as_patched=not source_sql, force=False)

		scheduler.toggle_scheduler(enable_scheduler)
		frappe.db.commit()

	scheduler_status = "disabled" if frappe.utils.scheduler.is_scheduler_disabled() else "enabled"
	print("*** Scheduler is", scheduler_status, "***")


def install_db(
	root_login=None,
	root_password=None,
	db_name=None,
	source_sql=None,
	admin_password=None,
	verbose=True,
	force=0,
	site_config=None,
	db_password=None,
	db_type=None,
	db_socket=None,
	db_host=None,
	db_port=None,
	db_user=None,
	setup=True,
	rollback_callback=None,
	mariadb_user_host_login_scope=None,
):
	import frappe.database
	from frappe.database import bootstrap_database, drop_user_and_database, setup_database

	if not db_type:
		db_type = frappe.conf.db_type

	make_conf(
		db_name,
		site_config=site_config,
		db_password=db_password,
		db_type=db_type,
		db_socket=db_socket,
		db_host=db_host,
		db_port=db_port,
		db_user=db_user,
	)
	frappe.flags.in_install_db = True

	if root_login:
		frappe.flags.root_login = root_login

	if root_password:
		frappe.flags.root_password = root_password

	if setup:
		setup_database(force, verbose, mariadb_user_host_login_scope)
		if rollback_callback:
			rollback_callback.add(lambda: drop_user_and_database(db_name, db_user or db_name))

	bootstrap_database(
		verbose=verbose,
		source_sql=source_sql,
	)

	frappe.conf.admin_password = frappe.conf.admin_password or admin_password

	remove_missing_apps()

	frappe.db.create_auth_table()
	frappe.db.create_global_search_table()
	frappe.db.create_user_settings_table()

	frappe.flags.in_install_db = False


def find_org(org_repo: str) -> tuple[str, str]:
	"""find the org a repo is in

	find_org()
	ref -> https://github.com/frappe/bench/blob/develop/bench/utils/__init__.py#L390

	:param org_repo:
	:type org_repo: str

	:raises InvalidRemoteException: if the org is not found

	:return: organisation and repository
	:rtype: Tuple[str, str]
	"""
	import requests

	from frappe.exceptions import InvalidRemoteException

	for org in ["frappe", "erpnext"]:
		response = requests.head(f"https://api.github.com/repos/{org}/{org_repo}")
		if response.status_code == 400:
			response = requests.head(f"https://github.com/{org}/{org_repo}")
		if response.ok:
			return org, org_repo

	raise InvalidRemoteException


def fetch_details_from_tag(_tag: str) -> tuple[str, str, str]:
	"""parse org, repo, tag from string

	fetch_details_from_tag()
	ref -> https://github.com/frappe/bench/blob/develop/bench/utils/__init__.py#L403

	:param _tag: input string
	:type _tag: str

	:return: organisation, repostitory, tag
	:rtype: Tuple[str, str, str]
	"""
	app_tag = _tag.split("@")
	org_repo = app_tag[0].split("/")

	try:
		repo, tag = app_tag
	except ValueError:
		repo, tag = [*app_tag, None]

	try:
		org, repo = org_repo
	except Exception:
		org, repo = find_org(org_repo[0])

	return org, repo, tag


def parse_app_name(name: str) -> str:
	"""parse repo name from name

	__setup_details_from_git()
	ref -> https://github.com/frappe/bench/blob/develop/bench/app.py#L114


	:param name: git tag
	:type name: str

	:return: repository name
	:rtype: str
	"""
	name = name.rstrip("/")
	if os.path.exists(name):
		repo = os.path.split(name)[-1]
	elif is_git_url(name):
		if name.startswith("git@") or name.startswith("ssh://"):
			_repo = name.split(":")[1].rsplit("/", 1)[1]
		else:
			_repo = name.rsplit("/", 2)[2]
		repo = _repo.split(".", 1)[0]
	else:
		_, repo, _ = fetch_details_from_tag(name)
	return repo


def install_app(name, verbose=False, set_as_patched=True, force=False):
	from frappe.core.doctype.scheduled_job_type.scheduled_job_type import sync_jobs
	from frappe.model.sync import sync_for
	from frappe.modules.utils import sync_customizations
	from frappe.utils.fixtures import sync_fixtures

	frappe.flags.in_install = name
	frappe.flags.ignore_in_install = False

	frappe.clear_cache()
	app_hooks = frappe.get_hooks(app_name=name)
	installed_apps = frappe.get_installed_apps()

	# install pre-requisites
	if app_hooks.required_apps:
		for app in app_hooks.required_apps:
			required_app = parse_app_name(app)
			install_app(required_app, verbose=verbose)

	frappe.flags.in_install = name
	frappe.clear_cache()

	if name not in frappe.get_all_apps():
		raise Exception(f"App {name} not in apps.txt")

	if not force and name in installed_apps:
		click.secho(f"App {name} already installed", fg="yellow")
		return

	print(f"\nInstalling {name}...")

	if name != "frappe":
		frappe.only_for("System Manager")

	for before_install in app_hooks.before_install or []:
		out = frappe.get_attr(before_install)()
		if out is False:
			return

	for fn in frappe.get_hooks("before_app_install"):
		frappe.get_attr(fn)(name)

	if name != "frappe":
		add_module_defs(name, ignore_if_duplicate=force)

	sync_for(name, force=force, reset_permissions=True)

	add_to_installed_apps(name)

	frappe.get_doc("Portal Settings", "Portal Settings").sync_menu()

	if set_as_patched:
		set_all_patches_as_completed(name)

	for after_install in app_hooks.after_install or []:
		frappe.get_attr(after_install)()

	for fn in frappe.get_hooks("after_app_install"):
		frappe.get_attr(fn)(name)

	sync_jobs()
	sync_fixtures(name)
	sync_customizations(name)
	sync_dashboards(name)

	for after_sync in app_hooks.after_sync or []:
		frappe.get_attr(after_sync)()  #

	frappe.flags.in_install = False


def add_to_installed_apps(app_name, rebuild_website=True):
	installed_apps = frappe.get_installed_apps()
	if app_name not in installed_apps:
		installed_apps.append(app_name)
		frappe.db.set_global("installed_apps", json.dumps(installed_apps))
		frappe.db.commit()
		if frappe.flags.in_install:
			post_install(rebuild_website)

	frappe.get_single("Installed Applications").update_versions()


def remove_from_installed_apps(app_name):
	installed_apps = frappe.get_installed_apps()
	if app_name in installed_apps:
		installed_apps.remove(app_name)
		frappe.db.set_value(
			"DefaultValue", {"defkey": "installed_apps"}, "defvalue", json.dumps(installed_apps)
		)
		_clear_cache("__global")
		frappe.db.commit()
		if frappe.flags.in_install:
			post_install()


def remove_app(app_name, dry_run=False, yes=False, no_backup=False, force=False):
	"""Remove app and all linked to the app's module with the app from a site."""

	site = frappe.local.site
	app_hooks = frappe.get_hooks(app_name=app_name)

	# dont allow uninstall app if not installed unless forced
	if not force:
		if app_name not in frappe.get_installed_apps():
			click.secho(f"App {app_name} not installed on Site {site}", fg="yellow")
			return

	# Don't allow uninstalling if we have dependent apps installed
	for app in frappe.get_installed_apps():
		if app != app_name:
			hooks = frappe.get_hooks(app_name=app)
			if hooks.required_apps and any(app_name in required_app for required_app in hooks.required_apps):
				click.secho(f"App {app_name} is a dependency of {app}. Uninstall {app} first.", fg="yellow")
				return

	print(f"Uninstalling App {app_name} from Site {site}...")

	if not dry_run and not yes:
		confirm = click.confirm(
			"All doctypes (including custom), modules related to this app will be"
			" deleted. Are you sure you want to continue?"
		)
		if not confirm:
			return

	if not (dry_run or no_backup):
		from frappe.utils.backups import scheduled_backup

		print("Backing up...")
		scheduled_backup(ignore_files=True)

	frappe.flags.in_uninstall = True

	for before_uninstall in app_hooks.before_uninstall or []:
		frappe.get_attr(before_uninstall)()

	for fn in frappe.get_hooks("before_app_uninstall"):
		frappe.get_attr(fn)(app_name)

	modules = frappe.get_all("Module Def", filters={"app_name": app_name}, pluck="name")

	drop_doctypes = _delete_modules(modules, dry_run=dry_run)
	_delete_doctypes(drop_doctypes, dry_run=dry_run)

	if not dry_run:
		remove_from_installed_apps(app_name)
		frappe.get_single("Installed Applications").update_versions()
		frappe.db.commit()

	for after_uninstall in app_hooks.after_uninstall or []:
		frappe.get_attr(after_uninstall)()

	for fn in frappe.get_hooks("after_app_uninstall"):
		frappe.get_attr(fn)(app_name)

	click.secho(f"Uninstalled App {app_name} from Site {site}", fg="green")
	frappe.flags.in_uninstall = False


def _delete_modules(modules: list[str], dry_run: bool) -> list[str]:
	"""Delete modules belonging to the app and all related doctypes.

	Note: All record linked linked to Module Def are also deleted.

	Return: list of deleted doctypes."""
	drop_doctypes = []

	doctype_link_field_map = _get_module_linked_doctype_field_map()
	for module_name in modules:
		print(f"Deleting Module '{module_name}'")

		for doctype in frappe.get_all(
			"DocType", filters={"module": module_name}, fields=["name", "issingle"]
		):
			print(f"* removing DocType '{doctype.name}'...")

			if not dry_run:
				if doctype.issingle:
					frappe.delete_doc("DocType", doctype.name, ignore_on_trash=True, force=True)
				else:
					drop_doctypes.append(doctype.name)

		_delete_linked_documents(module_name, doctype_link_field_map, dry_run=dry_run)

		print(f"* removing Module Def '{module_name}'...")
		if not dry_run:
			frappe.delete_doc("Module Def", module_name, ignore_on_trash=True, force=True)

	return drop_doctypes


def _delete_linked_documents(module_name: str, doctype_linkfield_map: dict[str, str], dry_run: bool) -> None:
	"""Deleted all records linked with module def"""
	for doctype, fieldname in doctype_linkfield_map.items():
		for record in frappe.get_all(doctype, filters={fieldname: module_name}, pluck="name"):
			print(f"* removing {doctype} '{record}'...")
			if not dry_run:
				frappe.delete_doc(doctype, record, ignore_on_trash=True, force=True)


def _get_module_linked_doctype_field_map() -> dict[str, str]:
	"""Get all the doctypes which have module linked with them.

	Return ordered dictionary with doctype->link field mapping."""

	# Hardcoded to change order of deletion
	ordered_doctypes = [
		("Workspace", "module"),
		("Report", "module"),
		("Page", "module"),
		("Web Form", "module"),
	]
	doctype_to_field_map = OrderedDict(ordered_doctypes)

	linked_doctypes = frappe.get_all(
		"DocField",
		filters={"fieldtype": "Link", "options": "Module Def"},
		fields=["parent", "fieldname"],
	)
	existing_linked_doctypes = [d for d in linked_doctypes if frappe.db.exists("DocType", d.parent)]

	for d in existing_linked_doctypes:
		# DocType deletion is handled separately in the end
		if d.parent not in doctype_to_field_map and d.parent != "DocType":
			doctype_to_field_map[d.parent] = d.fieldname

	return doctype_to_field_map


def _delete_doctypes(doctypes: list[str], dry_run: bool) -> None:
	for doctype in set(doctypes):
		print(f"* dropping Table for '{doctype}'...")
		if not dry_run:
			frappe.delete_doc("DocType", doctype, ignore_on_trash=True, force=True)
			frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `tab{doctype}`")


def post_install(rebuild_website=False):
	from frappe.website.utils import clear_website_cache

	if rebuild_website:
		clear_website_cache()

	init_singles()
	frappe.db.commit()
	frappe.clear_cache()


def set_all_patches_as_completed(app):
	from frappe.modules.patch_handler import get_patches_from_app

	patches = get_patches_from_app(app)
	for patch in patches:
		frappe.get_doc({"doctype": "Patch Log", "patch": patch}).insert(ignore_permissions=True)
	frappe.db.commit()


def init_singles():
	singles = frappe.get_all("DocType", filters={"issingle": True}, pluck="name")
	for single in singles:
		if frappe.db.get_singles_dict(single):
			continue

		try:
			doc = frappe.new_doc(single)
			doc.flags.ignore_mandatory = True
			doc.flags.ignore_validate = True
			doc.save()
		except (ImportError, frappe.DoesNotExistError):
			# The doctype exists, but controller is deleted,
			# no need to attempt to init such single, ref: #16917
			continue


def make_conf(
	db_name=None,
	db_password=None,
	site_config=None,
	db_type=None,
	db_socket=None,
	db_host=None,
	db_port=None,
	db_user=None,
):
	site = frappe.local.site
	make_site_config(
		db_name,
		db_password,
		site_config,
		db_type=db_type,
		db_socket=db_socket,
		db_host=db_host,
		db_port=db_port,
		db_user=db_user,
	)
	sites_path = frappe.local.sites_path
	frappe.destroy()
	frappe.init(site, sites_path=sites_path)


def make_site_config(
	db_name=None,
	db_password=None,
	site_config=None,
	db_type=None,
	db_socket=None,
	db_host=None,
	db_port=None,
	db_user=None,
):
	frappe.create_folder(os.path.join(frappe.local.site_path))
	site_file = get_site_config_path()

	if not os.path.exists(site_file):
		if not (site_config and isinstance(site_config, dict)):
			site_config = get_conf_params(db_name, db_password)

			if db_type:
				site_config["db_type"] = db_type

			if db_type == "sqlite":
				site_config["db_name"] = db_name

			else:
				if db_socket:
					site_config["db_socket"] = db_socket

				if db_host:
					site_config["db_host"] = db_host

				if db_port:
					site_config["db_port"] = db_port

				site_config["db_user"] = db_user or db_name

		with open(site_file, "w") as f:
			f.write(json.dumps(site_config, indent=1, sort_keys=True))


def update_site_config(key, value, validate=True, site_config_path=None):
	"""Update a value in site_config"""
	from frappe.config import clear_site_config_cache
	from frappe.utils.synchronization import filelock

	if not site_config_path:
		site_config_path = get_site_config_path()

	# Sometimes global config file is passed directly to this function
	_is_global_conf = "common_site_config" in site_config_path

	with filelock("site_config", is_global=_is_global_conf):
		_update_config_file(key=key, value=value, config_file=site_config_path)
		clear_site_config_cache()


def _update_config_file(key: str, value, config_file: str):
	"""Updates site or common config"""
	with open(config_file) as f:
		site_config = json.loads(f.read())

	# In case of non-int value
	if value in ("0", "1"):
		value = int(value)

	# boolean
	if value == "false":
		value = False
	if value == "true":
		value = True

	# remove key if value is None
	if value == "None":
		if key in site_config:
			del site_config[key]
	else:
		site_config[key] = value

	with open(config_file, "w") as f:
		f.write(json.dumps(site_config, indent=1, sort_keys=True))

	if hasattr(frappe.local, "conf"):
		frappe.local.conf[key] = value


def get_site_config_path():
	return os.path.join(frappe.local.site_path, "site_config.json")


def get_conf_params(db_name=None, db_password=None):
	if not db_name:
		db_name = input("Database Name: ")
		if not db_name:
			raise Exception("Database Name Required")

	if not db_password:
		from frappe.utils import random_string

		db_password = random_string(16)

	return {"db_name": db_name, "db_password": db_password}


def make_site_dirs():
	for dir_path in [
		os.path.join("public", "files"),
		os.path.join("private", "backups"),
		os.path.join("private", "files"),
		"locks",
		"logs",
	]:
		path = frappe.get_site_path(dir_path)
		os.makedirs(path, exist_ok=True)


def add_module_defs(app, ignore_if_duplicate=False):
	modules = frappe.get_module_list(app)
	for module in modules:
		d = frappe.new_doc("Module Def")
		d.app_name = app
		d.module_name = module
		d.insert(ignore_permissions=True, ignore_if_duplicate=ignore_if_duplicate)


def remove_missing_apps():
	import importlib

	apps = ("frappe_subscription", "shopping_cart")
	installed_apps = json.loads(frappe.db.get_global("installed_apps") or "[]")
	for app in apps:
		if app in installed_apps:
			try:
				importlib.import_module(app)

			except ImportError:
				installed_apps.remove(app)
				frappe.db.set_global("installed_apps", json.dumps(installed_apps))


def convert_archive_content(sql_file_path):
	if frappe.conf.db_type == "mariadb":
		# ever since mariaDB 10.6, row_format COMPRESSED has been deprecated and removed
		# this step is added to ease restoring sites depending on older mariaDB servers
		# This change was reverted by mariadb in 10.6.6
		# Ref: https://mariadb.com/kb/en/innodb-compressed-row-format/#read-only
		from pathlib import Path

		from frappe.utils import random_string

		version = _guess_mariadb_version()
		if not version or (version <= (10, 6, 0) or version >= (10, 6, 6)):
			return

		click.secho(
			"MariaDB version being used does not support ROW_FORMAT=COMPRESSED, "
			"converting into DYNAMIC format.",
			fg="yellow",
		)

		old_sql_file_path = Path(f"{sql_file_path}_{random_string(10)}")
		sql_file_path = Path(sql_file_path)

		os.rename(sql_file_path, old_sql_file_path)
		sql_file_path.touch()

		with open(old_sql_file_path) as r, open(sql_file_path, "a") as w:
			for line in r:
				w.write(line.replace("ROW_FORMAT=COMPRESSED", "ROW_FORMAT=DYNAMIC"))

		old_sql_file_path.unlink()


def _guess_mariadb_version() -> tuple[int] | None:
	# Using command-line because we *might* not have a connection yet and this command is required
	# in non-interactive mode.
	# Use db.sql("select version()") instead if connection is available.
	with suppress(Exception):
		mariadb = which("mariadb") or which("mysql")
		version_output = subprocess.getoutput(f"{mariadb} --version")
		version_regex = r"(?P<version>\d+\.\d+\.\d+)-MariaDB"

		version = re.search(version_regex, version_output).group("version")

		return tuple(int(v) for v in version.split("."))


def extract_files(site_name, file_path):
	import shutil
	import subprocess

	from frappe.utils import get_bench_relative_path

	file_path = get_bench_relative_path(file_path)

	# Need to do frappe.init to maintain the site locals
	frappe.init(site_name)
	abs_site_path = os.path.abspath(frappe.get_site_path())

	# Copy the files to the parent directory and extract
	shutil.copy2(os.path.abspath(file_path), abs_site_path)

	# Get the file name splitting the file path on
	tar_name = os.path.split(file_path)[1]
	tar_path = os.path.join(abs_site_path, tar_name)

	try:
		if file_path.endswith(".tar"):
			subprocess.check_output(["tar", "xvf", tar_path, "--strip", "2"], cwd=abs_site_path)
		elif file_path.endswith(".tgz"):
			subprocess.check_output(["tar", "zxvf", tar_path, "--strip", "2"], cwd=abs_site_path)
	except Exception:
		raise
	finally:
		frappe.destroy()

	return tar_path


def is_downgrade(sql_file_path, verbose=False):
	"""Check if input db backup will get downgraded on current bench

	This function is only tested with mariadb.
	TODO: Add postgres support
	"""
	if frappe.conf.db_type != "mariadb":
		return False

	backup_version = get_backup_version(sql_file_path) or get_old_backup_version(sql_file_path)
	current_version = Version(frappe.__version__)

	# Assume it's not a downgrade if we can't determine backup version
	if backup_version is None:
		return False

	is_downgrade = backup_version > current_version

	if verbose and is_downgrade:
		print(f"Your site is currently on Frappe {current_version} and your backup is {backup_version}.")

	return is_downgrade


def get_old_backup_version(sql_file_path: str) -> Version | None:
	"""Return the frappe version used to create the specified database dump.

	This methods supports older versions of Frappe wich used a different format.
	"""
	header = get_db_dump_header(sql_file_path).split("\n")
	if match := re.search(r"Frappe (\d+\.\d+\.\d+)", header[0]):
		return Version(match[1])
	return None


def get_backup_version(sql_file_path: str) -> Version | None:
	"""Return the frappe version used to create the specified database dump."""
	header = get_db_dump_header(sql_file_path).split("\n")
	metadata = ""
	if "begin frappe metadata" in header[0]:
		for line in header[1:]:
			if "end frappe metadata" in line:
				break
			metadata += line.replace("--", "").strip() + "\n"
		parser = configparser.ConfigParser()
		parser.read_string(metadata)
		return Version(parser["frappe"]["version"])

	return None


def is_partial(sql_file_path: str) -> bool:
	"""
	Function to return whether the database dump is a partial backup or not

	:param sql_file_path: path to the database dump file
	:return: True if the database dump is a partial backup, False otherwise
	"""
	if frappe.conf.db_type == "sqlite":
		return False

	header = get_db_dump_header(sql_file_path)
	return "Partial Backup" in header


def partial_restore(sql_file_path, verbose=False):
	if frappe.conf.db_type == "mariadb":
		from frappe.database.mariadb.setup_db import import_db_from_sql
	elif frappe.conf.db_type == "postgres":
		import warnings

		from frappe.database.postgres.setup_db import import_db_from_sql

		warn = click.style(
			"Delete the tables you want to restore manually before attempting"
			" partial restore operation for PostgreSQL databases",
			fg="yellow",
		)
		warnings.warn(warn, stacklevel=2)
	else:
		click.secho("Unsupported database type", fg="red")
		return

	import_db_from_sql(source_sql=sql_file_path, verbose=verbose)


def validate_database_sql(path: str, _raise: bool = True) -> None:
	"""Check if file has contents and if `__Auth` table exists

	Args:
	        path (str): Path of the decompressed SQL file
	        _raise (bool, optional): Raise exception if invalid file. Defaults to True.
	"""

	if path.endswith(".gz"):
		executable_name = "zgrep"
	else:
		executable_name = "grep"

	if os.path.getsize(path):
		if (executable := which(executable_name)) is None:
			frappe.throw(
				f"`{executable_name}` not found in PATH! This is required to take a backup.",
				exc=frappe.ExecutableNotFound,
			)
		try:
			frappe.utils.execute_in_shell(f"{executable} -m1 __Auth {path}", check_exit_code=True)
			return
		except Exception:
			error_message = "Table `__Auth` not found in file."
	else:
		error_message = f"{path} is an empty file!"

	if error_message:
		click.secho(error_message, fg="red")

	if _raise:
		raise frappe.InvalidDatabaseFile


def get_db_dump_header(file_path: str, file_bytes: int = 256) -> str:
	"""
	Get the header of a database dump file

	:param file_path: path to the database dump file
	:param file_bytes: number of bytes to read from the file
	:return: The first few bytes of the file as requested
	"""

	# Use `gzip` to open the file if the extension is `.gz`
	if file_path.endswith(".gz"):
		with gzip.open(file_path, "rb") as f:
			return f.read(file_bytes).decode()

	with open(file_path, "rb") as f:
		return f.read(file_bytes).decode()
