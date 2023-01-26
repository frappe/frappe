# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe


@frappe.whitelist()
def update_task(args, field_map):
	"""Updates Doc (called via gantt) based on passed `field_map`"""
	args = frappe._dict(json.loads(args))
	field_map = frappe._dict(json.loads(field_map))
	d = frappe.get_doc(args.doctype, args.name)
	d.set(field_map.start, args.start)
	d.set(field_map.end, args.end)
	d.save()
