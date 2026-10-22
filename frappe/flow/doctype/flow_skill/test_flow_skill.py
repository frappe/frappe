# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import os
import shutil
import tempfile
from typing import Any
from unittest.mock import patch

import frappe
from frappe.flow.doctype.flow_skill.flow_skill import (
	MAX_GLOBAL_SKILLS,
	skill_command,
	skill_file,
	sync_skills,
)
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


def _skill(**overrides: Any) -> dict:
	doc = {
		"doctype": "Flow Skill",
		"title": "Expense Approval",
		"description": "How to review and approve an expense claim.",
		"instructions": "Check the receipt against the claim, then approve it.",
	}
	doc.update(overrides)
	return doc


class TestFlowSkill(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_a_user_invocable_skill_needs_a_typable_command_of_its_own(self):
		self.assertEqual(skill_command("Expense Approval"), "expense-approval")
		self.assertEqual(skill_command("  Manager's Sign-off / Q&A  "), "manager-s-sign-off-q-a")
		taken = "Pre flight already answers to /skill:pre-flight"
		frappe.get_doc(_skill(title="Pre flight", user_invocable=1)).insert()
		skill = frappe.get_doc(_skill(user_invocable=1)).insert()
		with self.subTest("a rename"), self.assertRaisesRegex(frappe.ValidationError, taken):
			frappe.rename_doc("Flow Skill", skill.name, "Pre-flight")
		frappe.get_doc(_skill(title="Pre-flight")).insert()  # not user-invocable, so no clash
		with self.subTest("a new skill"), self.assertRaisesRegex(frappe.ValidationError, taken):
			frappe.get_doc(_skill(title="Pre_flight", user_invocable=1)).insert()
		frappe.get_doc(_skill(title="खर्च")).insert()
		with (
			self.subTest("no letter or digit"),
			self.assertRaisesRegex(frappe.ValidationError, "letter or digit"),
		):
			frappe.get_doc(_skill(title="मंज़ूरी", user_invocable=1)).insert()

		frappe.rename_doc("Flow Skill", skill.name, "Pre flight", merge=True, rebuild_search=False)
		self.assertFalse(frappe.db.exists("Flow Skill", skill.name))

	def test_a_description_past_the_prompt_budget_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "at most 1024 characters"):
			frappe.get_doc(_skill(description="x" * 1025)).insert()


class TestFlowSkillSystemGenerated(IntegrationTestCase):
	"""Desk edits can't break system-generated skills; the owning app (ignore_permissions) can."""

	def tearDown(self):
		frappe.db.rollback()

	def test_the_desk_cannot_change_a_system_generated_skill_but_may_disable_it(self):
		skill = frappe.get_doc(_skill(is_system_generated=1)).insert()
		for label, error, change in (
			("delete", "Cannot delete system-generated", lambda: frappe.delete_doc("Flow Skill", skill.name)),
			(
				"rename",
				"Cannot rename system-generated",
				lambda: frappe.rename_doc("Flow Skill", skill.name, "Renamed Skill"),
			),
		):
			with self.subTest(label), self.assertRaisesRegex(frappe.ValidationError, error):
				change()
		for field, value, error in (
			("is_system_generated", 0, "Cannot remove the system-generated flag"),
			("instructions", "Rewritten by the Desk.", "Cannot change Instructions"),
		):
			skill.reload()
			skill.set(field, value)
			with self.subTest(field=field), self.assertRaisesRegex(frappe.ValidationError, error):
				skill.save()

		skill.reload()
		skill.enabled = 0
		skill.save()
		self.assertEqual(frappe.db.get_value("Flow Skill", skill.name, "enabled"), 0)


