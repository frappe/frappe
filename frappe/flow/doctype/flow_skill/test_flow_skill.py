# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import os
import shutil
import tempfile
from typing import Any
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from flow.flow.doctype.flow_skill.flow_skill import MAX_GLOBAL_SKILLS, skill_command, sync_skills

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

	def test_a_skill_is_named_after_its_title_and_starts_enabled(self):
		skill = frappe.get_doc(_skill()).insert()
		self.assertEqual(skill.name, "Expense Approval")
		self.assertEqual(skill.enabled, 1)

	def test_a_skill_is_not_user_invocable_until_flagged(self):
		skill = frappe.get_doc(_skill()).insert()
		self.assertEqual(skill.user_invocable, 0)

	def test_the_command_is_the_title_in_lowercase_with_hyphens(self):
		self.assertEqual(skill_command("Expense Approval"), "expense-approval")
		self.assertEqual(skill_command("  Manager's Sign-off / Q&A  "), "manager-s-sign-off-q-a")

	def test_two_user_invocable_skills_cannot_share_a_command(self):
		frappe.get_doc(_skill(title="Pre flight", user_invocable=1)).insert()
		frappe.get_doc(_skill(title="Pre-flight")).insert()
		with self.assertRaisesRegex(
			frappe.ValidationError, "Pre flight already answers to /skill:pre-flight"
		):
			frappe.get_doc(_skill(title="Pre_flight", user_invocable=1)).insert()

	def test_a_user_invocable_skill_needs_a_typable_title(self):
		frappe.get_doc(_skill(title="खर्च")).insert()
		with self.assertRaisesRegex(frappe.ValidationError, "letter or digit"):
			frappe.get_doc(_skill(title="मंज़ूरी", user_invocable=1)).insert()

	def test_two_skills_cannot_share_a_title(self):
		frappe.get_doc(_skill()).insert()
		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc(_skill(instructions="Something else.")).insert()

	def test_a_description_past_the_prompt_budget_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "at most 1024 characters"):
			frappe.get_doc(_skill(description="x" * 1025)).insert()

	def test_description_and_instructions_are_required(self):
		for field in ("description", "instructions"):
			with self.subTest(field=field), self.assertRaises(frappe.MandatoryError):
				frappe.get_doc(_skill(**{field: None})).insert()


