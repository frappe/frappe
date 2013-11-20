# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def on_update(self):
		"""clear cache"""
		from webnotes.sessions import clear_cache
		clear_cache('Guest')

		from webnotes.webutils import clear_cache
		clear_cache()