class TestFlowSkillGlobalLimit(IntegrationTestCase):
	"""A global skill lands in every agent's prompt, so it is capped tighter than a bound one."""

	def tearDown(self):
		frappe.db.rollback()

	def test_only_enabled_global_skills_are_capped(self):
		bound = frappe.db.count("Flow Skill", {"is_global": 0})  # apps ship skills too
		for i in range(MAX_GLOBAL_SKILLS + 5):
			frappe.get_doc(_skill(title=f"Bound {i:03d}")).insert()
		self.assertEqual(frappe.db.count("Flow Skill", {"is_global": 0}), bound + MAX_GLOBAL_SKILLS + 5)

		with self.subTest("one global skill too many is refused"):
			for i in range(MAX_GLOBAL_SKILLS):
				frappe.get_doc(_skill(title=f"Global {i:03d}", is_global=1)).insert()
			with self.assertRaisesRegex(frappe.ValidationError, "At most 10 skills"):
				frappe.get_doc(_skill(title="One Too Many", is_global=1)).insert()
		doc = frappe.get_doc("Flow Skill", "Global 000")
		with self.subTest("an existing global skill can still be saved at the cap"):
			doc.description = "Reworded."
			doc.save()
			self.assertEqual(frappe.db.get_value("Flow Skill", "Global 000", "description"), "Reworded.")
		with self.subTest("disabling a global skill frees a slot"):
			doc.enabled = 0
			doc.save()
			frappe.get_doc(_skill(title="Takes The Slot", is_global=1)).insert()
			doc.reload()
			doc.enabled = 1
			with self.assertRaisesRegex(frappe.ValidationError, "At most 10 skills"):
				doc.save()


