# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _

class GlobalSearchSettings(Document):

	def validate(self):
		dts, core_dts, repeated_dts = [], [], []

		for dt in self.allowed_in_global_search:
			if dt.document_type in dts:
				repeated_dts.append(dt.document_type)

			if frappe.get_meta(dt.document_type).module == "Core":
				core_dts.append(dt.document_type)

			dts.append(dt.document_type)

		if core_dts:
			core_dts = (", ".join([frappe.bold(dt) for dt in core_dts]))
			frappe.throw(_("Core Modules {0} cannot be searched in Global Search.").format(core_dts))

		if repeated_dts:
			repeated_dts = (", ".join([frappe.bold(dt) for dt in repeated_dts]))
			frappe.throw(_("Document Type {0} has been repeated.").format(repeated_dts))

def get_doctypes_for_global_search():
	doctypes = frappe.get_list("Global Search DocType", fields=["document_type"], order_by="idx ASC")
	if not doctypes:
		return []

	return [d.document_type for d in doctypes]

@frappe.whitelist()
def reset_global_search_settings_doctypes():
	update_global_search_doctypes()

def update_global_search_doctypes():
	global_search_doctypes = frappe.get_hooks("global_search_doctypes")
	doctype_list = set([dt.name for dt in frappe.get_list("DocType")])
	allowed_in_global_search = []

	for dt in global_search_doctypes:
		if dt.get("index") is not None:
			allowed_in_global_search.insert(dt.get("index"), dt.get("doctype"))
			continue

		allowed_in_global_search.append(dt.get("doctype"))

	global_search_settings = frappe.get_single("Global Search Settings")
	global_search_settings.allowed_in_global_search = []
	for dt in allowed_in_global_search:
		if dt not in doctype_list:
			continue

		global_search_settings.append("allowed_in_global_search", {
			"document_type": dt
		})
	global_search_settings.save(ignore_permissions=True)