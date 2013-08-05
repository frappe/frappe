# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes

from webnotes import form, msgprint

class DocType:
	def __init__(self, doc, doclist):
		self.doc = doc
		self.doclist = doclist

	def on_update(self):
		# clear cache on save
		webnotes.clear_cache()

	def upload_many(self,form):
		pass

	def upload_callback(self,form):
		pass
		
	def execute_test(self, arg=''):
		if webnotes.user.name=='Guest':
			raise Exception, 'Guest cannot call execute test!'
		out = ''
		exec(arg and arg or self.doc.test_code)
		webnotes.msgprint('that worked!')
		return out
