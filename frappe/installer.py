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
from frappe import _
from frappe.defaults import _clear_cache
from frappe.utils import cint, comma_and, is_git_url
from frappe.utils.dashboard import sync_dashboards
from frappe.utils.synchronization import filelock

APP_STATE_LOCK = "toggle_app_state"


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

	clear_site_locks()
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
	frappe.db.create_sequence_table()

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
	elif name in frappe.get_all_apps():
		return name
	else:
		_, repo, _ = fetch_details_from_tag(name)
	return repo


def parse_required_app_name(requirement: str) -> str:
	"""Parse the app name out of a `required_apps` entry.

	Entries can be `erpnext`, `frappe/erpnext`, a git URL or any of those with an `@branch`.
	Unlike `parse_app_name`, this resolves the name locally, so it is safe to call for an app
	that is not present on the bench.
	"""
	name = requirement.rstrip("/").split("#")[0]
	name = name.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
	return name.split("@")[0].removesuffix(".git")


def is_required_by(app_name: str, dependent_app: str) -> bool:
	"""Check if `dependent_app` declares `app_name` in its `required_apps` hook.

	Entries are parsed before comparing. Matching the raw string instead would flag any app whose
	name happens to be a substring of a requirement, e.g. `appe` against `frappe/erpnext`.
	"""
	return any(
		app_name == parse_required_app_name(required_app)
		for required_app in frappe.get_hooks("required_apps", app_name=dependent_app)
	)


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
		if name in frappe.get_disabled_apps():
			enable_app(name)
		else:
			click.secho(f"App {name} already installed", fg="yellow")
		return

	print(f"\nInstalling {name}...")

	other_class_overrides = frappe.get_hooks("override_doctype_class")
	if (
		other_class_overrides
		and app_hooks.override_doctype_class
		and any(dt in app_hooks.override_doctype_class for dt in other_class_overrides)
	):
		click.secho(f"App {name} overrides a doctype that is already overridden by another app.", fg="yellow")

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

	if name not in (frappe.local.app_modules or {}):
		frappe.cache.delete_value("app_modules")
		frappe.setup_module_map(include_all_apps=True)

	sync_for(name, force=force, reset_permissions=True)

	if name == "frappe":
		# The framework's own rows can only be written after the sync, because a bare site has no
		# `tabModule Def` for them to go in, which is why the call above skips `frappe`.
		#
		# They used to arrive as a side effect of `make_module_and_roles`, which gives a module a
		# row when one of its doctypes is synced, so a module shipping no doctype got none. That
		# never mattered until the framework split its navigation, and a nav-only module carrying
		# a workspace and a sidebar now falls through it. The fixtures still import, since
		# `import_file` ignores links, but a module with no row does not exist as far as the site
		# is concerned: it is absent from every module list the desk builds, so the module is
		# missing from the dock on a fresh site and present on a migrated one.
		add_module_defs(name, ignore_if_duplicate=True)

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

	frappe.clear_cache()
	frappe.client_cache.erase_persistent_caches()
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
	frappe.db.commit()
	_sync_installed_apps_to_site_config()


def remove_from_installed_apps(app_name):
	installed_apps = frappe.get_installed_apps()
	if app_name in installed_apps:
		installed_apps.remove(app_name)
		frappe.db.set_value(
			"DefaultValue", {"defkey": "installed_apps"}, "defvalue", json.dumps(installed_apps)
		)
		_clear_cache("__global")
		frappe.local.doc_events_hooks = None
		with filelock(APP_STATE_LOCK):
			if app_name in frappe.get_disabled_apps():
				set_app_disabled(app_name, False)
			frappe.get_single("Installed Applications").update_versions()
			frappe.db.commit()
		if frappe.flags.in_install:
			post_install()
		_sync_installed_apps_to_site_config()


def set_app_disabled(app_name, disabled):
	"""Add the app to the `disabled_apps` global, or take it out again.

	The caller holds the `APP_STATE_LOCK` and owns the commit, so that the read and
	the write below cannot interleave with another toggle.
	"""
	# read the global directly: `get_disabled_apps` is request cached and may be stale here
	disabled_apps = json.loads(frappe.db.get_global("disabled_apps") or "[]")

	if disabled and app_name not in disabled_apps:
		disabled_apps.append(app_name)
	elif not disabled and app_name in disabled_apps:
		disabled_apps.remove(app_name)

	frappe.db.set_global("disabled_apps", json.dumps(disabled_apps))
	frappe.local.request_cache and frappe.local.request_cache.clear()
	frappe.get_single("Installed Applications").update_versions()


