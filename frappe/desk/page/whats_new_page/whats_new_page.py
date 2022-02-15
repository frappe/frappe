# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import requests
from datetime import datetime

@frappe.whitelist(allow_guest=True)
def get_whats_new_posts():
	host = "https://test-st.frappe.cloud"
	post_list = []

	try:
		res = requests.get(host + '/api/method/frappe.desk.doctype.whats_new.whats_new.fetch_latest_posts')
	except:
		frappe.throw('Error in establishing connection with host')

	data = res.json()
	post_list = data.get("message")[0] or []
	event_list = data.get("message")[1] or []

	return post_list, event_list


@frappe.whitelist(allow_guest=True)
def add_whats_new_event_to_calendar(date, time, title):

	date_time = datetime.strptime((date+' '+time), "%Y-%m-%d %H:%M:%S")
	if frappe.db.exists("Event", {"subject":title, "starts_on":date_time}):
		frappe.throw(title=frappe._("Event Already Created"), msg=frappe._("An event for {0} scheduled on {1} already exists").format(frappe.bold(title), frappe.bold(date_time)))

	calendar_event = {
		"doctype": "Event",
		"subject": title,
		"starts_on": date_time,
		"event_type": "Public"
	}
	frappe.get_doc(calendar_event).insert(ignore_permissions=True)
	return True