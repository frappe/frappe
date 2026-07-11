# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class AutomationRun(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.automation.doctype.automation_run_step.automation_run_step import AutomationRunStep
		from frappe.types import DF

		actions_snapshot: DF.JSON | None
		automation: DF.Link | None
		automation_title: DF.Data | None
		depth: DF.Int
		ended_at: DF.Datetime | None
		error_summary: DF.SmallText | None
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		started_at: DF.Datetime | None
		status: DF.Literal[
			"Queued", "Running", "Waiting", "Success", "Partially Failed", "Failed", "Skipped"
		]
		steps: DF.Table[AutomationRunStep]
	# end: auto-generated types

	pass


def on_doctype_update():
	frappe.db.add_index("Automation Run", ["automation", "creation"])
	frappe.db.add_index("Automation Run", ["reference_doctype", "reference_name"])
