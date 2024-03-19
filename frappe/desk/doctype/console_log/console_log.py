# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class ConsoleLog(Document):
	def after_delete(self):
		# because on_trash can be bypassed
		frappe.throw(frappe._("Console Logs can not be deleted"))
