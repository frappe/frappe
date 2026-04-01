# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, WorkflowTransitionError
from frappe.utils import get_datetime, add_days, today, date_diff, parse_json


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("DocType"),
			"fieldname": "reference_doctype",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Document"),
			"fieldname": "reference_name",
			"fieldtype": "Dynamic Link",
			"options": "reference_doctype",
			"width": 190,
		},
		{
			"label": _("Status"),
			"fieldname": "workflow_state",
			"fieldtype": "Data",
			"width": 240,
		},
		{
			"label": _("Created Date"),
			"fieldname": "created_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": _("Workflow Action Date"),
			"fieldname": "workflow_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": _("Days Pending"),
			"fieldname": "days_pending",
			"fieldtype": "Int",
			"width": 120,
		},
	]


def get_data(filters):
	user = filters.get("user") or frappe.session.user
	user_roles = frappe.get_roles(user)
	
	workflow_actions = frappe.get_all(
		"Workflow Action",
		filters={
			"status": "Open",
			"role": ["in", user_roles]
		},
		fields=[
			"reference_doctype",
			"reference_name",
			"creation as workflow_date"
		],
		order_by="creation desc",
	)

	latest_actions = {}

	for wa in workflow_actions:
		key = (wa.reference_doctype, wa.reference_name)

		if key not in latest_actions:
			latest_actions[key] = wa

	workflow_actions = list(latest_actions.values())

	data = []

	for wa in workflow_actions:
		if filters.get("reference_doctype") and wa.reference_doctype != filters.get("reference_doctype"):
			continue

		Doc = frappe.qb.DocType(wa.reference_doctype)

		select_fields = [Doc.name, Doc.workflow_state, Doc.creation.as_("created_date")]

		query = (
			frappe.qb.from_(Doc)
			.select(*select_fields)
			.where(Doc.name == wa.reference_name)
			.where(Doc.docstatus < 2)
		)

		if filters.get("from_date"):
			query = query.where(Doc.creation >= get_datetime(filters.get("from_date")))

		if filters.get("to_date"):
			query = query.where(Doc.creation < get_datetime(add_days(filters.get("to_date"), 1)))

		if filters.get("workflow_state"):
			query = query.where(Doc.workflow_state == filters.get("workflow_state"))

		results = query.run(as_dict=True)
		if not results:
			continue

		result = results[0]
		workflow_state = result.get("workflow_state")
		workflow_action = filters.get("workflow_action")
		
		if workflow_action and not workflow_action_allowed(
			wa.reference_doctype,
			workflow_state,
			workflow_action,
			user_roles
		):
			continue

		data.append(
			{
				"reference_doctype": wa.reference_doctype,
				"reference_name": wa.reference_name,
				"workflow_state": workflow_state,
				"created_date": result.get("created_date"),
				"workflow_date": wa.workflow_date,
				"days_pending": date_diff(today(), wa.workflow_date)
			}
		)
	
	data = sorted(data, key=lambda x: x.get("workflow_date") or "", reverse=True)
	return data


def workflow_action_allowed(doctype, workflow_state, workflow_action, user_roles):
	workflow_name = frappe.get_value(
		"Workflow",
		{"document_type": doctype, "is_active": 1},
		"name"
	)

	if not workflow_name:
		return False

	return frappe.db.exists(
		"Workflow Transition",
		{
			"parent": workflow_name,
			"state": workflow_state,
			"action": workflow_action,
			"allowed": ["in", user_roles],
		}
	)


@frappe.whitelist()
def apply_workflow_action(rows: str, action: str):
	rows = parse_json(rows)
	errors = []

	for row in rows:
		try:
			doc = frappe.get_doc(row["doctype"], row["name"])
			apply_workflow(doc, action)
		except WorkflowTransitionError:
			errors.append(
				_("Permission denied for {0} action on {1} {2}.")
				.format(action, row["doctype"], row["name"])
			)
		except Exception as e:
			errors.append(
				_("Cannot apply {0} on {1} {2}: {3}")
				.format(action, row["doctype"], row["name"], str(e))
			)

	if errors:
		frappe.throw("<br>".join(errors))