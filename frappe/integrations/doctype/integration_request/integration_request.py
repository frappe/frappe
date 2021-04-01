# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import json
from six import string_types
from frappe.integrations.utils import json_handler

class IntegrationRequest(Document):
	def autoname(self):
		if self.flags._name:
			self.name = self.flags._name

	def update_status(self, params, status):
		data = json.loads(self.data)
		data.update(params)

		self.data = json.dumps(data)
		self.status = status
		self.save(ignore_permissions=True)
		frappe.db.commit()

	def handle_success(self, response):
		"""update the output field with the response along with the relevant status"""
		if isinstance(response, string_types):
			response = json.loads(response)
		self.db_set("status", "Completed")
		self.db_set("output", json.dumps(response, default=json_handler))

	def handle_failure(self, response):
		"""update the error field with the response along with the relevant status"""
		if isinstance(response, string_types):
			response = json.loads(response)
		self.db_set("status", "Failed")
		self.db_set("error", json.dumps(response, default=json_handler))