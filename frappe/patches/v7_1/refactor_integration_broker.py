# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
import json

def execute():
	for doctype_name in ["Razorpay Log", "Razorpay Payment", "Razorpay Settings"]:
		delete_doc("DocType", doctype_name)
	
	reload_doctypes()
	setup_services()

def delete_doc(doctype, doctype_name):
	frappe.delete_doc(doctype, doctype_name)

def reload_doctypes():
	for doctype in ("razorpay_settings", "paypal_settings", "dropbox_settings", "ldap_settings"):
		frappe.reload_doc("integrations", "doctype", doctype)

def setup_services():
	for service in [{"old_name": "Razorpay", "new_name": "Razorpay"},
		{"old_name": "PayPal", "new_name": "PayPal"},
		{"old_name": "Dropbox Integration", "new_name": "Dropbox"},
		{"old_name": "LDAP Auth", "new_name": "LDAP"}]:

		try:
			service_doc = frappe.get_doc("Integration Service", service["old_name"])
			settings = json.loads(service_doc.custom_settings_json)

			service_settings = frappe.new_doc("{0} Settings".format(service["new_name"]))
			service_settings.update(settings)
			
			service_settings.flags.ignore_mandatory = True
			service_settings.save(ignore_permissions=True)

			if service["old_name"] in ["Dropbox Integration", "LDAP Auth"]:
				delete_doc("Integration Service", service["old_name"])
				
				new_service_doc = frappe.get_doc({
					"doctype": "Integration Service",
					"service": service["new_name"],
					"enabled": 1
				})
				
				new_service_doc.flags.ignore_mandatory = True
				new_service_doc.save(ignore_permissions=True)

		except Exception:
			pass
