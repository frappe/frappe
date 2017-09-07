from __future__ import unicode_literals
import frappe
from frappe.frappeclient import FrappeClient
from .base import BaseConnection

class FrappeConnection(BaseConnection):
	def __init__(self, connector):
		self.connector = connector
		self.connection = FrappeClient(self.connector.hostname,
			self.connector.username, self.connector.password)

	def push(self, doctype, doc, migration_id):
		doc.doctype = doctype
		if migration_id:
			doc.name = migration_id
			self.connection.update(doc)
		else:
			self.connection.insert(doc)
