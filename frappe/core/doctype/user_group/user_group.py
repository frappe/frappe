# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe

# import frappe
from frappe.model.document import Document


class UserGroup(Document):
	def after_insert(self):
		frappe.cache().delete_key("user_groups")

	def on_trash(self):
		frappe.cache().delete_key("user_groups")
