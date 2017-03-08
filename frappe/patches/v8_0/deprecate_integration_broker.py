import frappe

def execute():
	setup_enabled_integrations()

	for doctype in ["integration_request", "oauth_authorization_code", "oauth_bearer_token", "oauth_client"]:
		frappe.reload_doc('integrations', 'doctype', doctype)
	
	for doctype in ["Integration Service", "Integration Service Parameter"]:
		frappe.delete_doc("DocType", doctype)
	
	frappe.delete_doc("Module Def", "Integration Broker")

def setup_enabled_integrations():
	for service in frappe.get_all("Integration Service",
		filters={"enabled": 1, "service": ('in', ("Dropbox", "LDAP"))}, fields=["name"]):

		doctype = "{0} Settings".format(service.name)
		frappe.db.set_value(doctype, doctype, 'enabled', 1)