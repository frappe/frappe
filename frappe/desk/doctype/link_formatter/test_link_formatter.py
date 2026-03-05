# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestLinkFormatter(IntegrationTestCase):
	"""
	Integration tests for LinkFormatter.
	Use this class for testing interactions between multiple components.
	"""


def test_link_formatter_data_created(self):
	"""Ensure migration created the required link formatter configuration"""

	link_formatter = frappe.get_doc("Link Formatter", "Link Formatter")
	self.assertTrue(
		any(
			row.doctype_name == "User"
			and row.link_fieldname == "user"
			and row.display_fieldname == "user_full_name"
			for row in link_formatter.link_field_display
		)
	)
