from __future__ import unicode_literals

import frappe


def execute():
	frappe.db.sql("""UPDATE `tabUser` SET reset_key_created_on = now()
		WHERE reset_password_key IS NOT NULL""")
