# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.automation_engine.actions.base import AutomationParamError, get_action, get_action_registry
from frappe.automation_engine.actions.core import (
	AssignToUser,
	CallWebhook,
	CreateDocument,
	IncrementFieldValue,
	RunScript,
	SendNotification,
	SetFieldValue,
)
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import enable_safe_exec


def make_todo(**kwargs):
	return frappe.get_doc({"doctype": "ToDo", "description": "x", **kwargs}).insert()


class TestActions(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.local.automation_actions = None

	def tearDown(self):
		frappe.db.rollback()
		frappe.local.automation_actions = None

	def test_registry_contains_core_actions(self):
		registry = get_action_registry()
		for action_type in (
			"SetFieldValue",
			"IncrementFieldValue",
			"CreateDocument",
			"SendNotification",
			"AssignToUser",
			"CallWebhook",
			"RunScript",
		):
			self.assertIn(action_type, registry)

	def test_get_action_throws_for_unknown(self):
		self.assertRaises(frappe.ValidationError, get_action, "NopeAction")

	def test_set_field_value_renders_template(self):
		todo = make_todo(priority="Low")
		SetFieldValue().execute(todo, {"field": "priority", "value": "High"}, {})
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")

	def test_set_field_value_validates_field_exists(self):
		self.assertRaises(AutomationParamError, SetFieldValue().validate, {"field": "nope_field"}, "ToDo")

	def test_set_field_value_multiple_fields(self):
		todo = make_todo(priority="Low", color="#000000")
		SetFieldValue().execute(todo, {"values": {"priority": "High", "color": "#ED6396"}}, {})
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "color"), "#ED6396")

	def test_single_field_and_values_map_are_both_applied(self):
		# Filling both boxes must not silently drop one: a doctype whose validation spans two
		# fields (set a Lost status, give a lost reason) is unsatisfiable if only one lands.
		todo = make_todo(priority="Low", color="#000000")
		SetFieldValue().execute(
			todo, {"field": "priority", "value": "High", "values": {"color": "#ED6396"}}, {}
		)
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "priority"), "High")
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "color"), "#ED6396")

	def test_set_field_value_multiple_validates_each_field(self):
		self.assertRaises(
			AutomationParamError,
			SetFieldValue().validate,
			{"values": {"priority": "High", "nope_field": "x"}},
			"ToDo",
		)

	def test_create_document(self):
		src = make_todo()
		detail = CreateDocument().execute(
			src, {"doctype": "ToDo", "values": {"description": "created-by-automation"}}, {}
		)
		self.assertTrue(frappe.db.exists("ToDo", {"description": "created-by-automation"}))
		self.assertIn("Created", detail["detail"])

	def test_increment_field_value(self):
		flow = frappe.new_doc("Automation Flow")
		flow.update({"title": "counter", "trigger_type": "Manual", "date_offset": 2})
		IncrementFieldValue().execute(flow.insert(), {"field": "date_offset", "amount": 3}, {})
		self.assertEqual(frappe.db.get_value("Automation Flow", flow.name, "date_offset"), 5)

	def test_create_document_requires_existing_doctype(self):
		self.assertRaises(
			AutomationParamError, CreateDocument().validate, {"doctype": "No Such DocType"}, "ToDo"
		)

	def test_create_document_renders_template_values(self):
		src = make_todo(priority="High")
		CreateDocument().execute(
			src, {"doctype": "ToDo", "values": {"description": "prio-{{ doc.priority }}"}}, {}
		)
		self.assertTrue(frappe.db.exists("ToDo", {"description": "prio-High"}))

	def test_assign_to_user(self):
		note = frappe.get_doc({"doctype": "Note", "title": "assign-me", "public": 1}).insert()
		AssignToUser().execute(note, {"assign_to": ["Administrator"]}, {})
		assigned = frappe.db.get_value("Note", note.name, "_assign") or ""
		self.assertIn("Administrator", assigned)

	def test_assign_to_user_requires_assignee(self):
		self.assertRaises(AutomationParamError, AssignToUser().validate, {}, "ToDo")

	def test_send_notification_system_creates_log(self):
		todo = make_todo()
		before = frappe.db.count("Notification Log", {"for_user": "Administrator"})
		SendNotification().execute(
			todo,
			{"channel": "System", "recipients": ["Administrator"], "subject": "hi", "message": "there"},
			{},
		)
		after = frappe.db.count("Notification Log", {"for_user": "Administrator"})
		self.assertEqual(after, before + 1)

	def test_send_notification_accepts_recipients_as_a_json_string(self):
		# `recipients` is declared JSON; a builder may store it as the string form. Iterating
		# that string sends one character per "recipient".
		todo = make_todo()
		captured = {}
		original = frappe.sendmail
		frappe.sendmail = lambda **kwargs: captured.update(kwargs)
		try:
			SendNotification().execute(
				todo,
				{"channel": "Email", "recipients": '["a@example.com"]', "subject": "s", "message": "m"},
				{},
			)
		finally:
			frappe.sendmail = original
		self.assertEqual(captured["recipients"], ["a@example.com"])

	def test_send_notification_wraps_a_single_bare_recipient(self):
		todo = make_todo()
		captured = {}
		original = frappe.sendmail
		frappe.sendmail = lambda **kwargs: captured.update(kwargs)
		try:
			SendNotification().execute(
				todo,
				{"channel": "Email", "recipients": "a@example.com", "subject": "s", "message": "m"},
				{},
			)
		finally:
			frappe.sendmail = original
		self.assertEqual(captured["recipients"], ["a@example.com"])

	def test_send_notification_resolves_the_owner_token(self):
		todo = make_todo()
		captured = {}
		original = frappe.sendmail
		frappe.sendmail = lambda **kwargs: captured.update(kwargs)
		try:
			SendNotification().execute(
				todo,
				{"channel": "Email", "recipients": ["@owner"], "subject": "s", "message": "m"},
				{},
			)
		finally:
			frappe.sendmail = original
		self.assertEqual(captured["recipients"], [todo.owner])

	def test_send_notification_resolves_the_assignees_token(self):
		note = frappe.get_doc({"doctype": "Note", "title": "notify-assignees", "public": 1}).insert()
		AssignToUser().execute(note, {"assign_to": ["Administrator"]}, {})
		note.reload()
		captured = {}
		original = frappe.sendmail
		frappe.sendmail = lambda **kwargs: captured.update(kwargs)
		try:
			SendNotification().execute(
				note,
				{"channel": "Email", "recipients": ["@assignees"], "subject": "s", "message": "m"},
				{},
			)
		finally:
			frappe.sendmail = original
		self.assertEqual(captured["recipients"], ["Administrator"])

	def test_send_notification_dedupes_resolved_recipients(self):
		todo = make_todo()
		captured = {}
		original = frappe.sendmail
		frappe.sendmail = lambda **kwargs: captured.update(kwargs)
		try:
			SendNotification().execute(
				todo,
				{
					"channel": "Email",
					"recipients": ["@owner", todo.owner, "other@example.com"],
					"subject": "s",
					"message": "m",
				},
				{},
			)
		finally:
			frappe.sendmail = original
		self.assertEqual(captured["recipients"], [todo.owner, "other@example.com"])

	def test_send_notification_skips_sending_when_a_token_resolves_to_nobody(self):
		note = frappe.get_doc({"doctype": "Note", "title": "notify-nobody", "public": 1}).insert()
		calls = []
		original = frappe.sendmail
		frappe.sendmail = lambda **kwargs: calls.append(kwargs)
		try:
			SendNotification().execute(
				note,
				{"channel": "Email", "recipients": ["@assignees"], "subject": "s", "message": "m"},
				{},
			)
		finally:
			frappe.sendmail = original
		self.assertEqual(calls, [])

	def test_assign_to_user_accepts_assignees_as_a_json_string(self):
		note = frappe.get_doc({"doctype": "Note", "title": "assign-me-json", "public": 1}).insert()
		AssignToUser().execute(note, {"assign_to": '["Administrator"]'}, {})
		self.assertIn("Administrator", frappe.db.get_value("Note", note.name, "_assign") or "")

	def test_empty_json_string_still_fails_validation(self):
		self.assertRaises(AutomationParamError, SendNotification().validate, {"recipients": "[]"}, "ToDo")
		self.assertRaises(AutomationParamError, AssignToUser().validate, {"assign_to": "[]"}, "ToDo")

	def test_send_notification_requires_existing_template(self):
		self.assertRaises(
			AutomationParamError,
			SendNotification().validate,
			{"recipients": ["Administrator"], "email_template": "No Such Template"},
			"ToDo",
		)

	def test_send_notification_renders_email_template(self):
		todo = make_todo(description="templated")
		template = frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": "Automation Test Template",
				"subject": "Subject {{ doc.description }}",
				"response": "Body {{ doc.description }}",
			}
		).insert(ignore_permissions=True)
		subject, message = SendNotification()._content({"email_template": template.name}, todo, {})
		self.assertEqual(subject, "Subject templated")
		self.assertEqual(message, "Body templated")

	def test_send_notification_email_delegates_to_sendmail(self):
		todo = make_todo()
		captured = {}
		original = frappe.sendmail
		frappe.sendmail = lambda **kwargs: captured.update(kwargs)
		try:
			SendNotification().execute(
				todo,
				{"channel": "Email", "recipients": ["a@example.com"], "subject": "s", "message": "m"},
				{},
			)
		finally:
			frappe.sendmail = original
		self.assertEqual(captured["recipients"], ["a@example.com"])
		self.assertEqual(captured["reference_name"], todo.name)


