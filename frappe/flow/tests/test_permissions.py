# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.flow import api
from frappe.flow.memory import store as memory_store
from frappe.flow.permissions import FLOW_USER_ROLE, ensure_flow_role
from frappe.tests import IntegrationTestCase

ROLE_DOCTYPES = ("Flow Agent", "Flow Model", "Flow Session", "Flow Run", "Flow Skill")


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

	def test_flow_is_open_only_to_the_role_and_system_managers(self):
		self.assertEqual(frappe.db.get_value("Role", FLOW_USER_ROLE, "desk_access"), 1)
		outsider = _user("flow-access-none@example.com")
		member = _user("flow-access-member@example.com", FLOW_USER_ROLE)
		manager = _user("flow-access-manager@example.com", "System Manager")
		for doctype in ROLE_DOCTYPES:
			with self.subTest(doctype):
				self.assertFalse(frappe.has_permission(doctype, "read", user=outsider))
				self.assertTrue(frappe.has_permission(doctype, "read", user=member))
				self.assertTrue(frappe.has_permission(doctype, "read", user=manager))

		# every endpoint refuses a user without the role
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
			"rewind": {"session": session.name, "target_seq": 0},
			"compact": {"session": session.name},
			"entries": {"session": session.name},
			"set_model": {"session": session.name, "model": "m"},
			"set_title": {"session": session.name, "title": "t"},
			"set_auto_approve": {"session": session.name, "auto_approve": 1},
			"delete_session": {"session": session.name},
			"list_shares": {"session": session.name},
			"share_session": {"session": session.name, "user": "Administrator"},
			"unshare_session": {"session": session.name, "user": "Administrator"},
			"find_users": {"query": "a"},
			"set_general_access": {"session": session.name, "access": "Everyone"},
			"sync_session": {"session": session.name},
			"submit_feedback": {"run_name": run.name, "rating": "Up"},
			"attach_file": {"file": "x"},
			"cleanup_attachments": {"session": session.name},
			"skills": {"session": session.name},
		}
		self.assertEqual(set(calls), set(api.__all__))
		frappe.set_user(outsider)
		for name, kwargs in calls.items():
			with self.subTest(name), self.assertRaises(frappe.PermissionError):
				getattr(api, name)(**kwargs)

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
		# Trigger sessions are for System Managers, not every Flow User
		self.assertFalse(frappe.has_permission("Flow Session", "read", fired, user=member))
		self.assertFalse(frappe.get_list("Flow Session", filters={"name": fired.name}, user=member))
		# unless their owner opens them to every Flow user, to read
		fired.db_set("general_access", "Everyone")
		self.assertTrue(frappe.has_permission("Flow Session", "read", fired, user=member))
		self.assertFalse(frappe.has_permission("Flow Session", "write", fired, user=member))
		for doc in (chat, run, memory):
			with self.subTest(doc.doctype):
				self.assertFalse(frappe.get_list(doc.doctype, filters={"name": doc.name}, user=manager))
				self.assertFalse(frappe.has_permission(doc.doctype, "delete", doc, user=manager))
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

	def test_roles_decide_who_uses_an_agent_or_model_directly_and_reads_its_skills(self):
		tester = self._role("Flow Roles Tester")
		member = _user("flow-roles-member@example.com", FLOW_USER_ROLE)
		holder = _user("flow-roles-holder@example.com", FLOW_USER_ROLE, tester)
		manager = _user("flow-roles-manager@example.com", "System Manager")
		agent = frappe.get_doc("Flow Agent", _agent())
		locked_model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "Flow Locked Model",
				"model_id": "openai/gpt-4o",
				"enabled": 1,
				"roles": [{"role": tester}],
			}
		).insert()
		locked = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "Flow Locked Agent",
				"model": locked_model.name,
				"instructions": "x",
				"enabled": 1,
				"roles": [{"role": tester}],
			}
		).insert()
		shared, bound, hidden, off = (
			frappe.get_doc(
				{"doctype": "Flow Skill", "title": title, "description": "x", "instructions": "x", **fields}
			)
			.insert()
			.name
			for title, fields in (
				("Flow Roles Global", {"enabled": 1, "is_global": 1}),
				("Flow Roles Bound", {"enabled": 1}),
				("Flow Roles Hidden", {"enabled": 1}),
				("Flow Roles Off", {"enabled": 0}),
			)
		)
		agent.update({"skills": [{"skill": bound}, {"skill": off}], "sub_agents": [{"agent": locked.name}]})
		agent.save()
		locked.append("skills", {"skill": hidden})
		locked.save()

		models = [agent.model, locked_model.name]
		for user, agents, open_models, skills in (
			(member, [agent.name], [agent.model], [shared, bound]),
			(holder, [agent.name, locked.name], models, [shared, bound, hidden]),
			(manager, [agent.name, locked.name], models, [shared, bound, hidden, off]),
		):
			with self.subTest(user):
				for doctype, names, readable in (
					("Flow Agent", [agent.name, locked.name], agents),
					("Flow Model", models, open_models),
					("Flow Skill", [shared, bound, hidden, off], skills),
				):
					listed = frappe.get_list(
						doctype, filters={"name": ["in", names]}, pluck="name", user=user
					)
					self.assertEqual(sorted(listed), sorted(readable))
					for name in names:
						self.assertEqual(
							frappe.has_permission(doctype, "read", name, user=user), name in readable
						)
				# a locked agent on a locked model still works as a sub-agent of one open to them
				frappe.set_user(user)
				with patch("frappe.flow.lib.model.resolve_provider_credentials", return_value={}):
					configs = agent.subagent_configs("S1", {})
				frappe.set_user("Administrator")
				self.assertEqual([config["name"] for config in configs], [locked.name])

	def _role(self, name: str) -> str:
		if not frappe.db.exists("Role", name):
			frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert(
				ignore_permissions=True
			)
		return name
