# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files
from frappe.modules import make_boilerplate

class Report(Document):
	def validate(self):
		"""only administrator can save standard report"""
		if not self.module:
			self.module = frappe.db.get_value("DocType", self.ref_doctype, "module")

		if not self.is_standard:
			self.is_standard = "No"
			if frappe.session.user=="Administrator" and getattr(frappe.local.conf, 'developer_mode',0)==1:
				self.is_standard = "Yes"

		if self.is_standard == "No" and frappe.db.get_value("Report", self.name, "is_standard") == "Yes":
			frappe.throw(_("Cannot edit a standard report. Please duplicate and create a new report"))

		if self.is_standard == "Yes" and frappe.session.user!="Administrator":
			frappe.throw(_("Only Administrator can save a standard report. Please rename and save."))

		if self.report_type in ("Query Report", "Script Report") \
			and frappe.session.user!="Administrator":
			frappe.throw(_("Only Administrator allowed to create Query / Script Reports"))

	def on_update(self):
		self.export_doc()

	def export_doc(self):
		if frappe.flags.in_import:
			return

		if self.is_standard == 'Yes' and (frappe.local.conf.get('developer_mode') or 0) == 1:
			export_to_files(record_list=[['Report', self.name]],
				record_module=self.module)

			self.create_report_py()

	def create_report_py(self):
		if self.report_type == "Script Report":
			make_boilerplate("controller.py", self, {"name": self.name})
			make_boilerplate("controller.js", self, {"name": self.name})

	@Document.whitelist
	def toggle_disable(self, disable):
		self.db_set("disabled", cint(disable))
