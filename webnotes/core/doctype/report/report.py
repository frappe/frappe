# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes import conf, _

class DocType:
	def __init__(self, doc, doclist):
		self.doc, self.doclist = doc, doclist
		
	def validate(self):
		"""only administrator can save standard report"""
		if not self.doc.is_standard:
			self.doc.is_standard = "No"
			if webnotes.session.user=="Administrator" and getattr(conf, 'developer_mode',0)==1:
				self.doc.is_standard = "Yes"

		if self.doc.is_standard == "Yes" and webnotes.session.user!="Administrator":
			webnotes.msgprint(_("Only Administrator can save a standard report. Please rename and save."), 
				raise_exception=True)

		if self.doc.report_type in ("Query Report", "Script Report") \
			and webnotes.session.user!="Administrator":
			webnotes.msgprint(_("Only Administrator allowed to create Query / Script Reports"),
				raise_exception=True)

	def on_update(self):
		self.export_doc()
	
	def export_doc(self):
		from webnotes.modules.export_file import export_to_files
		if self.doc.is_standard == 'Yes' and (conf.get('developer_mode') or 0) == 1:
			export_to_files(record_list=[['Report', self.doc.name]], 
				record_module=webnotes.conn.get_value("DocType", self.doc.ref_doctype, "module"))
