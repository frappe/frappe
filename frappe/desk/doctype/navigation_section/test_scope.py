# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from frappe.desk.doctype.navigation_section.scope import DEFAULT_APP, Scope, scope_of
from frappe.tests import UnitTestCase


class TestScope(UnitTestCase):
	"""The read filters and the identity, without a site."""

	def test_a_doctype_scope_matches_that_doctype_alone(self):
		self.assertEqual(
			Scope("crm", "CRM Deal").filters(),
			{"app": "crm", "reference_doctype": "CRM Deal"},
		)

	def test_an_app_level_scope_matches_the_sections_with_no_doctype(self):
		"""An optional Link reads back as "" or None depending on the path it took."""
		self.assertEqual(
			Scope("crm").filters(),
			{"app": "crm", "reference_doctype": ("in", ("", None))},
		)

	def test_an_empty_reference_doctype_is_app_level(self):
		self.assertTrue(Scope("crm").is_app_level)
		self.assertFalse(Scope("crm", "CRM Deal").is_app_level)

	def test_the_fields_a_section_is_created_with_carry_the_doctype_as_stored(self):
		self.assertEqual(Scope("crm").as_fields(), {"app": "crm", "reference_doctype": ""})

	def test_two_apps_are_different_scopes_for_the_same_doctype(self):
		self.assertNotEqual(Scope("crm", "Note"), Scope("helpdesk", "Note"))

	def test_the_app_defaults_to_the_framework(self):
		self.assertEqual(Scope().app, DEFAULT_APP)

	def test_a_section_reads_back_as_the_scope_it_was_created_in(self):
		section = {"app": "crm", "reference_doctype": "CRM Deal"}

		self.assertEqual(scope_of(section), Scope("crm", "CRM Deal"))

	def test_a_section_with_no_doctype_reads_back_app_level(self):
		self.assertEqual(scope_of({"app": "crm", "reference_doctype": None}), Scope("crm"))

	def test_a_section_with_no_app_does_not_read_back_as_the_framework(self):
		"""`app` is required, so a section without one is a broken row rather than a
		framework one — and no read filters for it, so it must fail every comparison."""
		self.assertNotEqual(scope_of({"app": ""}), Scope(DEFAULT_APP))

	def test_a_blank_app_reads_back_the_same_however_it_is_stored(self):
		self.assertEqual(scope_of({"app": None}), scope_of({"app": ""}))
