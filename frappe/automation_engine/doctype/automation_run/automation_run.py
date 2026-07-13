# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class AutomationRun(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.automation_engine.doctype.automation_run_step.automation_run_step import AutomationRunStep
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
			"Queued",
			"Running",
			"Waiting",
			"Success",
			"Partially Failed",
			"Failed",
			"Skipped",
			"Simulated",
		]
		steps: DF.Table[AutomationRunStep]
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days=90):
		frappe.db.delete(
			"Automation Run",
			{"creation": ("<", frappe.utils.add_days(frappe.utils.now(), -days))},
		)


def on_doctype_update():
	frappe.db.add_index("Automation Run", ["automation", "creation"])
	frappe.db.add_index("Automation Run", ["reference_doctype", "reference_name"])
