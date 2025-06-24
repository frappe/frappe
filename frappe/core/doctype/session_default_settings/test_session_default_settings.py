# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.session_default_settings.session_default_settings import (
	clear_session_defaults,
	set_session_default_values,
)
from frappe.tests import IntegrationTestCase


class TestSessionDefaultSettings(IntegrationTestCase):
	def test_set_session_default_settings(self):
		frappe.set_user("Administrator")
		settings = frappe.get_single("Session Default Settings")
		settings.session_defaults = []
		settings.append("session_defaults", {"ref_doctype": "Role"})
		settings.save()

		set_session_default_values({"role": "Website Manager"})

		todo = frappe.get_doc(
			doctype="ToDo", description="test session defaults set", assigned_by="Administrator"
		).insert()
		self.assertEqual(todo.role, "Website Manager")

	def test_clear_session_defaults(self):
		clear_session_defaults()
		todo = frappe.get_doc(
			doctype="ToDo", description="test session defaults cleared", assigned_by="Administrator"
		).insert()
		self.assertNotEqual(todo.role, "Website Manager")
