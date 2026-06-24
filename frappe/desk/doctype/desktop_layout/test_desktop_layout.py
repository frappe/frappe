# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestDesktopLayout(IntegrationTestCase):
	"""
	Integration tests for DesktopLayout.
	Use this class for testing interactions between multiple components.
	"""

	def test_save_layout_accepts_native_payloads(self):
		from frappe.desk.doctype.desktop_layout.desktop_layout import save_layout

		# layout as a native list instead of a JSON string (frappe.parse_json passthrough)
		save_layout(user=frappe.session.user, layout=[{"name": "ToDo", "label": "ToDo"}])
		self.assertTrue(frappe.db.exists("Desktop Layout", frappe.session.user))
		frappe.delete_doc("Desktop Layout", frappe.session.user, force=True)
