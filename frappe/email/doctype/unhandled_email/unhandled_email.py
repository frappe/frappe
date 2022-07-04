# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class UnhandledEmail(Document):
	pass


def remove_old_unhandled_emails():
	frappe.db.delete(
		"Unhandled Email", {"creation": ("<", frappe.utils.add_days(frappe.utils.nowdate(), -30))}
	)
