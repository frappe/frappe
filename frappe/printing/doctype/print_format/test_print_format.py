# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
import re
import unittest
from typing import TYPE_CHECKING, ClassVar

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

if TYPE_CHECKING:
	from frappe.printing.doctype.print_format.print_format import PrintFormat


class TestPrintFormat(IntegrationTestCase):
	def test_print_user(self, style=None):
		# The default (Standard) print now renders through the new builder's renderer.
		print_html = frappe.get_print("User", "Administrator", style=style)
		self.assertIn('class="print-format-doc"', print_html)
		self.assertIn("First Name", print_html)
		self.assertIn('<div class="value">', print_html)
		return print_html

	def test_print_user_standard(self):
		print_html = self.test_print_user("Standard")
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

	def render(self, df):
		from frappe.utils.print_format_generator import get_html

		frappe.delete_doc("Print Format", self.FORMAT_NAME, force=True, ignore_missing=True)
		format_data = {
			"sections": [{"label": "", "columns": [{"label": "", "fields": [df]}]}],
			"header": {"columns": []},
			"footer": {"columns": []},
		}
		frappe.get_doc(
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
		return get_html("User", "Administrator", self.FORMAT_NAME)

	def test_image_element(self):
		df = {"fieldname": "image_test", "fieldtype": "Image", "custom": 1, "label": "Logo"}
		html = self.render(df | {"image_url": "/img/logo.svg", "width": "40mm", "align": "center"})
		self.assertIn('src="/img/logo.svg"', html)
		self.assertIn("width: 40mm", html)
		self.assertIn("field-align-center", html)

		# no source -> block is skipped entirely
		self.assertNotIn("print-image", self.render(df | {"image_url": ""}))

	def test_barcode_element(self):
		df = {"fieldname": "barcode_test", "fieldtype": "Barcode", "custom": 1, "label": ""}

		html = self.render(
			df
			| {
				"barcode_value": "TEST-123",
				"barcode_format": "CODE39",
				"show_text": False,
				"width": "50mm",
			}
		)
		self.assertIn('data-barcode-value="TEST-123"', html)
		self.assertIn('"format": "CODE39"', html)
		self.assertIn('"displayValue": false', html)
		self.assertIn("width: 50mm", html)
		# the client-side renderer must be shipped with the document
		self.assertIn("print.bundle", html)
		self.assertIn("render_barcode", html)

		# value bound to a doc field
		html = self.render(df | {"barcode_field": "name", "barcode_format": "CODE128"})
		self.assertIn('data-barcode-value="Administrator"', html)

		# no value -> block is skipped entirely
		self.assertNotIn("print-barcode", self.render(df | {"barcode_value": ""}))

	def test_qr_code(self):
		import base64

		from frappe.utils.print_format_generator import get_qr_code

		html = self.render(
			{
				"fieldname": "barcode_test",
				"fieldtype": "Barcode",
				"custom": 1,
				"barcode_field": "name",
				"barcode_format": "QR",
				"width": "30mm",
				"align": "right",
			}
		)
		# QR renders server-side as an embedded SVG image, no client-side JsBarcode svg
		self.assertIn('src="data:image/svg+xml;base64,', html)
		self.assertIn("field-align-right", html)
		self.assertNotIn("<svg data-barcode-value", html)

		data_uri = get_qr_code("hello world")
		prefix = "data:image/svg+xml;base64,"
		self.assertTrue(data_uri.startswith(prefix))
		self.assertIn(b"<svg", base64.b64decode(data_uri[len(prefix) :]))


class TestPrintFormatHardening(IntegrationTestCase):
	"""Malformed layouts and conditions must not take the print down."""

	NAME = "_Test Hardening"

	def make(self, layout, **kwargs):
		frappe.delete_doc("Print Format", self.NAME, force=True, ignore_missing=True)
		doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": self.NAME,
				"doc_type": "User",
				"standard": "No",
				"print_format_builder_beta": 1,
				"format_data": layout if isinstance(layout, str) else frappe.as_json(layout),
				**kwargs,
			}
		)
		doc.insert()
		self.addCleanup(frappe.delete_doc, "Print Format", self.NAME, force=True, ignore_missing=True)
		return doc

	def render(self, layout, **kwargs):
		from frappe.utils.print_format_generator import get_html

		self.make(layout, **kwargs)
		return get_html("User", "Administrator", self.NAME)

	@staticmethod
	def layout(*fields, **section):
		sec = {"label": "", "columns": [{"label": "", "fields": list(fields)}]}
		sec.update(section)
		return {"sections": [sec], "header": {"columns": []}, "footer": {"columns": []}}

	DATA: ClassVar[dict] = {"label": "First Name", "fieldname": "first_name", "fieldtype": "Data"}

	def test_malformed_layout_renders_empty_instead_of_erroring(self):
		for label, format_data in {
			"corrupt json": '{"sections": [BROKEN',
			"sections is a string": '{"sections": "nope"}',
			"sections is null": '{"sections": null}',
			"section without columns": '{"sections": [{"label": "x"}]}',
			"column without fields": '{"sections": [{"columns": [{"label": ""}]}]}',
			"non-dict field": '{"sections": [{"columns": [{"fields": ["nope"]}]}]}',
		}.items():
			with self.subTest(layout=label):
				self.assertIn("print-format-doc", self.render(format_data))

	def test_broken_condition_is_rejected_on_save(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(self.layout({**self.DATA, "visible_if": "doc.first_name ==== 'x'"}))

		self.make(self.layout({**self.DATA, "visible_if": "   "}))

	def test_runtime_condition_failure_shows_field_and_logs(self):
		before = frappe.db.count("Error Log")
		html = self.render(self.layout({**self.DATA, "label": "PROBE", "visible_if": "doc.nope.nope"}))
		self.assertIn("PROBE", html)
		self.assertGreater(frappe.db.count("Error Log"), before)

	def test_malformed_table_columns_do_not_crash(self):
		table = {"label": "T", "fieldname": "roles", "fieldtype": "Table", "options": "Has Role"}
		for table_columns in (["nope", 3], "nope", {"a": 1}, 7, ""):
			with self.subTest(table_columns=table_columns):
				html = self.render(self.layout({**table, "table_columns": table_columns}))
				self.assertIn("print-format-doc", html)

	def test_non_string_condition_does_not_crash(self):
		for condition in (5, ["a"], {"a": 1}):
			with self.subTest(condition=condition):
				html = self.render(self.layout({**self.DATA, "label": "PROBE", "visible_if": condition}))
				self.assertIn("PROBE", html)

	def test_failing_row_condition_logs_once_not_once_per_row(self):
		frappe.db.delete("Error Log")
		self.render(
			self.layout(
				{
					"label": "T",
					"fieldname": "roles",
					"fieldtype": "Table",
					"options": "Has Role",
					"row_condition": "row.nope.nope",
					"table_columns": [
						{"label": "Role", "fieldname": "role", "fieldtype": "Link", "width": 100}
					],
				}
			)
		)
		self.assertGreater(frappe.db.count("Has Role", {"parent": "Administrator"}), 1)
		self.assertEqual(frappe.db.count("Error Log"), 1)

	def test_labels_are_escaped(self):
		payload = "<script>alert(1)</script>"
		self.assertNotIn(payload, self.render(self.layout({**self.DATA, "label": payload})))
		self.assertNotIn(
			payload,
			self.render(
				{
					"sections": [{"label": payload, "columns": [{"label": "", "fields": [self.DATA]}]}],
					"header": {"columns": []},
					"footer": {"columns": []},
				}
			),
		)
		self.assertNotIn(
			payload,
			self.render(
				self.layout(
					{
						"label": "T",
						"fieldname": "roles",
						"fieldtype": "Table",
						"options": "Has Role",
						"table_columns": [
							{"label": payload, "fieldname": "role", "fieldtype": "Link", "width": 100}
						],
					}
				)
			),
		)


class TestClassicConverter(IntegrationTestCase):
	"""Conversion of classic print-format-builder layouts to the beta builder."""

	FORMAT_NAME = "_Test Classic Conversion"

	CLASSIC_FORMAT_DATA: ClassVar[list] = [
		{
			"fieldname": "print_heading_template",
			"fieldtype": "Custom HTML",
			"options": "<div class='print-heading'><h2>User<br><small>{{ doc.name }}</small></h2></div>",
		},
		{"fieldtype": "Section Break", "label": "Details"},
		{"fieldtype": "Column Break"},
		{"fieldname": "first_name", "print_hide": 0, "nolabel": 1},
		{"fieldname": "last_name", "print_hide": 0, "label": "Surname", "align": "right"},
		{"fieldname": "email", "print_hide": 1},
		{"fieldname": "dropped_field", "print_hide": 0},
		{"fieldtype": "Column Break"},
		{"fieldtype": "HTML", "options": "<p>Jinja: {{ doc.name }}</p>"},
		{
			"fieldname": "roles",
			"print_hide": 0,
			"visible_columns": [{"fieldname": "role", "print_width": "150px", "print_hide": 0}],
		},
		{"fieldtype": "Section Break", "label": "Empty Tail"},
		{"fieldtype": "Column Break"},
		{"fieldname": "another_dropped_field", "print_hide": 0},
	]

	EXPECTED_BETA_LAYOUT: ClassVar[dict] = {
		"sections": [
			{
				"label": "Details",
				"show_label": "hide",
				"columns": [
					{
						"label": "",
						"fields": [
							{
								"label": "First Name",
								"fieldname": "first_name",
								"fieldtype": "Data",
								"options": None,
								"show_label": "hide",
							},
							{
								"label": "Surname",
								"fieldname": "last_name",
								"fieldtype": "Data",
								"options": None,
								"align": "right",
							},
						],
					},
					{
						"label": "",
						"fields": [
							{
								"label": "Custom HTML",
								"fieldname": "custom_html_1",
								"fieldtype": "HTML",
								"html": "<p>Jinja: {{ doc.name }}</p>",
								"custom": 1,
							},
							{
								"label": "Roles Assigned",
								"fieldname": "roles",
								"fieldtype": "Table",
								"options": "Has Role",
								"show_label": "hide",
								"table_columns": [
									{
										"label": "Sr",
										"fieldname": "idx",
										"fieldtype": "Int",
										"options": None,
										"width": 10,
									},
									{
										"label": "Role",
										"fieldname": "role",
										"fieldtype": "Link",
										"options": "Role",
										"width": 20.0,
									},
								],
							},
						],
					},
				],
			}
		],
		"header": {
			"columns": [
				{
					"label": "",
					"fields": [
						{
							"label": "",
							"fieldname": "print_heading_template",
							"fieldtype": "HTML",
							"html": "<div class='print-heading'><h2>User<br><small>{{ doc.name }}</small></h2></div>",
							"custom": 1,
						}
					],
				}
			]
		},
		"footer": {"columns": [{"label": "", "fields": []}]},
	}

	def make_classic_format(self):
		frappe.delete_doc("Print Format", self.FORMAT_NAME, force=True, ignore_missing=True)
		doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": self.FORMAT_NAME,
				"doc_type": "User",
				"standard": "No",
				"format_data": frappe.as_json(self.CLASSIC_FORMAT_DATA),
			}
		).insert()
		doc.db_set(
			{"print_format_builder": 1, "print_format_builder_beta": 0, "pdf_generator": "wkhtmltopdf"}
		)
		doc.reload()
		self.addCleanup(frappe.delete_doc, "Print Format", self.FORMAT_NAME, force=True)
		return doc

	def test_convert_classic_to_beta_golden(self):
		from frappe.printing.doctype.print_format.classic_converter import convert_classic_to_beta

		layout, dropped = convert_classic_to_beta(self.CLASSIC_FORMAT_DATA, frappe.get_meta("User"))
		self.assertEqual(dropped, ["dropped_field", "another_dropped_field"])
		self.assertEqual(layout, self.EXPECTED_BETA_LAYOUT)

	def test_section_headings_preserved(self):
		from frappe.printing.doctype.print_format.classic_converter import convert_classic_to_beta

		layout, _ = convert_classic_to_beta(
			self.CLASSIC_FORMAT_DATA, frappe.get_meta("User"), frappe._dict(show_section_headings=1)
		)
		self.assertNotIn("show_label", layout["sections"][0])

	def test_section_print_hide_drops_section(self):
		from frappe.printing.doctype.print_format.classic_converter import (
			convert_classic_to_beta,
			create_default_layout,
		)

		fields = [
			frappe._dict(fieldtype="Section Break", fieldname="s1", label="Visible", print_hide=0),
			frappe._dict(fieldtype="Data", fieldname="first_name", label="First", print_hide=0),
			frappe._dict(fieldtype="Section Break", fieldname="s2", label="Hidden", print_hide=1),
			frappe._dict(fieldtype="Data", fieldname="last_name", label="Last", print_hide=0),
		]

		default = create_default_layout(frappe._dict(fields=fields))
		converted, _ = convert_classic_to_beta(fields, frappe.get_meta("User"))

		for layout in (default, converted):
			names = [f["fieldname"] for s in layout["sections"] for c in s["columns"] for f in c["fields"]]
			self.assertIn("first_name", names)
			self.assertNotIn("last_name", names)

	def test_default_layout_has_document_heading(self):
		"""The default (no custom format) print keeps the classic document heading:
		select_print_heading / print_heading / doctype, plus the document name."""
		from frappe.printing.doctype.print_format.classic_converter import (
			create_default_layout,
			get_default_print_format,
		)
		from frappe.utils.print_format_generator import PrintFormatGenerator

		layout = create_default_layout(frappe.get_meta("ToDo"))
		heading = layout["header"]["columns"][0]["fields"][0]
		self.assertEqual(heading["fieldtype"], "HTML")
		self.assertEqual(heading["fieldname"], "print_heading_template")

		todo = frappe.get_doc({"doctype": "ToDo", "description": "Heading test"}).insert(
			ignore_permissions=True
		)
		self.addCleanup(todo.delete, ignore_permissions=True)

		generator = PrintFormatGenerator(get_default_print_format("ToDo"), todo)
		html = generator.get_html_preview()
		self.assertIn('<div class="print-heading">', html)
		self.assertIn("<div>ToDo</div>", html)
		self.assertIn(f'<small class="sub-heading">{todo.name}</small>', html)

	def test_print_width_mapping(self):
		from frappe.printing.doctype.print_format.classic_converter import (
			distribute_widths,
			parse_print_width,
		)

		self.assertEqual(parse_print_width("150px"), 20.0)
		self.assertEqual(parse_print_width("25%"), 25.0)
		self.assertIsNone(parse_print_width(""))
		self.assertIsNone(parse_print_width("garbage"))

		columns = [{"width": 20.0}, {"width": None}, {"width": None}]
		self.assertEqual([c["width"] for c in distribute_widths(columns)], [20.0, 40.0, 40.0])

		oversized = [{"width": 80.0}, {"width": 120.0}]
		self.assertEqual([c["width"] for c in distribute_widths(oversized)], [40.0, 60.0])

	def test_uses_beta_renderer(self):
		from frappe.printing.doctype.print_format.classic_converter import uses_beta_renderer

		classic = frappe._dict(print_format_builder=1, format_data="[]")
		beta = frappe._dict(print_format_builder_beta=1, format_data="{}")
		custom = frappe._dict(custom_format=1, format_data="[]")
		self.assertFalse(uses_beta_renderer(None))
		self.assertFalse(uses_beta_renderer(frappe._dict(print_format_builder=1)))
		self.assertFalse(uses_beta_renderer(custom))
		self.assertTrue(uses_beta_renderer(classic))
		self.assertTrue(uses_beta_renderer(beta))

	def test_standard_jinja_format_stays_off_the_beta_renderer(self):
		from frappe.printing.doctype.print_format.classic_converter import uses_beta_renderer

		# app-shipped Jinja format: html lives in the module's .html file, so there is
		# no format_data for the beta renderer to read
		doc = frappe.new_doc("Print Format")
		doc.name = "_Test Standard Jinja Format"
		doc.doc_type = "User"
		doc.module = "Core"
		doc.standard = "Yes"
		doc.custom_format = 0
		doc.before_save()

		self.assertEqual(doc.print_format_builder_beta, 0)
		self.assertFalse(uses_beta_renderer(doc))

		# rows flipped before the before_save fix are still in the wild — the flag
		# alone must not route a layout-less standard format to the beta renderer
		doc.print_format_builder_beta = 1
		self.assertFalse(uses_beta_renderer(doc))
		doc.format_data = '{"sections": []}'
		self.assertTrue(uses_beta_renderer(doc))

	def test_print_designer_format_stays_off_the_beta_renderer(self):
		from frappe.printing.doctype.print_format.classic_converter import uses_beta_renderer

		doc = frappe.new_doc("Print Format")
		doc.name = "_Test Print Designer Format"
		doc.doc_type = "User"
		doc.module = "Core"
		doc.custom_format = 0
		doc.print_designer = 1
		doc.format_data = '{"header": [], "body": []}'
		doc.before_save()

		self.assertEqual(doc.print_format_builder_beta, 0)
		self.assertFalse(uses_beta_renderer(doc))

		# rows already flipped on insert must not reach the beta renderer either
		doc.print_format_builder_beta = 1
		self.assertFalse(uses_beta_renderer(doc))

	def test_convert_print_format_document(self):
		from frappe.printing.doctype.print_format.classic_converter import convert_print_format

		doc = self.make_classic_format()
		dropped = convert_print_format(doc)

		self.assertEqual(dropped, ["dropped_field", "another_dropped_field"])
		self.assertEqual(doc.print_format_builder, 0)
		self.assertEqual(doc.print_format_builder_beta, 1)
		self.assertEqual(doc.pdf_generator, "chrome")
		self.assertEqual(doc.page_number, "Bottom Center")
		self.assertEqual(frappe.parse_json(doc.classic_format_data), self.CLASSIC_FORMAT_DATA)
		self.assertEqual(frappe.parse_json(doc.format_data), self.EXPECTED_BETA_LAYOUT)

		# re-running converts from the backup, not the already-converted layout
		self.assertEqual(convert_print_format(doc), dropped)
		self.assertEqual(frappe.parse_json(doc.format_data), self.EXPECTED_BETA_LAYOUT)

	def test_get_beta_layout(self):
		from frappe.printing.doctype.print_format.classic_converter import get_beta_layout

		self.make_classic_format()
		result = get_beta_layout(self.FORMAT_NAME)
		self.assertEqual(result["layout"], self.EXPECTED_BETA_LAYOUT)
		self.assertEqual(result["dropped"], ["dropped_field", "another_dropped_field"])
		self.assertEqual(frappe.parse_json(result["classic_format_data"]), self.CLASSIC_FORMAT_DATA)
		# read-only: the stored document is untouched
		self.assertEqual(frappe.db.get_value("Print Format", self.FORMAT_NAME, "print_format_builder"), 1)

	def test_classic_format_renders_via_beta_renderer(self):
		self.make_classic_format()
		html = frappe.get_print("User", "Administrator", print_format=self.FORMAT_NAME)

		self.assertIn("print-format-doc", html)
		self.assertIn("<p>Jinja: Administrator</p>", html)
		self.assertIn('data-fieldname="first_name"', html)
		self.assertIn('data-fieldname="roles"', html)
		self.assertIn('data-fieldname="idx"', html)
		self.assertIn("print-heading", html)

	def test_zero_font_size_renders_at_default(self):
		# app-shipped classic fixtures carry no font_size, which lands as 0 — the
		# stylesheet must not emit font-size: 0px or the whole page is invisible
		self.make_classic_format()
		frappe.db.set_value("Print Format", self.FORMAT_NAME, "font_size", 0)
		html = frappe.get_print("User", "Administrator", print_format=self.FORMAT_NAME)
		self.assertNotIn("font-size: 0px", html)
		self.assertIn("font-size: 14px", html)

	def test_migrate_all_classic_formats(self):
		from frappe.printing.doctype.print_format.classic_converter import migrate_all_classic_formats

		self.make_classic_format()
		report = migrate_all_classic_formats()

		self.assertIn(self.FORMAT_NAME, report)
		doc = frappe.get_doc("Print Format", self.FORMAT_NAME)
		self.assertEqual(doc.print_format_builder_beta, 1)
		self.assertEqual(doc.print_format_builder, 0)
		# original classic array is preserved as a backup for rollback
		self.assertEqual(frappe.parse_json(doc.classic_format_data), self.CLASSIC_FORMAT_DATA)

		# idempotent: re-running re-converts from the backup and stays beta
		migrate_all_classic_formats()
		doc.reload()
		self.assertEqual(doc.print_format_builder_beta, 1)
		self.assertEqual(frappe.parse_json(doc.classic_format_data), self.CLASSIC_FORMAT_DATA)

	def test_converted_sections_get_spacing(self):
		"""Classic put the gap in its markup; the conversion has to store one."""
		from frappe.printing.doctype.print_format.classic_converter import (
			CONVERTED_SECTION_GAP_PX,
			convert_classic_to_beta,
		)

		classic = [
			{"fieldtype": "Section Break", "label": "One"},
			{"fieldname": "first_name", "print_hide": 0},
			{"fieldtype": "Section Break", "label": "Two"},
			{"fieldname": "last_name", "print_hide": 0},
		]
		layout, _dropped = convert_classic_to_beta(classic, frappe.get_meta("User"))

		# the first section sits under the header, which already has its own gap
		self.assertIsNone(layout["sections"][0].get("margin"))
		self.assertEqual(layout["sections"][1]["margin"]["top"], CONVERTED_SECTION_GAP_PX)

	def test_spacing_patch_skips_sections_edited_since_conversion(self):
		from frappe.patches.v16_0.repair_converted_print_formats import add_section_spacing
		from frappe.printing.doctype.print_format.classic_converter import CONVERTED_SECTION_GAP_PX

		layout = {
			"sections": [
				{"label": "first", "columns": []},
				{"label": "bare", "columns": []},
				{"label": "tuned", "columns": [], "margin": {"top": 40}},
			]
		}
		# one tuned section means someone has been in the builder — leave it all alone
		self.assertFalse(add_section_spacing(layout))
		self.assertIsNone(layout["sections"][1].get("margin"))
		self.assertEqual(layout["sections"][2]["margin"]["top"], 40)

		untouched = {
			"sections": [
				{"label": "first", "columns": []},
				{"label": "a", "columns": []},
				{"label": "b", "columns": []},
			]
		}
		self.assertTrue(add_section_spacing(untouched))
		# the first section sits under the header, which already has its own gap
		self.assertIsNone(untouched["sections"][0].get("margin"))
		self.assertEqual(untouched["sections"][1]["margin"]["top"], CONVERTED_SECTION_GAP_PX)
		self.assertEqual(untouched["sections"][2]["margin"]["top"], CONVERTED_SECTION_GAP_PX)

		# re-running changes nothing
		self.assertFalse(add_section_spacing(untouched))

	def test_conversion_fills_numeric_fields_left_empty(self):
		from frappe.printing.doctype.print_format.classic_converter import (
			NUMERIC_DEFAULT_FIELDS,
			convert_print_format,
		)

		doc = self.make_classic_format()
		for fieldname in NUMERIC_DEFAULT_FIELDS:
			doc.set(fieldname, 0)
		convert_print_format(doc)

		meta = frappe.get_meta("Print Format")
		for fieldname in NUMERIC_DEFAULT_FIELDS:
			with self.subTest(fieldname=fieldname):
				self.assertEqual(doc.get(fieldname), flt(meta.get_field(fieldname).default))

		doc.margin_left = 3
		for fieldname in ("margin_top", "margin_bottom", "margin_right"):
			doc.set(fieldname, 0)
		convert_print_format(doc)
		self.assertEqual(doc.margin_left, 3)
		self.assertEqual(doc.margin_right, 0)

	def test_repair_converted_print_formats(self):
		from frappe.patches.v16_0.repair_converted_print_formats import execute

		self.make_classic_format()
		from frappe.printing.doctype.print_format.classic_converter import migrate_all_classic_formats

		migrate_all_classic_formats()

		# recreate the pre-fix conversion output: zero font size, 5.33% serial column
		doc = frappe.get_doc("Print Format", self.FORMAT_NAME)
		layout = frappe.parse_json(doc.format_data)
		table = layout["sections"][0]["columns"][1]["fields"][1]
		table["table_columns"][0]["width"] = 5.33
		table["table_columns"][1]["width"] = 94.67
		frappe.db.set_value(
			"Print Format",
			self.FORMAT_NAME,
			{"font_size": 0, "format_data": frappe.as_json(layout)},
		)

		execute()

		doc.reload()
		self.assertEqual(doc.font_size, 14)
		columns = frappe.parse_json(doc.format_data)["sections"][0]["columns"][1]["fields"][1][
			"table_columns"
		]
		self.assertEqual(columns[0]["width"], 10)
		self.assertEqual(columns[1]["width"], 90.0)

		# already-repaired rows are untouched
		modified = frappe.db.get_value("Print Format", self.FORMAT_NAME, "format_data")
		execute()
		self.assertEqual(frappe.db.get_value("Print Format", self.FORMAT_NAME, "format_data"), modified)

	def test_migration_skips_corrupt_format(self):
		"""A format with unparseable format_data is skipped, not fatal to the run."""
		from frappe.printing.doctype.print_format.classic_converter import migrate_all_classic_formats

		self.make_classic_format()
		bad_name = "_Test Corrupt Classic"
		frappe.delete_doc("Print Format", bad_name, force=True, ignore_missing=True)
		bad = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": bad_name,
				"doc_type": "User",
				"standard": "No",
				"format_data": "[]",
			}
		).insert()
		bad.db_set({"print_format_builder": 1, "print_format_builder_beta": 0, "format_data": "{ not json ]"})
		self.addCleanup(frappe.delete_doc, "Print Format", bad_name, force=True)

		report = migrate_all_classic_formats()

		self.assertIn(self.FORMAT_NAME, report)
		self.assertNotIn(bad_name, report)


