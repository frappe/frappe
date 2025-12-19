# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.email.doctype.notification.notification import get_context
from frappe.model.document import Document
from frappe.utils.data import validate_json_string

HOOK_MAP = {
	"before_save": "On Creation",
	"on_update": "On Update",
}


class AutomationRule(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		doctype_event: DF.Literal["On Creation", "On Update"]
		dt: DF.Link
		enabled: DF.Check
		last_triggered_at: DF.Datetime | None
		rule: DF.JSON
	# end: auto-generated types

	def validate(self) -> None:
		validate_json_string(self.rule)

	def apply(self, doc) -> None:
		rule = json.loads(self.rule)
		if not self.should_apply(doc, rule):
			return

		rule = rule.get("rule") or []
		self.handle_rule(doc, rule)

	def should_apply(self, doc, rule) -> bool:
		filter_expression: str = rule.get("presets", "")
		if not filter_expression:
			return True

		context = get_context(doc)
		if not frappe.safe_eval(filter_expression, None, context):
			return False

		return True

	def handle_rule(self, doc, rule) -> None:
		context = get_context(doc.as_dict())
		matched = False

		for r in rule:
			rule_type = r.get("type", "")
			actions = r.get("actions", [])

			if rule_type == "if":
				expression = r.get("condition", "")
				if expression and frappe.safe_eval(expression, None, context):
					self.run_actions(doc, actions)
					matched = True

			elif rule_type == "else" and not matched:
				self.run_actions(doc, actions)

	def run_actions(self, doc, actions) -> None:
		for a in actions:
			action_type = a.get("type") or ""
			if not action_type:
				continue
			# assign comment, email , set, etc.
			if action_type == "set":
				self.set_field(doc, a)
			if action_type == "notify":
				frappe.msgprint(a.get("message") or "")
			if action_type == "add_comment":
				pass

	def set_field(self, doc, action) -> None:
		field = action.get("field") or ""
		value = action.get("value") or ""
		if not field:
			return
		doc.set(field, value)


def apply_automations(doc, hook) -> None:
	doctype: str = doc.doctype
	if doctype == "Automation Rule":
		return
	allowed_doctypes = frappe.get_hooks("automation_rule_config").get("allowed_doctypes", [])
	if doctype not in allowed_doctypes:
		return

	event: str | None = HOOK_MAP.get(hook, None)
	if not event:
		return
	if event == "On Creation" and not doc.is_new():
		return

	automations: list[str] = frappe.db.get_all(
		"Automation Rule",
		{"enabled": 1, "doctype_event": event, "dt": doctype},
		pluck="name",
	)
	for a in automations:
		automation_doc = frappe.get_doc("Automation Rule", a)
		automation_doc.apply(doc)
