# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase


class TestLetterHead(FrappeTestCase):
	def test_auto_image(self):
		letter_head = frappe.get_doc(
			dict(doctype="Letter Head", letter_head_name="Test", source="Image", image="/public/test.png")
		).insert()

		# test if image is automatically set
		self.assertTrue(letter_head.image in letter_head.content)
