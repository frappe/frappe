# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestBlogSettings(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestBlogSettings(UnitTestCase):
	"""
	Unit tests for BlogSettings.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestBlogSettings(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
