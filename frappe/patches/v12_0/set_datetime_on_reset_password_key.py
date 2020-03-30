from __future__ import unicode_literals

import frappe


def execute():
	frappe.db.sql("""
UPDATE `tabUser`
SET
	expire_reset_password_key = getdate()
WHERE
	reset_password_key IS NOT NULL
""")
