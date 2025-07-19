import frappe


def execute():
	"""Renames Studio App documents to slugified app titles instead of the app-{hash} format"""
	studio_apps = frappe.get_all("Studio App", fields=["name", "app_title"])
	for app in studio_apps:
		new_name = app.app_title.lower().replace(" ", "-")
		frappe.rename_doc("Studio App", app.name, new_name)
