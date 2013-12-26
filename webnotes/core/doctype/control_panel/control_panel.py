# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes

from webnotes import form, msgprint
import webnotes.defaults

class DocType:
	def __init__(self, doc, doclist):
		self.doc = doc
		self.doclist = doclist

	def on_update(self):
		# clear cache on save
		webnotes.cache().delete_value('time_zone')
		webnotes.clear_cache()
