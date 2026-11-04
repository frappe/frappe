# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.desk.doctype.doctype_view.key_space import SURVIVOR_CANDIDATES, reserved_keys
from frappe.desk.doctype.view_type.view_type import applies_to, type_keys, validate_settings
from frappe.tests import IntegrationTestCase


class TestCardsViewType(IntegrationTestCase):
	def test_the_type_is_a_record_and_its_key_is_released(self):
		self.assertEqual(type_keys()["cards"], "Cards")
		self.assertNotIn("cards", SURVIVOR_CANDIDATES)
		self.assertIn("cards", reserved_keys())
		self.assertTrue(applies_to("Cards", "ToDo"))

	def test_validate_settings_accepts_fields_of_the_doctype_and_the_name(self):
		validate_settings("Cards", "Note", {})
		validate_settings("Cards", "Note", {"title_field": "title", "body_field": "content"})
		validate_settings("Cards", "Note", {"title_field": "name", "body_field": None})

	def test_validate_settings_refuses_a_field_the_doctype_lacks(self):
		for key in ("title_field", "body_field"):
			with self.assertRaisesRegex(frappe.ValidationError, "not a field of"):
				validate_settings("Cards", "Note", {key: "no_such_field"})
