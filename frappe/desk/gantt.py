# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe


@frappe.whitelist()
def update_task(args: str | dict, field_map: str | dict):
	"""Updates Doc (called via gantt) based on passed `field_map`"""
	args = frappe._dict(frappe.parse_json(args))
	field_map = frappe._dict(frappe.parse_json(field_map))
	d = frappe.get_doc(args.doctype, args.name)
	d.set(field_map.start, args.start)
	d.set(field_map.end, args.end)
	d.save()
