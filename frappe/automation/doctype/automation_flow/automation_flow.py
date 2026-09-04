# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.automation_engine.registry import DOC_TRIGGER_TYPES, clear_automation_cache
from frappe.model.document import Document

STEP_TYPES = ("Action", "Wait", "WaitForEvent", "If")
WAIT_STEP_TYPES = ("Wait", "WaitForEvent")
WAIT_UNITS = ("Seconds", "Minutes", "Hours", "Days")


class AutomationFlow(Document):
	"""A trigger, its filters, and the steps that run when it matches.

	`relationships` names record aliases that steps can target; each alias is
	resolved through a provider an app registered with the automation engine.
	`next_run` is the scheduler's stored due time for cron flows.
	"""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.automation.doctype.automation_action.automation_action import AutomationAction
		from frappe.types import DF

		actions: DF.Table[AutomationAction]
		automation_user: DF.Link | None
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
		next_run: DF.Datetime | None
		revalidate_on_run: DF.Check
		relationships: DF.JSON | None
		run_as: DF.Literal["Triggering User", "Document Owner", "Automation User"]
		stop_on_error: DF.Check
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
		self.validate_execution_identity()
		self.validate_actions()
		if self.enabled:
			self.validate_ready_to_enable()

	def validate_ready_to_enable(self):
		"""Only allow enabling a rule whose every part can actually run today."""
		if not self.actions:
			frappe.throw(_("Enable an Automation Flow only after adding at least one action"))

	def validate_actions(self):
		from frappe.automation_engine.actions.base import get_action

		keys = set()
		targets = self.get_action_targets()
		for row in self.actions:
			self.set_step_key(row, keys)
			self.validate_step(row)
			self.validate_branch(row)
			self.validate_action_aliases(row, targets)
			if row.step_type in (*WAIT_STEP_TYPES, "If"):
				continue
			action = get_action(row.action_type)
			self.validate_action_context(action)
			params = frappe.parse_json(row.params) if row.params else {}
			action.validate(params, targets.get(row.target))
			targets.update(action.output_targets(params, row.output_alias))

	def get_action_targets(self):
		from frappe.automation_engine.relationships import get_relationship_targets

		return get_relationship_targets(self.document_type, self.relationships)

	def validate_action_aliases(self, row, targets):
		from frappe.automation_engine.conditions import validate_related_condition

		row.target = row.target or "trigger"
		if row.target not in targets:
			frappe.throw(_("Row {0}: unknown target alias {1}").format(row.idx, row.target))
		validate_related_condition(row.related_condition, targets)
		if row.output_alias and row.output_alias in targets:
			frappe.throw(_("Row {0}: duplicate output alias {1}").format(row.idx, row.output_alias))

	def set_step_key(self, row, keys):
		row.step_key = row.step_key or f"step_{row.idx}"
		if row.step_key in keys:
			frappe.throw(_("Row {0}: Step Key must be unique").format(row.idx))
		keys.add(row.step_key)

	def validate_execution_identity(self):
		self.run_as = self.run_as or "Automation User"
		if self.run_as != "Automation User":
			return
		self.automation_user = self.automation_user or "Administrator"
		if not frappe.db.get_value("User", self.automation_user, "enabled"):
			frappe.throw(_("Automation User {0} is disabled or missing").format(self.automation_user))

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
		if row.step_type == "Wait":
			self.validate_wait(row)
		if row.step_type == "WaitForEvent":
			self.validate_event_wait(row)

	def validate_wait(self, row):
		params = frappe.parse_json(row.params) if row.params else {}
		if not params.get("value") or not params.get("unit"):
			frappe.throw(_("Wait steps require a duration value and unit"))
		if params["unit"] not in WAIT_UNITS:
			frappe.throw(_("Row {0}: Wait unit must be one of {1}").format(row.idx, ", ".join(WAIT_UNITS)))

	def validate_event_wait(self, row):
		from frappe.automation_engine.events import validate_wait_params

		validate_wait_params(frappe.parse_json(row.params) if row.params else {})

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
		self.set_next_run()

	def set_next_run(self):
		from frappe.automation_engine.scheduler import next_fire

		if self.trigger_type != "Scheduled":
			self.next_run = None
		elif self.has_value_changed("cron_expression") or not self.next_run:
			self.next_run = next_fire(self.cron_expression, frappe.utils.now_datetime())

	def validate_cron(self):
		from croniter import croniter

		if not self.cron_expression:
			frappe.throw(_("Scheduled trigger requires a Cron Expression"))
		if not croniter.is_valid(self.cron_expression):
			frappe.throw(_("Invalid cron expression: {0}").format(self.cron_expression))

	def on_update(self):
		clear_automation_cache(self.document_type)
		# Retargeting a flow leaves the old doctype's cached map holding a rule that no longer
		before = self.get_doc_before_save()
		if before and before.document_type and before.document_type != self.document_type:
			clear_automation_cache(before.document_type)

	def on_trash(self):
		clear_automation_cache(self.document_type)
		queue = frappe.qb.DocType("Automation Trigger Queue")
		subscription = frappe.qb.DocType("Automation Event Subscription")
		frappe.qb.from_(subscription).delete().where(
			subscription.resume_queue.isin(
				frappe.qb.from_(queue).select(queue.name).where(queue.automation == self.name)
			)
		).run()
		frappe.db.delete("Automation Trigger Queue", {"automation": self.name})
