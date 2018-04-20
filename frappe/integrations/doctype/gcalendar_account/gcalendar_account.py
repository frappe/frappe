# -*- coding: utf-8 -*-
# Copyright (c) 2018, DOKOS and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class GCalendarAccount(Document):
	def validate(self):
		if self.enabled == 1:
			self.create_google_connector()

	def create_google_connector(self):
		connector_name = 'Calendar Connector-' + self.name
		if frappe.db.exists('Data Migration Connector', connector_name):
			calendar_connector = frappe.get_doc('Data Migration Connector', connector_name)
			calendar_connector.connector_type = 'Custom'
			calendar_connector.python_module = 'frappe.data_migration.doctype.data_migration_connector.connectors.calendar_connector'
			calendar_connector.username = self.name
			calendar_connector.save()
			return

		frappe.get_doc({
			'doctype': 'Data Migration Connector',
			'connector_type': 'Custom',
			'connector_name': connector_name,
			'python_module': 'frappe.data_migration.doctype.data_migration_connector.connectors.calendar_connector',
			'username': self.name
		}).insert()
