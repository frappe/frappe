# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class ContactUsSettings(Document):
	def on_update(self):
		from frappe.website.utils import clear_cache

		clear_cache("contact")
