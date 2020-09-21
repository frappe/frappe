# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import os
from frappe.model.document import Document
from frappe import _
from frappe.modules.export_file import (
	export_to_files,
	create_folder,
	get_module_path,
	scrub_dt_dn,
)


class WebTemplate(Document):
	def validate(self):
		if self.standard and not (frappe.conf.developer_mode or frappe.flags.in_patch):
			frappe.throw(_("Enable developer mode to create a standard Web Template"))

		for field in self.fields:
			if not field.fieldname:
				field.fieldname = frappe.scrub(field.label)

		if self.standard and not self.module:
			frappe.throw(_("Please select which module this Web Template belongs to."))

	def on_update(self):
		if self.standard and frappe.conf.developer_mode:
			export_to_files(record_list=[["Web Template", self.name]], create_init=True)
			self.create_template_file()

	def create_template_file(self):
		"""Touch a HTML file for the Web Template and add existing content, if any."""
		if self.standard:
			module = self.module or "Website" # required for smooth migration
			folder = create_folder(module, self.doctype, self.name, False)
			path = os.path.join(folder, frappe.scrub(self.name) + ".html")
			if not os.path.exists(path):
				with open(path, "w") as template_file:
					if self.template:
						template_file.write(self.template)

	def render(self, values):
		values = values or "{}"
		values = frappe.parse_json(values)
		return get_rendered_template(self.name, values)


def get_rendered_template(web_template_name, values):
	web_template = frappe.get_doc("Web Template", web_template_name)

	if web_template.standard:
		module_path = get_module_path(web_template.module)
		dt, dn = scrub_dt_dn("Web Template", web_template.name)
		scrubbed = frappe.scrub(web_template.name)
		full_path = os.path.join("frappe", module_path, dt, dn, scrubbed + ".html")
		root_app_path = os.path.abspath(os.path.join(frappe.get_app_path("frappe"), ".."))
		template = os.path.relpath(full_path, root_app_path)
	else:
		template = web_template.template

	context = values or {}
	context.update({"values": values})
	return frappe.render_template(template, context)
