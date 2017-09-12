from __future__ import unicode_literals
import frappe
from frappe.frappeclient import FrappeClient, FrappeException
from .base import BaseConnection

class FrappeConnection(BaseConnection):
	def __init__(self, connector):
		self.connector = connector
		self.connection = FrappeClient(self.connector.hostname,
			self.connector.username, self.connector.password)

	def push(self, doctype, doc, migration_id):
		doc.doctype = doctype
		try:
			if migration_id:
				doc.name = migration_id
				response_doc = self.connection.update(doc)
			else:
				response_doc = self.connection.insert(doc)
			return frappe._dict(dict(
				doc=response_doc,
				ok=True
			))
		except FrappeException as e:
			frappe.msgprint(e.args[0])
			return frappe._dict(dict(
				doc=doc,
				ok=False
			))
			# raise frappe.ValidationError