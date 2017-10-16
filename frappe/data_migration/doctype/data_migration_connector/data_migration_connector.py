# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _
from .connectors.base import BaseConnection
from .connectors.postgres import PostGresConnection
from .connectors.frappe_connection import FrappeConnection

class DataMigrationConnector(Document):
	def validate(self):
		if not (self.python_module or self.connector_type):
			frappe.throw(_('Enter python module or select connector type'))

		if self.python_module:
			try:
				get_connection_class(self.python_module)
			except:
				frappe.throw(frappe._('Invalid module path'))

	def get_connection(self):
		if self.python_module:
			_class = get_connection_class(self.python_module)
			return _class(self)
		else:
			if self.connector_type == 'Frappe':
				self.connection = FrappeConnection(self)
			elif self.connector_type == 'PostGres':
				self.connection = PostGresConnection(self.as_dict())

		return self.connection

def get_connection_class(python_module):
	filename = python_module.rsplit('.', 1)[-1]
	classname = frappe.unscrub(filename).replace(' ', '')
	module = frappe.get_module(python_module)

	raise_error = False
	if hasattr(module, classname):
		_class = getattr(module, classname)
		if not issubclass(_class, BaseConnection):
			raise_error = True
	else:
		raise_error = True

	if raise_error:
		raise ImportError(filename)

	return _class
