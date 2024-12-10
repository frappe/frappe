# Copyright (c) 2024, Frappe Technologies and Contributors
# See license.txt

# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestPermissionInspector(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestPermissionInspector(UnitTestCase):
	"""
	Unit tests for PermissionInspector.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestPermissionInspector(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
