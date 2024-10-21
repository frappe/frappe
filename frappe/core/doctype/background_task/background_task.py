# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BackgroundTask(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		kwargs: DF.Code | None
		method: DF.Data | None
		queue: DF.Data | None
		result: DF.Code | None
		status: DF.Literal["Queued", "In Progress", "Completed", "Failed", "Stopped"]
		task_end: DF.Datetime | None
		task_id: DF.Data
		task_runtime: DF.Duration | None
		task_start: DF.Datetime | None
		timeout: DF.Int
	# end: auto-generated types

	@property
	def task_runtime(self):
		return ((self.task_end or frappe.utils.now_datetime()) - self.task_start).total_seconds()
