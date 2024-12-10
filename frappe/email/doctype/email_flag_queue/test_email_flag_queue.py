# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase

# test_records = frappe.get_test_records('Email Flag Queue')


class TestEmailFlagQueue(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestEmailFlagQueue(UnitTestCase):
	"""
	Unit tests for EmailFlagQueue.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestEmailFlagQueue(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
