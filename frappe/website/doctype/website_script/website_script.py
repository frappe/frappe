# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

import frappe

from frappe.model.document import Document

class WebsiteScript(Document):

	def on_update(self):
		"""clear cache"""
		frappe.clear_cache(user = 'Guest')

		from frappe.website.utils import clear_cache
		clear_cache()