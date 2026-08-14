# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE


import frappe
from frappe import _
from frappe.automation_engine.actions.base import AutomationAction, AutomationParamError


def _render(value, doc):
	"""Render a Jinja-templated string against the document; pass through non-templates."""
	if isinstance(value, str) and "{{" in value:
		return frappe.render_template(value, {"doc": doc})
	return value


class SetFieldValue(AutomationAction):
	action_type = "SetFieldValue"
	label = "Set Field Value"
	description = "Set a field on the triggering document."
	params_schema = [
		{
			"fieldname": "field",
			"label": "Field",
			"fieldtype": "Select",
			"reqd": 1,
			"options_source": "doc_fields",
		},
		{"fieldname": "value", "label": "Value", "fieldtype": "Data", "reqd": 1},
	]

	def validate(self, params, doctype):
		field = params.get("field")
		if not field:
			raise AutomationParamError(_("Field is required"), fieldname="field")
		if not frappe.get_meta(doctype).get_field(field):
			raise AutomationParamError(_("{0} has no field {1}").format(doctype, field), fieldname="field")

	def execute(self, doc, params, context):
		field, value = params["field"], _render(params.get("value"), doc)
		doc.set(field, value)
		doc.save(ignore_permissions=True)
		return _("Set {0} = {1}").format(field, value)


class CreateDocument(AutomationAction):
	action_type = "CreateDocument"
	label = "Create Document"
	description = "Create a new document, optionally seeded from the triggering document."
	params_schema = [
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

	def execute(self, doc, params, context):
		target = frappe.new_doc(params["doctype"])
		for field, value in (params.get("values") or {}).items():
			target.set(field, _render(value, doc))
		target.insert(ignore_permissions=True)
		return _("Created {0} {1}").format(params["doctype"], target.name)


class SendNotification(AutomationAction):
	action_type = "SendNotification"
	label = "Send Notification"
	description = "Send an email or system notification, optionally from an Email Template."
	params_schema = [
		{
			"fieldname": "channel",
			"label": "Channel",
			"fieldtype": "Select",
			"options": "Email\nSystem",
			"reqd": 1,
		},
		{"fieldname": "recipients", "label": "Recipients", "fieldtype": "JSON", "reqd": 1},
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
		if not params.get("recipients"):
			raise AutomationParamError(_("At least one recipient is required"), fieldname="recipients")

	def execute(self, doc, params, context):
		subject, message = self._content(params, doc)
		recipients = params.get("recipients") or []
		if params.get("channel") == "System":
			return self._notify_system(doc, recipients, subject, message)
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)
		return _("Emailed {0}").format(", ".join(recipients))

	def _content(self, params, doc):
		if params.get("email_template"):
			template = frappe.get_doc("Email Template", params["email_template"])
			return (
				frappe.render_template(template.subject, {"doc": doc}),
				frappe.render_template(template.response or template.response_html or "", {"doc": doc}),
			)
		return _render(params.get("subject") or "", doc), _render(params.get("message") or "", doc)

	def _notify_system(self, doc, recipients, subject, message):
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
	description = "Assign the triggering document to one or more users (wraps ToDo assignment)."
	params_schema = [
		{"fieldname": "assign_to", "label": "Assign To", "fieldtype": "JSON", "reqd": 1},
		{"fieldname": "description", "label": "Description", "fieldtype": "Data"},
	]

	def validate(self, params, doctype):
		if not params.get("assign_to"):
			raise AutomationParamError(_("At least one assignee is required"), fieldname="assign_to")

	def execute(self, doc, params, context):
		from frappe.desk.form.assign_to import add

		users = params.get("assign_to") or []
		add(
			{
				"doctype": doc.doctype,
				"name": doc.name,
				"assign_to": users,
				"description": _render(params.get("description"), doc) or doc.doctype,
			}
		)
		return _("Assigned to {0}").format(", ".join(users))


CORE_ACTIONS = [SetFieldValue, CreateDocument, SendNotification, AssignToUser]
