# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from pprint import pprint
import json

@frappe.whitelist()
def get_master_calendar_events(doctypeinfo):
	import os
	current_path = os.path.dirname(__file__)
	with open(current_path + '/calendar_map.json') as f:
		data = json.load(f)

	doctypes=frappe.get_hooks("calendars")
	words = doctypeinfo.split(",")
	master_events = []
	for info in words:
		if(info in doctypes):
			field_map = frappe._dict(data[info]["field_map"])
			fields=[field_map.start, field_map.end, field_map.title, 'name']

			if field_map.color:
				fields.append(field_map.color)

			events = frappe.get_list(info ,fields=fields)
			for event in events:
					color = "#D2D1FB"

					if field_map.color in event:
						color = event[field_map.color] if event[field_map.color] else "#D2D1FB"

					master_events.append({'start': str(event[field_map.start]),
											'end': str(event[field_map.end]),
											"title" : str(info) +": "+ str(event[field_map.title]),
											"id" : str(event['name']),
											"color": str(color),
											"doctype" : str(info),
											"textColor": "#4D4DA8"
										})

	return master_events



