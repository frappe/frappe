# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestWebPageView(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestWebPageView(UnitTestCase):
	"""
	Unit tests for WebPageView.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestWebPageView(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
