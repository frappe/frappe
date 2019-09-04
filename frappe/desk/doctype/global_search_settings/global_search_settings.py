# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _

class GlobalSearchSettings(Document):

	def validate(self):
		core_dts = []
		for dt in self.allowed_in_global_search:
			if frappe.get_meta(dt.document).module == "Core":
				core_dts.append(dt.document)

		if core_dts:
			core_dts = (", ".join([frappe.bold(dt) for dt in core_dts]))
			frappe.throw(_("Core Modules {0} cannot be searched in Global Search.").format(core_dts))

def get_doctypes_for_global_search(as_list=False):
	doctypes = frappe.get_list("Global Search Allow", fields=["document"], order_by="idx ASC")
	if not doctypes:
		return []

	dts = [d.document for d in doctypes]
	if as_list:
		return dts

	return ",".join(["'{0}'".format(dt) for dt in dts])