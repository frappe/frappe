# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document
from frappe.utils.data import compare, validate_json_string

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
		presets: list[list[str] | str] | list = rule.get("presets", [])
		if not len(presets):
			return True

		if not eval_conditions(presets, doc):
			return False

		return True

	def handle_rule(self, doc, rule) -> None:
		matched = False

		for r in rule:
			rule_type = r.get("type", "")
			actions = r.get("actions", [])

			if rule_type == "if":
				conditions = r.get("conditions", "")
				if len(conditions) and eval_conditions(conditions, doc):
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


operatorMap = {
	"is": "is",
	"is not": "is not",
	"in": "in",
	"not in": "not in",
	"equals": "=",
	"not equals": "!=",
	"yes": True,
	"no": False,
	"like": "LIKE",
	"not like": "NOT LIKE",
	">": ">",
	"<": "<",
	">=": ">=",
	"<=": "<=",
	"between": "between",
	"timespan": "timespan",
}


def eval_conditions(conditions: list[list[str] | str], context: dict) -> bool:
	"""
	Evaluate a list of filter conditions with logical operators ("and"/"or") against a context.

	Args:
	    conditions: A list containing condition lists and logical operators.
	        Each condition is a list: [fieldname, operator, value].
	        Operators ("and"/"or") are strings between conditions.
	                    example: [["ticket_type", "equals", "Bug"], "or", ["priority", "not equals", "High"]]
	    context: A dictionary providing values for fieldnames. The doc which you get by frappe.get_doc()

	Returns:
	    bool: The result of evaluating all conditions with the specified logical operator.
	"""

	if not len(conditions) or not isinstance(conditions, list):
		return False

	global_operator: str = ""
	results: list[bool] = []

	for c in conditions:
		if not isinstance(c, list):
			global_operator = c
			continue
		result: bool = compare(context.get(c[0], ""), operatorMap[c[1]], c[2])
		results.append(result)

	if global_operator == "or":
		return any(results)
	else:
		return all(results)
