# Copyright (c) 2023, Frappe Technologies and Contributors
# See license.txt

# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestGoogleContacts(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestGoogleContacts(UnitTestCase):
	"""
	Unit tests for GoogleContacts.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestGoogleContacts(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
