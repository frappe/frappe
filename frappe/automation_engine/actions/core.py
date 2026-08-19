# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE


from typing import ClassVar

import frappe
from frappe import _
from frappe.automation_engine.actions.base import AutomationAction, AutomationParamError
from frappe.utils import flt

NUMERIC_FIELDTYPES = ("Int", "Float", "Currency", "Percent")


def _render(value, doc, context=None):
	"""Render a Jinja-templated string against the document; pass through non-templates."""
	if isinstance(value, str) and "{{" in value:
		# nosemgrep: the template is an action parameter, authored by the System Manager who
		# configured the flow - the same trust model as Notification and Email Template.
		return frappe.render_template(value, _render_context(doc, context))
	return value


def _render_context(doc, context=None):
	context = context or {}
	return {
		# `doc` is the step's target; `trigger` is what started the run, which is the same
		# document unless the step aims at a relationship alias or an earlier step's output.
		"doc": doc,
		"target": doc,
		"trigger": context.get("trigger_doc") or doc,
		"payload": context.get("payload") or {},
		"context": context,
	}


def _require_doc(doc, action_type):
	if doc is None:
		raise AutomationParamError(_("{0} requires a target document").format(action_type))


def _as_list(value) -> list:
	"""Normalize a JSON param that may arrive as a list, its string form, or one bare value.

	A builder can store `["a@example.com"]` as the string; iterating that sends one character
	per recipient.
	"""
	if not value:
		return []
	if isinstance(value, str):
		parsed = frappe.parse_json(value) if value.strip().startswith("[") else value
		return list(parsed) if isinstance(parsed, list) else [parsed]
	return list(value)


class SetFieldValue(AutomationAction):
	action_type = "SetFieldValue"
	label = "Set Field Value"
	description = "Set one or more fields on the triggering document."
	params_schema: ClassVar[list] = [
		{"fieldname": "field", "label": "Field", "fieldtype": "Select", "options_source": "doc_fields"},
		{"fieldname": "value", "label": "Value", "fieldtype": "Data"},
		# Set several fields at once: {"values": {"color": "#ED6396", "priority": "High"}}.
		{"fieldname": "values", "label": "Field Values", "fieldtype": "JSON"},
	]

	def validate(self, params, doctype):
		pairs = self._pairs(params)
		if not pairs:
			raise AutomationParamError(_("Set at least one field"), fieldname="field")
		if not doctype:
			return
		meta = frappe.get_meta(doctype)
		for field in pairs:
			if not meta.get_field(field):
				raise AutomationParamError(
					_("{0} has no field {1}").format(doctype, field), fieldname="field"
				)

	def execute(self, doc, params, context):
		_require_doc(doc, self.label)
		pairs = self._pairs(params)
		for field, value in pairs.items():
			doc.set(field, _render(value, doc, context))
		doc.save()
		return _("Set {0}").format(", ".join(pairs))

	def _pairs(self, params) -> dict:
		"""Normalize single field/value and a `values` map into {field: value}.

		Both boxes may be filled, and both land: a doctype whose validation spans two fields is
		unsatisfiable if one is silently dropped.
		"""
		values = params.get("values") or {}
		if isinstance(values, str):
			values = frappe.parse_json(values) or {}
		pairs = dict(values)
		if params.get("field"):
			pairs[params["field"]] = params.get("value")
		return pairs


class CreateDocument(AutomationAction):
	action_type = "CreateDocument"
	label = "Create Document"
	description = "Create a new document."
	requires_document = False
	output_schema: ClassVar[dict] = {"destination_reference": {"doctype": "Dynamic", "cardinality": "one"}}
	params_schema: ClassVar[list] = [
		{
			"fieldname": "doctype",
			"label": "Document Type",
			"fieldtype": "Link",
			"options": "DocType",
			"reqd": 1,
		},
		{"fieldname": "values", "label": "Field Values", "fieldtype": "JSON"},
	]

	def validate(self, params, doctype):
		if not params.get("doctype"):
			raise AutomationParamError(_("Target Document Type is required"), fieldname="doctype")
		if not frappe.db.exists("DocType", params.get("doctype")):
			raise AutomationParamError(_("Unknown DocType"), fieldname="doctype")

	def output_doctype(self, params):
		return params.get("doctype")

	def execute(self, doc, params, context):
		target = frappe.new_doc(params["doctype"])
		values = params.get("values")
		if isinstance(values, str):
			values = frappe.parse_json(values)
		for field, value in (values or {}).items():
			target.set(field, _render(value, doc, context))
		target.insert()
		return {
			"detail": _("Created {0} {1}").format(params["doctype"], target.name),
			"destination_reference": {"doctype": target.doctype, "name": target.name},
		}


