# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
	Sync's doctype and docfields from txt files to database
	perms will get synced only if none exist
"""
import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.modules.patch_handler import _patch_mode
from frappe.utils import update_progress_bar


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
		]:
			files.append(os.path.join(FRAPPE_PATH, "desk", "doctype", desk_module, f"{desk_module}.json"))

	for module_name in frappe.local.app_modules.get(app_name) or []:
		folder = os.path.dirname(frappe.get_module(app_name + "." + module_name).__file__)
		files = get_doc_files(files=files, start_path=folder)

	l = len(files)

	if l:
		for i, doc_path in enumerate(files):
			import_file_by_path(
				doc_path, force=force, ignore_version=True, reset_permissions=reset_permissions
			)

			frappe.db.commit()

			# show progress bar
			update_progress_bar(f"Updating DocTypes for {app_name}", i, l)

		# print each progress bar on new line
		print()


def get_doc_files(files, start_path):
	"""walk and sync all doctypes and pages"""

	files = files or []

	# load in sequence - warning for devs
	document_types = [
		"doctype",
		"page",
		"report",
		"dashboard_chart_source",
		"print_format",
		"web_page",
		"website_theme",
		"web_form",
		"web_template",
		"notification",
		"print_style",
		"workspace",
		"onboarding_step",
		"module_onboarding",
		"form_tour",
		"client_script",
		"server_script",
		"custom_field",
		"property_setter",
	]
	for doctype in document_types:
		doctype_path = os.path.join(start_path, doctype)
		if os.path.exists(doctype_path):
			for docname in os.listdir(doctype_path):
				if os.path.isdir(os.path.join(doctype_path, docname)):
					doc_path = os.path.join(doctype_path, docname, docname) + ".json"
					if os.path.exists(doc_path):
						if doc_path not in files:
							files.append(doc_path)

	return files
