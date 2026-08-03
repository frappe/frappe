# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class WorkflowState(Document):
	_DOCTYPE_NAME = "Workflow State"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		icon: DF.Icon | None
		style: DF.Literal["", "Primary", "Info", "Success", "Warning", "Danger", "Inverse"]
		workflow_state_name: DF.Data
	# end: auto-generated types

	pass
