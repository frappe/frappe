import frappe

def execute():
	for doctype in ["integration_request", "oauth_authorization_code", "oauth_bearer_token", "oauth_client"]:
		frappe.reload_doc('integrations', 'doctype', doctype)
	
	for doctype in ["Integration Service", "Integration Service Parameter"]:
		frappe.delete_doc("DocType", doctype)
	
	frappe.delete_doc("Module Def", "Integration Broker")