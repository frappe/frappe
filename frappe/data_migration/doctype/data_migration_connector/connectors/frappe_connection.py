from __future__ import unicode_literals
import frappe
from frappe.frappeclient import FrappeClient, FrappeException
from .base import BaseConnection

class FrappeConnection(BaseConnection):
	def __init__(self, connector):
		self.connector = connector
		self.connection = FrappeClient(self.connector.hostname,
			self.connector.username, self.connector.password)

	def insert(self, doctype, doc):
		doc = frappe._dict(doc)
		doc.doctype = doctype
		try:
			response_doc = self.connection.insert(doc)
			return frappe._dict(dict(
				data=response_doc,
				migration_id_value=response_doc['name'],
				ok=True
			))
		except FrappeException as e:
			frappe.msgprint(e.args[0])
			return frappe._dict(dict(
				doc=doc,
				ok=False,
				error=e.args[0]
			))
			# raise frappe.ValidationError

	def update(self, doctype, doc, migration_id):
		doc = frappe._dict(doc)
		doc.doctype = doctype
		doc.name = migration_id
		try:
			response_doc = self.connection.update(doc)
			return frappe._dict(dict(
				doc=response_doc,
				ok=True
			))
		except FrappeException as e:
			frappe.msgprint(e.args[0])
			return frappe._dict(dict(
				doc=doc,
				ok=False,
				error=e.args[0]
			))

	def delete(self, doctype, migration_id):
		try:
			self.connection.delete(doctype, migration_id)
			return frappe._dict(dict(
				ok=True
			))
		except FrappeException as e:
			return handle_error(e)

	def get_list(self, doctype, fields='"*"', filters=None, start=0, page_length=20):
		try:
			doc_list = self.connection.get_list(doctype, fields=fields, filters=filters,
				limit_start=start, limit_page_length=page_length)
			return frappe._dict(dict(
				data=doc_list,
				migration_id_field='name',
				ok=True
			))
		except FrappeException as e:
			return handle_error(e)

def handle_error(e):
	frappe.msgprint(e.args[0])
	return frappe._dict(dict(
		ok=False,
		error=e.args[0]
	))