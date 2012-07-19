from __future__ import unicode_literals
class DocType:
	def __init__(self, doc, doclist):
		self.doc, self.doclist = doc, doclist
		
	def autoname(self):
		self.doc.name = self.doc.name.title()