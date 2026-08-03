# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class AutomationRunStep(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		action_type: DF.Data | None
		detail: DF.LongText | None
		output: DF.JSON | None
		duration_ms: DF.Int
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		status: DF.Literal["Success", "Failed", "Skipped", "Waiting"]
		step_idx: DF.Int
	# end: auto-generated types

	pass
