# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
import unittest
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase


class TestPage(IntegrationTestCase):
	def test_naming(self):
		self.assertRaises(
			frappe.NameError,
			frappe.get_doc(doctype="Page", page_name="DocType", module="Core").insert,
		)

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def test_trashing(self):
		page = frappe.new_doc("Page", page_name=frappe.generate_hash(), module="Core").insert()

		page.delete()
		frappe.db.commit()

		module_path = frappe.get_module_path(page.module)
		dir_path = os.path.join(module_path, "page", frappe.scrub(page.name))

		self.assertFalse(os.path.exists(dir_path))
