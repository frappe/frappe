# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ListViewSettings(Document):

	def on_update(self):
		frappe.clear_document_cache(self.doctype, self.name)

@frappe.whitelist()
def get_listview_columns(doctype):
	meta = frappe.get_meta(doctype)
	listview_columns = []

	subject_field = {
		"label": "Name",
		"fieldname": "name"
	}

	if meta.title_field:
		title_field = meta.get_field(meta.title_field)

		subject_field["label"] = title_field.label,
		subject_field["fieldname"] = title_field.fieldname

	listview_columns.append(subject_field)

	for field in meta.fields:
		if field.in_list_view and field.label and field.fieldname:
			listview_columns.append({
				"label": field.label,
				"fieldname": field.fieldname
			})

	return listview_columns