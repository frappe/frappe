# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import hashlib

import frappe
from frappe.model.document import Document


class AutomationEventSubscription(Document):
	def autoname(self):
		value = f"{self.run}:{self.step_key}"
		self.name = hashlib.sha256(value.encode()).hexdigest()

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		event_name: DF.Data
		correlation_key: DF.Data
		event_payload: DF.JSON | None
		expires_at: DF.Datetime
		resume_queue: DF.Link
		run: DF.Link
		status: DF.Literal["Waiting", "Matched", "Timed Out", "Cancelled"]
		step_key: DF.Data
	# end: auto-generated types


def on_doctype_update():
	frappe.db.add_index(
		"Automation Event Subscription",
		["event_name", "correlation_key", "status"],
		index_name="event_correlation_status",
	)
	frappe.db.add_index(
		"Automation Event Subscription",
		["status", "expires_at"],
		index_name="event_expiry_status",
	)
