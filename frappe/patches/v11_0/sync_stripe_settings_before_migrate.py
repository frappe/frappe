from __future__ import unicode_literals

import frappe
from frappe.utils.password import get_decrypted_password


def execute():
	publishable_key = frappe.db.sql(
		"select value from tabSingles where doctype='Stripe Settings' and field='publishable_key'"
	)
	if publishable_key:
		secret_key = get_decrypted_password(
			"Stripe Settings", "Stripe Settings", fieldname="secret_key", raise_exception=False
		)
		if secret_key:
			frappe.reload_doc("integrations", "doctype", "stripe_settings")
			frappe.db.commit()

			settings = frappe.new_doc("Stripe Settings")
			settings.gateway_name = (
				frappe.db.get_value("Global Defaults", None, "default_company") or "Stripe Settings"
			)
			settings.publishable_key = publishable_key
			settings.secret_key = secret_key
			settings.save(ignore_permissions=True)

	frappe.db.sql("""DELETE FROM tabSingles WHERE doctype='Stripe Settings'""")
