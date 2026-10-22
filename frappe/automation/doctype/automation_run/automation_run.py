# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now


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
		queue_row: DF.Data | None
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		relationships: DF.JSON | None
		run_state: DF.JSON | None
		started_at: DF.Datetime | None
		status: DF.Literal["Running", "Waiting", "Success", "Partially Failed", "Failed", "Skipped"]
		steps: DF.Table[AutomationRunStep]
		user: DF.Link | None
	# end: auto-generated types

	_DOCTYPE_NAME = "Automation Run"

	@staticmethod
	def clear_old_logs(days=30):
		# A Waiting run is still owed a resume, however long ago it started.
		run = frappe.qb.DocType("Automation Run")
		old = (run.creation < (Now() - Interval(days=days))) & (run.status != "Waiting")
		names = frappe.qb.from_(run).select(run.name).where(old)
		step = frappe.qb.DocType("Automation Run Step")
		frappe.db.delete(step, filters=step.parent.isin(names))
		frappe.db.delete(run, filters=old)


def on_doctype_update():
	frappe.db.add_index("Automation Run", ["automation", "creation"])
	frappe.db.add_index("Automation Run", ["reference_doctype", "reference_name"])
