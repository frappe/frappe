# Copyright (c) 2023, Frappe Technologies and Contributors
# See license.txt

import frappe
import frappe.recorder
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request


class TestRecorder(FrappeTestCase):
	def setUp(self):
		self.start_recoder()

	def start_recoder(self):
		frappe.recorder.stop()
		frappe.recorder.delete()
		set_request()
		frappe.recorder.start()
		frappe.recorder.record()

	def stop_recorder(self):
		frappe.recorder.dump()

	def test_recorder_list(self):
		frappe.get_all("User")  # trigger one query
		self.stop_recorder()

		requests = frappe.get_all("Recorder")
		self.assertGreaterEqual(len(requests), 1)
		request = frappe.get_doc("Recorder", requests[0].name)
		self.assertGreaterEqual(len(request.sql_queries), 1)
