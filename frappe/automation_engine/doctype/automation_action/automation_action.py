# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class AutomationAction(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		action_type: DF.Literal["SetFieldValue", "CreateDocument", "SendNotification", "AssignToUser"]
		params: DF.JSON | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		step_condition: DF.Code | None
		step_type: DF.Literal["Action", "Wait", "If", "Else"]
	# end: auto-generated types

	pass