class TestPrintFormatChildTableVisibility(IntegrationTestCase):
	"""Per-row and per-column conditional visibility for child Table fields."""

	FORMAT_NAME = "_Test Child Table Visibility"

	def setUp(self):
		frappe.delete_doc("Contact", "PFB Table Test", force=True, ignore_missing=True)
		self.contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "PFB Table Test",
				"email_ids": [
					{"email_id": "primary@example.com", "is_primary": 1},
					{"email_id": "secondary@example.com", "is_primary": 0},
				],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Contact", self.contact.name, force=True)

	def render(self, df, skip_validation=False):
		from frappe.utils.print_format_generator import get_html

		frappe.delete_doc("Print Format", self.FORMAT_NAME, force=True, ignore_missing=True)
		format_data = {
			"sections": [{"label": "", "columns": [{"label": "", "fields": [df]}]}],
			"header": {"columns": []},
			"footer": {"columns": []},
		}
		doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": self.FORMAT_NAME,
				"doc_type": "Contact",
				"standard": "No",
				"print_format_builder_beta": 1,
				"format_data": frappe.as_json(format_data),
			}
		)
		if skip_validation:
			doc.flags.ignore_validate = True
		doc.insert()
		self.addCleanup(frappe.delete_doc, "Print Format", self.FORMAT_NAME, force=True)
		return get_html("Contact", self.contact.name, self.FORMAT_NAME)

	def table_field(self, **overrides):
		df = {
			"fieldname": "email_ids",
			"fieldtype": "Table",
			"label": "Emails",
			"options": "Contact Email",
			"table_columns": [
				{"label": "Email", "fieldname": "email_id", "fieldtype": "Data", "width": 60},
				{"label": "Primary", "fieldname": "is_primary", "fieldtype": "Check", "width": 40},
			],
		}
		df.update(overrides)
		return df

	def test_row_condition_drops_non_matching_rows(self):
		html = self.render(self.table_field(row_condition="row.is_primary"))
		self.assertIn("primary@example.com", html)
		self.assertNotIn("secondary@example.com", html)

	def test_bad_row_condition_keeps_all_rows(self):
		html = self.render(self.table_field(row_condition="row.does_not_exist >"), skip_validation=True)
		self.assertIn("primary@example.com", html)
		self.assertIn("secondary@example.com", html)

	def test_all_rows_filtered_hides_table(self):
		html = self.render(self.table_field(row_condition="1 == 2"))
		self.assertNotIn('data-fieldname="email_ids"', html)

	def test_all_columns_dropped_hides_table(self):
		df = self.table_field()
		for col in df["table_columns"]:
			col["column_condition"] = "1 == 2"
		html = self.render(df)
		self.assertNotIn('data-fieldname="email_ids"', html)

	def test_column_condition_drops_column(self):
		kept = self.render(self.table_field())
		self.assertIn('data-fieldname="is_primary"', kept)

		df = self.table_field()
		df["table_columns"][1]["column_condition"] = "doc.first_name == 'no match'"
		html = self.render(df)
		self.assertNotIn('data-fieldname="is_primary"', html)
		self.assertIn('data-fieldname="email_id"', html)
		self.assertIn("primary@example.com", html)
		self.assertIn("secondary@example.com", html)

	def test_column_emptiness_respects_row_condition(self):
		# Keep only the non-primary row; is_primary is 0 in that row, so the column has
		# no value in the rendered rows and must be dropped — even though the filtered-out
		# primary row had a 1.
		html = self.render(self.table_field(row_condition="not row.is_primary"))
		self.assertIn("secondary@example.com", html)
		self.assertNotIn("primary@example.com", html)
		self.assertIn('data-fieldname="email_id"', html)
		self.assertNotIn('data-fieldname="is_primary"', html)

	def test_bad_column_condition_keeps_column(self):
		df = self.table_field()
		df["table_columns"][1]["column_condition"] = "doc.does_not_exist >"
		html = self.render(df, skip_validation=True)
		self.assertIn('data-fieldname="is_primary"', html)
		self.assertIn('data-fieldname="email_id"', html)

	def test_print_settings_available_in_conditions(self):
		html = self.render(
			self.table_field(row_condition="print_settings.doctype == 'Print Settings' and row.is_primary")
		)
		self.assertIn("primary@example.com", html)
		self.assertNotIn("secondary@example.com", html)

		df = self.table_field()
		df["table_columns"][1]["column_condition"] = "print_settings.doctype == 'Nope'"
		html = self.render(df)
		self.assertNotIn('data-fieldname="is_primary"', html)
		self.assertIn('data-fieldname="email_id"', html)


