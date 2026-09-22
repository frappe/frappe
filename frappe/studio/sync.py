import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.modules.patch_handler import _patch_mode

from studio.build import build_custom_apps


def after_migrate():
	_patch_mode(True)
	sync_studio_apps()
	remove_orphaned_apps_and_pages()
	_patch_mode(False)
	# Rebuild all published custom (DB) apps.
	build_custom_apps()


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
				import_file_by_path(get_app_file_path(app_folder))

				sync_pages(app_folder)
				sync_components(app_folder)


def remove_orphaned_apps_and_pages():
	"""Delete standard apps and pages from DB whose exported files are gone, like frappe's orphaned doctype remover."""
	apps, pages = get_exported_docnames()
	standard = {"is_standard": 1, "frappe_app": ("in", frappe.get_installed_apps())}

	for app in frappe.get_all("Studio App", filters=standard, pluck="name"):
		if app not in apps:
			print(f"Deleting orphan Studio App {app}")
			frappe.delete_doc("Studio App", app, force=True)

	for page in frappe.get_all("Studio Page", filters=standard, pluck="name"):
		if page not in pages:
			print(f"Deleting orphan Studio Page {page}")
			frappe.delete_doc("Studio Page", page, force=True, ignore_missing=True)


def get_exported_docnames() -> tuple[set[str], set[str]]:
	"""Docnames of every Studio App and Studio Page that has a file on disk, as (apps, pages).

	Walks folders rather than studio_apps.txt: an app whose folder exists but isn't listed is
	unsynced, not an orphan.
	"""
	apps, pages = set(), set()
	for app in frappe.get_installed_apps():
		studio_folder_path = frappe.get_app_source_path(app, "studio")
		if not os.path.isdir(studio_folder_path):
			continue
		for entry in os.listdir(studio_folder_path):
			app_folder = os.path.join(studio_folder_path, entry)
			app_path = get_app_file_path(app_folder)
			if not os.path.isfile(app_path):
				continue
			apps.add(read_json_file(app_path).get("name"))
			# exported page `name` is the scrubbed title; the docname is `page_name`
			pages.update(read_json_file(path).get("page_name") for path in get_page_file_paths(app_folder))
	return apps, pages


def sync_pages(app_folder):
	# each page is a folder holding <stem>.json + <stem>.ts; the script lives in the .ts (the runtime
	# loads it directly), so the DB `script` field stays empty for exported pages
	for page_path in get_page_file_paths(app_folder):
		import_file_by_path(page_path)


def sync_components(app_folder):
	studio_component_folder = os.path.join(app_folder, "studio_components")
	if not os.path.exists(studio_component_folder):
		return

	for component in os.listdir(studio_component_folder):
		if component.endswith(".json"):
			component_path = os.path.join(studio_component_folder, component)
			import_file_by_path(component_path)


def get_app_file_path(app_folder) -> str:
	# the folder keeps the app's name as-is, but its JSON is written scrubbed (`my-app/my_app.json`)
	return os.path.join(app_folder, f"{frappe.scrub(os.path.basename(app_folder))}.json")


def get_page_file_paths(app_folder) -> list[str]:
	studio_page_folder = os.path.join(app_folder, "studio_page")
	if not os.path.exists(studio_page_folder):
		return []
	paths = []
	for entry in os.listdir(studio_page_folder):
		page_path = os.path.join(studio_page_folder, entry, f"{entry}.json")
		if os.path.isfile(page_path):
			paths.append(page_path)
	return paths


def read_json_file(path) -> dict:
	return frappe.parse_json(frappe.read_file(path))
