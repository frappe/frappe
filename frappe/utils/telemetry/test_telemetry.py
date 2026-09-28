from unittest.mock import patch

import frappe
from frappe.core.doctype.module_def.test_module_def import custom_module, doctype_in, module_declared_by
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
		with custom_module("Test Telemetry Module") as module:
			doctype = doctype_in(module, "Test Telemetry App DocType").name
			with module_declared_by(module, "wiki"):
				self.assertCapturedApp(doctype, "wiki")

	def test_custom_doctype(self):
		with custom_module("Test Telemetry Module") as module:
			self.assertCapturedApp(doctype_in(module, "Test Telemetry Custom DocType").name, "frappe")
