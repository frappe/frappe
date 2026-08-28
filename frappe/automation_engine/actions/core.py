# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE


from typing import ClassVar
from urllib.parse import urljoin, urlparse

import frappe
from frappe import _
from frappe.automation_engine.actions.base import AutomationAction, AutomationParamError
from frappe.utils import cint, flt

NUMERIC_FIELDTYPES = ("Int", "Float", "Currency", "Percent")
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
ALLOWED_SCHEMES = ("http", "https")
DEFAULT_WEBHOOK_TIMEOUT = 30
MAX_WEBHOOK_TIMEOUT = 120
MAX_REDIRECTS = 5
WEBHOOK_RESPONSE_LIMIT = 2000


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


OWNER_TOKEN = "@owner"
ASSIGNEES_TOKEN = "@assignees"


def recipient_tokens() -> list[dict]:
	"""Stand-ins the notification action resolves against the triggering document."""
	return [
		{"name": OWNER_TOKEN, "full_name": _("Document owner")},
		{"name": ASSIGNEES_TOKEN, "full_name": _("Assignees")},
	]


def resolve_recipients(recipients: list, doc) -> list:
	"""Expand the tokens to real users, keeping order and dropping duplicates."""
	resolved = []
	for recipient in recipients:
		if recipient == OWNER_TOKEN:
			resolved.append(doc.owner if doc else None)
		elif recipient == ASSIGNEES_TOKEN:
			resolved.extend(_assignees(doc))
		else:
			resolved.append(recipient)
	return list(dict.fromkeys(user for user in resolved if user))


def _assignees(doc) -> list:
	if not doc:
		return []
	return frappe.parse_json(doc.get("_assign") or "[]") or []


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
			"options_source": "notification_recipients",
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
		recipients = resolve_recipients(_as_list(params.get("recipients")), doc)
		if not recipients:
			return _("No recipients to notify")
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


class CallWebhook(AutomationAction):
	action_type = "CallWebhook"
	label = "Call Webhook"
	description = "Send an HTTP request to an external URL."
	requires_document = False
	params_schema: ClassVar[list] = [
		{"fieldname": "url", "label": "URL", "fieldtype": "Data", "reqd": 1},
		{
			"fieldname": "method",
			"label": "Method",
			"fieldtype": "Select",
			"options": "\n".join(HTTP_METHODS),
		},
		{"fieldname": "headers", "label": "Headers", "fieldtype": "JSON"},
		{"fieldname": "payload", "label": "Payload", "fieldtype": "JSON"},
		{"fieldname": "timeout", "label": "Timeout (seconds)", "fieldtype": "Int"},
	]
	output_schema: ClassVar[dict] = {"status_code": {"fieldtype": "Int"}, "response": {"fieldtype": "Text"}}

	def validate(self, params, doctype):
		url = (params.get("url") or "").strip()
		if not url:
			raise AutomationParamError(_("URL is required"), fieldname="url")
		# A templated URL is only a URL once rendered; the guard that matters runs then.
		if "{{" not in url:
			_check_url_shape(url)
		if (params.get("method") or "POST").upper() not in HTTP_METHODS:
			raise AutomationParamError(_("Unsupported HTTP method"), fieldname="method")
		if cint(params.get("timeout")) < 0 or cint(params.get("timeout")) > MAX_WEBHOOK_TIMEOUT:
			raise AutomationParamError(
				_("Timeout must be between 1 and {0} seconds").format(MAX_WEBHOOK_TIMEOUT),
				fieldname="timeout",
			)
		_json_param(params.get("headers"), "headers")
		_json_param(params.get("payload"), "payload")

	def execute(self, doc, params, context):
		url = _render(params.get("url"), doc, context)
		method = (params.get("method") or "POST").upper()
		headers = _rendered_json(params.get("headers"), doc, context, "headers")
		payload = _rendered_json(params.get("payload"), doc, context, "payload")
		timeout = cint(params.get("timeout")) or DEFAULT_WEBHOOK_TIMEOUT
		response = _send_guarded_request(method, url, headers, payload, timeout)
		body = (response.text or "")[:WEBHOOK_RESPONSE_LIMIT]
		if response.status_code >= 400:
			raise frappe.ValidationError(
				_("{0} {1} returned {2}: {3}").format(method, url, response.status_code, body)
			)
		return {
			"detail": _("{0} {1} returned {2}").format(method, url, response.status_code),
			"status_code": response.status_code,
			"response": body,
		}


