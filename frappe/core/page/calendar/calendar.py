# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import importlib
import frappe
import os
from pprint import pprint
import json


@frappe.whitelist()
def get_master_calendar_events(doctypeinfo, start, end):
	data = get_field_map()
	# frappe calendar
	print(doctypeinfo)
	doctypes=json.loads(doctypeinfo)
	master_events = []
	for info in doctypes:
		print("------------------------------------------->>>>>"+info)
		field_map = frappe._dict(data[info]["field_map"])
		fields=[field_map.start, field_map.end, field_map.title, field_map.description, 'name']
		if field_map.color:
			fields.append(field_map.color)
		if "get_events_method" in data[info]:
			try:
				events = frappe.call(data[info]["get_events_method"], start, end)
				print(events)
			except:
				frappe.throw("some thing went wrong")

		else:
			
			start_date = "ifnull(%s, '0001-01-01 00:00:00')" % field_map.start
			end_date = "ifnull(%s, '2199-12-31 00:00:00')" % field_map.end

			filters = [
				[info, start_date, '<=', end],
				[info, end_date, '>=', start],
			]
			try:
				events = frappe.get_list(info ,fields=fields,filters=filters)
			except:
				frappe.throw("Something  when wrong")

		for event in events:
				color = "#D2D1FB"

				if field_map.color in event:
					color = event[field_map.color] if event[field_map.color] else "#D2D1FB"

				master_events.append({'start': str(event[field_map.start]),
										'end': str(event[field_map.end]),
										"title" : str(event[field_map.title]),
										"id" : str(event['name']),
										"description": str(event[field_map.description]),
										"color": str(color),
										"doctype" : str(info),
										"textColor": "#4D4DA8"
									})

	return master_events

@frappe.whitelist()
def update_event(start, end, doctype, name):
	try:
		data = get_field_map()
		field_map = frappe._dict(data[doctype]["field_map"])
		doc = frappe.get_doc(doctype, name)
		doc.set(field_map.start, start)
		doc.set(field_map.end, end)
		doc.save()
		return 1
	except:
		return 0

@frappe.whitelist()
def get_all_calendars():
	
	data = get_field_map()

	more_cal = []
	for key in data:
		more_cal.append(key)
	
	return more_cal

@frappe.whitelist()
def get_field_map():

	all_apps =frappe.get_all_apps() 
	data = {}
	for app in all_apps:
		app_path =frappe.get_app_path(app)
		map_path = app_path + '/calendar_map.json'
		if os.path.exists(map_path):
			with open(map_path) as f:
				d = json.load(f)
				fm = frappe._dict(d)
				data.update(fm)
	return data









