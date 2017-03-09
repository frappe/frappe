import frappe
from frappe.integrations.utils import create_payment_gateway

def execute():
	setup_enabled_integrations()

	for doctype in ["integration_request", "oauth_authorization_code", "oauth_bearer_token", "oauth_client"]:
		frappe.reload_doc('integrations', 'doctype', doctype)
	
	frappe.reload_doc("core", "doctype", "payment_gateway")
	update_doctype_module()
	create_payment_gateway_master_records()

	for doctype in ["Integration Service", "Integration Service Parameter"]:
		frappe.delete_doc("DocType", doctype)
	
	if not frappe.db.get_value("DocType", {"module": "Integration Broker"}, "name"):
		frappe.delete_doc("Module Def", "Integration Broker")

def setup_enabled_integrations():
	if not frappe.db.exists("DocType", "Integration Service"):
		return

	for service in frappe.get_all("Integration Service",
		filters={"enabled": 1, "service": ('in', ("Dropbox", "LDAP"))}, fields=["name"]):

		doctype = "{0} Settings".format(service.name)
		frappe.db.set_value(doctype, doctype, 'enabled', 1)

def update_doctype_module():
	frappe.db.sql("""update tabDocType set module='Integrations'
		where name in ('Integration Request', 'Oauth Authorization Code',
			'Oauth Bearer Token', 'Oauth Client') """)

	frappe.db.sql(""" update tabDocType set module='Core' where name = 'Payment Gateway'""")

def create_payment_gateway_master_records():
	for payment_gateway in ["Razorpay", "PayPal"]:
		doctype = "{0} Settings".format(payment_gateway)
		doc = frappe.get_doc(doctype)
		doc_meta = frappe.get_meta(doctype)
		all_mandatory_fields_has_value = True

		for d in doc_meta.fields:
			if d.reqd and not doc.get(d.fieldname):
				all_mandatory_fields_has_value = False
				break

		if all_mandatory_fields_has_value:
			create_payment_gateway(payment_gateway)
