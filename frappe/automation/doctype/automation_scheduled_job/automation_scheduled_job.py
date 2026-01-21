# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class AutomationScheduledJob(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		automation_rule: DF.Link | None
		completed_at: DF.Datetime | None
		execute_at: DF.Datetime | None
		fieldname: DF.Data | None
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		status: DF.Literal["Scheduled", "Completed", "Cancelled", "Failed"]
	# end: auto-generated types

	pass
