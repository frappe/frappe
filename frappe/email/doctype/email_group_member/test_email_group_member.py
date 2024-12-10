# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase

# test_records = frappe.get_test_records('Email Group Member')


class TestEmailGroupMember(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestEmailGroupMember(UnitTestCase):
	"""
	Unit tests for EmailGroupMember.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestEmailGroupMember(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
