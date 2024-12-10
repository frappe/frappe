# Copyright (c) 2022, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.core.doctype.rq_worker.rq_worker import RQWorker
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestRQWorker(FrappeTestCase):
	def test_get_worker_list(self):
		workers = RQWorker.get_list({})
=======
from frappe.tests import IntegrationTestCase, UnitTestCase


class UnitTestRqWorker(UnitTestCase):
	"""
	Unit tests for RqWorker.
	Use this class for testing individual functions and methods.
	"""

	pass


class TestRQWorker(IntegrationTestCase):
	def test_get_worker_list(self):
		workers = RQWorker.get_list()
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		self.assertGreaterEqual(len(workers), 1)
		self.assertTrue(any("short" in w.queue_type for w in workers))

	def test_worker_serialization(self):
<<<<<<< HEAD
		workers = RQWorker.get_list({})
=======
		workers = RQWorker.get_list()
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		frappe.get_doc("RQ Worker", workers[0].name)
