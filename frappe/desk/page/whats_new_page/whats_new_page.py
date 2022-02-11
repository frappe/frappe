# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import requests

@frappe.whitelist(allow_guest=True)
def get_whats_new_posts():
	host = "http://test-st.frappe.cloud"
	# host = "http://test-erp:8000"
	try:
		res = requests.get(host + '/api/method/frappe.desk.doctype.whats_new.whats_new.fetch_latest_posts')
	except:
		frappe.throw('Error in establishing connection with host')
	data = res.json()
	print('DATA ', data)
	return data.get('message') or []
	# res.raise_for_status()
