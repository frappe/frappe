from __future__ import unicode_literals
import frappe

from frappe.model import rename_field
from frappe.model.meta import get_table_columns

def execute():
	tables = frappe.db.sql_list("show tables")
	if "tabUser" not in tables:
		frappe.rename_doc("DocType", "Profile", "User", force=True)

	if frappe.db.exists("DocType", "Website Route Permission"):
		frappe.reload_doc("website", "doctype", "website_route_permission")
		if "profile" in get_table_columns("Website Route Permission"):
			rename_field("Website Route Permission", "profile", "user")
	frappe.reload_doc("website", "doctype", "blogger")

	if "profile" in get_table_columns("Blogger"):
		rename_field("Blogger", "profile", "user")
