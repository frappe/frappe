import frappe
from frappe.utils import cint

def execute():
	frappe.reload_doc("integrations", "doctype", "ldap_settings")

	if not frappe.db.exists("DocType", "Integration Service"):
		return

	if not frappe.db.exists("Integration Service", "LDAP"):
		return

	if not cint(frappe.db.get_value("Integration Service", "LDAP", 'enabled')):
		return

	import ldap
	try:
		ldap_settings = frappe.get_doc("LDAP Settings")
		ldap_settings.save(ignore_permissions=True)
	except ldap.LDAPError:
		pass
