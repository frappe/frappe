# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
Sync's doctype and docfields from txt files to database
perms will get synced only if none exist
"""

import os
import re

import frappe
from frappe.cache_manager import clear_controller_cache
from frappe.model.base_document import get_controller
from frappe.modules.import_file import import_file_by_path
from frappe.modules.patch_handler import _patch_mode
from frappe.modules.utils import get_app_level_directory_path
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
	("desk", "onboarding_step"),
	("desk", "module_onboarding"),
	("desk", "form_tour"),
	("custom", "client_script"),
	("core", "server_script"),
	("custom", "custom_field"),
	("custom", "property_setter"),
]


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
		]:
			files.append(os.path.join(FRAPPE_PATH, "desk", "doctype", desk_module, f"{desk_module}.json"))

		for module_name, document_type in IMPORTABLE_DOCTYPES:
			file = os.path.join(FRAPPE_PATH, module_name, "doctype", document_type, f"{document_type}.json")
			if file not in files:
				files.append(file)

	for module_name in frappe.local.app_modules.get(app_name) or []:
		folder = os.path.dirname(frappe.get_module(app_name + "." + module_name).__file__)
		files = get_doc_files(files=files, start_path=folder)

	app_level_folders = ["desktop_icon", "workspace_sidebar", "sidebar_item_group"]
	for folder_name in app_level_folders:
		directory_path = get_app_level_directory_path(folder_name, app_name)
		if os.path.exists(directory_path):
			icon_files = [os.path.join(directory_path, filename) for filename in os.listdir(directory_path)]
			for doc_path in icon_files:
				files.append(doc_path)

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


def get_doc_files(files, start_path):
	"""walk and sync all doctypes and pages"""

	files = files or []

	for _module, doctype in IMPORTABLE_DOCTYPES + [
		(None, frappe.scrub(dt)) for dt in frappe.get_hooks("importable_doctypes")
	]:
		doctype_path = os.path.join(start_path, doctype)
		if os.path.exists(doctype_path):
			for docname in os.listdir(doctype_path):
				if os.path.isdir(os.path.join(doctype_path, docname)):
					doc_path = os.path.join(doctype_path, docname, docname) + ".json"
					if os.path.exists(doc_path):
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
	orphan_doctypes = []

	clear_controller_cache()
	class_overrides = frappe.get_hooks("override_doctype_class", {})

	for doctype in doctype_names:
		if doctype in class_overrides:
			continue
		try:
			get_controller(doctype=doctype)
		except (ImportError, frappe.DoesNotExistError):
			orphan_doctypes.append(doctype)
		except Exception:
			continue

	if not orphan_doctypes:
		return

	print(f"Orphaned DocType(s) found: {', '.join(orphan_doctypes)}")
	for i, name in enumerate(orphan_doctypes):
		frappe.delete_doc("DocType", name, force=True, ignore_missing=True)
		update_progress_bar("Deleting orphaned DocTypes", i, len(orphan_doctypes))
	frappe.db.commit()
	print()


def remove_orphan_entities():
	entites = ["Workspace", "Dashboard", "Page", "Report"]
	app_level_entities = ["Workspace Sidebar", "Desktop Icon"]
	entity_filter_map = {
		"Workspace": [{"public": 1, "module": ["is", "set"], "app": ["is", "set"]}],
		"Page": {"standard": "Yes"},
		"Report": {"is_standard": "Yes"},
		"Dashboard": {"is_standard": True},
		"Workspace Sidebar": {"standard": True},
		"Desktop Icon": {"standard": True},
	}
	entity_file_map = create_entity_file_map(entites)

	for entity in entites:
		print(f"Removing orphan {entity}s")
		all_enitities = frappe.get_all(
			entity, filters=entity_filter_map.get(entity), fields=["name", "module"]
		)
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
	for app_entity in app_level_entities:
		print(f"Removing orphan {app_entity}s")
		all_enitities = frappe.get_all(
			app_entity, filters=entity_filter_map.get(app_entity), fields=["name", "app"]
		)
		for i, w in enumerate(all_enitities):
			if w.app and not check_if_record_exists("app", frappe.get_app_path(w.app), app_entity, w.name):
				try:
					print(f"Deleting entity {app_entity} {w.name}")
					frappe.delete_doc(app_entity, w.name, force=True, ignore_missing=True)
					update_progress_bar(f"Deleting orphaned {app_entity}", i, len(all_enitities))
					print()

				except Exception as e:
					print(f"Error occurred while deleting entity: {app_entity} {w.name}")
					print(e)

	# save the deleted icons
	frappe.db.commit()  # nosemgrep


def create_entity_file_map(entities):
	import glob

	from frappe.modules.import_file import read_doc_from_file

	entity_file_map = {}
	for entity in entities:
		entity_file_map[entity] = {}
	for app in frappe.get_installed_apps():
		app_path = frappe.get_app_path(app)
		for entity in entities:
			entity_folder = entity.lower()
			if entity.lower() == "dashboard":
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
