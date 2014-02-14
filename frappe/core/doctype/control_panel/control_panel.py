# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe

from frappe import form, msgprint
import frappe.defaults

class DocType:
	def __init__(self, doc, doclist):
		self.doc = doc
		self.doclist = doclist

	def on_update(self):
		# clear cache on save
		frappe.cache().delete_value('time_zone')
		frappe.clear_cache()
