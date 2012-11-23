from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, doc, doclist):
		self.doc, self.doclist = doc, doclist
		
	def autoname(self):
		self.doc.name = self.doc.name.title()
		
	def validate(self):
		"""only administrator can save standard report"""
		if self.doc.is_standard == "Yes" and webnotes.session.user!="Administrator":
			webnotes.msgprint("""Only Administrator can save a standard report.
			Please rename and save.""", raise_exception=True)

	def on_update(self):
		self.export_doc()
	
	def export_doc(self):
		# export
		import conf
		if self.doc.is_standard == 'Yes' and getattr(conf, 'developer_mode', 0) == 1:
			from webnotes.modules.export_file import export_to_files
			export_to_files(record_list=[['Report', self.doc.name]], 
				record_module=webnotes.conn.get_value("DocType", self.doc.ref_doctype, "module"))	