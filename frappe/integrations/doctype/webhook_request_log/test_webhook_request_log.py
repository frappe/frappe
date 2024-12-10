# Copyright (c) 2021, Frappe Technologies and Contributors
# License: MIT. See LICENSE

# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestWebhookRequestLog(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestWebhookRequestLog(UnitTestCase):
	"""
	Unit tests for WebhookRequestLog.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestWebhookRequestLog(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
