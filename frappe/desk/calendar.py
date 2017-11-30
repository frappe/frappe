# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
import json

@frappe.whitelist()
def update_event(args, field_map):
	"""Updates Event (called via calendar) based on passed `field_map`"""
	args = frappe._dict(json.loads(args))
	field_map = frappe._dict(json.loads(field_map))
	w = frappe.get_doc(args.doctype, args.name)
	w.set(field_map.start, args[field_map.start])
	w.set(field_map.end, args.get(field_map.end))
	w.save()

def get_event_conditions(doctype, filters=None):
	"""Returns SQL conditions with user permissions and filters for event queries"""
	from frappe.desk.reportview import get_filters_cond
	if not frappe.has_permission(doctype):
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	return get_filters_cond(doctype, filters, [], with_match_conditions = True)

@frappe.whitelist()
def get_events(doctype, start, end, field_map, filters=None, fields=None):
	field_map = frappe._dict(json.loads(field_map))

	if filters:
		filters = json.loads(filters or '')

	if not fields:
		fields = [field_map.start, field_map.end, field_map.title, 'name']

	filters += [
		[doctype, field_map.start, '<=', end],
		[doctype, field_map.end, '>=', start],
	]

	return frappe.get_list(doctype, fields=fields, filters=filters)
