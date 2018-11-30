# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.desk.doctype.event.event import get_events as default_event
from erpnext.selling.doctype.sales_order.sales_order import get_events as sales_order_event
from frappe.desk.calendar import get_events as task_event
from erpnext.hr.doctype.holiday_list.holiday_list import get_events as holiday

@frappe.whitelist()
def get_master_calendar_events(doctypeinfo):
	doctypes=frappe.get_hooks("calendars")
	words = doctypeinfo.split(",")
	master_events = []
	for info in words:
		if(info in doctypes):
			if(info == "Event"):
				events = default_event("2018-10-28 00:00:00", "2018-12-09 00:00:00")
				for event in events:
					master_events.append({'start': event.starts_on, 'end': event.ends_on, "title" : 'Event', "color": "yellow"})

			if info == "Task":
				events = frappe.get_list("Task" ,fields=['*'])
				print(events)
				for event in events:
					master_events.append({'start': event.exp_start_date, 'end': event.exp_end_date, "title" : 'Task'})

			if info == "Sales Order":
				events = sales_order_event("2018-10-28 00:00:00","2018-12-09 00:00:00")
				for event in events:
					master_events.append({'start': event.delivery_date, "title" : 'Sales Order', "color": "orange"})

			if info == "Holiday List":
				events = holiday("2018-10-28 00:00:00","2018-12-09 00:00:00")
				print(events)


	return master_events



