# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe


def execute():
	frappe.reload_doc("website", "doctype", "website_theme_ignore_app")
	themes = frappe.db.get_all(
		"Website Theme", filters={"theme_url": ("not like", "/files/website_theme/%")}
	)
	for theme in themes:
		doc = frappe.get_doc("Website Theme", theme.name)
		try:
			doc.generate_bootstrap_theme()
			doc.save()
		except: # noqa: E722
			print('Ignoring....')
			print(frappe.get_traceback())
