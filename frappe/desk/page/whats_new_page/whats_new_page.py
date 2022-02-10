# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import requests

@frappe.whitelist(allow_guest=True)
def get_whats_new_posts():

	res = requests.get('http://test-erp:8000/api/method/frappe.desk.doctype.whats_new.whats_new.fetch_latest_posts')
	res.raise_for_status()
	data = res.json()
	return data.get('message') or []
