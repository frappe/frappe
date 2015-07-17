from __future__ import unicode_literals
import frappe

from frappe.model.utils.rename_field import rename_field
from frappe.model.meta import get_table_columns

def execute():
	tables = frappe.db.sql_list("show tables")
	if "tabUser" not in tables:
		frappe.rename_doc("DocType", "Profile", "User", force=True)

	frappe.reload_doc("website", "doctype", "blogger")

	if "profile" in get_table_columns("Blogger"):
		rename_field("Blogger", "profile", "user")
