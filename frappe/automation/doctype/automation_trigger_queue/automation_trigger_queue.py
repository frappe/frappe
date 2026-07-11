# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class AutomationTriggerQueue(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		attempt: DF.Int
		automation: DF.Link
		depth: DF.Int
		event_payload: DF.JSON | None
		ref_doctype: DF.Data | None
		ref_name: DF.Data | None
		resume_from_idx: DF.Int
		resume_run: DF.Data | None
		run_after: DF.Datetime | None
		status: DF.Literal["Pending", "Running", "Done", "Failed", "Skipped"]
		triggered_at: DF.Datetime | None
	# end: auto-generated types

	pass