class AppSkills:
	"""Stands in for every installed app's skills folder, in a scratch directory."""

	def __init__(self, test: IntegrationTestCase):
		self.root = test.enterContext(tempfile.TemporaryDirectory())
		get_app_source_path = frappe.get_app_source_path

		def source_path(app: str, *joins: str) -> str:
			return os.path.join(self.root, app) if joins == ("skills",) else get_app_source_path(app, *joins)

		test.enterContext(patch("frappe.get_app_source_path", side_effect=source_path))

	def write(
		self,
		name: str,
		*,
		app: str = "frappe",
		description: str = "Close overdue ToDos.",
		body: str = "Close each one.",
		text: str | None = None,
	) -> str:
		"""Write the app's skills/<name>/SKILL.md and return its folder."""
		folder = os.path.join(self.root, app, name)
		os.makedirs(folder, exist_ok=True)
		with open(os.path.join(folder, "SKILL.md"), "w") as file:
			file.write(text or f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n")
		return folder


class TestAppSkills(IntegrationTestCase):
	def setUp(self):
		self.skills = AppSkills(self)

	def tearDown(self):
		frappe.db.rollback()

	def test_sync_mirrors_each_app_skill_and_keeps_site_choices(self):
		folder = self.skills.write("close-todos")
		self.assertEqual(sync_skills(), ["close-todos"])
		doc = frappe.get_doc("Flow Skill", "close-todos")
		with self.subTest("a new skill is locked to its app"):
			self.assertEqual(
				(doc.app, doc.description, doc.instructions, doc.is_system_generated),
				("frappe", "Close overdue ToDos.", "Close each one.", 1),
			)
			self.assertEqual((doc.enabled, doc.is_global, doc.user_invocable), (1, 0, 0))
		with self.subTest("an unchanged skill is not saved again"):
			sync_skills()
			self.assertEqual(frappe.db.get_value("Flow Skill", "close-todos", "modified"), doc.modified)

		frappe.db.set_value("Flow Skill", "close-todos", {"enabled": 0, "user_invocable": 1})
		self.skills.write("close-todos", description="Changed.", body="New body.")
		sync_skills()
		doc.reload()
		self.assertEqual(
			(doc.description, doc.instructions, doc.enabled, doc.user_invocable),
			("Changed.", "New body.", 0, 1),
		)

		model = frappe.get_doc(
			{
				"doctype": "Flow Model",
				"title": "App Skill Model",
				"model_id": "openai/gpt-4o-mini",
				"enabled": 1,
			}
		).insert()
		agent = frappe.get_doc(
			{
				"doctype": "Flow Agent",
				"title": "App Skill Agent",
				"model": model.name,
				"instructions": "Help with todos.",
				"skills": [{"skill": "close-todos"}],
			}
		).insert()
		shutil.rmtree(folder)

		self.assertEqual(sync_skills(), [])
		self.assertFalse(frappe.db.exists("Flow Skill", "close-todos"))
		self.assertEqual(frappe.get_all("Flow Agent Skill", {"parent": agent.name}, pluck="skill"), [])

	def test_sync_refuses_a_folder_it_cannot_mirror_safely(self):
		with self.subTest("a Desk skill of the same name is left alone"):
			frappe.get_doc(_skill(title="close-todos")).insert()
			self.skills.write("close-todos")
			with self.assertRaisesRegex(frappe.ValidationError, "not owned by an app"):
				sync_skills()
			self.assertEqual(frappe.db.get_value("Flow Skill", "close-todos", "is_system_generated"), 0)

		# each case below starts from empty skills folders
		with self.subTest("two apps cannot ship the same skill"):
			skills = AppSkills(self)
			skills.write("open-todos", app="frappe")
			skills.write("open-todos", app="other_app")
			with (
				patch("frappe.get_installed_apps", return_value=["frappe", "other_app"]),
				self.assertRaisesRegex(frappe.ValidationError, "shipped by both frappe and other_app"),
			):
				sync_skills()
			self.assertFalse(frappe.db.exists("Flow Skill", "open-todos"))

		with self.subTest("a skill named unlike its folder is refused with its path"):
			AppSkills(self).write("odd-todos", text="---\nname: other\ndescription: Wrong name.\n---\nBody\n")
			with self.assertRaisesRegex(frappe.ValidationError, "odd-todos/SKILL.md: skill name 'other'"):
				sync_skills()

		with self.subTest("a cut-off scan stops before deleting anything"):
			skills = AppSkills(self)
			skills.write("first-todos")
			sync_skills()
			skills.write("second-todos")
			with (
				patch("flow_harness.session.skills.MAX_SKILL_DIRECTORY_ENTRIES", 1),
				self.assertRaisesRegex(frappe.ValidationError, "has more than 1 entries"),
			):
				sync_skills()
			self.assertTrue(frappe.db.exists("Flow Skill", "first-todos"))

	def test_a_file_or_folder_of_an_app_skill_is_read_by_its_path(self):
		folder = self.skills.write("close-todos")
		other = self.skills.write("other-skill")
		os.makedirs(os.path.join(folder, "examples", "tabs", ".cache"))
		for path in (
			"examples/notes.md",
			"examples/tabs/block.json",
			"examples/tabs/.env",
			"examples/tabs/.cache/a.md",
		):
			with open(os.path.join(folder, path), "w") as file:
				file.write("Example.")
		os.symlink(os.path.join(other, "SKILL.md"), os.path.join(folder, "examples", "link.md"))
		sync_skills()

		for path, content in (
			("examples/", "examples/notes.md\nexamples/tabs/block.json"),
			("examples/tabs/block.json", "Example."),
		):
			with self.subTest(path=path):
				self.assertEqual(skill_file("close-todos", path), content)

	def test_only_small_text_files_inside_an_app_skill_folder_are_read(self):
		folder = self.skills.write("close-todos")
		other = self.skills.write("other-skill")
		with open(os.path.join(other, "notes.md"), "w") as file:
			file.write("Not this skill's.")
		with open(os.path.join(folder, ".env"), "w") as file:
			file.write("SECRET=1")
		with open(os.path.join(folder, "logo.png"), "wb") as file:
			file.write(b"\x89PNG\xff\xfe")
		os.symlink(os.path.join(other, "notes.md"), os.path.join(folder, "link.md"))
		sync_skills()
		# rows can be written by hand: a Desk skill, a name that is no folder, an app not installed
		for title, app in (("Expense Approval", None), ("..", "frappe"), ("os-skill", "os")):
			frappe.get_doc(_skill(title=title, app=app)).insert()

		for name, path, error in (
			("close-todos", "../other-skill/notes.md", "has no file"),
			("close-todos", os.path.join(other, "notes.md"), "has no file"),
			("close-todos", ".env", "has no file"),
			("close-todos", "link.md", "has no file"),
			("close-todos", "missing.md", "has no file"),
			("Expense Approval", "forms.md", "has no files"),
			("..", "hooks.py", "has no files"),
			("os-skill", "hooks.py", "has no files"),
			("close-todos", "logo.png", "not a text file"),
		):
			with self.subTest(name=name, path=path), self.assertRaisesRegex(frappe.ValidationError, error):
				skill_file(name, path)
		with (
			self.subTest("larger than the cap"),
			patch("frappe.flow.doctype.flow_skill.flow_skill.MAX_SKILL_FILE_BYTES", 4),
			self.assertRaisesRegex(frappe.ValidationError, "larger than"),
		):
			skill_file("close-todos", "SKILL.md")
