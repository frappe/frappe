# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.database.duckdb.database import get_latest_sync
from frappe.tests import IntegrationTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestDuckDBSync(IntegrationTestCase):
	"""
	Integration tests for DuckDBSync.
	Use this class for testing interactions between multiple components.
	"""

	def test_latest_sync_is_the_newest_complete_one_opened_read_only(self):
		complete = frappe.get_doc(doctype="DuckDB Sync", doc_type="Role").insert()
		complete.db_set("docstatus", 1)
		pending = frappe.get_doc(doctype="DuckDB Sync", doc_type="Role").insert()
		pending.db_set("docstatus", 1)
		frappe.get_doc(doctype="DuckDB Sync", doc_type="Role").insert()

		with patch("frappe.database.duckdb.database.get_duckdb", side_effect=lambda *args: args):
			self.assertIsNone(get_latest_sync("Role"))
			for item in complete.db_tables:
				item.db_set("synced", 1)
			self.assertEqual(get_latest_sync("Role"), (True, complete.filename))
