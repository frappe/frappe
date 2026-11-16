# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WorkflowTransitionTasks(Document):
	_DOCTYPE_NAME = "Workflow Transition Tasks"

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

	def validate(self):
		for task in self.tasks:
			if task.task in ("Server Script", "Webhook") and not task.link:
				frappe.throw(
					_("Row #{0}: {1} is required").format(task.idx, frappe.bold(_(task.task))),
					frappe.MandatoryError,
				)
