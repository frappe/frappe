# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
import re
import unittest
from typing import TYPE_CHECKING

import frappe
from frappe.tests import IntegrationTestCase

if TYPE_CHECKING:
	from frappe.printing.doctype.print_format.print_format import PrintFormat


class TestPrintFormat(IntegrationTestCase):
	def test_print_user(self, style=None):
		print_html = frappe.get_print("User", "Administrator", style=style)
		self.assertTrue("<label>First Name: </label>" in print_html)
		self.assertTrue(re.findall(r'<div class="col-xs-[^"]*">[\s]*administrator[\s]*</div>', print_html))
		return print_html

	def test_print_user_standard(self):
		print_html = self.test_print_user("Standard")
		self.assertTrue(re.findall(r"\.print-format {[\s]*font-size: 9pt;", print_html))
		self.assertFalse(re.findall(r"th {[\s]*background-color: #eee;[\s]*}", print_html))
		self.assertFalse("font-family: serif;" in print_html)

	def test_print_user_modern(self):
		print_html = self.test_print_user("Modern")
		self.assertTrue("/* modern format: for-test */" in print_html)

	def test_print_user_classic(self):
		print_html = self.test_print_user("Classic")
		self.assertTrue("/* classic format: for-test */" in print_html)

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	def test_export_doc(self):
		doc: PrintFormat = frappe.get_doc("Print Format", self.globalTestRecords["Print Format"][0]["name"])

		# this is only to make export_doc happy
		doc.standard = "Yes"
		_before = frappe.conf.developer_mode
		frappe.conf.developer_mode = True
		export_path = doc.export_doc()
		frappe.conf.developer_mode = _before

		exported_doc_path = f"{export_path}.json"
		doc.reload()
		doc_dict = doc.as_dict(no_nulls=True, convert_dates_to_str=True)

		self.assertTrue(os.path.exists(exported_doc_path))
		self.assertFalse(os.path.exists(os.path.join(os.path.dirname(exported_doc_path), "__init__.py")))

		with open(exported_doc_path) as f:
			exported_doc = frappe.parse_json(f.read())

		for key, value in exported_doc.items():
			if key in doc_dict:
				with self.subTest(key=key):
					self.assertEqual(value, doc_dict[key])

		self.addCleanup(os.remove, exported_doc_path)


class TestPrintFormatBuilderElements(IntegrationTestCase):
	"""Image and Barcode layout elements of the beta print format builder."""

	FORMAT_NAME = "_Test Builder Elements"

	def make_format(self, fields):
		frappe.delete_doc("Print Format", self.FORMAT_NAME, force=True, ignore_missing=True)
		format_data = {
			"sections": [{"label": "", "columns": [{"label": "", "fields": fields}]}],
			"header": {"columns": []},
			"footer": {"columns": []},
		}
		pf = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": self.FORMAT_NAME,
				"doc_type": "User",
				"standard": "No",
				"print_format_builder_beta": 1,
				"format_data": frappe.as_json(format_data),
			}
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", self.FORMAT_NAME, force=True)
		return pf

	def get_rendered_html(self):
		from frappe.utils.print_format_generator import get_html

		return get_html("User", "Administrator", self.FORMAT_NAME)

	def test_image_element(self):
		self.make_format(
			[
				{
					"label": "Logo",
					"fieldname": "image_test",
					"fieldtype": "Image",
					"custom": 1,
					"image_url": "/assets/frappe/images/frappe-framework-logo.svg",
					"width": "40mm",
					"align": "center",
				}
			]
		)
		html = self.get_rendered_html()
		self.assertIn('src="/assets/frappe/images/frappe-framework-logo.svg"', html)
		self.assertIn("width: 40mm", html)
		self.assertIn("field-align-center", html)

	def test_image_element_without_source_renders_nothing(self):
		self.make_format(
			[{"label": "", "fieldname": "image_test", "fieldtype": "Image", "custom": 1, "image_url": ""}]
		)
		html = self.get_rendered_html()
		self.assertNotIn("print-image", html)

	def test_barcode_element_static_value(self):
		self.make_format(
			[
				{
					"label": "",
					"fieldname": "barcode_test",
					"fieldtype": "Barcode",
					"custom": 1,
					"barcode_field": "",
					"barcode_value": "TEST-123",
					"barcode_format": "CODE39",
					"show_text": False,
					"width": "50mm",
				}
			]
		)
		html = self.get_rendered_html()
		self.assertIn('data-barcode-value="TEST-123"', html)
		self.assertIn('"format": "CODE39"', html)
		self.assertIn('"displayValue": false', html)
		self.assertIn("width: 50mm", html)
		# the client-side renderer must be shipped with the document
		self.assertIn("print.bundle", html)
		self.assertIn("render_barcode", html)

	def test_barcode_element_field_value(self):
		self.make_format(
			[
				{
					"label": "",
					"fieldname": "barcode_test",
					"fieldtype": "Barcode",
					"custom": 1,
					"barcode_field": "name",
					"barcode_value": "",
					"barcode_format": "CODE128",
				}
			]
		)
		html = self.get_rendered_html()
		self.assertIn('data-barcode-value="Administrator"', html)

	def test_qr_element_renders_server_side(self):
		self.make_format(
			[
				{
					"label": "",
					"fieldname": "barcode_test",
					"fieldtype": "Barcode",
					"custom": 1,
					"barcode_field": "name",
					"barcode_value": "",
					"barcode_format": "QR",
					"width": "30mm",
					"align": "right",
				}
			]
		)
		html = self.get_rendered_html()
		self.assertIn('src="data:image/png;base64,', html)
		self.assertIn("field-align-right", html)
		self.assertNotIn("<svg data-barcode-value", html)

	def test_barcode_element_without_value_renders_nothing(self):
		self.make_format(
			[
				{
					"label": "",
					"fieldname": "barcode_test",
					"fieldtype": "Barcode",
					"custom": 1,
					"barcode_field": "",
					"barcode_value": "",
					"barcode_format": "CODE128",
				}
			]
		)
		html = self.get_rendered_html()
		self.assertNotIn("print-barcode", html)

	def test_get_qr_code(self):
		import base64

		from frappe.utils.print_format_generator import get_qr_code

		data_uri = get_qr_code("hello world")
		prefix = "data:image/png;base64,"
		self.assertTrue(data_uri.startswith(prefix))
		png = base64.b64decode(data_uri[len(prefix) :])
		self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
