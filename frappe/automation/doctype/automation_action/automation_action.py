# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class AutomationAction(Document):
	"""One step of a flow.

	`step_key` is a stable identifier that outputs, aliases and resumed runs
	refer to a step by, so it must survive reordering. `parent_step` holds the
	idx of the enclosing If step (0 for top-level steps) and `branch` says
	which arm of that If the step belongs to; the builder maintains both.
	"""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		action_type: DF.Data | None
		branch: DF.Literal["", "If", "Else"]
		output_alias: DF.Data | None
		params: DF.JSON | None
		parent: DF.Data
		parent_step: DF.Int
		parentfield: DF.Data
		parenttype: DF.Data
		related_condition: DF.JSON | None
		step_condition: DF.Code | None
		step_key: DF.Data | None
		step_type: DF.Literal["Action", "Wait", "If", "Else"]
		target: DF.Data | None
	# end: auto-generated types

	pass
