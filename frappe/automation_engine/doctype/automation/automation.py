# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

# IMP: the runner/drainer must NEVER call `rule.save()` on an Automation.
# Bookkeeping (circuit-breaker state, "last run", etc.) goes to Redis or
# frappe.db.set_value(..., update_modified=False).
# A controller save fires on_update then invalidate case then rebuild registry thrash
# also TimestampMismatch against concurrent config editors.

import frappe
from frappe import _
from frappe.automation_engine.registry import DOC_TRIGGER_TYPES, clear_automation_cache
from frappe.model.document import Document


class Automation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.automation_engine.doctype.automation_action.automation_action import AutomationAction
		from frappe.types import DF

		actions: DF.Table[AutomationAction]
		condition: DF.Code | None
		cron_expression: DF.Data | None
		custom_event: DF.Data | None
		date_direction: DF.Literal["", "Before", "After"]
		date_field: DF.Literal[None]
		date_offset: DF.Int
		disabled_reason: DF.SmallText | None
		document_type: DF.Link | None
		enabled: DF.Check
		filters: DF.JSON | None
		from_value: DF.Data | None
		revalidate_on_run: DF.Check
		stop_on_error: DF.Check
		throttle_per_minute: DF.Int
		title: DF.Data
		to_value: DF.Data | None
		trigger_field: DF.Literal[None]
		trigger_type: DF.Literal[
			"Doc Created",
			"Doc Updated",
			"Field Value Changed",
			"Doc Deleted",
			"Doc Submitted",
			"Doc Cancelled",
			"Date Based",
			"Scheduled",
			"Custom Event",
			"Manual",
		]
	# end: auto-generated types

	def validate(self):
		self.validate_document_type()
		self.validate_trigger_config()
		self.validate_actions()
		if self.enabled and not self.actions:
			frappe.throw(_("Enable an Automation only after adding at least one action"))

	def validate_actions(self):
		from frappe.automation_engine.actions.base import get_action

		for row in self.actions:
			action = get_action(row.action_type)
			if self.document_type:
				action.validate(frappe.parse_json(row.params) if row.params else {}, self.document_type)

	def validate_document_type(self):
		if self.document_type and frappe.get_meta(self.document_type).istable:
			frappe.throw(_("Automation cannot target a child table: {0}").format(self.document_type))

	def validate_trigger_config(self):
		needs_doctype = self.trigger_type in DOC_TRIGGER_TYPES or self.trigger_type == "Date Based"
		if needs_doctype and not self.document_type:
			frappe.throw(_("{0} trigger requires a Document Type").format(self.trigger_type))
		if self.trigger_type == "Field Value Changed" and not self.trigger_field:
			frappe.throw(_("Field Value Changed trigger requires a Trigger Field"))
		if self.trigger_type == "Date Based" and not (self.date_field and self.date_direction):
			frappe.throw(_("Date Based trigger requires a Date Field and a Date Direction"))
		if self.trigger_type == "Custom Event" and not self.custom_event:
			frappe.throw(_("Custom Event trigger requires an event name"))
		if self.trigger_type == "Scheduled":
			self.validate_cron()

	def validate_cron(self):
		from croniter import croniter

		if not self.cron_expression:
			frappe.throw(_("Scheduled trigger requires a Cron Expression"))
		if not croniter.is_valid(self.cron_expression):
			frappe.throw(_("Invalid cron expression: {0}").format(self.cron_expression))

	def on_update(self):
		clear_automation_cache(self.document_type)

	def on_trash(self):
		clear_automation_cache(self.document_type)
		frappe.db.delete("Automation Trigger Queue", {"automation": self.name})
