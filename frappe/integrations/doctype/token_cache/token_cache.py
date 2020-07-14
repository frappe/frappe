# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class TokenCache(Document):

	def get_auth_header(self):
		if self.access_token:
			headers = {'Authorization': 'Bearer ' + self.access_token}
			return headers

		raise frappe.exceptions.DoesNotExistError
