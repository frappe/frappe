# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.api.file import get_attached_images, move_file
from frappe.tests import IntegrationTestCase


class TestFileAPI(IntegrationTestCase):
	def test_get_attached_images_accepts_native_list(self):
		todo = frappe.get_doc(doctype="ToDo", description="file api").insert()
		# names as a native list instead of a JSON string (frappe.parse_json passthrough)
		out = get_attached_images("ToDo", [todo.name])
		self.assertIsInstance(out, dict)
		todo.delete()

	def test_move_file_accepts_native_list(self):
		# file_list as a native list (frappe.parse_json passthrough); empty list is a no-op move
		move_file(file_list=[], new_parent="Home", old_parent="Home")
