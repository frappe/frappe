# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class OAuthClient(Document):
	def validate(self):
		self.client_id = self.name
		if not self.client_secret:
			self.client_secret = frappe.generate_hash(length=10)
