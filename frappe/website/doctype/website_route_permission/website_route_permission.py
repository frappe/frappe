# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.website.permissions import remove_empty_permissions, clear_permissions

from frappe.model.document import Document

class WebsiteRoutePermission(Document):
		
	def on_update(self):
		remove_empty_permissions()
		clear_permissions(self.user)
		