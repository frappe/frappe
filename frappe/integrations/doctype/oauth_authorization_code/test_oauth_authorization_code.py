# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase

# test_records = frappe.get_test_records('OAuth Authorization Code')


class TestOAuthAuthorizationCode(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestOauthAuthorizationCode(UnitTestCase):
	"""
	Unit tests for OauthAuthorizationCode.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestOAuthAuthorizationCode(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
