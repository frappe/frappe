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
		name = frappe.get_doc(_skill(is_system_generated=1)).insert(ignore_permissions=True).name
		skill = frappe.get_doc("Flow Skill", name)
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

	def test_only_an_app_creates_a_skill_named_after_it(self):
		for overrides in ({"app": "frappe"}, {"is_system_generated": 1}):
			with (
				self.subTest(overrides),
				self.assertRaisesRegex(frappe.ValidationError, "Only an app can create"),
			):
				frappe.get_doc(_skill(**overrides)).insert()
		with self.subTest("a new name"), self.assertRaisesRegex(frappe.ValidationError, "cannot contain /"):
			frappe.get_doc(_skill(title="frappe/expense-approval")).insert()
		skill = frappe.get_doc(_skill()).insert()
		with self.subTest("a rename"), self.assertRaisesRegex(frappe.ValidationError, "cannot contain /"):
			frappe.rename_doc("Flow Skill", skill.name, "frappe/expense-approval")

		frappe.rename_doc("Flow Skill", skill.name, "Expense Review", rebuild_search=False)
		self.assertEqual(frappe.db.get_value("Flow Skill", "Expense Review", "title"), "Expense Review")


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
		self.started = frappe.utils.now()

	def tearDown(self):
		frappe.db.rollback()

	def skipped(self, title: str) -> list[str]:
		"""The reasons this test's syncs logged under `title`. Error Logs live in the log database,
		which a rollback does not undo."""
		return frappe.get_all("Error Log", {"method": title, "creation": [">=", self.started]}, pluck="error")

	def test_sync_mirrors_each_app_skill_and_keeps_site_choices(self):
		folder = self.skills.write("close-todos")
		self.assertEqual(sync_skills(), ["frappe/close-todos"])
		doc = frappe.get_doc("Flow Skill", "frappe/close-todos")
		with self.subTest("a new skill is locked to its app"):
			self.assertEqual(
				(doc.title, doc.app, doc.description, doc.instructions, doc.is_system_generated),
				("frappe/close-todos", "frappe", "Close overdue ToDos.", "Close each one.", 1),
			)
			self.assertEqual((doc.enabled, doc.is_global, doc.user_invocable), (1, 0, 0))
		with self.subTest("an unchanged skill is not saved again"):
			sync_skills()
			self.assertEqual(
				frappe.db.get_value("Flow Skill", "frappe/close-todos", "modified"), doc.modified
			)

		frappe.db.set_value("Flow Skill", "frappe/close-todos", {"enabled": 0, "user_invocable": 1})
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
				"skills": [{"skill": "frappe/close-todos"}],
			}
		).insert()
		shutil.rmtree(folder)

		self.assertEqual(sync_skills(), [])
		self.assertFalse(frappe.db.exists("Flow Skill", "frappe/close-todos"))
		self.assertEqual(frappe.get_all("Flow Agent Skill", {"parent": agent.name}, pluck="skill"), [])

	def test_a_skill_is_named_after_its_app_so_no_other_takes_its_name(self):
		frappe.get_doc(_skill(title="close-todos")).insert()
		self.skills.write("close-todos")
		self.skills.write("close-todos", app="other_app", description="Theirs.")
		with patch("frappe.get_installed_apps", return_value=["frappe", "other_app"]):
			self.assertEqual(sync_skills(), ["frappe/close-todos", "other_app/close-todos"])

		self.assertEqual(
			frappe.get_all(
				"Flow Skill", {"name": ["like", "%close-todos"]}, ["name", "description"], order_by="name"
			),
			[
				{"name": "close-todos", "description": "How to review and approve an expense claim."},
				{"name": "frappe/close-todos", "description": "Close overdue ToDos."},
				{"name": "other_app/close-todos", "description": "Theirs."},
			],
		)

	def test_sync_skips_a_folder_it_cannot_mirror_safely(self):
		# each case starts from empty skills folders
		with self.subTest("a skill named unlike its folder keeps its row as it was"):
			skills = AppSkills(self)
			skills.write("odd-todos")
			sync_skills()
			skills.write("odd-todos", text="---\nname: other\ndescription: Wrong name.\n---\nBody\n")
			skills.write("open-todos")
			self.assertEqual(sync_skills(), ["frappe/open-todos"])
			self.assertEqual(
				frappe.db.get_value("Flow Skill", "frappe/odd-todos", "description"), "Close overdue ToDos."
			)
			[reason] = self.skipped("Flow Skill frappe/odd-todos skipped")
			self.assertIn("odd-todos/SKILL.md: skill name 'other'", reason)

		with self.subTest("a cut-off scan skips the app before deleting anything"):
			skills = AppSkills(self)
			skills.write("first-todos")
			sync_skills()
			skills.write("second-todos")
			with patch("flow_harness.session.skills.MAX_SKILL_DIRECTORY_ENTRIES", 1):
				self.assertEqual(sync_skills(), [])
			self.assertTrue(frappe.db.exists("Flow Skill", "frappe/first-todos"))
			self.assertFalse(frappe.db.exists("Flow Skill", "frappe/second-todos"))
			[reason] = self.skipped("Flow Skills of frappe skipped")
			self.assertIn("has more than 1 entries", reason)

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
				self.assertEqual(skill_file("frappe/close-todos", path), content)

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
			frappe.get_doc(_skill(title=title, app=app)).insert(ignore_permissions=True)

		for name, path, error in (
			("frappe/close-todos", "../other-skill/notes.md", "has no file"),
			("frappe/close-todos", os.path.join(other, "notes.md"), "has no file"),
			("frappe/close-todos", ".env", "has no file"),
			("frappe/close-todos", "link.md", "has no file"),
			("frappe/close-todos", "missing.md", "has no file"),
			("Expense Approval", "forms.md", "has no files"),
			("frappe/..", "hooks.py", "has no files"),
			("os/os-skill", "hooks.py", "has no files"),
			("frappe/close-todos", "logo.png", "not a text file"),
		):
			with self.subTest(name=name, path=path), self.assertRaisesRegex(frappe.ValidationError, error):
				skill_file(name, path)
		with (
			self.subTest("larger than the cap"),
			patch("frappe.flow.doctype.flow_skill.flow_skill.MAX_SKILL_FILE_BYTES", 4),
			self.assertRaisesRegex(frappe.ValidationError, "larger than"),
		):
			skill_file("frappe/close-todos", "SKILL.md")
