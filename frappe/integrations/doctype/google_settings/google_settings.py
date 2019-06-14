# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe import _

class GoogleSettings(Document):

	def validate(self):
		if self.enable and not (self.client_id and self.client_secret):
			frappe.throw(_("Client ID and Client Secret cannot be empty."))
