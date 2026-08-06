# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

# IMP: the runner/drainer must NEVER call `rule.save()` on an Automation Flow.
# Bookkeeping (circuit-breaker state, "last run", etc.) goes to Redis or
# frappe.db.set_value(..., update_modified=False).
# A controller save fires on_update then invalidate case then rebuild registry thrash
# also TimestampMismatch against concurrent config editors.

import frappe
from frappe import _
from frappe.automation_engine.registry import DOC_TRIGGER_TYPES, clear_automation_cache
from frappe.model.document import Document

# Triggers whose runtime path isn't wired yet (no emitter / no scheduler). They may be
# saved as drafts, but enabling one would silently never fire — so enable is blocked.
NON_EXECUTABLE_TRIGGERS = ("Custom Event", "Date Based")

# "Else" is not a step of its own — an If's two arms are expressed by its children's
# `branch` field, so a bare Else row would have nothing to execute.
STEP_TYPES = ("Action", "Wait", "If")


class AutomationFlow(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.automation.doctype.automation_action.automation_action import AutomationAction
		from frappe.types import DF

		actions: DF.Table[AutomationAction]
		condition: DF.Code | None
		cron_expression: DF.Data | None
		custom_event: DF.Data | None
		date_direction: DF.Literal["Before", "After"]
		date_field: DF.Literal[None]
		date_offset: DF.Int
		disabled_reason: DF.SmallText | None
		document_type: DF.Link | None
		enabled: DF.Check
		filters: DF.Code | None
		from_value: DF.Data | None
		log_only: DF.Check
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
		if self.enabled:
			self.validate_ready_to_enable()

	def validate_ready_to_enable(self):
		"""Only allow enabling a rule whose every part can actually run today.

		Wait steps and not-yet-wired triggers are legal to draft, but enabling them would
		silently no-op (Custom Event/Date Based) or halt mid-run (Wait), so block enable.
		"""
		if not self.actions:
			frappe.throw(_("Enable an Automation Flow only after adding at least one action"))
		if self.trigger_type in NON_EXECUTABLE_TRIGGERS:
			frappe.throw(
				_("{0} triggers are not executable yet — keep this Automation Flow as a draft").format(
					self.trigger_type
				)
			)
		if any((row.step_type or "Action") == "Wait" for row in self.actions):
			frappe.throw(
				_("Wait steps are not executable yet — remove them or keep this Automation Flow as a draft")
			)

	def validate_actions(self):
		from frappe.automation_engine.actions.base import get_action

		for row in self.actions:
			self.validate_step(row)
			self.validate_branch(row)
			if row.step_type in ("Wait", "If"):
				continue
			action = get_action(row.action_type)
			self.validate_action_context(action)
			action.validate(frappe.parse_json(row.params) if row.params else {}, self.document_type)

	def validate_branch(self, row):
		"""A step inside an If must name that If (by idx) and which arm it belongs to."""
		if not row.parent_step:
			if row.branch:
				frappe.throw(_("Row {0}: Branch is only meaningful inside an If step").format(row.idx))
			return
		if row.parent_step >= row.idx:
			frappe.throw(_("Row {0}: Parent Step must be an earlier row").format(row.idx))
		if not self.if_step_at(row.parent_step):
			frappe.throw(_("Row {0}: Parent Step {1} is not an If step").format(row.idx, row.parent_step))
		if row.branch not in ("If", "Else"):
			frappe.throw(_("Row {0}: choose the If or Else branch").format(row.idx))

	def if_step_at(self, idx):
		return next((r for r in self.actions if r.idx == idx and r.step_type == "If"), None)

	def validate_action_context(self, action):
		if action.requires_document and not self.document_type:
			frappe.throw(_("{0} requires a Document Type").format(action.label))
		if action.supported_trigger_types and self.trigger_type not in action.supported_trigger_types:
			frappe.throw(_("{0} does not support {1} triggers").format(action.label, self.trigger_type))

	def validate_step(self, row):
		row.step_type = row.step_type or "Action"
		if row.step_type not in STEP_TYPES:
			frappe.throw(_("Row {0}: unsupported Step Type {1}").format(row.idx, row.step_type))
		if row.step_type == "Action" and not row.action_type:
			frappe.throw(_("Action Type is required for action steps"))
		if row.step_type == "If" and not row.step_condition:
			frappe.throw(_("Row {0}: an If step needs a Step Condition").format(row.idx))
		if row.step_type != "Wait":
			return
		params = frappe.parse_json(row.params) if row.params else {}
		if not params.get("value") or not params.get("unit"):
			frappe.throw(_("Wait steps require a duration value and unit"))

	def validate_document_type(self):
		if self.document_type and frappe.get_meta(self.document_type).istable:
			frappe.throw(_("Automation Flow cannot target a child table: {0}").format(self.document_type))

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
