# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import conf, _

from frappe.model.document import Document

class Report(Document):
	def __init__(self, doc, doclist):
		self.doc, self.doclist = doc, doclist
		
	def validate(self):
		"""only administrator can save standard report"""
		if not self.doc.module:
			self.doc.module = frappe.db.get_value("DocType", self.doc.ref_doctype, "module")
		
		if not self.doc.is_standard:
			self.doc.is_standard = "No"
			if frappe.session.user=="Administrator" and getattr(conf, 'developer_mode',0)==1:
				self.doc.is_standard = "Yes"

		if self.doc.is_standard == "Yes" and frappe.session.user!="Administrator":
			frappe.msgprint(_("Only Administrator can save a standard report. Please rename and save."), 
				raise_exception=True)

		if self.doc.report_type in ("Query Report", "Script Report") \
			and frappe.session.user!="Administrator":
			frappe.msgprint(_("Only Administrator allowed to create Query / Script Reports"),
				raise_exception=True)
				
	def on_update(self):
		self.export_doc()
	
	def export_doc(self):
		from frappe.modules.export_file import export_to_files
		if self.doc.is_standard == 'Yes' and (conf.get('developer_mode') or 0) == 1:
			export_to_files(record_list=[['Report', self.doc.name]], 
				record_module=self.doc.module)