class IncrementFieldValue(AutomationAction):
	action_type = "IncrementFieldValue"
	label = "Increment Field Value"
	description = "Add a number to a field on the target document."
	params_schema: ClassVar[list] = [
		{
			"fieldname": "field",
			"label": "Field",
			"fieldtype": "Select",
			"options_source": "doc_fields",
			"reqd": 1,
		},
		{"fieldname": "amount", "label": "Amount", "fieldtype": "Float", "reqd": 1},
	]

	def validate(self, params, doctype):
		field = params.get("field")
		if not field:
			raise AutomationParamError(_("Field is required"), fieldname="field")
		if not doctype:
			return
		df = frappe.get_meta(doctype).get_field(field)
		if not df or df.fieldtype not in NUMERIC_FIELDTYPES:
			raise AutomationParamError(_("Choose a numeric field"), fieldname="field")

	def execute(self, doc, params, context):
		_require_doc(doc, self.label)
		field = params["field"]
		amount = flt(_render(params.get("amount"), doc, context))
		# Lock the row first, then re-read: two runs incrementing the same document serialize
		# here instead of both adding to the same stale value.
		self._lock(doc)
		doc.reload()
		old_value = flt(doc.get(field))
		doc.set(field, old_value + amount)
		doc.save()
		return {
			"detail": _("Changed {0} by {1}").format(field, amount),
			"old_value": old_value,
			"new_value": old_value + amount,
			"delta": amount,
		}

	def _lock(self, doc):
		table = frappe.qb.DocType(doc.doctype)
		frappe.qb.from_(table).select(table.name).where(table.name == doc.name).for_update().run()


class SendNotification(AutomationAction):
	action_type = "SendNotification"
	label = "Send Notification"
	description = "Send an email or system notification."
	params_schema: ClassVar[list] = [
		{
			"fieldname": "channel",
			"label": "Channel",
			"fieldtype": "Select",
			"options": "Email\nSystem",
			"reqd": 1,
		},
		{
			"fieldname": "recipients",
			"label": "Recipients",
			"fieldtype": "JSON",
			"reqd": 1,
			"options_source": "users",
		},
		{
			"fieldname": "email_template",
			"label": "Email Template",
			"fieldtype": "Link",
			"options": "Email Template",
		},
		{"fieldname": "subject", "label": "Subject", "fieldtype": "Data"},
		{"fieldname": "message", "label": "Message", "fieldtype": "Text Editor"},
	]

	def validate(self, params, doctype):
		if not _as_list(params.get("recipients")):
			raise AutomationParamError(_("At least one recipient is required"), fieldname="recipients")
		if params.get("email_template") and not frappe.db.exists("Email Template", params["email_template"]):
			raise AutomationParamError(_("Unknown Email Template"), fieldname="email_template")

	def execute(self, doc, params, context):
		subject, message = self._content(params, doc, context)
		recipients = _as_list(params.get("recipients"))
		if params.get("channel") == "System":
			return self._notify_system(doc, recipients, subject, message)
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			reference_doctype=doc.doctype if doc else None,
			reference_name=doc.name if doc else None,
		)
		return _("Emailed {0}").format(", ".join(recipients))

	def _content(self, params, doc, context):
		if params.get("email_template"):
			template = frappe.get_doc("Email Template", params["email_template"])
			return (
				# nosemgrep: the template body is an Email Template, already an authored artefact.
				frappe.render_template(template.subject, _render_context(doc, context)),
				frappe.render_template(  # nosemgrep
					template.response or template.response_html or "", _render_context(doc, context)
				),
			)
		return _render(params.get("subject") or "", doc, context), _render(
			params.get("message") or "", doc, context
		)

	def _notify_system(self, doc, recipients, subject, message):
		_require_doc(doc, self.label)
		for user in recipients:
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"for_user": user,
					"type": "Alert",
					"subject": subject,
					"email_content": message,
					"document_type": doc.doctype,
					"document_name": doc.name,
				}
			).insert(ignore_permissions=True)
		return _("Notified {0}").format(", ".join(recipients))


class AssignToUser(AutomationAction):
	action_type = "AssignToUser"
	label = "Assign to User"
	description = "Assign the triggering document to one or more users."
	params_schema: ClassVar[list] = [
		{
			"fieldname": "assign_to",
			"label": "Assign To",
			"fieldtype": "JSON",
			"reqd": 1,
			"options_source": "users",
		},
		{"fieldname": "description", "label": "Description", "fieldtype": "Data"},
	]

	def validate(self, params, doctype):
		if not _as_list(params.get("assign_to")):
			raise AutomationParamError(_("At least one assignee is required"), fieldname="assign_to")

	def execute(self, doc, params, context):
		from frappe.desk.form.assign_to import add

		_require_doc(doc, self.label)
		users = _as_list(params.get("assign_to"))
		add(
			{
				"doctype": doc.doctype,
				"name": doc.name,
				"assign_to": users,
				"description": _render(params.get("description"), doc, context) or doc.doctype,
			}
		)
		return _("Assigned to {0}").format(", ".join(users))


CORE_ACTIONS = [SetFieldValue, IncrementFieldValue, CreateDocument, SendNotification, AssignToUser]
