# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals

import frappe
from frappe import _, throw
from frappe.model.document import Document


class Currency(Document):
	def validate(self):
		if not frappe.flags.in_install_app:
			frappe.clear_cache()
