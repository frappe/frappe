import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.modules.patch_handler import _patch_mode


def after_migrate():
	_patch_mode(True)
	sync_app()
	_patch_mode(False)


def sync_app():
	for app in frappe.get_installed_apps():
		if app == "studio":
			continue

		studio_folder_path = frappe.get_app_source_path(app, "studio")
		if not os.path.exists(studio_folder_path):
			continue

		for app_name in os.listdir(studio_folder_path):
			print(f"Syncing Studio App {app_name} for {app}")
			if os.path.isdir(os.path.join(studio_folder_path, app_name)):
				app_folder = os.path.join(studio_folder_path, app_name)
				app_path = os.path.join(app_folder, app_name) + ".json"
				import_file_by_path(app_path)

				sync_pages(app_folder)


def sync_pages(app_folder):
	studio_page_folder = os.path.join(app_folder, "studio_page")
	for page in os.listdir(studio_page_folder):
		if page.endswith(".json"):
			page_path = os.path.join(studio_page_folder, page)
			print(f"Syncing Studio Page {page} from {app_folder}")
			import_file_by_path(page_path)
