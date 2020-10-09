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

	def handle_sucess(self, response):
		"""update the output field with the response along with the relevant status"""
		self.process_response("output", response)

	def handle_failure(self, response):
		"""update the error field with the response along with the relevant status"""
		self.process_response("error", response)

	def process_response(self, ref_field, response):
		"""Update the response in integration request with status based on reference"""
		if isinstance(response, string_types):
			response = json.loads(response)

		status = "Completed" if ref_field == "output" else "Failed"
		self.db_set(ref_field, json.dumps(response, default=json_handler))
		self.db_set("status", status)