# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestLetterHead(FrappeTestCase):
	def test_auto_image(self):
		letter_head = frappe.get_doc(
			dict(doctype="Letter Head", letter_head_name="Test", source="Image", image="/public/test.png")
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestLetterHead(UnitTestCase):
	"""
	Unit tests for LetterHead.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestLetterHead(IntegrationTestCase):
	def test_auto_image(self):
		letter_head = frappe.get_doc(
			doctype="Letter Head", letter_head_name="Test", source="Image", image="/public/test.png"
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		).insert()

		# test if image is automatically set
		self.assertTrue(letter_head.image in letter_head.content)
