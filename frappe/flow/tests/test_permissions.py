# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase

from flow import api
from flow.memory import store as memory_store
from flow.patches.grant_flow_role import FLOW_USER_ROLE_PROFILE
from flow.patches.grant_flow_role import execute as grant_flow_role
from flow.permissions import FLOW_USER_ROLE, ensure_flow_role

ROLE_DOCTYPES = ("Flow Agent", "Flow Model", "Flow Session", "Flow Run")


def _user(email: str, *roles: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
		).insert(ignore_permissions=True)
	if roles:
		frappe.get_doc("User", email).add_roles(*roles)
	return email


def _agent() -> str:
	if frappe.db.exists("Flow Agent", "Flow Access Agent"):
		return "Flow Access Agent"
	model = frappe.get_doc(
		{
			"doctype": "Flow Model",
			"title": "Flow Access Model",
			"model_id": "openai/gpt-4o-mini",
			"enabled": 1,
		}
	).insert()
	return (
		frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Flow Access Agent",
				"model": model.name,
				"instructions": "x",
				"enabled": 1,
			}
		)
		.insert()
		.name
	)


class TestFlowAccess(IntegrationTestCase):
	def setUp(self):
		ensure_flow_role()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_the_role_exists_with_desk_access(self):
		ensure_flow_role()
		self.assertEqual(frappe.db.get_value("Role", FLOW_USER_ROLE, "desk_access"), 1)

	def test_the_doctype_rows_follow_the_role(self):
		outsider = _user("flow-access-none@example.com")
		member = _user("flow-access-member@example.com", FLOW_USER_ROLE)
		manager = _user("flow-access-manager@example.com", "System Manager")
		for doctype in ROLE_DOCTYPES:
			with self.subTest(doctype):
				self.assertFalse(frappe.has_permission(doctype, "read", user=outsider))
				self.assertTrue(frappe.has_permission(doctype, "read", user=member))
				self.assertTrue(frappe.has_permission(doctype, "read", user=manager))

	def test_sessions_runs_and_personal_memories_stay_private_to_their_owner(self):
		self.addCleanup(memory_store.drop_table)
		owner = _user("flow-private-owner@example.com", FLOW_USER_ROLE)
		member = _user("flow-private-member@example.com", FLOW_USER_ROLE)
		manager = _user("flow-private-manager@example.com", "System Manager")
		agent = _agent()
		frappe.set_user(owner)
		chat = frappe.get_doc(
			{"doctype": "Flow Session", "agent": agent, "messages": [{"role": "user", "content": "Private."}]}
		).insert(ignore_permissions=True)
		fired = frappe.get_doc({"doctype": "Flow Session", "agent": agent, "source": "Trigger"}).insert(
			ignore_permissions=True
		)
		run, fired_run = (
			frappe.get_doc(
				{"doctype": "Flow Run", "session": s.name, "source": s.source, "status": "Completed"}
			).insert(ignore_permissions=True)
			for s in (chat, fired)
		)
		memory, agent_memory = (
			frappe.get_doc(
				{
					"doctype": "Flow Agent Memory",
					"agent": agent,
					"scope": scope,
					"user": owner,
					"content": "Noted.",
				}
			).insert(ignore_permissions=True)
			for scope in ("User", "Agent")
		)
		frappe.set_user("Administrator")

		for user in (member, manager):
			with self.subTest(user):
				self.assertFalse(frappe.has_permission("Flow Session", "read", chat, user=user))
				self.assertFalse(frappe.has_permission("Flow Run", "read", run, user=user))
				self.assertFalse(frappe.has_permission("Flow Agent Memory", "read", memory, user=user))
				self.assertFalse(
					frappe.get_list(
						"Flow Session Message",
						parent_doctype="Flow Session",
						filters={"parent": chat.name},
						user=user,
					)
				)
		for doc in (chat, run, memory):
			with self.subTest(doc.doctype):
				self.assertFalse(frappe.get_list(doc.doctype, filters={"name": doc.name}, user=manager))
				self.assertTrue(frappe.has_permission(doc.doctype, "delete", doc, user=manager))
		for doc in (fired, fired_run, agent_memory):
			with self.subTest(doc.doctype):
				self.assertTrue(frappe.has_permission(doc.doctype, "read", doc, user=manager))
				self.assertTrue(frappe.get_list(doc.doctype, filters={"name": doc.name}, user=manager))

		# changing the fields the rules read cannot open a record, and runs stay read-only
		frappe.set_user(manager)
		for doctype, name, changes, refusal in (
			("Flow Run", run.name, {"source": "Trigger"}, frappe.PermissionError),
			("Flow Run", fired_run.name, {"status": "Failed"}, frappe.PermissionError),
			("Flow Agent Memory", memory.name, {"scope": "Agent"}, frappe.CannotChangeConstantError),
			("Flow Agent Memory", memory.name, {"user": manager}, frappe.CannotChangeConstantError),
		):
			with self.subTest(doctype, changes=changes):
				doc = frappe.get_doc(doctype, name)
				doc.update(changes)
				with self.assertRaises(refusal):
					doc.save()

	def test_every_endpoint_refuses_a_user_without_the_role(self):
		agent = _agent()
		session = frappe.get_doc({"doctype": "Flow Session", "agent": agent}).insert(ignore_permissions=True)
		run = frappe.get_doc(
			{"doctype": "Flow Run", "session": session.name, "source": "Manual", "status": "Completed"}
		).insert(ignore_permissions=True)
		calls = {
			"boot": {},
			"create_session": {"agent": agent},
			"session": {"session": session.name},
			"list_sessions": {},
			"run": {"session": session.name, "message": "hi"},
			"resume": {"session": session.name, "answers": "{}"},
			"abort": {"session": session.name},
			"cancel_pending": {"session": session.name},
			"entries": {"session": session.name},
			"set_model": {"session": session.name, "model": "m"},
			"set_title": {"session": session.name, "title": "t"},
			"set_auto_approve": {"session": session.name, "auto_approve": 1},
			"delete_session": {"session": session.name},
			"sync_session": {"session": session.name},
			"submit_feedback": {"run_name": run.name, "rating": "Up"},
			"attach_file": {"file": "x"},
			"cleanup_attachments": {"session": session.name},
			"skills": {"session": session.name},
		}
		self.assertEqual(set(calls), set(api.__all__))
		frappe.set_user(_user("flow-access-none@example.com"))
		for name, kwargs in calls.items():
			with self.subTest(name), self.assertRaises(frappe.PermissionError):
				getattr(api, name)(**kwargs)

	def test_the_patch_keeps_managers_and_trigger_accounts_on_flow(self):
		manager = _user("flow-grant-manager@example.com", "System Manager")
		plain = _user("flow-grant-plain@example.com")
		retired = _user("flow-grant-retired@example.com", "System Manager")
		frappe.db.set_value("User", retired, "enabled", 0)
		manager_profile = self._profile("Flow Grant Managers", "System Manager")
		profiled = _user("flow-grant-profiled@example.com")
		self._assign_profile(profiled, manager_profile)

		operator_role = self._role("Flow Grant Operator")
		operator_profile = self._profile("Flow Grant Operators", operator_role)
		operator = _user("flow-grant-operator@example.com")
		peer = _user("flow-grant-peer@example.com")
		self._assign_profile(operator, operator_profile)
		self._assign_profile(peer, operator_profile)
		self._trigger_before_the_rule(title="Flow Grant Active Trigger", run_as=operator)

		website_user = _user("flow-grant-website@example.com")
		unsafe_trigger = self._trigger_before_the_rule(title="Flow Grant Unsafe Trigger", run_as=website_user)
		dormant_operator = _user("flow-grant-dormant@example.com", operator_role)
		dormant_trigger = self._trigger_before_the_rule(
			title="Flow Grant Dormant Trigger", run_as=dormant_operator, enabled=0
		)

		grant_flow_role()

		for name in (manager, profiled, operator):
			self.assertIn(FLOW_USER_ROLE, frappe.get_roles(name), name)
		for name in (plain, retired, peer, website_user, dormant_operator):
			self.assertNotIn(FLOW_USER_ROLE, frappe.get_roles(name), name)
		self.assertNotIn(
			FLOW_USER_ROLE, [row.role for row in frappe.get_doc("Role Profile", manager_profile).roles]
		)
		self.assertNotIn(
			FLOW_USER_ROLE, [row.role for row in frappe.get_doc("Role Profile", operator_profile).roles]
		)
		for name in (profiled, operator):
			profiles = {row.role_profile for row in frappe.get_doc("User", name).role_profiles}
			self.assertIn(FLOW_USER_ROLE_PROFILE, profiles)
		self.assertEqual(
			[row.role for row in frappe.get_doc("Role Profile", FLOW_USER_ROLE_PROFILE).roles],
			[FLOW_USER_ROLE],
		)
		self.assertEqual(frappe.db.get_value("Flow Trigger", unsafe_trigger, "enabled"), 0)
		self.assertEqual(frappe.db.get_value("Flow Trigger", dormant_trigger, "enabled"), 0)
		self.assertEqual(frappe.db.get_value("User", website_user, "user_type"), "Website User")

	def _role(self, name: str) -> str:
		if not frappe.db.exists("Role", name):
			frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert(
				ignore_permissions=True
			)
		return name

	def _profile(self, name: str, *roles: str) -> str:
		if not frappe.db.exists("Role Profile", name):
			frappe.get_doc(
				{"doctype": "Role Profile", "role_profile": name, "roles": [{"role": role} for role in roles]}
			).insert(ignore_permissions=True)
		return name

	def _assign_profile(self, user: str, profile: str) -> None:
		doc = frappe.get_doc("User", user)
		doc.append("role_profiles", {"role_profile": profile})
		doc.save(ignore_permissions=True)

	def _trigger_before_the_rule(self, **fields) -> str:
		"""A trigger saved before its account had to be able to read the agent."""
		trigger = frappe.get_doc(
			{
				"doctype": "Flow Trigger",
				"title": "Flow Grant Trigger",
				"agent": _agent(),
				"event": "Scheduled",
				"cron_expression": "0 0 * * *",
				"prompt_template": "hi",
				**fields,
			}
		)
		trigger.flags.ignore_validate = True
		return trigger.insert(ignore_permissions=True).name
