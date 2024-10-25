# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute() -> None:
	frappe.reload_doc("website", "doctype", "website_theme_ignore_app")
	themes = frappe.get_all("Website Theme", filters={"theme_url": ("not like", "/files/website_theme/%")})
	for theme in themes:
		doc = frappe.get_doc("Website Theme", theme.name)
		try:
			doc.save()
		except Exception:
			print("Ignoring....")
			print(frappe.get_traceback())
