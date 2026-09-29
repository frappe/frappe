from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.telemetry import capture_doc


class TestCaptureDoc(IntegrationTestCase):
	def setUp(self):
		for target, value in (("site_age", 1), ("capture", None)):
			patcher = patch(f"frappe.utils.telemetry.{target}", return_value=value)
			self.addCleanup(patcher.stop)
			setattr(self, target, patcher.start())

	def assertCapturedApp(self, doctype, app):
		capture_doc(frappe.new_doc(doctype), "Insert")
		self.assertEqual(self.capture.call_args.args, ("document_created", app))

	def test_frappe_doctype(self):
		self.assertCapturedApp("User", "frappe")

	def test_app_doctype(self):
		with patch.dict(frappe.local.module_app, {"core": "wiki"}):
			self.assertCapturedApp("User", "wiki")

	def test_unmapped_module(self):
		with patch.dict(frappe.local.module_app):
			del frappe.local.module_app["core"]
			self.assertCapturedApp("User", "frappe")
