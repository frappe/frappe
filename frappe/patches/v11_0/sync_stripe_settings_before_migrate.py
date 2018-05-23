import frappe

def execute():
	before_migration_settings = frappe.get_doc("Stripe Settings", None)
	publishable_key = before_migration_settings.publishable_key
	secret_key = before_migration_settings.get_password(fieldname='secret_key', raise_exception=False)

	if publishable_key is None or secret_key is None:
		pass
	else:

		frappe.reload_doc('integrations', 'doctype', 'stripe_settings')
		frappe.db.commit()

		settings = frappe.new_doc("Stripe Settings")
		settings.gateway_name = frappe.db.get_value("Global Defaults", None, "default_company") if not None else "Stripe Settings"
		settings.publishable_key = publishable_key
		settings.secret_key = secret_key
		settings.save(ignore_permissions=True)

	frappe.db.sql("""DELETE FROM tabSingles WHERE doctype='Stripe Settings'""")
