# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 
from __future__ import unicode_literals
import frappe
from frappe.utils import cstr

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def autoname(self):
		self.doc.name = self.doc.dt + "-" + self.doc.script_type

	def on_update(self):
		frappe.clear_cache(doctype=self.doc.dt)
	
	def on_trash(self):
		frappe.clear_cache(doctype=self.doc.dt)

