# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import hashlib

import frappe
from frappe.flow.api import guest
from frappe.flow.daemon.callback import tool_callback
from frappe.flow.tests.test_ai_api import ApiCase, _agent_doc, _ensure_manager, _ensure_user

GUEST_TOOL = "guest_whoami"
OTHER = "guest-api-other@example.com"


class TestGuestApi(ApiCase):
	"""Someone who is not signed in chats with a public agent; the chat's token is its only key."""

	def setUp(self):
		super().setUp()
		frappe.get_doc(
			{
				"doctype": "Flow Tool",
				"title": GUEST_TOOL,
				"slug": GUEST_TOOL,
				"description": "The user this tool runs as.",
				"type": "Imported",
				"import_path": "frappe.flow.tests.test_daemon_callback.whoami",
			}
		).insert()
		self.agent.update({"public": 1, "tools": [{"tool": GUEST_TOOL}]})
		self.agent.save()
		self.manager, self.other = _ensure_manager(), _ensure_user(OTHER)
		frappe.set_user("Guest")

	def start(self) -> tuple[str, str]:
		chat = guest.start(self.agent.name)
		return chat["session"], chat["token"]

	def test_a_guest_chats_with_a_public_agent(self):
		session, token = self.start()
		doc = frappe.get_doc("Flow Session", session)
		self.assertEqual((doc.owner, doc.approval_mode), ("Guest", "Auto-approve"))
		self.assertEqual(doc.guest_token, _hash(token))

		guest.send(session, token, "hi")
		self.assertEqual(guest.entries(session, token)["entries"][-1]["type"], "run_ended")
		# a later read starts partway, which the flow server gives only from its "all" view
		guest.entries(session, token, since=2)
		self.assertEqual(self.daemon.calls[-1], ("entries", session, 2, "all"))
		# its tools run as Guest
		self.assertEqual(tool_callback(session, GUEST_TOOL)["content"], "Guest")

		# only while the agent is public
		frappe.db.set_value("Flow Agent", self.agent.name, "public", 0)
		with self.assertRaises(frappe.PermissionError):
			guest.start(self.agent.name)
		with self.assertRaises(frappe.PermissionError):
			guest.send(session, token, "hi")

	def test_a_guests_message_arrives_as_written(self):
		frappe.local.form_dict = frappe._dict(message="mail <me@example.com>, use List<String>")
		frappe.is_whitelisted(guest.send)
		self.assertEqual(frappe.form_dict.message, "mail <me@example.com>, use List<String>")

	def test_only_its_token_opens_a_guest_chat(self):
		session, token = self.start()
		_, other_token = self.start()
		# the realtime relay asks with the token's hash
		self.assertTrue(guest.can_stream(session, _hash(token)))
		for wrong in (other_token, ""):
			self.assertFalse(guest.can_stream(session, _hash(wrong)))
			with self.assertRaises(frappe.PermissionError):
				guest.send(session, wrong, "hi")
			with self.assertRaises(frappe.PermissionError):
				guest.entries(session, wrong)
		# and the hash is no token
		with self.assertRaises(frappe.PermissionError):
			guest.entries(session, _hash(token))

		# being Guest opens nothing, as they all are; a System Manager reads it, other users don't
		doc = frappe.get_doc("Flow Session", session)
		for user in ("Guest", self.other):
			self.assertFalse(frappe.has_permission("Flow Session", "read", doc, user=user))
		frappe.set_user(self.manager)
		self.assertIn(session, frappe.get_list("Flow Session", pluck="name"))

		# a token on a chat that is not Guest's opens nothing: its owner could have written it
		frappe.db.set_value("Flow Session", session, "owner", self.other)
		self.assertFalse(guest.can_stream(session, _hash(token)))

	def test_a_signed_in_caller_chats_as_guest_and_stays_signed_in(self):
		frappe.set_user(self.other)
		frappe.session.sid = "their-sid"
		frappe.session.data.csrf_token = "their-token"

		session, token = self.start()
		run = guest.send(session, token, "hi")["run"]

		self.assertEqual(frappe.db.get_value("Flow Session", session, "owner"), "Guest")
		self.assertEqual(frappe.db.get_value("Flow Run", run, "owner"), "Guest")
		self.assertEqual(
			(frappe.session.user, frappe.session.sid, frappe.session.data.csrf_token),
			(self.other, "their-sid", "their-token"),
		)

	def test_a_guest_gets_only_the_skills_bound_to_the_agent(self):
		def skills() -> set[str]:
			agent = frappe.get_doc("Flow Agent", self.agent.name)
			return {row["name"] for row in agent.invocable_skills()}

		frappe.set_user("Administrator")
		for title, is_global in (("Guest Guide", 0), ("Staff Handbook", 1)):
			frappe.get_doc(
				{
					"doctype": "Flow Skill",
					"title": title,
					"description": title,
					"instructions": f"Body of {title}.",
					"is_global": is_global,
					"user_invocable": 1,
				}
			).insert()
		self.agent.reload()
		self.agent.append("skills", {"skill": "Guest Guide"})
		self.agent.save()
		self.assertLessEqual({"Guest Guide", "Staff Handbook"}, skills())

		frappe.set_user("Guest")
		self.assertEqual(skills(), {"Guest Guide"})

	def test_a_public_agent_cannot_have_the_memory_tool(self):
		frappe.set_user("Administrator")
		agent = frappe.get_doc(_agent_doc(self.model.name, title="Public Memory", public=1))
		agent.append("tools", {"tool": "frappe/update_memory"})
		with self.assertRaisesRegex(frappe.ValidationError, "cannot use the memory tool"):
			agent.insert()

		# a tool that asks for approval is allowed: a guest chat approves every call by itself
		self.agent.reload()
		self.agent.append("tools", {"tool": "frappe/delete"})
		self.agent.save()


def _hash(token: str) -> str:
	return hashlib.sha256(token.encode()).hexdigest()
