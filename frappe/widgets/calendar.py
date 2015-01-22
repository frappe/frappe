# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
import json

@frappe.whitelist()
def update_event(args, field_map):
	args = frappe._dict(json.loads(args))
	field_map = frappe._dict(json.loads(field_map))
	w = frappe.get_doc(args.doctype, args.name)
	w.set(field_map.start, args[field_map.start])
	w.set(field_map.end, args.get(field_map.end))
	w.save()

