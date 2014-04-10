# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import conf, _

from frappe.model.document import Document

class Report(Document):
	def validate(self):
		"""only administrator can save standard report"""
		if not self.module:
			self.module = frappe.db.get_value("DocType", self.ref_doctype, "module")
		
		if not self.is_standard:
			self.is_standard = "No"
			if frappe.session.user=="Administrator" and getattr(conf, 'developer_mode',0)==1:
				self.is_standard = "Yes"

		if self.is_standard == "Yes" and frappe.session.user!="Administrator":
			frappe.msgprint(_("Only Administrator can save a standard report. Please rename and save."), 
				raise_exception=True)

		if self.report_type in ("Query Report", "Script Report") \
			and frappe.session.user!="Administrator":
			frappe.msgprint(_("Only Administrator allowed to create Query / Script Reports"),
				raise_exception=True)
				
	def on_update(self):
		self.export_doc()
	
	def export_doc(self):
		from frappe.modules.export_file import export_to_files
		if self.is_standard == 'Yes' and (conf.get('developer_mode') or 0) == 1:
			export_to_files(record_list=[['Report', self.name]], 
				record_module=self.module)
