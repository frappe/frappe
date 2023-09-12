# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
	Sync's doctype and docfields from txt files to database
	perms will get synced only if none exist
"""
import os

import frappe
from frappe.model.base_document import get_controller
from frappe.modules.import_file import import_file_by_path
from frappe.modules.patch_handler import _patch_mode
from frappe.utils import update_progress_bar

IMPORTABLE_DOCTYPES = [
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

		for module_name, document_type in IMPORTABLE_DOCTYPES:
			file = os.path.join(FRAPPE_PATH, module_name, "doctype", document_type, f"{document_type}.json")
			if file not in files:
				files.append(file)

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

	for _module, doctype in IMPORTABLE_DOCTYPES:
		doctype_path = os.path.join(start_path, doctype)
		if os.path.exists(doctype_path):
			for docname in os.listdir(doctype_path):
				if os.path.isdir(os.path.join(doctype_path, docname)):
					doc_path = os.path.join(doctype_path, docname, docname) + ".json"
					if os.path.exists(doc_path):
						if doc_path not in files:
							files.append(doc_path)

	return files


def remove_stale_doctypes():
	"""Find and remove any stale doctypes."""

	doctype_names = frappe.get_all("DocType", {"istable": 0}, pluck="name")
	stale_doctype = []

	for doctype in doctype_names:
		try:
			get_controller(doctype=doctype)
		except ImportError:
			stale_doctype.append(doctype)

	length = len(stale_doctype)
	if length == 0:
		return

	print(f"{length} stale DocType/s found.")
	for i, name in enumerate(stale_doctype):
		frappe.delete_doc("DocType", name, force=True, ignore_missing=True)
		frappe.db.commit()

		update_progress_bar("Deleting non-existant DocTypes", i, length)
	print()


def remove_stale_reports():
	"""Find and remove any stale reports."""

	if not frappe.get_site_config().get("developer_mode"):
		# Skip if developer mode is not enabled.
		print("Enable developer mode to check for stale reports.")
		return

	reports_names = frappe.get_all(
		"Report", filters={"is_standard": "Yes"}, fields=["name", "module"]
	)
	stale_reports = []
	for report in reports_names:
		path = os.path.join(
			frappe.get_module_path(report.module), frappe.scrub("report"), frappe.scrub(report.name)
		)
		if not os.path.isdir(path):
			stale_reports.append(report.name)

	length = len(stale_reports)

	if length == 0:
		return

	print(f"{length} stale report/s found.")
	for i, name in enumerate(stale_reports):
		frappe.delete_doc("Report", name, force=True, ignore_missing=True)
		frappe.db.commit()

		update_progress_bar("Deleting non-existant Reports", i, length)
	print()


def remove_stale_pages():
	"""Find and remove any stale pagess."""

	pages_names = frappe.get_all(
		"Page", filters={"standard": "Yes", "system_page": 0}, fields=["name", "module"]
	)
	stale_pages = []
	for page in pages_names:
		path = os.path.join(
			frappe.get_module_path(page.module), frappe.scrub("page"), frappe.scrub(page.name)
		)
		if not os.path.isdir(path):
			stale_pages.append(page.name)

	length = len(stale_pages)

	if length == 0:
		return

	print(f"{length} stale page/s found.")
	for i, name in enumerate(stale_pages):
		frappe.delete_doc("Page", name, force=True, ignore_missing=True)
		frappe.db.commit()

		update_progress_bar("Deleting non-existant Pages", i, length)
	print()
