# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class GoogleSettings(Document):

	def validate(self):
		if not (self.client_id and self.client_secret):
			frappe.throw(_("Set Client ID and Client Secret for Google Integrations."))
