# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils.data import get_link_to_form
import requests
from frappe import _
from datetime import datetime

@frappe.whitelist(allow_guest=True)
def get_whats_new_posts():
	host = "http://test-st.frappe.cloud"
	post_list = []

	try:
		res = requests.get(host + '/api/method/frappe.desk.doctype.whats_new.whats_new.fetch_latest_posts')
	except:
		frappe.throw('Error in establishing connection with host')

	data = res.json()
	post_list = data.get("message")[0] or []
	event_list = data.get("message")[1] or []

	print('EVENT LIST', event_list)
	today = datetime.now().today()
	# date_found = 0
	closest_upcoming_events = []
	for event in event_list:
		if datetime.strptime(event.get("event_date"), "%Y-%m-%d").date() >= today.date():
			closest_upcoming_events.append(event)
	closest_upcoming_events = reversed(closest_upcoming_events)
	print('REVERSED LIST', closest_upcoming_events)

	return post_list, closest_upcoming_events


@frappe.whitelist(allow_guest=True)
def add_whats_new_event_to_calendar(date, time, title):
	if date == "undefined":
		frappe.throw(_("Date is not in vaild format"))
	if time == "undefined":
		frappe.throw(_("Time is in invalid format"))

	date_time = datetime.strptime((date+' '+time), "%Y-%m-%d %H:%M:%S")
	if frappe.db.exists("Event", {"subject":title, "starts_on":date_time}):
		event_name = frappe.db.get_value("Event", {"subject":title, "starts_on": (date+' '+time)}, "name")
		frappe.throw(title=_("Event Already Exists"), msg=_("An event {} already exists in your ERPNext system.").format(get_link_to_form("Event", event_name)))

	calendar_event = {
		"doctype": "Event",
		"subject": title,
		"starts_on": date_time,
		"event_type": "Public"
	}
	event_doc = frappe.get_doc(calendar_event)
	event_doc.insert(ignore_permissions=True)
	frappe.msgprint(title=_("Event Created Successfully"), msg=_('Successfully Created Event {} in your ERPNext account').format(get_link_to_form("Event", event_doc.get("name"))))

	return True