class RunScript(AutomationAction):
	action_type = "RunScript"
	label = "Run Script"
	description = "Run a server script with the flow's documents in scope."
	requires_document = False
	params_schema: ClassVar[list] = [
		{"fieldname": "script", "label": "Script", "fieldtype": "Code", "options": "Python", "reqd": 1},
	]

	def validate(self, params, doctype):
		from frappe.utils.safe_exec import is_safe_exec_enabled

		script = (params.get("script") or "").strip()
		if not script:
			raise AutomationParamError(_("Script is required"), fieldname="script")
		if not is_safe_exec_enabled():
			raise AutomationParamError(
				_("Server Scripts are disabled. Enable them from the bench configuration."),
				fieldname="script",
			)
		_compile_script(script)
		# Who may author a script step is a save-time question. The step itself runs under the
		# flow's execution identity, which is deliberately not a System Manager most of the time.
		if not frappe.flags.get("in_automation_run") and "System Manager" not in frappe.get_roles():
			raise AutomationParamError(
				_("Only a System Manager can add a Run Script step"), fieldname="script"
			)

	def execute(self, doc, params, context):
		from frappe.utils.safe_exec import safe_exec

		scope = _render_context(doc, context)
		scope["result"] = frappe._dict()
		rule = context.get("rule") if context else None
		safe_exec(
			params.get("script") or "",
			_locals=scope,
			# The drainer owns the transaction: a step that commits would strand the rows it
			# leaves behind mid-run.
			restrict_commit_rollback=True,
			script_filename=f"automation_{rule.name}" if rule else "automation",
		)
		result = dict(scope.get("result") or {})
		result.setdefault("detail", _("Ran script"))
		return result


def _check_url_shape(url: str):
	parsed = urlparse(url)
	if parsed.scheme not in ALLOWED_SCHEMES:
		raise AutomationParamError(_("URL must be http or https"), fieldname="url")
	if not parsed.hostname:
		raise AutomationParamError(_("URL has no host"), fieldname="url")


def _guard_url(url: str):
	"""Refuse anything that resolves off the public internet: the flow author picks the URL,
	but nothing in the framework should let them reach the metadata service or a neighbour."""
	import ipaddress
	import socket

	_check_url_shape(url)
	hostname = urlparse(url).hostname
	try:
		addr_info = socket.getaddrinfo(hostname, None)
	except socket.gaierror:
		raise AutomationParamError(_("Could not resolve host: {0}").format(hostname), fieldname="url")

	for record in addr_info:
		try:
			address = ipaddress.ip_address(record[4][0])
		except (ValueError, IndexError):
			continue
		if not address.is_global:
			raise AutomationParamError(
				_("Requests to internal network addresses are not permitted"), fieldname="url"
			)


def _send_guarded_request(method, url, headers, payload, timeout):
	"""Follow redirects by hand so every hop is guarded; requests would only check the first."""
	import requests

	body = frappe.as_json(payload) if payload else None
	headers = {"Content-Type": "application/json", **(headers or {})} if body else dict(headers or {})
	for _hop in range(MAX_REDIRECTS + 1):
		_guard_url(url)
		response = requests.request(
			method=method, url=url, data=body, headers=headers, timeout=timeout, allow_redirects=False
		)
		location = response.headers.get("Location") if response.is_redirect else None
		if not location:
			return response
		url = urljoin(url, location)
		if response.status_code in (301, 302, 303) and method != "HEAD":
			method, body = "GET", None

	raise AutomationParamError(_("Too many redirects"), fieldname="url")


def _json_param(value, fieldname):
	"""Parse a JSON param into a dict, or raise pointing at the box that holds it."""
	if not value:
		return {}
	if isinstance(value, dict):
		return value
	parsed = frappe.parse_json(value)
	if not isinstance(parsed, dict):
		raise AutomationParamError(_("{0} must be a JSON object").format(fieldname), fieldname=fieldname)
	return parsed


def _rendered_json(value, doc, context, fieldname):
	return {key: _render(item, doc, context) for key, item in _json_param(value, fieldname).items()}


def _compile_script(script):
	from RestrictedPython import compile_restricted

	from frappe.utils.safe_exec import FrappeTransformer

	try:
		compile_restricted(script, policy=FrappeTransformer)
	except Exception as error:
		raise AutomationParamError(str(error), fieldname="script")


CORE_ACTIONS = [
	SetFieldValue,
	IncrementFieldValue,
	CreateDocument,
	SendNotification,
	AssignToUser,
	CallWebhook,
	RunScript,
]
