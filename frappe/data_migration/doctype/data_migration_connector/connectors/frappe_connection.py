from __future__ import unicode_literals

import frappe
from frappe.frappeclient import FrappeClient

from .base import BaseConnection


class FrappeConnection(BaseConnection):
	def __init__(self, connector):
		self.connector = connector
		self.connection = FrappeClient(
			self.connector.hostname, self.connector.username, self.get_password()
		)
		self.name_field = "name"

	def insert(self, doctype, doc):
		doc = frappe._dict(doc)
		doc.doctype = doctype
		return self.connection.insert(doc)

	def update(self, doctype, doc, migration_id):
		doc = frappe._dict(doc)
		doc.doctype = doctype
		doc.name = migration_id
		return self.connection.update(doc)

	def delete(self, doctype, migration_id):
		return self.connection.delete(doctype, migration_id)

	def get(self, doctype, fields='"*"', filters=None, start=0, page_length=20):
		return self.connection.get_list(
			doctype, fields=fields, filters=filters, limit_start=start, limit_page_length=page_length
		)
