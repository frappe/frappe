# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class GlobalTagsSettings(Document):

	def validate(self):
		core_dts = []
		for dt in self.allowed_in_global_search:
			if frappe.get_meta(dt.document_type).module == "Core":
				core_dts.append(dt.document_type)

		if core_dts:
			core_dts = (", ".join([frappe.bold(dt) for dt in core_dts]))
			frappe.throw(_("Core Modules {0} cannot be searched in Global Tags.").format(core_dts))

def get_doctypes_for_global_search():
	doctypes = frappe.get_list("Global Tags DocType", fields=["document_type"], order_by="idx ASC")
	if not doctypes:
		return []

	return [d.document_type for d in doctypes]

@frappe.whitelist()
def reset_global_tags_settings_doctypes():
	update_global_tags_doctypes()

def update_global_tags_doctypes():
	global_tags_doctypes = frappe.get_list("DocType", filters=[["module", "!=", "Core"]])

	global_tags_settings = frappe.get_single("Global Search Settings")
	global_tags_settings.allowed_in_global_tags = []
	for dt in global_tags_doctypes:
		global_tags_settings.append("allowed_in_global_tags", {
			"document_type": dt.name
		})
	global_tags_settings.save(ignore_permissions=True)