class TestPrintFormatDraft(IntegrationTestCase):
	"""The builder parks edits in draft_data; only Save & Apply touches what prints."""

	def setUp(self):
		self.pf = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Test Draft {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": frappe.as_json({"sections": [], "header": {}, "footer": {}}),
				"margin_top": 10,
			}
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", self.pf.name, force=True)

	def live(self, *fields):
		return frappe.db.get_value("Print Format", self.pf.name, list(fields), as_dict=True)

	def stamp(self):
		"""The format's current `modified` — every draft endpoint requires it."""
		return frappe.db.get_value("Print Format", self.pf.name, "modified")

	def test_draft_does_not_change_what_prints(self):
		from frappe.printing.doctype.print_format.print_format import (
			apply_draft,
			discard_draft,
			save_draft,
		)

		save_draft(self.pf.name, {"margin_top": 25, "font": "Inter"}, self.stamp())
		live = self.live("margin_top", "font", "draft_data")
		self.assertEqual(live.margin_top, 10)
		self.assertIsNone(live.font)
		self.assertEqual(frappe.parse_json(live.draft_data)["margin_top"], 25)

		apply_draft(self.pf.name, self.stamp())
		live = self.live("margin_top", "font", "draft_data")
		self.assertEqual(live.margin_top, 25)
		self.assertEqual(live.font, "Inter")
		self.assertFalse(live.draft_data)

		save_draft(self.pf.name, {"margin_top": 99}, self.stamp())
		discard_draft(self.pf.name, self.stamp())
		live = self.live("margin_top", "draft_data")
		self.assertEqual(live.margin_top, 25)
		self.assertFalse(live.draft_data)

	def test_draft_ignores_fields_outside_the_whitelist(self):
		from frappe.printing.doctype.print_format.print_format import apply_draft, save_draft

		save_draft(self.pf.name, {"margin_top": 25, "disabled": 1, "standard": "Yes"}, self.stamp())
		self.assertNotIn("disabled", frappe.parse_json(self.live("draft_data").draft_data))

		apply_draft(self.pf.name, self.stamp(), {"margin_top": 30, "disabled": 1})
		live = self.live("margin_top", "disabled")
		self.assertEqual(live.margin_top, 30)
		self.assertEqual(live.disabled, 0)

	def test_a_stale_write_cannot_clobber_a_newer_draft(self):
		"""db_set skips the timestamp check save() runs, so the endpoints do it."""
		from frappe.printing.doctype.print_format.print_format import (
			apply_draft,
			discard_draft,
			save_draft,
		)

		stale = self.stamp()
		save_draft(self.pf.name, {"margin_top": 20}, stale)

		for call in (
			lambda: save_draft(self.pf.name, {"margin_top": 55}, stale),
			lambda: apply_draft(self.pf.name, stale),
			lambda: discard_draft(self.pf.name, stale),
		):
			with self.assertRaises(frappe.TimestampMismatchError):
				call()

		self.assertEqual(frappe.parse_json(self.live("draft_data").draft_data)["margin_top"], 20)
