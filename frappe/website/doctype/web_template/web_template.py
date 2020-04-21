# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import os
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files, create_folder, get_module_path, scrub_dt_dn


class WebTemplate(Document):
	def validate(self):
		for field in self.fields:
			if not field.fieldname:
				field.fieldname = frappe.scrub(field.label)

	def on_update(self):
		if self.standard and frappe.conf.developer_mode:
			export_to_files(record_list=[["Web Template", self.name]], create_init=True)
			self.create_template_file()

	def create_template_file(self):
		if self.standard:
			folder = create_folder("Website", self.doctype, self.name, False)
			path = os.path.join(folder, frappe.scrub(self.name) + '.html')
			if not os.path.exists(path):
				open(path, 'w').close()

	def render(self, values):
		return get_rendered_template(self.name, values)


def get_rendered_template(web_template, values):
	standard = frappe.db.get_value("Web Template", web_template, "standard")
	if standard:
		module_path = get_module_path("Website")
		dt, dn = scrub_dt_dn("Web Template", web_template)
		scrubbed = frappe.scrub(web_template)
		full_path = os.path.join("frappe", module_path, dt, dn, scrubbed + ".html")
		root_app_path = os.path.abspath(os.path.join(frappe.get_app_path('frappe'), '..'))
		template = os.path.relpath(full_path, root_app_path)
	else:
		template = frappe.db.get_value("Web Template", web_template, "template")

	context = values or {}
	context.update({'values': values})
	return frappe.render_template(template, context)
