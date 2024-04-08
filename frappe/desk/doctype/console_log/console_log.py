# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class ConsoleLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		committed: DF.Check
		script: DF.Code | None
		type: DF.Data | None
	# end: auto-generated types

	def after_delete(self):
		# because on_trash can be bypassed
		frappe.throw(frappe._("Console Logs can not be deleted"))
