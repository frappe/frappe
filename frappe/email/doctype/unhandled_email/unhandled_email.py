# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class UnhandledEmail(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		email_account: DF.Link | None
		message_id: DF.Code | None
		raw: DF.Code | None
		reason: DF.LongText | None
		uid: DF.Data | None
	# end: auto-generated types
	pass


def remove_old_unhandled_emails():
	frappe.db.delete(
		"Unhandled Email", {"creation": ("<", frappe.utils.add_days(frappe.utils.nowdate(), -30))}
	)
