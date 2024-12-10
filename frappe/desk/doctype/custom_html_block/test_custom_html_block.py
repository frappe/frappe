# Copyright (c) 2023, Frappe Technologies and Contributors
# See license.txt

# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestCustomHTMLBlock(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestCustomHtmlBlock(UnitTestCase):
	"""
	Unit tests for CustomHtmlBlock.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestCustomHTMLBlock(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
