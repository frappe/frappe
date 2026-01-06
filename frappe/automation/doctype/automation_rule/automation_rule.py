# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import json
from typing import TYPE_CHECKING, cast

import frappe
from frappe.model.document import Document
from frappe.utils.data import compare, validate_json_string
from frappe.utils.jinja import get_template

if TYPE_CHECKING:
	from .types import AutomationAction, EmailAction, SetAction

HOOK_MAP = {
	"before_save": "On Creation",
	"on_update": "On Update",
	"after_insert": "On Creation",  # actions like email, add comment can be triggered only after insert but should be done as soon as the doc is created
}
AFTER_INSERT_ACTION_TYPES: set[str] = {"email", "add_comment"}
BEFORE_SAVE_ACTION_TYPES: set[str] = {"set"}


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

	def apply(self, doc, hook: str) -> None:
		rule = json.loads(self.rule)
		if not self.should_apply(doc, rule):
			return

		rule = rule.get("rule") or []
		self.handle_rule(doc, rule, hook)

	def should_apply(self, doc, rule) -> bool:
		presets: list[list[str] | str] | list = rule.get("presets", [])
		if not len(presets):
			return True

		if not eval_conditions(presets, doc):
			return False

		return True

	def handle_rule(self, doc, rule, hook: str) -> None:
		matched = False
		is_automation_triggered = False

		for r in rule:
			rule_type = r.get("type", "")
			actions = r.get("actions", [])

			if rule_type == "if":
				conditions = r.get("conditions", "")
				if len(conditions) and eval_conditions(conditions, doc):
					self.run_actions(doc, actions, hook)
					matched = True
					is_automation_triggered = True

			elif rule_type == "else" and not matched:
				self.run_actions(doc, actions, hook)
				is_automation_triggered = True

			# Support top-level actions too (optional)
			if rule_type in ("email", "set"):
				self.run_actions(doc, [r], hook)
				is_automation_triggered = True

		if is_automation_triggered:
			self.db_set("last_triggered_at", frappe.utils.now())

	def run_actions(self, doc, actions: list["AutomationAction"], hook: str) -> None:
		for a in actions:
			action_type = a.get("type", "")
			if not action_type:
				continue

			# Route actions by timing
			if hook == "before_save":
				if action_type not in BEFORE_SAVE_ACTION_TYPES:
					continue
			elif hook == "after_insert":
				if action_type not in AFTER_INSERT_ACTION_TYPES:
					continue

			# assign comment, email , set, etc.
			if action_type == "set":
				self.set_field(doc, cast("SetAction", a))
			elif action_type == "email":
				self.send_email(doc, cast("EmailAction", a))
			elif action_type == "add_comment":
				pass

	def set_field(self, doc, action: "SetAction") -> None:
		field = action.get("field", "")
		value = action.get("value", "")
		if not field:
			return
		doc.set(field, value)

	def send_email(self, doc, action: "EmailAction") -> None:
		# {'type': 'email', 'to': 'sender', 'via': 'rich_text', 'template': '', 'message': '<p>Hello {{role}},<br><br>Regards,<br>Ritvik</p>', 'doctype': 'Email Template'}
		recipient = action.get("to")
		message = self.parse_message(action.get("message", ""), doc)
		add_reference = action.get("create_communication", False)
		frappe.sendmail(
			recipients=[doc.get(recipient)] if recipient else [],
			subject="Automated Email",
			message=message,
			reference_doctype=doc.doctype if add_reference else None,
			reference_name=doc.name if add_reference else None,
		)
		if add_reference:
			communication = frappe.get_doc(
				{
					"doctype": "Communication",
					"communication_type": "Automated Message",
					"subject": "Automated Email",
					"content": message,
					"reference_doctype": doc.doctype,
					"reference_name": doc.name,
					"communication_medium": "Email",
				}
			)
			communication.insert(ignore_permissions=True)

	def parse_message(self, message: str, doc) -> str:
		rendered = frappe.render_template(message, context={**doc.as_dict()})
		return rendered


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


def apply_automations(doc, method=None) -> None:
	# Frappe doc_events call handlers as (doc, method)
	hook = method or ""
	doctype: str = doc.doctype
	if doctype == "Automation Rule":
		return
	allowed_doctypes = frappe.get_hooks("automation_rule_config").get("allowed_doctypes", [])
	if doctype not in allowed_doctypes:
		return

	event: str | None = HOOK_MAP.get(hook, None)
	if not event:
		return
	# For "On Creation" rules, run on:
	# - before_save: only if doc is new
	# - after_insert: always (doc isn't "new" anymore at this point)
	if event == "On Creation" and hook == "before_save" and not doc.is_new():
		return

	automations: list[str] = frappe.db.get_all(
		"Automation Rule",
		{"enabled": 1, "doctype_event": event, "dt": doctype},
		pluck="name",
	)
	for a in automations:
		automation_doc = frappe.get_doc("Automation Rule", a)
		automation_doc.apply(doc, hook)
