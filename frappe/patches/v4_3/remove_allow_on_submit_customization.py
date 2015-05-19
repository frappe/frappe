# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	for d in frappe.get_all("Property Setter", fields=["name", "doc_type"],
		filters={"doctype_or_field": "DocField", "property": "allow_on_submit", "value": "1"}):
		frappe.delete_doc("Property Setter", d.name)
		frappe.clear_cache(doctype=d.doc_type)
