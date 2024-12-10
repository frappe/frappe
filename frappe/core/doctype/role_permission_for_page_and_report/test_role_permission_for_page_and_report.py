# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestRolePermissionforPageandReport(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestRolePermissionForPageAndReport(UnitTestCase):
	"""
	Unit tests for RolePermissionForPageAndReport.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestRolePermissionforPageandReport(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
