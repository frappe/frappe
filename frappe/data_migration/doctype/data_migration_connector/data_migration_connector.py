# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.model.document import Document
from .connectors.postgres import PostGresConnection
from .connectors.frappe_connection import FrappeConnection

class DataMigrationConnector(Document):
	def get_connection(self):
		if self.connector_type == 'Frappe':
			self.connection = FrappeConnection(self)
		elif self.connector_type == 'PostGres':
			self.connection = PostGresConnection(self.as_dict())

		return self.connection

	def get_objects(self, object_type, condition=None, selection="*"):
		return self.connector.get_objects(object_type, condition, selection)

	def get_join_objects(self, object_type, join_type, primary_key):
		return self.connector.get_join_objects(object_type, join_type, primary_key)
