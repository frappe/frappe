# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase

# test_records = frappe.get_test_records('Kanban Board')


class TestKanbanBoard(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestKanbanBoard(UnitTestCase):
	"""
	Unit tests for KanbanBoard.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestKanbanBoard(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	pass
