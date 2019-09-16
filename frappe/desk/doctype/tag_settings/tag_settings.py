# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class TagSettings(Document):

	def validate(self):
		core_dts = []
		for dt in self.allowed_in_global_search:
			if frappe.get_meta(dt.document_type).module == "Core":
				core_dts.append(dt.document_type)

		if core_dts:
			core_dts = (", ".join([frappe.bold(dt) for dt in core_dts]))
			frappe.throw(_("Core Modules {0} cannot be searched in Tags.").format(core_dts))

def get_doctypes_for_global_search():
	doctypes = frappe.get_list("Tag DocType", fields=["document_type"], order_by="idx ASC")
	if not doctypes:
		return []

	return [d.document_type for d in doctypes]

@frappe.whitelist()
def reset_tag_settings_doctypes():
	update_global_tags_doctypes()

def update_global_tags_doctypes():
	global_tags_doctypes = frappe.get_list("DocType", filters=[["module", "!=", "Core"]])

	tag_settings = frappe.get_single("Tag Settings")
	tag_settings.allowed_in_global_tags = []
	for dt in global_tags_doctypes:
		tag_settings.append("allowed_in_global_tags", {
			"document_type": dt.name
		})
	tag_settings.save(ignore_permissions=True)