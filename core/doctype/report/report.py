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