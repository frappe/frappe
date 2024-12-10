# Copyright (c) 2021, Frappe Technologies and Contributors
# See license.txt

# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestPrintFormatFieldTemplate(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestPrintFormatFieldTemplate(UnitTestCase):
	"""
	Unit tests for PrintFormatFieldTemplate.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestPrintFormatFieldTemplate(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
