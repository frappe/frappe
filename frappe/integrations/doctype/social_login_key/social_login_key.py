# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, os
from frappe.model.document import Document
from frappe.modules.utils import export_module_json

class SocialLoginKey(Document):

	def autoname(self):
		self.name = frappe.scrub(self.provider_name)

	def after_insert(self):
		# Create `User Social Login` Child Table Row on `User` with fields Provider, Username and User ID
		pass

	def on_trash(self):
		# Delete Related User Social Login cdt on User
		pass
