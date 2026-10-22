import importlib.util
import os

import frappe
from frappe.modules.import_file import import_file_by_path
from frappe.modules.patch_handler import _patch_mode
from frappe.studio.build import build_custom_apps
from frappe.studio.doctype.studio_component.studio_component import mark_components_standard
from frappe.studio.utils import get_app_file_path, get_exported_app_folders


def after_migrate():
	_patch_mode(True)
	sync_studio_apps()
	remove_orphaned_apps_and_pages()
	_patch_mode(False)
	# Rebuild all published custom (DB) apps.
	build_custom_apps()


def after_app_install(app_name):
	"""Sync studio apps from the installed app; one without a package has none to sync."""
	if importlib.util.find_spec(app_name):
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
		for app_folder in get_exported_app_folders(frappe.get_app_source_path(app, "studio")):
			print(f"Syncing Studio App {os.path.basename(app_folder)} for {app}")
			import_file_by_path(get_app_file_path(app_folder))
			sync_pages(app_folder)
			sync_components(app_folder)


def remove_orphaned_apps_and_pages():
	"""Delete standard apps and pages from DB whose exported files are gone, like frappe's orphaned doctype remover."""
	apps, pages = get_exported_docnames()
	standard = {"is_standard": 1, "frappe_app": ("in", frappe.get_installed_apps())}

	for app in frappe.get_all("Studio App", filters=standard, pluck="name"):
		if app not in apps:
			print(f"Removing orphan Studio App {app}")
			frappe.delete_doc("Studio App", app, force=True)

	for page in frappe.get_all("Studio Page", filters=standard, fields=["name", "page_title"]):
		if page.name not in pages:
			print(f"Removing orphan Studio Page {page.page_title}")
			frappe.delete_doc("Studio Page", page.name, force=True, ignore_missing=True)


def get_exported_docnames() -> tuple[set[str], set[str]]:
	"""Docnames of every Studio App and Studio Page that has a file on disk, as (apps, pages)."""
	apps, pages = set(), set()
	for app in frappe.get_installed_apps():
		for app_folder in get_exported_app_folders(frappe.get_app_source_path(app, "studio")):
			apps.add(read_json_file(get_app_file_path(app_folder)).get("name"))
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

	names = []
	for component in os.listdir(studio_component_folder):
		if component.endswith(".json"):
			component_path = os.path.join(studio_component_folder, component)
			import_file_by_path(component_path)
			names.append(read_json_file(component_path).get("name"))
	mark_components_standard(names)


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
