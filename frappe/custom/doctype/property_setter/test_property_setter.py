# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase

# test_records = frappe.get_test_records('Property Setter')


class TestPropertySetter(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestPropertySetter(UnitTestCase):
	"""
	Unit tests for PropertySetter.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestPropertySetter(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
