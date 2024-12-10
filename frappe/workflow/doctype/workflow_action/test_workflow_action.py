# Copyright (c) 2021, Frappe Technologies and Contributors
# License: MIT. See LICENSE

# import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestWorkflowAction(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestWorkflowAction(UnitTestCase):
	"""
	Unit tests for WorkflowAction.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestWorkflowAction(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
