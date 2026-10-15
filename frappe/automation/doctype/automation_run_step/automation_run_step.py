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
		condition: DF.Code | None
		condition_values: DF.JSON | None
		detail: DF.LongText | None
		duration_ms: DF.Int
		exception: DF.Data | None
		message: DF.SmallText | None
		output: DF.JSON | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		status: DF.Literal["Success", "Failed", "Skipped", "Waiting"]
		step_idx: DF.Int
		step_key: DF.Data | None
		traceback: DF.Code | None
	# end: auto-generated types

	_DOCTYPE_NAME = "Automation Run Step"
