# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WorkflowTransitionTasks(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from frappe.workflow.doctype.workflow_transition_task.workflow_transition_task import (
			WorkflowTransitionTask,
		)

		tasks: DF.Table[WorkflowTransitionTask]
	# end: auto-generated types

	pass
