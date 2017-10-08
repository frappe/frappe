# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from .connectors.postgres import PostGresConnection
from .connectors.frappe_connection import FrappeConnection

class DataMigrationConnector(Document):
	def validate(self):
		if not (self.python_module or self.connector_type):
			frappe.throw(_('Enter python module or select connector type'))

		if self.python_module:
			try:
				frappe.get_module(self.python_module)
			except:
				frappe.throw(frappe._('Invalid module path'))

	def get_connection(self):
		if self.python_module:
			module = frappe.get_module(self.python_module)
			return module.get_connection(self)
		else:
			if self.connector_type == 'Frappe':
				self.connection = FrappeConnection(self)
			elif self.connector_type == 'PostGres':
				self.connection = PostGresConnection(self.as_dict())

		return self.connection

	def get_objects(self, object_type, condition=None, selection="*"):
		return self.connector.get_objects(object_type, condition, selection)

	def get_join_objects(self, object_type, join_type, primary_key):
		return self.connector.get_join_objects(object_type, join_type, primary_key)
