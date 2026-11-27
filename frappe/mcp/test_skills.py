# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os

import frappe
from frappe.api.skills import get_skill, list_skills
from frappe.flow.doctype.flow_skill.test_flow_skill import AppSkills
from frappe.flow.permissions import FLOW_USER_ROLE, ensure_flow_role
from frappe.mcp.test_utils import McpTestCase
from frappe.tests import IntegrationTestCase

APP_SKILL = "frappe/skills-api-todos"


def _user(email: str, *roles: str) -> str:
	user = frappe.get_doc(
		{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
	).insert(ignore_permissions=True)
	if roles:
		user.add_roles(*roles)
	return user.name


def _skill(title: str, **fields) -> str:
	doc = {
		"doctype": "Flow Skill",
		"title": title,
		"description": f"When to use {title}.",
		"instructions": f"Body of {title}.",
		"enabled": 1,
		**fields,
	}
	return frappe.get_doc(doc).insert(ignore_permissions=True).name


def _app_skill(skills: AppSkills) -> str:
	"""An app skill with a references/forms.md file, as sync_skills writes it."""
	folder = skills.write(APP_SKILL.removeprefix("frappe/"))
	os.makedirs(os.path.join(folder, "references"))
	with open(os.path.join(folder, "references", "forms.md"), "w") as file:
		file.write("Use the ToDo form.")
	return _skill(APP_SKILL, app="frappe", is_system_generated=1)


def _agent(title: str, skills: list[str], **fields) -> str:
	model = frappe.get_doc(
		{"doctype": "Flow Model", "title": f"{title} Model", "model_id": "openai/gpt-4o-mini", "enabled": 1}
	).insert()
	return (
		frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": title,
				"model": model.name,
				"instructions": "x",
				"enabled": 1,
				"skills": [{"skill": skill} for skill in skills],
				**fields,
			}
		)
		.insert()
		.name
	)


class TestSkills(IntegrationTestCase):
	def setUp(self):
		ensure_flow_role()
		if not frappe.db.exists("Role", "Skills API Tester"):
			frappe.get_doc({"doctype": "Role", "role_name": "Skills API Tester", "desk_access": 1}).insert()
		self.member = _user("skills-api-member@example.com", FLOW_USER_ROLE)
		self.manager = _user("skills-api-manager@example.com", "System Manager")
		self.outsider = _user("skills-api-outsider@example.com")
		self.shared = _skill("Skills API Global", is_global=1)
		self.bound = _skill("Skills API Bound")
		self.hidden = _skill("Skills API Hidden")
		self.off = _skill("Skills API Off", enabled=0)
		self.app_skill = _app_skill(AppSkills(self))
		_agent("Skills API Agent", [self.bound, self.off, self.app_skill])
		_agent("Skills API Locked", [self.hidden], roles=[{"role": "Skills API Tester"}])
		self.fixtures = {self.shared, self.bound, self.hidden, self.off, self.app_skill}

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def listed(self, user: str) -> set[str]:
		frappe.set_user(user)
		return {skill["name"] for skill in list_skills()["skills"]} & self.fixtures

	def test_a_flow_user_reads_global_skills_and_those_of_agents_open_to_them(self):
		self.assertEqual(self.listed(self.member), {self.shared, self.bound, self.app_skill})
		with self.assertRaises(frappe.PermissionError):
			get_skill(self.hidden)

	def test_a_system_manager_does_not_get_a_disabled_skill(self):
		self.assertEqual(self.listed(self.manager), {self.shared, self.bound, self.hidden, self.app_skill})
		with self.assertRaises(frappe.DoesNotExistError):
			get_skill(self.off)

	def test_a_user_without_flow_access_gets_no_skills(self):
		frappe.set_user(self.outsider)
		self.assertEqual(list_skills(), {"skills": []})

	def test_a_skill_gives_its_instructions_and_an_app_skill_its_files(self):
		frappe.set_user(self.member)
		self.assertEqual(
			get_skill(self.shared),
			{
				"name": self.shared,
				"description": "When to use Skills API Global.",
				"instructions": "Body of Skills API Global.",
			},
		)
		self.assertEqual(
			get_skill(self.app_skill, "references/forms.md"),
			{"name": self.app_skill, "file": "references/forms.md", "content": "Use the ToDo form."},
		)
		with self.assertRaisesRegex(frappe.ValidationError, "has no files"):
			get_skill(self.shared, "references/forms.md")


class TestSkillRoutes(McpTestCase):
	def setUp(self):
		super().setUp()
		frappe.get_doc("User", self.user).add_roles("System Manager")
		self.app_skill = _app_skill(AppSkills(self))
		self.addCleanup(self.delete_skill)

	def delete_skill(self):
		frappe.delete_doc("Flow Skill", self.app_skill, ignore_permissions=True)
		frappe.db.commit()  # nosemgrep

	def get(self, path: str):
		response = self.request(method="GET", path=f"/api/v2/skill{path}", body="")
		self.assertEqual(response.status_code, 200, response.json)
		return response.json["data"]

	def test_rest_routes_list_and_get_a_skill_by_a_name_with_a_slash(self):
		listed = self.get("")["skills"]
		self.assertIn({"name": self.app_skill, "description": "When to use frappe/skills-api-todos."}, listed)
		self.assertEqual(self.get(f"/{self.app_skill}")["instructions"], f"Body of {self.app_skill}.")
		self.assertEqual(
			self.get(f"/{self.app_skill}?file=references/forms.md")["content"], "Use the ToDo form."
		)

	def tool(self, tool: str, **arguments):
		response = self.request(
			{
				"jsonrpc": "2.0",
				"id": 1,
				"method": "tools/call",
				"params": {"name": tool, "arguments": arguments},
			}
		)
		self.assertFalse(response.json["result"]["isError"], response.json["result"])
		return response.json["result"]["structuredContent"]

	def test_mcp_tools_match_the_rest_routes(self):
		self.assertEqual(self.tool("list_skills"), self.get(""))
		self.assertEqual(self.tool("get_skill", name=self.app_skill), self.get(f"/{self.app_skill}"))
		self.assertEqual(
			self.tool("get_skill", name=self.app_skill, file="references/forms.md"),
			self.get(f"/{self.app_skill}?file=references/forms.md"),
		)
		definitions = self.request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json["result"][
			"tools"
		]
		for definition in definitions:
			if definition["name"] in ("list_skills", "get_skill"):
				self.assertTrue(definition["annotations"]["readOnlyHint"])
