from __future__ import unicode_literals
import datetime
import frappe
from frappe.desk.notifications import get_notifications
from frappe.utils.kick.query import Query
from frappe.utils.kick.helper import *

class Engine(object):
	def __init__(self, params):
		self.params = params
		self.query = params.query.lower()
		self.query_helper = Query(self.query)
		self.prepare_doctype_names(frappe.get_list('DocType', {"istable":0}))
	
	def prepare_doctype_names(self, doctypes):
		self.doctype_names = {d.name.lower():d.name for d in doctypes}
		self.prepare_tables(doctypes)

	def prepare_tables(self, doctypes):
		self.tables = filter(lambda x: x in self.query or x[:-1] in self.query, 
			[d.name.lower() for d in doctypes])
		self.query_helper.append_open(self.doctype_names)

	def get_doctype(self):
		return self.doctype_names[self.tables[0]]
	
	










