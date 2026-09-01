# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
Sync's doctype and docfields from txt files to database
perms will get synced only if none exist
"""

import glob
import os
import re

import frappe
from frappe.desk.doctype.desktop_icon.desktop_icon import import_desktop_icon_fixtures
from frappe.modules.import_file import import_file_by_path
from frappe.modules.patch_handler import _patch_mode
from frappe.utils import update_progress_bar

IMPORTABLE_DOCTYPES = [
	# for a permission type "impersonate"
	# its custom field should exists in DocPerm
	# to ensure permissions defined in doctype.json are synced correctly
	("core", "permission_type"),
	("core", "doctype"),
	("core", "page"),
	("core", "report"),
	("desk", "dashboard_chart_source"),
	("printing", "print_format"),
	("website", "web_page"),
	("website", "website_theme"),
	("website", "web_form"),
	("website", "web_template"),
	("email", "notification"),
	("printing", "print_style"),
	("desk", "workspace"),
	("desk", "workspace_sidebar"),
	("desk", "sidebar"),
	# Desk v2's navigation kinds. A kind is contributed as a record here plus a renderer beside
	# it, on two independent channels: the row arrives at migrate through this walk, the JS at
	# build. There is no bespoke seeder, so a manifest and a seeder cannot disagree.
	("desk", "navigation_item_type"),
	("desk", "onboarding_step"),
	("desk", "module_onboarding"),
	("desk", "form_tour"),
	("custom", "client_script"),
	("core", "server_script"),
	("custom", "custom_field"),
	("custom", "property_setter"),
	("printing", "letter_head"),
]

# The doctypes an app may ship rooted at the app itself rather than inside one of its modules.
#
# This is an explicit allowlist rather than a reuse of `IMPORTABLE_DOCTYPES`, because the app-root
# walk makes a folder name meaningful at the top of every installed app. Reusing the whole list
# would give that meaning to twenty-odd folder names at once. `Dock` joins the list when an app
# ships one.
#
# A module-rooted `Sidebar` is unaffected: it still uses `IMPORTABLE_DOCTYPES` on the per-module
# walk, from the same code.
#
# Do not confuse this with `APP_LEVEL_ENTITIES` below, which is the reaper's list of the old
# hand-written app-level fixtures that are being retired. This is the ordinary export path,
# rooted one level up.
APP_ROOTED_DOCTYPES = [("desk", "dock"), ("desk", "sidebar"), ("desk", "rail")]


def sync_all(force=0, reset_permissions=False):
	_patch_mode(True)
	for app in frappe.get_installed_apps():
		sync_for(app, force, reset_permissions=reset_permissions)

	_patch_mode(False)

	frappe.clear_cache()


def sync_for(app_name, force=0, reset_permissions=False):
	files = []

	if app_name == "frappe":
		# these need to go first at time of install

		FRAPPE_PATH = frappe.get_app_path("frappe")

		for core_module in [
			"docfield",
			"docperm",
			"doctype_action",
			"doctype_link",
			"doctype_state",
			"role",
			"has_role",
			"doctype",
		]:
			files.append(os.path.join(FRAPPE_PATH, "core", "doctype", core_module, f"{core_module}.json"))

		# sync permission type and its dependencies
		for dt in ["user", "docshare", "custom_docperm", "docperm", "permission_type"]:
			files.append(os.path.join(FRAPPE_PATH, "core", "doctype", dt, f"{dt}.json"))

		for custom_module in ["custom_field", "property_setter"]:
			files.append(
				os.path.join(FRAPPE_PATH, "custom", "doctype", custom_module, f"{custom_module}.json")
			)

		for website_module in ["web_form", "web_template", "web_form_field", "portal_menu_item"]:
			files.append(
				os.path.join(FRAPPE_PATH, "website", "doctype", website_module, f"{website_module}.json")
			)

		for desk_module in [
			"number_card",
			"dashboard_chart",
			"dashboard",
			"onboarding_permission",
			"onboarding_step",
			"onboarding_step_map",
			"module_onboarding",
			"workspace_link",
			"workspace_chart",
			"workspace_shortcut",
			"workspace_quick_list",
			"workspace_number_card",
			"workspace_custom_block",
			"workspace",
			"workspace_sidebar",
			"workspace_sidebar_item",
			"sidebar_item",
			"sidebar",
		]:
			files.append(os.path.join(FRAPPE_PATH, "desk", "doctype", desk_module, f"{desk_module}.json"))

		for module_name, document_type in IMPORTABLE_DOCTYPES:
			file = os.path.join(FRAPPE_PATH, module_name, "doctype", document_type, f"{document_type}.json")
			if file not in files:
				files.append(file)

	for module_name in frappe.local.app_modules.get(app_name) or []:
		folder = os.path.dirname(frappe.get_module(app_name + "." + module_name).__file__)
		files = get_doc_files(files=files, start_path=folder)

	# The same walk again, rooted at the app, for the few doctypes an app may ship outside any
	# module, which today means an app-rooted `Sidebar`. `get_doc_files` needs no changes for
	# this, since it already takes the directory to start from.
	#
	# This is not the old app-level fixture import, which is gone. `workspace_sidebar` was the
	# last of those, and its fixtures stop arriving with this release, because an app ships a
	# `Sidebar` now. An app that has not re-exported yet falls back to a computed base rather
	# than to nothing, which makes dropping them safe.
	files = get_doc_files(files=files, start_path=frappe.get_app_path(app_name), doctypes=APP_ROOTED_DOCTYPES)

	l = len(files)
	if l:
		for i, doc_path in enumerate(files):
			imported = import_file_by_path(
				doc_path, force=force, ignore_version=True, reset_permissions=reset_permissions
			)

			if imported:
				frappe.db.commit(chain=True)

			# show progress bar
			update_progress_bar(f"Updating DocTypes for {app_name}", i, l)

		# print each progress bar on new line
		print()

	# The icon grid's fixtures use their own entry point because of the desktop-mode guard: an
	# Apps-mode site holds no icon rows, shipped or generated, and switching to the grid is what
	# imports them.
	import_desktop_icon_fixtures(app_name, force=force)


def get_doc_files(files, start_path, doctypes=None):
	"""walk and sync all doctypes and pages

	`doctypes` narrows the walk to a named few, and is what the app-root call passes: at the
	top of an app only `APP_ROOTED_DOCTYPES` is meaningful. Left out, the walk is the whole
	importable set plus whatever apps added by hook, which is what a module folder gets.
	"""

	files = files or []
	general_walk = doctypes is None
	if general_walk:
		doctypes = IMPORTABLE_DOCTYPES + [
			(None, frappe.scrub(dt)) for dt in frappe.get_hooks("importable_doctypes")
		]

	for _module, doctype in doctypes:
		doctype_path = os.path.join(start_path, doctype)
		if os.path.exists(doctype_path):
			for docname in os.listdir(doctype_path):
				if os.path.isdir(os.path.join(doctype_path, docname)):
					doc_path = os.path.join(doctype_path, docname, docname) + ".json"
					if os.path.exists(doc_path):
						if doc_path not in files:
							files.append(doc_path)

	# Both of these are module-rooted, and an allowlisted walk covers only the named doctypes, so
	# they are skipped rather than given meaning at the top of an app.
	if not general_walk:
		return files

	# DocType Layouts: doctype/{document_type}/doctype_layout/{name}.json
	for doc_path in glob.glob(os.path.join(start_path, "doctype", "*", "doctype_layout", "*.json")):
		if doc_path not in files:
			files.append(doc_path)

	# DocType Settings Maps: doctype_settings_map/{name}.json
	for doc_path in glob.glob(os.path.join(start_path, "doctype_settings_map", "*.json")):
		if doc_path not in files:
			files.append(doc_path)

	return files


def remove_orphan_doctypes():
	"""Find and remove any orphaned doctypes.

	These are doctypes for which code and schema file is
	deleted but entry is present in DocType table.

	Note: Deleting the entry doesn't delete any data.
	So this is supposed to be non-destrictive operation.
	"""

	doctype_names = frappe.get_all("DocType", {"custom": 0}, pluck="name")

	# Existence of the schema file is enough, importing the controller just to check if the doctype
	# exists is expensive and can fail for unrelated reasons.
	known_doctypes = create_entity_file_map(["DocType"])["DocType"]
	orphan_doctypes = [doctype for doctype in doctype_names if doctype not in known_doctypes]

	if not orphan_doctypes:
		return

	print(f"Orphaned DocType(s) found: {', '.join(orphan_doctypes)}")
	for i, name in enumerate(orphan_doctypes):
		frappe.delete_doc("DocType", name, force=True, ignore_missing=True)
		update_progress_bar("Deleting orphaned DocTypes", i, len(orphan_doctypes))
	frappe.db.commit()
	print()


# What the reaper walks: a standard record here whose file has gone is an orphan and is
# deleted. `Workspace Sidebar` has left this list, because the archive's files are going away with
# this release, so keeping it here would delete the rows the conversion reads. Icon fixtures
# stay: their files are staying, and an icon has no computed base to absorb the loss.
ORPHANABLE_ENTITIES = [
	"Workspace",
	"Dashboard",
	"Page",
	"Report",
	"Notification",
	"Sidebar",
	"Dock",
	"Rail",
	"Navigation Item Type",
]
# Retiring with the icon-grid batch, together with the fixture import it mirrors; see
# `frappe/desk/RETIRING.md`.
APP_LEVEL_ENTITIES = ["Desktop Icon"]


def remove_orphan_entities(entity_types=None):
	entities = list(ORPHANABLE_ENTITIES)
	entity_filter_map = {
		# only a standard workspace is backed by a file in an app; a site's own public workspace
		# is never an orphan. This used to read `app is set`, back when a workspace carried its
		# app itself, which also swept up site-created workspaces that a migrate had stamped an
		# app onto, and deleted them.
		"Workspace": {"public": 1, "standard": 1},
		"Page": {"standard": "Yes"},
		"Report": {"is_standard": "Yes"},
		"Dashboard": {"is_standard": True},
		"Desktop Icon": {"standard": True},
		"Notification": {"is_standard": True},
		# only a standard sidebar is backed by a file; everything else belongs to the site
		# and is never an orphan
		"Sidebar": {"standard": True},
		# the same rule one table down: the app's own dock is the file-backed layer, and the
		# site's arrangement and every person's own are never candidates
		"Dock": {"standard": 1},
		# The same rule again for desk v2's rail: the app layer is the file-backed one, and the
		# site's arrangement and each person's own are never candidates.
		"Rail": {"standard": 1},
		# No filter, deliberately. Every navigation kind is app content -- nobody has create
		# permission on the table -- so every row is file-backed and every row is a candidate.
	}
	if entity_types:
		entities = entity_types if isinstance(entity_types, list) else [entity_types]

	# Built from the entities actually being walked. Built from the default list instead, a
	# caller naming anything outside it got an empty map, and an empty map makes every row look
	# like an orphan, so asking to reap one entity deleted all of another.
	entity_file_map = create_entity_file_map(entities)

	for entity in entities:
		print(f"Removing orphan {entity}s")
		# `name` and nothing else. The module was never read in the loop below, and selecting
		# it means an entity with no `module` column, or one whose rows may leave it blank,
		# cannot be swept at all: the query fails and takes the whole migrate with it.
		all_enitities = frappe.get_all(entity, filters=entity_filter_map.get(entity), fields=["name"])
		for i, w in enumerate(all_enitities):
			try:
				entity_file_map[entity][w.name]
			except KeyError:
				try:
					print(f"Deleting entity {entity} {w.name}")
					frappe.delete_doc(entity, w.name, force=True, ignore_missing=True)
					update_progress_bar(f"Deleting orphaned {entity}", i, len(all_enitities))
					print()

				except Exception as e:
					print(f"Error occurred while deleting entity: {entity} {w.name}")
					print(e)
		# save the deleted icons
		frappe.db.commit()  # nosemgrep
	#  Remove app level entities
	if entity_types and not set(entity_types).issubset(set(APP_LEVEL_ENTITIES)):
		return
	for app_entity in APP_LEVEL_ENTITIES:
		print(f"Removing orphan {app_entity}s")
		all_enitities = frappe.get_all(
			app_entity, filters=entity_filter_map.get(app_entity), fields=["name", "app"]
		)
		for i, entity in enumerate(all_enitities):
			try:
				if entity.app:
					app_path = frappe.get_app_path(entity.app)
					if not check_if_record_exists("app", app_path, app_entity, entity.name):
						try:
							print(f"Deleting entity {app_entity} {entity.name}")
							frappe.delete_doc(app_entity, entity.name, force=True, ignore_missing=True)
							update_progress_bar(f"Deleting orphaned {app_entity}", i, len(all_enitities))
							print()
						except Exception as e:
							print(f"Error occurred while deleting entity: {app_entity} {entity.name}")
							print(e)
			except ModuleNotFoundError as e:
				print(e)
				print(f"Deleting entity {app_entity} {entity.name}")
				frappe.db.delete(app_entity, {"name": entity.name})

	# save the deleted icons
	frappe.db.commit()  # nosemgrep


def create_entity_file_map(entities):
	from frappe.modules.import_file import read_doc_from_file

	entity_file_map = {}
	for entity in entities:
		entity_file_map[entity] = {}
	for app in frappe.get_installed_apps():
		app_path = frappe.get_app_path(app)
		for entity in entities:
			# `scrub`, not `lower`: a multi-word entity lives in a snake_case folder, so one
			# would have to be looked for in `custom_sidebar/`, not `custom sidebar/`. Every
			# entity here is a single word today, which hides the difference, and `lower` would
			# have made every record of the first multi-word entity look like an orphan.
			entity_folder = frappe.scrub(entity)
			if entity_folder == "dashboard":
				entity_folder = f"*_{entity_folder}"
			entity_files = list(glob.glob(f"{app_path}/**/{entity_folder}/**/*.json", recursive=True))
			for file in entity_files:
				entity_json = read_doc_from_file(file)
				if isinstance(entity_json, dict):
					entity_file_map[entity][entity_json.get("name")] = file
				elif isinstance(entity_json, list):
					if len(entity_json) > 0:
						entity_file_map[entity][entity_json[0].get("name")] = file

	return entity_file_map


def check_if_record_exists(type=None, path=None, entity_type=None, name=None, module_name=None):
	scrubbed_name = frappe.scrub(name.lower())
	scrubbed_entity_type = frappe.scrub(entity_type.lower())
	if scrubbed_entity_type == "dashboard" and module_name:
		scrubbed_entity_type = f"{frappe.scrub(module_name.lower())}_dashboard"

	def build_path(entity_name):
		if type == "app":
			return os.path.join(path, scrubbed_entity_type, f"{entity_name}.json")
		return os.path.join(path, scrubbed_entity_type, entity_name, f"{entity_name}.json")

	entity_path = build_path(scrubbed_name)
	if os.path.exists(entity_path):
		return True

	return False


def delete_duplicate_icons():
	# This handles app icons which are renamed. Removes the old entry from db.
	for app in frappe.get_installed_apps():
		icons = frappe.get_all("Desktop Icon", filters=[{"icon_type": "App"}, {"app": app}], pluck="name")

		if len(icons) > 1:
			for i in icons:
				app_path = frappe.get_app_path(app)
				if not check_if_record_exists(type="app", path=app_path, entity_type="Desktop Icon", name=i):
					print(f"Deleting icon {i}")
					frappe.delete_doc("Desktop Icon", i)

	# save the deleted icons
	frappe.db.commit()  # nosemgrep
