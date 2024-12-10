# Copyright (c) 2021, Frappe Technologies and Contributors
# License: MIT. See LICENSE
# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestUserGroupMember(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestUserGroupMember(UnitTestCase):
	"""
	Unit tests for UserGroupMember.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestUserGroupMember(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