def enable_app(app_name):
	"""Bring back an app that was disabled, without re-syncing its schema."""
	if app_name not in frappe.get_installed_apps():
		frappe.throw(_("App {0} is not installed").format(app_name))

	with filelock(APP_STATE_LOCK):
		frappe.flags.in_app_toggle = True
		try:
			disabled_apps = frappe.get_disabled_apps()
			for required_app in frappe.get_hooks("required_apps", app_name=app_name):
				dependency = parse_required_app_name(required_app)
				if dependency in disabled_apps:
					frappe.throw(_("App {0} depends on {1}. Enable {1} first.").format(app_name, dependency))

			for before_enable in frappe.get_hooks("before_enable", app_name=app_name):
				frappe.get_attr(before_enable)()

			set_app_disabled(app_name, False)

			for after_enable in frappe.get_hooks("after_enable", app_name=app_name):
				frappe.get_attr(after_enable)()

			frappe.db.commit()  # nosemgrep
		except Exception:
			frappe.db.rollback()
			raise
		finally:
			frappe.clear_cache()
			frappe.client_cache.erase_persistent_caches()
			frappe.flags.in_app_toggle = False

	click.secho(f"App {app_name} enabled on Site {frappe.local.site}", fg="green")


def disable_app(app_name):
	"""Keep the app's schema and data, but stop it from taking effect on this site."""
	if app_name == "frappe":
		frappe.throw(_("App frappe cannot be disabled"))

	if app_name not in frappe.get_installed_apps():
		frappe.throw(_("App {0} is not installed").format(app_name))

	with filelock(APP_STATE_LOCK):
		frappe.flags.in_app_toggle = True
		try:
			for app in frappe.get_active_apps():
				if app == app_name:
					continue
				if is_required_by(app_name, app):
					frappe.throw(
						_("App {0} is a dependency of {1}. Disable {1} first.").format(app_name, app)
					)

			for before_disable in frappe.get_hooks("before_disable", app_name=app_name):
				frappe.get_attr(before_disable)()

			set_app_disabled(app_name, True)

			for after_disable in frappe.get_hooks("after_disable", app_name=app_name):
				frappe.get_attr(after_disable)()

			frappe.db.commit()  # nosemgrep
		except Exception:
			frappe.db.rollback()
			raise
		finally:
			frappe.clear_cache()
			frappe.client_cache.erase_persistent_caches()
			frappe.flags.in_app_toggle = False

	click.secho(f"App {app_name} disabled on Site {frappe.local.site}", fg="green")