class FakeResponse:
	def __init__(self, status_code=200, text="ok", headers=None):
		self.status_code = status_code
		self.text = text
		self.headers = headers or {}

	@property
	def is_redirect(self):
		return self.status_code in (301, 302, 303, 307, 308) and "Location" in self.headers


def public_dns(host_ips):
	"""Resolve hosts from a map instead of the network; a literal IP resolves to itself."""

	def getaddrinfo(host, *args, **kwargs):
		ip = host_ips.get(host, host)
		return [(2, 1, 6, "", (ip, 0))]

	return patch("socket.getaddrinfo", side_effect=getaddrinfo)


class TestCallWebhook(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_validate_rejects_missing_and_malformed_urls(self):
		for params in ({}, {"url": "ftp://example.com"}, {"url": "https://"}):
			self.assertRaises(AutomationParamError, CallWebhook().validate, params, "ToDo")

	def test_validate_accepts_a_templated_url(self):
		CallWebhook().validate({"url": "{{ doc.description }}"}, "ToDo")

	def test_validate_rejects_unsupported_method_and_timeout(self):
		self.assertRaises(
			AutomationParamError,
			CallWebhook().validate,
			{"url": "https://example.com", "method": "TRACE"},
			"ToDo",
		)
		self.assertRaises(
			AutomationParamError,
			CallWebhook().validate,
			{"url": "https://example.com", "timeout": 6000},
			"ToDo",
		)

	def test_validate_rejects_non_object_headers(self):
		self.assertRaises(
			AutomationParamError,
			CallWebhook().validate,
			{"url": "https://example.com", "headers": "[1, 2]"},
			"ToDo",
		)

	def test_posts_rendered_payload_and_records_the_response(self):
		todo = make_todo(description="hello")
		with (
			public_dns({"example.com": "93.184.216.34"}),
			patch("requests.request", return_value=FakeResponse(text="done")) as request,
		):
			result = CallWebhook().execute(
				todo,
				{
					"url": "https://example.com/hook",
					"payload": {"note": "{{ doc.description }}"},
					"headers": {"X-Token": "abc"},
					"timeout": 7,
				},
				{},
			)

		self.assertEqual(result["status_code"], 200)
		self.assertEqual(result["response"], "done")
		kwargs = request.call_args.kwargs
		self.assertEqual(kwargs["method"], "POST")
		self.assertEqual(frappe.parse_json(kwargs["data"]), {"note": "hello"})
		self.assertEqual(kwargs["headers"]["X-Token"], "abc")
		self.assertEqual(kwargs["timeout"], 7)
		self.assertFalse(kwargs["allow_redirects"])

	def test_failed_status_fails_the_step(self):
		with (
			public_dns({"example.com": "93.184.216.34"}),
			patch("requests.request", return_value=FakeResponse(status_code=500, text="boom")),
		):
			self.assertRaises(
				frappe.ValidationError,
				CallWebhook().execute,
				None,
				{"url": "https://example.com/hook"},
				{},
			)

	def test_internal_addresses_are_blocked(self):
		for url in (
			"http://169.254.169.254/latest/meta-data/",
			"http://10.1.2.3/hook",
			"http://127.0.0.1:8000/hook",
		):
			with patch("requests.request") as request:
				self.assertRaises(AutomationParamError, CallWebhook().execute, None, {"url": url}, {})
				request.assert_not_called()

	def test_a_host_resolving_internally_is_blocked(self):
		with (
			public_dns({"sneaky.example.com": "10.0.0.5"}),
			patch("requests.request") as request,
		):
			self.assertRaises(
				AutomationParamError,
				CallWebhook().execute,
				None,
				{"url": "https://sneaky.example.com/hook"},
				{},
			)
			request.assert_not_called()

	def test_redirect_to_an_internal_address_is_blocked(self):
		redirect = FakeResponse(status_code=302, headers={"Location": "http://169.254.169.254/"})
		with (
			public_dns({"example.com": "93.184.216.34"}),
			patch("requests.request", return_value=redirect) as request,
		):
			self.assertRaises(
				AutomationParamError,
				CallWebhook().execute,
				None,
				{"url": "https://example.com/hook"},
				{},
			)
			self.assertEqual(request.call_count, 1)

	def test_redirect_to_a_public_address_is_followed(self):
		responses = [
			FakeResponse(status_code=302, headers={"Location": "https://other.example.com/final"}),
			FakeResponse(text="final"),
		]
		with (
			public_dns({"example.com": "93.184.216.34", "other.example.com": "93.184.216.35"}),
			patch("requests.request", side_effect=responses) as request,
		):
			result = CallWebhook().execute(None, {"url": "https://example.com/hook"}, {})

		self.assertEqual(result["response"], "final")
		self.assertEqual(request.call_count, 2)
		# A POST redirected with 302 continues as a GET without the body, as requests would.
		self.assertEqual(request.call_args.kwargs["method"], "GET")
		self.assertIsNone(request.call_args.kwargs["data"])

	def test_redirect_loop_stops(self):
		redirect = FakeResponse(status_code=302, headers={"Location": "https://example.com/hook"})
		with (
			public_dns({"example.com": "93.184.216.34"}),
			patch("requests.request", return_value=redirect),
		):
			self.assertRaises(
				AutomationParamError, CallWebhook().execute, None, {"url": "https://example.com/hook"}, {}
			)


class TestRunScript(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.enterClassContext(enable_safe_exec())

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_validate_requires_a_script(self):
		self.assertRaises(AutomationParamError, RunScript().validate, {}, "ToDo")

	def test_validate_rejects_a_script_that_does_not_compile(self):
		self.assertRaises(AutomationParamError, RunScript().validate, {"script": "def ("}, "ToDo")

	def test_validate_throws_when_server_scripts_are_disabled(self):
		with patch("frappe.utils.safe_exec.is_safe_exec_enabled", return_value=False):
			self.assertRaises(AutomationParamError, RunScript().validate, {"script": "pass"}, "ToDo")

	def test_only_a_system_manager_may_author_a_script_step(self):
		user = frappe.get_doc(
			{"doctype": "User", "email": "automation-scripter@example.com", "first_name": "Scripter"}
		).insert(ignore_permissions=True)
		frappe.set_user(user.name)
		try:
			self.assertRaises(AutomationParamError, RunScript().validate, {"script": "pass"}, "ToDo")
			# The step still revalidates inside a run, under an identity that is not an author.
			frappe.flags.in_automation_run = True
			RunScript().validate({"script": "pass"}, "ToDo")
		finally:
			frappe.flags.in_automation_run = None
			frappe.set_user("Administrator")

	def test_script_sees_the_document_and_returns_its_result(self):
		todo = make_todo(description="scripted")
		result = RunScript().execute(todo, {"script": "result['detail'] = 'saw ' + doc.description"}, {})
		self.assertEqual(result["detail"], "saw scripted")

	def test_script_without_a_result_still_reports_a_detail(self):
		self.assertEqual(RunScript().execute(None, {"script": "x = 1"}, {})["detail"], "Ran script")

	def test_script_cannot_commit(self):
		with self.assertRaises(Exception):
			RunScript().execute(None, {"script": "frappe.db.commit()"}, {})
