# Copyright (c) 2021, Frappe Technologies and Contributors
# See license.txt

# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestDocumentShareKey(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestDocumentShareKey(UnitTestCase):
	"""
	Unit tests for DocumentShareKey.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestDocumentShareKey(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
