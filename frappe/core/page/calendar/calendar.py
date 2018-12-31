# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import os
import json


@frappe.whitelist()
def get_master_calendar_events(doctype_list, start=None, end=None):

	if isinstance(doctype_list, frappe.string_types):
		doctype_list = json.loads(doctype_list)

	data = get_field_map()

	master_events = []
	for doctype in doctype_list:
		if frappe.has_permission(doctype):
			field_map = frappe._dict(data[doctype]["field_map"])
			fields=[field_map.start, field_map.end, field_map.title, field_map.description, 'name']
			if field_map.color:
				fields.append(field_map.color)
			if "get_events_method" in data[doctype]:
				events = frappe.call(data[doctype]["get_events_method"], start, end)


			else:
				start_date = "ifnull(%s, '0001-01-01 00:00:00')" % field_map.start
				end_date = "ifnull(%s, '2199-12-31 00:00:00')" % field_map.end

				filters = [
					[doctype, start_date, '<=', end],
					[doctype, end_date, '>=', start],
				]

				events = frappe.get_list(doctype ,fields=fields,filters=filters)

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
					"doctype" : str(doctype),
					"textColor": "#4D4DA8"
				})

	return master_events

@frappe.whitelist()
def update_event(start, end, doctype, name):
	data = get_field_map()
	field_map = frappe._dict(data[doctype]["field_map"])
	doc = frappe.get_doc(doctype, name)
	doc.set(field_map.start, start)
	doc.set(field_map.end, end)
	doc.save()

@frappe.whitelist()
def get_all_calendars():
	data = get_field_map()
	allowed_cal = []
	for key in data:
		if frappe.has_permission(key):
			allowed_cal.append(key)
	return allowed_cal

@frappe.whitelist()
def get_field_map(doctype=None):
	all_apps = frappe.get_installed_apps()
	data = {}
	for app in all_apps:
		app_path = frappe.get_app_path(app)
		map_path = app_path + '/calendar_map.json'
		if os.path.exists(map_path):
			with open(map_path) as f:
				d = json.load(f)
				fm = frappe._dict(d)
				data.update(fm)

	return data[doctype] if doctype else data









