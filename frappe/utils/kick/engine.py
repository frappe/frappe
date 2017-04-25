from __future__ import unicode_literals
import datetime
import frappe, re
from frappe.utils.kick.query import Query
from frappe.utils.kick.helper import *
from frappe.utils.kick.constant import *
from frappe.utils.kick.bot import Bot


class Engine(object):

	def __init__(self, params):
		self.params = params
		self.query = params.query.lower()
		self.prepare_doctype_names(frappe.get_list('DocType', {"istable": 0}))

	def prepare_doctype_names(self, doctypes):
		self.doctype_names = {d.name.lower(): d.name for d in doctypes}
		self.prepare_tables(doctypes)

	def prepare_tables(self, doctypes):
		self.tables = filter(lambda x: x in self.query or x[:-1] in self.query,
							 [d.name.lower() for d in doctypes])
		self.append_show()
	
	def append_show(self):
		contains = filter(lambda x: self.doctype_names.get(x) is not None, 
			[i for i in self.doctype_names])
		self.query = 'show ' + self.query if len(contains) > 0 else self.query

	def get_doctype(self):
		return self.doctype_names[self.tables[0]]
	
	def get_reply(self):
		return getattr(Bot, 'Bot')(self.get_doctype(), self.params, self.tables) \
			.get_reply_from_action(Query(self.query).get_action_from_text(self.params))
	




