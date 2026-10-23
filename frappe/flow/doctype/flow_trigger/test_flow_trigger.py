# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any

import frappe
from frappe.flow.permissions import FLOW_USER_ROLE
from frappe.flow.tools.builtins import sync_builtin_tools
from frappe.tests import IntegrationTestCase


def _model(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Model",
		"title": "Test Trigger Model",
		"model_id": "openai/gpt-4o-mini",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _agent(model_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Agent",
		"title": "Test Trigger Agent",
		"model": model_name,
		"instructions": "Be terse.",
		"enabled": 1,
	}
	doc.update(overrides)
	return doc


def _trigger(agent_name: str, **overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Trigger",
		"title": "Test Trigger",
		"agent": agent_name,
		"enabled": 1,
		"event": "DocType Event",
		"target_doctype": "ToDo",
		"doc_event": "after_insert",
		"prompt_template": "A new {{ doc.doctype }} '{{ doc.name }}' was created.",
	}
	doc.update(overrides)
	return doc


def _user(email: str, *roles: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
		).insert(ignore_permissions=True)
	frappe.get_doc("User", email).add_roles(*roles)
	return email


class TestFlowTriggerValidation(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sync_builtin_tools()

	def setUp(self):
		self.model = frappe.get_doc(_model()).insert()
		self.agent = frappe.get_doc(_agent(self.model.name)).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_the_account_a_trigger_runs_as_must_be_enabled_and_able_to_read_the_agent(self):
		disabled = _user("trigger-disabled@example.com")
		frappe.db.set_value("User", disabled, "enabled", 0)
		with self.assertRaisesRegex(frappe.ValidationError, "Run As must be an enabled user"):
			frappe.get_doc(_trigger(self.agent.name, run_as=disabled)).insert()

		outsider = _user("trigger-outsider@example.com")
		with self.assertRaisesRegex(frappe.ValidationError, "cannot use agent"):
			frappe.get_doc(_trigger(self.agent.name, run_as=outsider)).insert()

		doc = frappe.get_doc(_trigger(self.agent.name)).insert()  # owned by Administrator
		frappe.db.set_value("Flow Trigger", doc.name, "owner", outsider)
		with self.assertRaisesRegex(frappe.ValidationError, "cannot use agent"):
			frappe.get_doc("Flow Trigger", doc.name).save()

		member = _user("trigger-member@example.com", "System Manager", FLOW_USER_ROLE)
		self.assertEqual(
			frappe.get_doc(_trigger(self.agent.name, title="Member Trigger", run_as=member)).insert().run_as,
			member,
		)

	def test_event_fields_cron_condition_and_template_are_validated(self):
		scheduled = {"event": "Scheduled", "target_doctype": None, "doc_event": None}
		# a complete trigger of either event saves
		frappe.get_doc(_trigger(self.agent.name)).insert()
		frappe.get_doc(
			_trigger(self.agent.name, title="Scheduled Trigger", **scheduled, cron_expression="0 9 * * 5")
		).insert()

		for overrides, error in (
			({"target_doctype": None}, "Target DocType"),
			({"doc_event": None}, "Doc Event"),
			(scheduled, "Cron"),
			({**scheduled, "cron_expression": "this is not cron"}, "cron"),
			({"condition": "doc.status =="}, "condition"),
			({"condition": "status = doc.status"}, "result"),  # a script must set result
			({"prompt_template": "{{ broken"}, "template"),
		):
			with self.subTest(overrides), self.assertRaisesRegex(frappe.ValidationError, error):
				frappe.get_doc(_trigger(self.agent.name, **overrides)).insert()
