# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class Currency(Document):
	def validate(self):
		if not frappe.flags.in_install_app:
			frappe.clear_cache()
