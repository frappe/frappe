# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals, print_function
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def execute():
	if "match" in frappe.db.get_table_columns("DocPerm"):
		create_custom_field_for_owner_match()

def create_custom_field_for_owner_match():
	frappe.db.sql("""update `tabDocPerm` set apply_user_permissions=1 where `match`='owner'""")

	for dt in frappe.db.sql_list("""select distinct parent from `tabDocPerm`
		where `match`='owner' and permlevel=0 and parent != 'User'"""):

		# a link field pointing to User already exists
		if (frappe.db.get_value("DocField", {"parent": dt, "fieldtype": "Link", "options": "User", "default": "__user"})
			or frappe.db.get_value("Custom Field", {"dt": dt, "fieldtype": "Link", "options": "User", "default": "__user"})):
			print("User link field already exists for", dt)
			continue

		fieldname = "{}_owner".format(frappe.scrub(dt))

		create_custom_field(dt, frappe._dict({
			"permlevel": 0,
			"label": "{} Owner".format(dt),
			"fieldname": fieldname,
			"fieldtype": "Link",
			"options": "User",
			"default": "__user"
		}))

		frappe.db.sql("""update `tab{doctype}` set `{fieldname}`=owner""".format(doctype=dt,
			fieldname=fieldname))

		# commit is required so that we don't lose these changes because of an error in next loop's ddl
		frappe.db.commit()