def reapply_disabled_app_state():
	"""Run the `before_disable` hooks again for each app that the site disables.

	A migration can create the customizations that an app hid. These hooks run more than
	once, so they must give the same result each time.
	"""
	disabled_apps = frappe.get_disabled_apps()
	if not disabled_apps:
		return

	frappe.flags.in_app_toggle = True
	try:
		for app_name in disabled_apps:
			for before_disable in frappe.get_hooks("before_disable", app_name=app_name):
				frappe.get_attr(before_disable)()
	finally:
		frappe.flags.in_app_toggle = False


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
		if app != app_name and is_required_by(app_name, app):
			click.secho(f"App {app_name} is a dependency of {app}. Uninstall {app} first.", fg="yellow")
			return

	print(f"Uninstalling App {app_name} from Site {site}...")

	if not dry_run and not yes:
		confirm = click.confirm(
			"All doctypes (including custom) and modules belonging to this app will be"
			" deleted. This site's own custom modules are kept. Are you sure you want to continue?"
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

	drop_doctypes = _delete_modules(get_app_owned_modules(app_name), dry_run=dry_run)
	_delete_doctypes(drop_doctypes, dry_run=dry_run)
	release_custom_module_placements(app_name, dry_run=dry_run)

	if not dry_run:
		remove_from_installed_apps(app_name)
		frappe.get_single("Installed Applications").update_versions()
		frappe.db.commit()
		frappe.clear_cache()

	for after_uninstall in app_hooks.after_uninstall or []:
		frappe.get_attr(after_uninstall)()

	for fn in frappe.get_hooks("after_app_uninstall"):
		frappe.get_attr(fn)(app_name)

	frappe.client_cache.erase_persistent_caches()

	click.secho(f"Uninstalled App {app_name} from Site {site}", fg="green")
	frappe.flags.in_uninstall = False

	if not dry_run:
		frappe.clear_cache()


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
					frappe.delete_doc(doctype.name, doctype.name, ignore_on_trash=True, force=True)
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
	frappe.db.commit()  # nosemgrep
	frappe.clear_cache()


def set_all_patches_as_completed(app):
	from frappe.modules.patch_handler import get_patches_from_app

	patches = get_patches_from_app(app)
	for patch in patches:
		frappe.get_doc({"doctype": "Patch Log", "patch": patch}).insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep


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

		with open(site_file, "w") as f:  # nosemgrep
			f.write(json.dumps(site_config, indent=1, sort_keys=True))


def _sync_installed_apps_to_site_config():
	"""Mirror the installed-apps list into site_config.json for fast reads without a DB round-trip."""
	try:
		update_site_config("installed_apps", frappe.get_installed_apps())
	except Exception:
		pass


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


def clear_site_locks():
	import shutil
	from pathlib import Path

	path = Path(frappe.get_site_path("locks"))
	shutil.rmtree(path, ignore_errors=True)


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
		rename_conflicting_custom_module(module, app)

		d = frappe.new_doc("Module Def")
		d.app_name = app
		d.module_name = module
		d.insert(ignore_permissions=True, ignore_if_duplicate=ignore_if_duplicate)


def sync_module_defs() -> list[str]:
	"""Give every module an installed app declares a `Module Def` row. Returns what it added.

	`add_module_defs` runs once, when an app is installed, so a module an app adds *later* never
	reaches a site that already has that app -- and a module with no row does not exist as far as
	the site is concerned. Nothing can link to it, which means the workspaces, dashboards and
	`Sidebar` the app ships for it are skipped on import: `module` is a Link field. Every
	app that ever split its navigation has had to carry a patch calling `add_module_defs` to
	work around this. Running the sync on every migrate is what retires that patch, for every
	app at once and for the ones that have not been written yet.

	Only the missing rows are inserted, which is the difference from calling `add_module_defs`
	here directly. That one re-inserts every module of every app and runs
	`rename_conflicting_custom_module` over each -- fine as a one-shot at install, but on a
	migrate it would put a site's custom module through a rename check on every run.

	An existing row is changed in one case only: an app's own module with no `app_name` is given
	one, because a row with no placement is a row no dock lists. This is insurance rather than a
	live repair, since nothing clears a non-custom module's `app_name`, so on a healthy site the
	branch never fires. It costs nothing: `app_name` is already in `existing`, and the write
	happens only when it is empty. `ModuleDef.validate_placement` fills the same field on save;
	this covers rows that are never saved. A repaired row is printed rather than returned, since
	the return value is what the site gained, not what it fixed.

	A row naming a different app is left alone: two apps claiming one module name is a conflict to
	resolve deliberately, not by whichever app this loop reaches last.

	It only adds. A module dropped from `modules.txt` keeps its row, because deleting one cascades
	through `DocType.module` and every link to it, and an app temporarily renaming a module would
	take the site's data with it. Removal stays something an app does explicitly, in a patch.

	App-declared beats site-authored, as it does at install: a custom module holding a name an app
	now ships is renamed out of the way (see `rename_conflicting_custom_module`), because the
	namespace is flat and the app's module has nowhere else to go.
	"""
	existing = {row.name: row for row in frappe.get_all("Module Def", fields=["name", "app_name", "custom"])}

	added, repaired = [], []
	for app in frappe.get_installed_apps():
		for module in frappe.get_module_list(app):
			row = existing.get(module)
			# an app's module already has its row; only a *custom* module holding the name is
			# something to act on
			if row and not row.custom:
				# `db.set_value` skips `on_update`, so nothing clears the module cache here --
				# safe only because migrate clears it once, at the end.
				if not row.app_name:
					frappe.db.set_value("Module Def", module, "app_name", app, update_modified=False)
					row.app_name = app  # so a second app declaring the name does not take it
					repaired.append(module)
				continue

			rename_conflicting_custom_module(module, app)

			doc = frappe.new_doc("Module Def")
			doc.app_name = app
			doc.module_name = module
			doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
			# `existing` has to keep up: a second app declaring this same module must see the
			# row it just gained, or it counts as added twice and renames against itself
			existing[module] = doc
			added.append(module)

	if repaired:
		print(f"Placed modules that had no app: {comma_and(repaired, add_quotes=False)}")

	return added


def rename_conflicting_custom_module(module: str, app: str) -> str | None:
	"""Move a site's custom module out of the way of an app that ships `module`.

	The module namespace is flat -- `Module Def` is named after `module_name`, and that name is
	the foreign key everywhere (`DocType.module`, `scrub(module)`, every link) -- and it stays
	flat. So when the two collide **the app wins**: an install must never be blocked by a
	naming choice the site made months earlier, which is what failing here would do to a
	customer mid-upgrade.

	The site loses the name, not the module: the rename cascades through every link to it, so
	its doctypes, workspaces and sidebar follow it across, and the admin is told what moved.

	Return the module's new name, or `None` when nothing was in the way. An app's own module
	re-declaring itself is not a conflict.
	"""
	# `None` when nothing holds the name, `0` when the app's own module already does
	if not frappe.db.get_value("Module Def", module, "custom"):
		return None

	from frappe.model.rename_doc import rename_doc

	new_name = available_module_name(module)
	# `force`: the install is not a user edit, and whether to give up the name is not the site's
	# decision, because the app already ships a module with it.
	rename_doc(
		doctype="Module Def",
		old=module,
		new=new_name,
		force=True,
		ignore_permissions=True,
		show_alert=False,
	)

	# A `Sidebar` is named by its title (`autoname: field:title`), and the title defaults to the
	# module's name, so the site's sidebar for this module is probably sitting on the name the
	# app's own sidebar is about to be imported under. Renaming the module updated the sidebar's
	# link to it but left its name alone, so the name has to move too.
	#
	# The collision is on the title, not the module. Two sidebars may share a module but cannot
	# share a name, so a site sidebar titled "Leads" collides with an app's "Leads" whichever
	# modules the two belong to.
	if held := frappe.db.get_value("Sidebar", {"title": module}, "name"):
		rename_doc(
			doctype="Sidebar",
			old=held,
			new=new_name,
			force=True,
			ignore_permissions=True,
			show_alert=False,
		)

	message = _("Module {0} is now shipped by {1}; this site's module of that name is now {2}.").format(
		module, app, new_name
	)
	click.secho(f"* {message}", fg="yellow")
	frappe.msgprint(message, title=_("Custom Module Renamed"), indicator="orange")

	return new_name


def reclaim_module_name_for_its_app(module: str) -> str | None:
	"""`rename_conflicting_custom_module` for the paths that don't know the app.

	An app can also reach a site's module name sideways: a doctype imported by `bench migrate`
	brings its module with it, and the module is created on the spot if nothing holds the name.
	`modules.txt` is what says the name is an app's rather than the site's, so that is what
	decides -- and a module no app declares is the site's, left exactly where it is.
	"""
	app = frappe.local.module_app.get(frappe.scrub(module))
	return rename_conflicting_custom_module(module, app) if app else None


def available_module_name(module: str) -> str:
	"""`<module> (Custom)`, counting up until the name is free."""
	candidate = f"{module} (Custom)"
	suffix = 1
	while frappe.db.exists("Module Def", candidate):
		suffix += 1
		candidate = f"{module} (Custom {suffix})"
	return candidate


def get_app_owned_modules(app_name: str) -> list[str]:
	"""The modules `app_name` brought with it, which are the ones its uninstall may take.

	`custom = 0` is the whole of the guard, and it is a lifecycle question rather than a
	placement one: a site's own module may well name this app -- that is how an admin puts
	their module inside the app their team already works in -- but naming it does not hand the
	app the right to delete it. See `Module Def.validate_placement` for the other half.
	"""
	return frappe.get_all("Module Def", filters={"app_name": app_name, "custom": 0}, pluck="name")


def release_custom_module_placements(app_name: str, dry_run: bool = False) -> list[str]:
	"""Clear the placement of every custom module that named `app_name`, and return them.

	The dock they pointed at is going away with the app. Left set, the placement would name an
	app that is no longer installed and the module would be listed nowhere at all -- so it is
	dropped, and the module falls back to standing on its own. A custom module can never become
	unreachable.
	"""
	modules = frappe.get_all("Module Def", filters={"app_name": app_name, "custom": 1}, pluck="name")

	for module in modules:
		print(f"* releasing custom Module Def '{module}' from '{app_name}'...")
		if not dry_run:
			frappe.db.set_value("Module Def", module, "app_name", None)

	return modules


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
	"""Extract a public/private files archive directly into the site directory."""
	import subprocess

	from frappe.utils import get_bench_relative_path

	file_path = get_bench_relative_path(file_path)

	# Need to do frappe.init to maintain the site locals
	frappe.init(site_name)
	abs_site_path = os.path.abspath(frappe.get_site_path())

	if not file_path.endswith((".tar", ".tgz")):
		# Fail loudly on unrecognized extensions. Previous behavior silently
		# no-op'd — restore reported success with missing files.
		frappe.destroy()
		raise ValueError(
			f"Unsupported archive format for {os.path.basename(file_path)}: expected .tar or .tgz"
		)

	try:
		subprocess.run(
			["tar", "xf", os.path.abspath(file_path), "--strip", "2"],
			cwd=abs_site_path,
			check=True,
		)
	finally:
		frappe.destroy()


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
