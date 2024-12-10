# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestNumberCard(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestNumberCard(UnitTestCase):
	"""
	Unit tests for NumberCard.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestNumberCard(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
