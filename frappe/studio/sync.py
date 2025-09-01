import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.modules.patch_handler import _patch_mode


def after_migrate():
	_patch_mode(True)
	sync_studio_apps()
	_patch_mode(False)


def after_app_install(app_name):
	"""Sync studio apps from the installed app."""
	sync_studio_apps(app_name)


def before_app_uninstall(app_name):
	"""Delete studio apps from the uninstalled app."""
	apps = frappe.get_all("Studio App", filters={"frappe_app": app_name}, pluck="name")
	for studio_app in apps:
		print(f"Deleting Studio App {studio_app} for {app_name}")
		frappe.delete_doc("Studio App", studio_app)


def sync_studio_apps(app_name: str | None = None):
	apps = [app_name] if app_name else frappe.get_installed_apps()

	for app in apps:
		studio_folder_path = frappe.get_app_source_path(app, "studio")
		if not os.path.exists(studio_folder_path):
			continue

		if app == "studio":
			app_list = frappe.get_file_items(frappe.get_app_path("studio", "studio_apps.txt"))
		else:
			app_list = os.listdir(studio_folder_path)

		for studio_app in app_list:
			print(f"Syncing Studio App {studio_app} for {app}")
			if os.path.isdir(os.path.join(studio_folder_path, studio_app)):
				app_folder = os.path.join(studio_folder_path, studio_app)
				app_path = os.path.join(app_folder, studio_app) + ".json"
				import_file_by_path(app_path)

				sync_pages(app_folder)
				sync_components(app_folder)


def sync_pages(app_folder):
	studio_page_folder = os.path.join(app_folder, "studio_page")
	for page in os.listdir(studio_page_folder):
		if page.endswith(".json"):
			page_path = os.path.join(studio_page_folder, page)
			import_file_by_path(page_path)


def sync_components(app_folder):
	studio_component_folder = os.path.join(app_folder, "studio_components")
	if not os.path.exists(studio_component_folder):
		return

	for component in os.listdir(studio_component_folder):
		if component.endswith(".json"):
			component_path = os.path.join(studio_component_folder, component)
			import_file_by_path(component_path)