class TestFlowSkillSystemGenerated(IntegrationTestCase):
	"""Desk edits can't break system-generated skills; the owning app (ignore_permissions) can."""

	def tearDown(self):
		frappe.db.rollback()

	def _skill(self):
		return frappe.get_doc(_skill(is_system_generated=1)).insert()

	def test_cannot_delete_via_desk(self):
		skill = self._skill()
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot delete system-generated"):
			frappe.delete_doc("Flow Skill", skill.name)

	def test_owning_app_can_delete(self):
		skill = self._skill()
		frappe.delete_doc("Flow Skill", skill.name, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Flow Skill", skill.name))

	def test_cannot_rename(self):
		skill = self._skill()
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot rename system-generated"):
			frappe.rename_doc("Flow Skill", skill.name, "Renamed Skill")

	def test_cannot_unset_flag(self):
		skill = self._skill()
		skill.is_system_generated = 0
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot remove the system-generated flag"):
			skill.save()

	def test_instructions_are_locked_but_enabled_stays_editable(self):
		skill = self._skill()
		skill.instructions = "Rewritten by the Desk."
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot change Instructions"):
			skill.save()
		skill.reload()
		skill.enabled = 0
		skill.save()
		self.assertEqual(frappe.db.get_value("Flow Skill", skill.name, "enabled"), 0)

	def test_owning_app_can_change_instructions(self):
		skill = self._skill()
		skill.instructions = "Rewritten by the app."
		skill.save(ignore_permissions=True)
		self.assertEqual(
			frappe.db.get_value("Flow Skill", skill.name, "instructions"), "Rewritten by the app."
		)


class TestFlowSkillGlobalLimit(IntegrationTestCase):
	"""A global skill lands in every agent's prompt, so it is capped tighter than a bound one."""

	def tearDown(self):
		frappe.db.rollback()

	def _fill_the_cap(self):
		for i in range(MAX_GLOBAL_SKILLS):
			frappe.get_doc(_skill(title=f"Global {i:03d}", is_global=1)).insert()

	def test_one_global_skill_too_many_is_refused(self):
		self._fill_the_cap()
		with self.assertRaisesRegex(frappe.ValidationError, "At most 10 skills"):
			frappe.get_doc(_skill(title="One Too Many", is_global=1)).insert()

	def test_an_existing_global_skill_can_still_be_saved_at_the_cap(self):
		self._fill_the_cap()
		doc = frappe.get_doc("Flow Skill", "Global 000")
		doc.description = "Reworded."
		doc.save()
		self.assertEqual(frappe.db.get_value("Flow Skill", "Global 000", "description"), "Reworded.")

	def test_disabling_a_global_skill_frees_a_slot(self):
		self._fill_the_cap()
		doc = frappe.get_doc("Flow Skill", "Global 000")
		doc.enabled = 0
		doc.save()
		frappe.get_doc(_skill(title="Takes The Slot", is_global=1)).insert()
		doc.reload()
		doc.enabled = 1
		with self.assertRaisesRegex(frappe.ValidationError, "At most 10 skills"):
			doc.save()

	def test_a_bound_only_skill_is_not_capped(self):
		for i in range(MAX_GLOBAL_SKILLS + 5):
			frappe.get_doc(_skill(title=f"Bound {i:03d}")).insert()
		self.assertEqual(frappe.db.count("Flow Skill", {"is_global": 0}), MAX_GLOBAL_SKILLS + 5)


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
		app: str = "flow",
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

	def test_an_app_skill_becomes_a_locked_flow_skill(self):
		self.skills.write("close-todos")

		self.assertEqual(sync_skills(), ["close-todos"])

		doc = frappe.get_doc("Flow Skill", "close-todos")
		self.assertEqual(
			(doc.description, doc.instructions, doc.is_system_generated),
			("Close overdue ToDos.", "Close each one.", 1),
		)
		self.assertEqual((doc.enabled, doc.is_global, doc.user_invocable), (1, 0, 0))

	def test_a_resync_follows_the_file_but_keeps_site_choices(self):
		self.skills.write("close-todos")
		sync_skills()
		frappe.db.set_value("Flow Skill", "close-todos", {"enabled": 0, "user_invocable": 1})
		self.skills.write("close-todos", description="Changed.", body="New body.")

		sync_skills()

		doc = frappe.get_doc("Flow Skill", "close-todos")
		self.assertEqual(
			(doc.description, doc.instructions, doc.enabled, doc.user_invocable),
			("Changed.", "New body.", 0, 1),
		)

	def test_an_unchanged_skill_is_not_saved_again(self):
		self.skills.write("close-todos")
		sync_skills()
		modified = frappe.db.get_value("Flow Skill", "close-todos", "modified")

		sync_skills()

		self.assertEqual(frappe.db.get_value("Flow Skill", "close-todos", "modified"), modified)

	def test_a_skill_gone_from_disk_is_deleted_and_unlinked(self):
		folder = self.skills.write("close-todos")
		sync_skills()
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

	def test_a_desk_skill_with_the_same_name_is_left_alone(self):
		frappe.get_doc(_skill(title="close-todos")).insert()
		self.skills.write("close-todos")

		with self.assertRaisesRegex(frappe.ValidationError, "not owned by an app"):
			sync_skills()

		self.assertEqual(frappe.db.get_value("Flow Skill", "close-todos", "is_system_generated"), 0)

	def test_two_apps_cannot_ship_the_same_skill(self):
		self.skills.write("close-todos", app="frappe")
		self.skills.write("close-todos", app="flow")

		with self.assertRaisesRegex(frappe.ValidationError, "shipped by both frappe and flow"):
			sync_skills()

		self.assertFalse(frappe.db.exists("Flow Skill", "close-todos"))

	def test_a_skill_named_unlike_its_folder_is_refused_with_its_path(self):
		self.skills.write("close-todos", text="---\nname: other\ndescription: Wrong name.\n---\nBody\n")

		with self.assertRaisesRegex(frappe.ValidationError, "close-todos/SKILL.md: skill name 'other'"):
			sync_skills()

	def test_a_cut_off_scan_stops_before_deleting_anything(self):
		self.skills.write("close-todos")
		sync_skills()
		self.skills.write("open-todos")

		with (
			patch("flow_harness.session.skills.MAX_SKILL_DIRECTORY_ENTRIES", 1),
			self.assertRaisesRegex(frappe.ValidationError, "has more than 1 entries"),
		):
			sync_skills()

		self.assertTrue(frappe.db.exists("Flow Skill", "close-todos"))
