# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
import json
from frappe import _
from frappe.utils import get_request_session

@frappe.whitelist()
def get_billing_details():
	s = get_request_session()
	data = {"site_name": frappe.local.site}

	try:
		res = s.get(frappe.conf.billing_api['get_url'], data=json.dumps(data))
		res.raise_for_status()
	
		return res.json().get("message")
	except Exception:
		return {"billing_info": {}}

@frappe.whitelist()
def setup_billing_address(data):
	s = get_request_session()
	
	data = {
		"site_name": frappe.local.site,
		"address_details": json.loads(data)
	}
	
	try:
		res = s.post(frappe.conf.billing_api['post_url'], data=json.dumps(data))
		res.raise_for_status()
	except:
		frappe.msgprint(_("Something went wrong while saving the address. Please contact us at support@erpnext.com"))
	