# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from typing import Any

import frappe
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

	def test_a_skill_is_named_after_its_title_and_starts_enabled(self):
		skill = frappe.get_doc(_skill()).insert()
		self.assertEqual(skill.name, "Expense Approval")
		self.assertEqual(skill.enabled, 1)

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
