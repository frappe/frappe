# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import json
from typing import TYPE_CHECKING, cast

import frappe
from frappe.email.doctype.email_template.email_template import get_email_template
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from frappe.utils.data import add_to_date, compare, validate_json_string
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

		doctype_event: DF.Literal[
			"On Creation", "On Update", "Days Before", "Days After", "Minutes Before", "Minutes After"
		]
		dt: DF.Link
		enabled: DF.Check
		last_triggered_at: DF.Datetime | None
		rule: DF.JSON
		time_field: DF.Data | None
		time_offset: DF.Int
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

		if hook == "time_based":
			doc.save(ignore_permissions=True)

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
		recipient = action.get("to")
		subject, message = self.get_message_and_subject(action, doc)
		add_reference = action.get("create_communication", False)

		frappe.sendmail(
			recipients=[doc.get(recipient)] if recipient else [],
			subject=subject,
			message=message,
			reference_doctype=doc.doctype if add_reference else None,
			reference_name=doc.name if add_reference else None,
		)

		if add_reference:
			communication = frappe.get_doc(
				{
					"doctype": "Communication",
					"communication_type": "Automated Message",
					"subject": subject,
					"content": message,
					"reference_doctype": doc.doctype,
					"reference_name": doc.name,
					"communication_medium": "Email",
				}
			)
			communication.insert(ignore_permissions=True)

	def get_message_and_subject(self, action: "EmailAction", doc):
		source = action.get("via")
		if source == "template":
			template_name = action.get("template")
			# TODO: change it when we give HD Saved Reply (custom) template support
			template = get_email_template(template_name, doc.as_dict())
			subject = template.get("subject", "Automated Email")
			message = template.get("message", "")

		else:
			subject = action.get("subject", "Automated Email")
			message = frappe.render_template(action.get("message", ""), context={**doc.as_dict()})

		return subject, message


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

	automations: list[str] = frappe.get_list(
		"Automation Rule",
		{"enabled": 1, "doctype_event": event, "dt": doctype},
		pluck="name",
	)
	for a in automations:
		automation_doc = frappe.get_doc("Automation Rule", a)
		automation_doc.apply(doc, hook)

	if method != "after_insert":
		return

	time_based_automations = frappe.get_list(
		"Automation Rule",
		filters={"enabled": 1, "doctype_event": ["not in", ["On Creation", "On Update"]], "dt": doctype},
		fields=["name", "dt", "doctype_event", "rule", "time_field", "time_offset"],
	)

	if not time_based_automations:
		return

	for automation in time_based_automations:
		# automation.name /.dt
		# doc.name
		# status = "Scheduled"
		# execute at
		field = doc.get(automation.get("time_field"))
		execute_at = calculate_execute_at(
			automation.get("doctype_event"), field, automation.get("time_offset")
		)
		frappe.new_doc(
			"Automation Scheduled Job",
			reference_doctype=doctype,
			reference_name=doc.name,
			automation_rule=automation.name,
			execute_at=execute_at,
			fieldname=automation.get("time_field"),
		).insert(ignore_permissions=True)


def calculate_execute_at(doctype_event, field_value, offset):
	event_map = {
		"Minutes Before": add_to_date(field_value, minutes=-offset),
		"Minutes After": add_to_date(field_value, minutes=offset),
		"Days Before": add_to_date(field_value, days=-offset),
		"Days After": add_to_date(field_value, days=offset),
	}

	return event_map[doctype_event]


def execute_automation_logs():
	# find_jobs_to_run()
	# enqueue the automations found in find_jobs_to_run
	# onSuccess change the status of the log to "Completed"
	# onError change the status of the log to "Failed"
	print("Executing scheduled automation jobs...")
	jobs_to_run = frappe.get_list(
		"Automation Scheduled Job",
		filters={"status": ["in", ["Scheduled", "Failed"]], "execute_at": ["<=", frappe.utils.now()]},
		fields=["name", "reference_doctype", "reference_name", "automation_rule"],
	)
	print(jobs_to_run)
	for job in jobs_to_run:
		automation_rule = frappe.get_doc("Automation Rule", job.automation_rule)
		if not automation_rule.enabled:
			continue
		reference_doc = frappe.get_doc(job.reference_doctype, job.reference_name)
		enqueue(
			automation_rule.apply,
			doc=reference_doc,
			hook="time_based",
			queue="long",
			deduplicate=True,
			job_name=f"Automation Rule: {automation_rule.name} for {reference_doc.doctype} {reference_doc.name}",
			on_success="frappe.automation.doctype.automation_rule.automation_rule.mark_automation_job_completed",
			on_failure="frappe.automation.doctype.automation_rule.automation_rule.mark_automation_job_failed",
			job_id=job.name,
		)


def mark_automation_job_completed(job, connection, result):
	site, job_id = job.id.split("||", 1)

	frappe.init(site=site)
	frappe.connect()
	try:
		frappe.db.set_value("Automation Scheduled Job", job_id, "status", "Completed")
		frappe.db.commit()
	finally:
		frappe.destroy()


def mark_automation_job_failed(job, connection, type, value, traceback):
	site, job_id = job.id.split("||", 1)
	frappe.init(site=site)
	frappe.connect()
	try:
		frappe.db.set_value("Automation Scheduled Job", job_id, "status", "Failed")
		frappe.db.commit()
	finally:
		frappe.log_error(f"Automation Log Failed {job_id} \n {traceback}")
		frappe.destroy()
