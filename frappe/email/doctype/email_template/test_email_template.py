# Copyright (c) 2018, Frappe Technologies and Contributors
# License: MIT. See LICENSE
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestEmailTemplate(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestEmailTemplate(UnitTestCase):
	"""
	Unit tests for EmailTemplate.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestEmailTemplate(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
