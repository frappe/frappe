import frappe
from frappe import _
from frappe.permissions import is_system_user
from frappe.utils.sbom.collector import collect

PACKAGE_TYPES = {"pypi": "Python", "npm": "JavaScript"}


def get_context(context):
	if not is_system_user():
		frappe.throw(_("You need to be a system user to access this page."), frappe.PermissionError)

	inventory = collect(frappe.get_installed_apps())
	apps = []
	for app in inventory.apps:
		dependencies = [
			{
				"name": package.name,
				"version": package.version,
				"type": PACKAGE_TYPES[package.ecosystem],
				"license": package.license.summary,
				"author": package.author,
			}
			for package in inventory.direct_dependencies(app)
		]
		if any([app.authors, dependencies, app.description]):
			apps.append(
				{
					"name": app.name,
					"description": app.description,
					"authors": ", ".join(app.authors),
					"dependencies": dependencies,
				}
			)

	context.apps = apps
