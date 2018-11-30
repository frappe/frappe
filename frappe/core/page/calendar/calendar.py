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
	print("------------------inside---------------------")
	words = doctypeinfo.split(",")
	master_events = {}
	for info in words:
		if(info in doctypes):
			if(info == "Event"):
				events = default_event("2018-10-28 00:00:00", "2018-12-09 00:00:00")
				event_period = []
				for event in events:
					event_period.append({'start': event.starts_on, 'end': event.ends_on})
				master_events['Event'] = event_period

			if info == "Task":
				events = frappe.get_list("Task" ,fields=['*'])
				event_period = []
				for event in events:
					event_period.append({'start': event.exp_start_date, 'end': event.exp_end_date})
				master_events['Task'] = event_period



			if info == "Sales Order":
				events = sales_order_event("2018-10-28 00:00:00","2018-12-09 00:00:00")
				sales_events = []
				for event in events:
					sales_events.append({'start': event.delivery_date})
				master_events['Sales Order'] = sales_events

			if info == "Holiday List":
				events = holiday("2018-10-28 00:00:00","2018-12-09 00:00:00")
				print(events)


	return master_events



