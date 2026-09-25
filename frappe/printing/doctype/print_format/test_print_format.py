# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
import re
import unittest
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

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

	def test_onload_resolves_pdf_generator(self):
		classic = frappe.get_doc(
			{"doctype": "Print Format", "doc_type": "ToDo", "print_format_builder": 1, "pdf_generator": None}
		)
		classic.onload()
		self.assertEqual(classic.get_onload("pdf_generator"), "wkhtmltopdf")

		beta = frappe.get_doc(
			{
				"doctype": "Print Format",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"pdf_generator": "wkhtmltopdf",
			}
		)
		beta.onload()
		self.assertEqual(beta.get_onload("pdf_generator"), "chrome")

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

		with open(exported_doc_path) as f:
			exported_doc = frappe.parse_json(f.read())

		for key, value in exported_doc.items():
			if key in doc_dict:
				with self.subTest(key=key):
					self.assertEqual(value, doc_dict[key])

		self.addCleanup(os.remove, exported_doc_path)


def beta_layout(*fields, header=None, footer=None):
	return {
		"sections": [{"label": "", "columns": [{"label": "", "fields": list(fields)}]}],
		"header": header if header is not None else {"columns": []},
		"footer": footer if footer is not None else {"columns": []},
	}


class TestPrintFormatBuilderElements(IntegrationTestCase):
	"""Image and Barcode layout elements of the beta print format builder."""

	FORMAT_NAME = "_Test Builder Elements"

	def render(self, df):
		from frappe.utils.print_format_generator import get_html

		frappe.delete_doc("Print Format", self.FORMAT_NAME, force=True, ignore_missing=True)
		frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": self.FORMAT_NAME,
				"doc_type": "User",
				"standard": "No",
				"print_format_builder_beta": 1,
				"format_data": frappe.as_json(beta_layout(df)),
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

		self.assertNotIn("print-image", self.render(df | {"image_url": ""}))

	def test_date_format_overrides_system_format(self):
		from frappe.utils.print_format_generator import format_field_value

		frappe.db.set_value("User", "Administrator", "birth_date", "2026-02-11", update_modified=False)
		self.addCleanup(frappe.db.set_value, "User", "Administrator", "birth_date", None)
		df = {"fieldname": "birth_date", "fieldtype": "Date", "label": "Birth Date"}
		self.assertIn("11 Feb 2026", self.render(df | {"date_format": "d MMM yyyy"}))
		self.assertIn("February 11, 2026", self.render(df | {"date_format": "MMMM d, yyyy"}))
		self.assertNotIn("11 Feb 2026", self.render(df))

		user = frappe.get_doc("User", "Administrator")
		self.assertEqual(format_field_value(user, df), user.get_formatted("birth_date"))
		stamp = format_field_value(
			user, {"fieldname": "last_login", "fieldtype": "Datetime", "date_format": "dd/mm/yyyy"}
		)
		if user.last_login:
			self.assertRegex(stamp, r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}")

	def test_table_column_date_format_reaches_plain_and_merged_cells(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype
		from frappe.utils.print_format_generator import get_html

		child = new_doctype(
			istable=1,
			fields=[
				{"fieldname": "due", "fieldtype": "Date", "label": "Due"},
				{"fieldname": "note", "fieldtype": "Data", "label": "Note"},
			],
		).insert()
		parent = new_doctype(
			fields=[{"fieldname": "rows", "fieldtype": "Table", "options": child.name, "label": "Rows"}]
		).insert()
		self.addCleanup(parent.delete)
		self.addCleanup(child.delete)
		doc = frappe.get_doc(
			{"doctype": parent.name, "rows": [{"due": "2026-02-11", "note": "paid"}]}
		).insert()

		def column(**extra):
			return {"fieldname": "due", "fieldtype": "Date", "label": "Due", "width": 50} | extra

		def render(col):
			frappe.delete_doc("Print Format", self.FORMAT_NAME, force=True, ignore_missing=True)
			table = {"fieldname": "rows", "fieldtype": "Table", "options": child.name, "table_columns": [col]}
			frappe.get_doc(
				{
					"doctype": "Print Format",
					"name": self.FORMAT_NAME,
					"doc_type": parent.name,
					"standard": "No",
					"print_format_builder_beta": 1,
					"format_data": frappe.as_json(
						{"sections": [{"label": "", "columns": [{"label": "", "fields": [table]}]}]}
					),
				}
			).insert()
			self.addCleanup(frappe.delete_doc, "Print Format", self.FORMAT_NAME, force=True)
			return get_html(parent.name, doc.name, self.FORMAT_NAME)

		self.assertIn(">11 Feb 2026<", render(column(date_format="d MMM yyyy")))
		self.assertNotIn("11 Feb 2026", render(column()))
		merged = column(
			date_format="d MMM yyyy",
			merged_fields=[{"fieldname": "note", "fieldtype": "Data", "style": "muted"}],
		)
		html = render(merged)
		self.assertIn('cell-line--primary">11 Feb 2026<', html)
		self.assertIn('cell-line--muted">paid<', html)

	def test_allow_page_break_marks_field_breakable(self):
		def body(html):
			return html.split("<body", 1)[-1]

		df = {"fieldname": "first_name", "fieldtype": "Data", "label": "First Name"}
		self.assertNotIn("field--breakable", body(self.render(df)))
		self.assertIn("field--breakable", body(self.render(df | {"allow_page_break": 1})))

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
		self.assertIn("print.bundle", html)
		self.assertIn("render_barcode", html)

		html = self.render(df | {"barcode_field": "name", "barcode_format": "CODE128"})
		self.assertIn('data-barcode-value="Administrator"', html)

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
			self.make(beta_layout({**self.DATA, "visible_if": "doc.first_name ==== 'x'"}))

		self.make(beta_layout({**self.DATA, "visible_if": "   "}))

	def test_runtime_condition_failure_shows_field_and_logs(self):
		before = frappe.db.count("Error Log")
		html = self.render(beta_layout({**self.DATA, "label": "PROBE", "visible_if": "doc.nope.nope"}))
		self.assertIn("PROBE", html)
		self.assertGreater(frappe.db.count("Error Log"), before)

	def test_malformed_table_columns_do_not_crash(self):
		table = {"label": "T", "fieldname": "roles", "fieldtype": "Table", "options": "Has Role"}
		for table_columns in (["nope", 3], "nope", {"a": 1}, 7, ""):
			with self.subTest(table_columns=table_columns):
				html = self.render(beta_layout({**table, "table_columns": table_columns}))
				self.assertIn("print-format-doc", html)

	def test_non_string_condition_does_not_crash(self):
		for condition in (5, ["a"], {"a": 1}):
			with self.subTest(condition=condition):
				html = self.render(beta_layout({**self.DATA, "label": "PROBE", "visible_if": condition}))
				self.assertIn("PROBE", html)

	def test_failing_row_condition_logs_once_not_once_per_row(self):
		frappe.db.delete("Error Log")
		self.render(
			beta_layout(
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
		self.assertNotIn(payload, self.render(beta_layout({**self.DATA, "label": payload})))
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
				beta_layout(
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

	def test_string_zone_normalised(self):
		"""A v16 layout stores header and footer as HTML strings; they must print as a zone."""
		from frappe.utils.print_format_generator import PrintFormatGenerator, zone_from_html

		zone = zone_from_html("<p>Zone {{ doc.name }}</p>")
		self.assertEqual(zone["columns"][0]["fields"][0]["fieldname"], "_zone_html")
		self.assertEqual(zone_from_html("   "), {"columns": [{"label": "", "fields": []}]})

		pf = self.make(
			beta_layout(self.DATA, header="<p>HEADER {{ doc.name }}</p>", footer="<p>FOOTER-TEXT</p>")
		)
		generator = PrintFormatGenerator(pf, frappe.get_doc("User", "Administrator"), no_letterhead=1)
		header = generator.layout["header"]
		self.assertEqual(header["columns"][0]["fields"][0]["fieldname"], "_zone_html")
		html = generator.get_html_preview()
		self.assertIn("HEADER Administrator", html)
		self.assertIn("FOOTER-TEXT", html)


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
				"print_format_builder": 1,
				"format_data": frappe.as_json(self.CLASSIC_FORMAT_DATA),
			}
		).insert()
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

	def test_default_layout_skips_no_value_fields(self):
		from frappe.printing.doctype.print_format.classic_converter import create_default_layout

		fields = [
			frappe._dict(fieldtype="Tab Break", fieldname="details_tab", label="Details"),
			frappe._dict(fieldtype="Data", fieldname="first_name", label="First"),
			frappe._dict(fieldtype="Button", fieldname="reset", label="Reset"),
			frappe._dict(fieldtype="Table", fieldname="roles", label="Roles", options="Has Role"),
		]
		layout = create_default_layout(frappe._dict(fields=fields))
		names = [f["fieldname"] for s in layout["sections"] for c in s["columns"] for f in c["fields"]]
		self.assertEqual(names, ["first_name", "roles"])

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
		"""Only the beta flag routes to the new renderer; classic layouts keep the standard template."""
		from frappe.printing.doctype.print_format.classic_converter import uses_beta_renderer

		classic = frappe._dict(print_format_builder=1, format_data="[]")
		beta = frappe._dict(print_format_builder_beta=1, format_data="{}")
		custom = frappe._dict(custom_format=1, print_format_builder_beta=1, format_data="{}")
		designer = frappe._dict(print_designer=1, print_format_builder_beta=1, format_data="{}")
		self.assertFalse(uses_beta_renderer(None))
		self.assertFalse(uses_beta_renderer(frappe._dict(print_format_builder=1)))
		self.assertFalse(uses_beta_renderer(classic))
		self.assertFalse(uses_beta_renderer(custom))
		self.assertFalse(uses_beta_renderer(designer))
		self.assertTrue(uses_beta_renderer(beta))

	def test_standard_jinja_format_stays_off_the_beta_renderer(self):
		from frappe.printing.doctype.print_format.classic_converter import uses_beta_renderer

		doc = frappe.new_doc("Print Format")
		doc.name = "_Test Standard Jinja Format"
		doc.doc_type = "User"
		doc.module = "Core"
		doc.standard = "Yes"
		doc.custom_format = 0
		doc.before_save()

		self.assertEqual(doc.print_format_builder_beta, 0)
		self.assertFalse(uses_beta_renderer(doc))

		doc.print_format_builder_beta = 1
		self.assertFalse(uses_beta_renderer(doc))
		doc.format_data = '{"sections": []}'
		self.assertTrue(uses_beta_renderer(doc))

	def test_classic_format_keeps_rendering_through_standard_template(self):
		self.make_classic_format()
		html = frappe.get_print("User", "Administrator", print_format=self.FORMAT_NAME)

		self.assertNotIn("print-format-doc", html)
		self.assertIn("<p>Jinja: Administrator</p>", html)
		self.assertIn("print-heading", html)

	def test_convert_print_format_document(self):
		from frappe.printing.doctype.print_format.classic_converter import convert_print_format

		doc = self.make_classic_format()
		dropped = convert_print_format(doc)

		self.assertEqual(dropped, ["dropped_field", "another_dropped_field"])
		self.assertEqual(doc.print_format_builder, 0)
		self.assertEqual(doc.print_format_builder_beta, 1)
		self.assertEqual(doc.pdf_generator, "chrome")
		self.assertEqual(doc.page_number, "Bottom Center")
		self.assertEqual(frappe.parse_json(doc.classic_format_data)["format_data"], self.CLASSIC_FORMAT_DATA)
		self.assertEqual(frappe.parse_json(doc.format_data), self.EXPECTED_BETA_LAYOUT)

		self.assertEqual(convert_print_format(doc), dropped)
		self.assertEqual(frappe.parse_json(doc.format_data), self.EXPECTED_BETA_LAYOUT)

	def test_converted_sections_get_spacing(self):
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

		self.assertIsNone(layout["sections"][0].get("margin"))
		self.assertEqual(layout["sections"][1]["margin"]["top"], CONVERTED_SECTION_GAP_PX)

	def test_repair_skips_sections_edited_since_conversion(self):
		from frappe.printing.doctype.print_format.classic_converter import (
			CONVERTED_SECTION_GAP_PX,
			add_section_spacing,
			widen_serial_column,
		)

		layout = {
			"sections": [
				{"label": "first", "columns": []},
				{"label": "bare", "columns": []},
				{"label": "tuned", "columns": [], "margin": {"top": 40}},
			]
		}
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
		self.assertIsNone(untouched["sections"][0].get("margin"))
		self.assertEqual(untouched["sections"][1]["margin"]["top"], CONVERTED_SECTION_GAP_PX)
		self.assertFalse(add_section_spacing(untouched))

		columns = [{"fieldname": "idx", "width": 5.33}, {"fieldname": "role", "width": 94.67}]
		self.assertTrue(widen_serial_column(columns))
		self.assertEqual(columns[0]["width"], 10)
		self.assertEqual(columns[1]["width"], 90.0)
		self.assertFalse(widen_serial_column(columns))

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

	CONVERTED_FIELDS_BEFORE: ClassVar[dict] = {
		"pdf_generator": None,
		"page_number": None,
		"font_size": 0,
		"margin_top": 0,
		"margin_bottom": 0,
		"margin_left": 0,
		"margin_right": 0,
	}

	def test_convert_classic_keeps_backup_and_restores(self):
		from frappe.printing.doctype.print_format.classic_converter import CONVERTED_FIELDS
		from frappe.printing.doctype.print_format.print_format import (
			convert_to_builder,
			restore_classic_layout,
		)

		self.make_classic_format()
		frappe.db.set_value("Print Format", self.FORMAT_NAME, dict(self.CONVERTED_FIELDS_BEFORE))
		result = convert_to_builder(self.FORMAT_NAME)
		self.assertEqual(result["dropped"], ["dropped_field", "another_dropped_field"])

		doc = frappe.get_doc("Print Format", self.FORMAT_NAME)
		self.assertEqual(doc.print_format_builder_beta, 1)
		self.assertEqual(doc.print_format_builder, 0)
		self.assertEqual(doc.pdf_generator, "chrome")
		self.assertEqual(doc.page_number, "Bottom Center")
		self.assertEqual(doc.font_size, 14)
		backup = frappe.parse_json(doc.classic_format_data)
		self.assertEqual(backup["format_data"], self.CLASSIC_FORMAT_DATA)
		self.assertEqual(backup["fields"], self.CONVERTED_FIELDS_BEFORE)
		self.assertEqual(frappe.parse_json(doc.format_data), self.EXPECTED_BETA_LAYOUT)
		html = frappe.get_print("User", "Administrator", print_format=self.FORMAT_NAME)
		self.assertIn("print-format-doc", html)
		self.assertIn("<p>Jinja: Administrator</p>", html)

		layout = frappe.parse_json(doc.format_data)
		layout["sections"][0]["label"] = "Edited in builder"
		doc.format_data = frappe.as_json(layout)
		doc.margin_top = 33
		doc.save()
		self.assertRaises(frappe.ValidationError, convert_to_builder, self.FORMAT_NAME)
		doc = frappe.get_doc("Print Format", self.FORMAT_NAME)
		self.assertEqual(frappe.parse_json(doc.classic_format_data), backup)
		self.assertEqual(frappe.parse_json(doc.format_data)["sections"][0]["label"], "Edited in builder")
		self.assertEqual(doc.margin_top, 33)

		restore_classic_layout(self.FORMAT_NAME)
		doc = frappe.get_doc("Print Format", self.FORMAT_NAME)
		self.assertEqual(doc.print_format_builder, 1)
		self.assertEqual(doc.print_format_builder_beta, 0)
		self.assertFalse(doc.classic_format_data)
		self.assertEqual(frappe.parse_json(doc.format_data), self.CLASSIC_FORMAT_DATA)
		for fieldname in CONVERTED_FIELDS:
			with self.subTest(fieldname=fieldname):
				self.assertEqual(doc.get(fieldname), self.CONVERTED_FIELDS_BEFORE[fieldname])
		html = frappe.get_print("User", "Administrator", print_format=self.FORMAT_NAME)
		self.assertNotIn("print-format-doc", html)
		self.assertIn("<p>Jinja: Administrator</p>", html)

		self.assertRaises(frappe.ValidationError, restore_classic_layout, self.FORMAT_NAME)

	def test_standard_format_converts_only_in_developer_mode(self):
		from frappe.printing.doctype.print_format.print_format import (
			convert_to_builder,
			restore_classic_layout,
		)

		doc = self.make_classic_format()
		doc.db_set("standard", "Yes")
		developer_mode = frappe.conf.developer_mode
		frappe.conf.developer_mode = 0
		self.addCleanup(setattr, frappe.conf, "developer_mode", developer_mode)
		self.assertRaises(frappe.ValidationError, convert_to_builder, self.FORMAT_NAME)
		self.assertEqual(
			frappe.db.get_value("Print Format", self.FORMAT_NAME, "print_format_builder_beta"), 0
		)

		frappe.conf.developer_mode = 1
		convert_to_builder(self.FORMAT_NAME)
		frappe.conf.developer_mode = 0
		self.assertRaises(frappe.ValidationError, restore_classic_layout, self.FORMAT_NAME)
		self.assertEqual(
			frappe.db.get_value("Print Format", self.FORMAT_NAME, "print_format_builder_beta"), 1
		)

	def test_hybrid_format_is_refused(self):
		from frappe.utils.print_format_generator import PrintFormatGenerator

		doc = self.make_classic_format()
		doc.print_format_builder_beta = 1
		self.assertRaises(frappe.ValidationError, doc.save)

		doc.db_set("print_format_builder_beta", 1)
		doc.reload()
		self.assertRaises(
			frappe.ValidationError, PrintFormatGenerator, doc, frappe.get_doc("User", "Administrator")
		)

	def test_create_custom_format_based_on_classic_converts(self):
		from frappe.printing.doctype.print_format.print_format import (
			create_custom_format,
			restore_classic_layout,
		)

		self.make_classic_format()
		name = f"_Test From Classic {frappe.generate_hash(length=6)}"
		doc = create_custom_format("User", name, based_on=self.FORMAT_NAME)
		self.addCleanup(frappe.delete_doc, "Print Format", name, force=True)

		self.assertEqual(doc.print_format_builder_beta, 1)
		self.assertEqual(doc.print_format_builder, 0)
		self.assertEqual(doc.pdf_generator, "chrome")
		self.assertEqual(frappe.parse_json(doc.format_data), self.EXPECTED_BETA_LAYOUT)
		self.assertFalse(doc.classic_format_data)
		self.assertRaises(frappe.ValidationError, restore_classic_layout, name)
		self.assertEqual(frappe.db.get_value("Print Format", name, "print_format_builder_beta"), 1)
		source = frappe.get_doc("Print Format", self.FORMAT_NAME)
		self.assertEqual(source.print_format_builder, 1)
		self.assertEqual(frappe.parse_json(source.format_data), self.CLASSIC_FORMAT_DATA)

	def test_create_custom_format_copies_source_print_options(self):
		from frappe.printing.doctype.print_format.classic_converter import convert_print_format
		from frappe.printing.doctype.print_format.print_format import (
			COPIED_PRINT_OPTIONS,
			create_custom_format,
		)

		options = {
			"show_section_headings": 1,
			"line_breaks": 1,
			"align_labels_right": 1,
			"font": "Arial",
			"font_size": 11,
			"page_number": "Top Center",
			"margin_top": 25,
			"margin_left": 5,
			"css": ".print-format { color: red; }",
		}
		source = self.make_classic_format()
		source.update(options).save()
		name = f"_Test Copied Options {frappe.generate_hash(length=6)}"
		doc = create_custom_format("User", name, based_on=self.FORMAT_NAME)
		self.addCleanup(frappe.delete_doc, "Print Format", name, force=True)

		in_place = frappe.get_doc("Print Format", self.FORMAT_NAME)
		convert_print_format(in_place)
		self.assertNotIn("show_label", frappe.parse_json(doc.format_data)["sections"][0])
		self.assertEqual(frappe.parse_json(doc.format_data), frappe.parse_json(in_place.format_data))
		for fieldname in COPIED_PRINT_OPTIONS:
			with self.subTest(fieldname=fieldname):
				self.assertEqual(doc.get(fieldname), in_place.get(fieldname))
		self.assertEqual(doc.pdf_generator, "chrome")

	def test_convert_format_without_layout_builds_the_default_layout(self):
		from frappe.printing.doctype.print_format.classic_converter import convert_print_format

		doc = frappe.new_doc("Print Format")
		doc.doc_type = "ToDo"
		doc.name = "_Test Empty Layout"
		doc.print_format_builder = 1
		self.assertEqual(convert_print_format(doc), [])
		layout = frappe.parse_json(doc.format_data)
		self.assertTrue(layout["sections"])
		self.assertEqual(doc.print_format_builder_beta, 1)
		self.assertEqual(doc.pdf_generator, "chrome")

	def test_get_beta_layout_matches_convert_print_format(self):
		from frappe.printing.doctype.print_format.classic_converter import (
			NUMERIC_DEFAULT_FIELDS,
			conversion_values,
			convert_print_format,
			create_default_layout,
			get_beta_layout,
		)

		doc = self.make_classic_format()
		doc.update(self.CONVERTED_FIELDS_BEFORE)
		doc.format_data = frappe.as_json(
			[
				{
					"fieldname": "user_emails",
					"print_hide": 0,
					"visible_columns": [
						{"fieldname": "email_account", "print_hide": 0, "print_width": "50%"},
						{"fieldname": "email_id", "print_hide": 0, "print_width": "50%"},
					],
				}
			]
		)
		doc.save()
		converted = frappe.get_doc("Print Format", self.FORMAT_NAME)
		convert_print_format(converted)
		result = get_beta_layout(self.FORMAT_NAME)
		self.assertEqual(result["layout"], frappe.parse_json(converted.format_data))
		self.assertEqual(result["values"], conversion_values(converted))
		self.assertEqual(result["values"]["pdf_generator"], "chrome")
		self.assertEqual(result["values"]["page_number"], "Bottom Center")
		self.assertEqual(result["values"]["print_format_builder_beta"], 1)
		meta = frappe.get_meta("Print Format")
		for fieldname in NUMERIC_DEFAULT_FIELDS:
			self.assertEqual(result["values"][fieldname], flt(meta.get_field(fieldname).default))
		table = result["layout"]["sections"][0]["columns"][0]["fields"][0]
		self.assertEqual([c["width"] for c in table["table_columns"]], [10, 45, 45])

		doc.db_set("format_data", None)
		result = get_beta_layout(self.FORMAT_NAME)
		self.assertEqual(result["layout"], create_default_layout(frappe.get_meta("User")))
		self.assertEqual(result["dropped"], [])
		self.assertEqual(
			frappe.db.get_value("Print Format", self.FORMAT_NAME, "print_format_builder_beta"), 0
		)

	def test_create_custom_format_copies_standard_classic_without_developer_mode(self):
		from frappe.printing.doctype.print_format.print_format import create_custom_format

		source = self.make_classic_format()
		source.db_set("standard", "Yes", update_modified=False)
		name = f"_Test From Standard {frappe.generate_hash(length=6)}"
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			doc = create_custom_format("User", name, based_on=self.FORMAT_NAME)
		self.addCleanup(frappe.delete_doc, "Print Format", name, force=True)

		self.assertEqual(doc.standard, "No")
		self.assertEqual(doc.print_format_builder_beta, 1)
		self.assertEqual(frappe.parse_json(doc.format_data), self.EXPECTED_BETA_LAYOUT)
		source = frappe.get_doc("Print Format", self.FORMAT_NAME)
		self.assertEqual(source.standard, "Yes")
		self.assertEqual(source.print_format_builder, 1)
		self.assertEqual(source.print_format_builder_beta, 0)
		self.assertEqual(frappe.parse_json(source.format_data), self.CLASSIC_FORMAT_DATA)
		self.assertFalse(source.classic_format_data)

	def test_classic_create_refused(self):
		from frappe.printing.doctype.print_format.print_format import create_custom_format

		name = f"_Test Refused Classic {frappe.generate_hash(length=6)}"
		self.assertRaises(frappe.ValidationError, create_custom_format, "User", name, "Standard", False)
		self.assertFalse(frappe.db.exists("Print Format", name))

		doc = create_custom_format("User", name)
		self.addCleanup(frappe.delete_doc, "Print Format", name, force=True)
		self.assertEqual(doc.print_format_builder_beta, 1)
		self.assertEqual(doc.pdf_generator, "chrome")


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
		doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": self.FORMAT_NAME,
				"doc_type": "Contact",
				"standard": "No",
				"print_format_builder_beta": 1,
				"format_data": frappe.as_json(beta_layout(df)),
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

	def test_versions_are_recorded_and_restore_into_the_draft(self):
		from frappe.printing.doctype.print_format.print_format import (
			apply_draft,
			delete_version,
			get_versions,
			restore_version,
			save_draft,
			save_version,
		)

		save_draft(self.pf.name, {"margin_top": 25}, self.stamp())
		apply_draft(self.pf.name, self.stamp())
		save_draft(self.pf.name, {"margin_top": 40}, self.stamp())
		save_version(self.pf.name, "Wide top", {"margin_top": 40}, self.stamp())

		versions = get_versions(self.pf.name)
		self.assertEqual([v["type"] for v in versions], ["Manual", "Save & Apply"])
		self.assertEqual(versions[0]["label"], "Wide top")

		restore_version(self.pf.name, versions[1]["name"], self.stamp())
		live = self.live("margin_top", "draft_data")
		self.assertEqual(live.margin_top, 25)
		self.assertEqual(frappe.parse_json(live.draft_data)["margin_top"], 25)

		delete_version(self.pf.name, versions[0]["name"])
		self.assertEqual([v["type"] for v in get_versions(self.pf.name)], ["Save & Apply"])

	def test_draft_ignores_fields_outside_the_whitelist(self):
		from frappe.printing.doctype.print_format.print_format import apply_draft, save_draft

		save_draft(self.pf.name, {"margin_top": 25, "disabled": 1, "standard": "Yes"}, self.stamp())
		self.assertNotIn("disabled", frappe.parse_json(self.live("draft_data").draft_data))

		apply_draft(self.pf.name, self.stamp(), {"margin_top": 30, "disabled": 1})
		live = self.live("margin_top", "disabled")
		self.assertEqual(live.margin_top, 30)
		self.assertEqual(live.disabled, 0)

	def test_css_rides_the_draft_pipeline(self):
		from frappe.printing.doctype.print_format.print_format import apply_draft, save_draft

		save_draft(self.pf.name, {"css": ".print-format p { margin: 0; }"}, self.stamp())
		self.assertIn("css", frappe.parse_json(self.live("draft_data").draft_data))

		apply_draft(self.pf.name, self.stamp(), {"css": ".print-format p { margin: 0; }"})
		self.assertEqual(self.live("css").css, ".print-format p { margin: 0; }")

	def test_a_stale_write_cannot_clobber_a_newer_draft(self):
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


class TestWeasyPrintEngine(IntegrationTestCase):
	"""WeasyPrint stays as a deprecated, explicitly stored renderer for existing beta formats."""

	def make_beta(self, stored=None, **kwargs):
		doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Test WP {frappe.generate_hash(length=6)}",
				"doc_type": "User",
				"print_format_builder_beta": 1,
				"format_data": frappe.as_json(
					beta_layout(
						{"label": "First Name", "fieldname": "first_name", "fieldtype": "Data"},
						header="<p>WP-HEADER {{ doc.name }}</p>",
					)
				),
				**kwargs,
			}
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", doc.name, force=True)
		if stored and stored != doc.pdf_generator:
			doc.db_set("pdf_generator", stored, update_modified=False)
			doc.reload()
		return doc

	def test_new_format_cannot_pick_weasyprint(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_beta(pdf_generator="WeasyPrint")

	def test_before_save_keeps_weasyprint(self):
		doc = self.make_beta("WeasyPrint")
		self.assertEqual(doc.pdf_generator, "WeasyPrint")
		doc.before_save()
		self.assertEqual(doc.pdf_generator, "WeasyPrint")

		doc.pdf_generator = "wkhtmltopdf"
		doc.before_save()
		self.assertEqual(doc.pdf_generator, "chrome")

	def test_existing_weasyprint_format_keeps_it_on_save(self):
		doc = self.make_beta("WeasyPrint")
		doc.margin_top = 12
		doc.save()
		self.assertEqual(frappe.db.get_value("Print Format", doc.name, "pdf_generator"), "WeasyPrint")

	def test_resolve_pdf_generator(self):
		from frappe.utils.print_utils import resolve_pdf_generator

		self.assertEqual(resolve_pdf_generator(self.make_beta("WeasyPrint")), "WeasyPrint")
		self.assertEqual(resolve_pdf_generator(self.make_beta("Typst")), "Typst")
		self.assertEqual(resolve_pdf_generator(self.make_beta(), "wkhtmltopdf"), "chrome")
		self.assertEqual(resolve_pdf_generator(None), "wkhtmltopdf")
		self.assertEqual(resolve_pdf_generator(None, "chrome"), "chrome")
		self.assertEqual(resolve_pdf_generator(frappe._dict(pdf_generator="chrome")), "chrome")
		self.assertEqual(
			resolve_pdf_generator(frappe._dict(pdf_generator="chrome"), "wkhtmltopdf"), "wkhtmltopdf"
		)

	def patch_legacy_render(self):
		from frappe.utils import weasyprint_legacy

		return patch.object(
			weasyprint_legacy.PrintFormatGenerator, "render_pdf", autospec=True, return_value=b"%PDF-probe"
		)

	def test_weasyprint_hook(self):
		from frappe.utils import weasyprint_legacy
		from frappe.utils.weasyprint import get_weasyprint_pdf

		doc = self.make_beta("WeasyPrint")
		self.assertIsNone(get_weasyprint_pdf(doc.name, None, {}, None, pdf_generator="chrome"))

		frappe.local.form_dict = frappe._dict()
		pdf = frappe.get_print("User", "Administrator", print_format=doc.name, as_pdf=True, no_letterhead=1)
		self.assertTrue(pdf.startswith(b"%PDF"))

		with self.patch_legacy_render() as render:
			frappe.local.form_dict = frappe._dict()
			frappe.get_print("User", "Administrator", print_format=doc.name, as_pdf=True, no_letterhead=1)
		generator = render.call_args.args[0]
		self.assertIsInstance(generator, weasyprint_legacy.PrintFormatGenerator)
		self.assertEqual(generator.print_format.name, doc.name)
		header, footer = generator.get_header_footer_html()
		self.assertIn("<header>", header)
		self.assertIn("WP-HEADER Administrator", header)
		self.assertIsNone(footer)
		html = generator.get_html_preview()
		self.assertIn("WP-HEADER Administrator", html)
		self.assertIn('<div class="section-columns row">', html)
		self.assertNotIn("print-format-doc", html)

	def test_legacy_html_paths_match_v16(self):
		from frappe.utils.weasyprint import get_html
		from frappe.www.printpreview import get_context as preview_context
		from frappe.www.printview import get_context, get_html_and_style, trigger_print_script

		doc = self.make_beta("WeasyPrint")
		expected = get_html("User", "Administrator", doc.name)
		self.assertIn("WP-HEADER Administrator", expected)

		frappe.local.form_dict = frappe._dict(doctype="User", name="Administrator", format=doc.name)
		context = get_context(frappe._dict())
		self.assertEqual(context["body"], expected + trigger_print_script)
		self.assertFalse(context["standalone"])
		self.assertTrue(context["print_style"])

		frappe.local.form_dict = frappe._dict()
		out = get_html_and_style(doc="User", name="Administrator", print_format=doc.name)
		self.assertEqual(out["html"], expected)

		frappe.local.form_dict = frappe._dict(doctype="User", name="Administrator", print_format=doc.name)
		context = frappe._dict()
		preview_context(context)
		self.assertEqual(context.body, expected)

	def test_legacy_unwraps_zone_header(self):
		from frappe.utils.print_format_generator import zone_from_html
		from frappe.utils.weasyprint import get_html

		doc = self.make_beta("WeasyPrint")
		layout = frappe.parse_json(doc.format_data)
		self.assertIsInstance(layout["header"], str)
		expected = get_html("User", "Administrator", doc.name)

		layout["header"] = zone_from_html(layout["header"])
		layout["footer"] = {"columns": []}
		doc.db_set("format_data", frappe.as_json(layout), update_modified=False)
		frappe.clear_document_cache("Print Format", doc.name)
		self.assertEqual(get_html("User", "Administrator", doc.name), expected)

		layout["header"]["columns"][0]["fields"].append(
			{"label": "Email", "fieldname": "email", "fieldtype": "Data"}
		)
		doc.db_set("format_data", frappe.as_json(layout), update_modified=False)
		frappe.clear_document_cache("Print Format", doc.name)
		html = get_html("User", "Administrator", doc.name)
		self.assertIn("WP-HEADER Administrator", html)
		self.assertIn("admin@example.com", html)
		self.assertNotIn("{% raw %}", html)

	def test_chrome_format_does_not_use_legacy(self):
		from frappe.printing.doctype.print_format.classic_converter import uses_legacy_weasyprint
		from frappe.www.printview import get_html_and_style

		doc = self.make_beta()
		self.assertEqual(doc.pdf_generator, "chrome")
		self.assertFalse(uses_legacy_weasyprint(doc))
		frappe.local.form_dict = frappe._dict()
		with patch("frappe.utils.weasyprint.legacy_generator") as legacy:
			html = frappe.get_print("User", "Administrator", print_format=doc.name, no_letterhead=1)
			out = get_html_and_style(doc="User", name="Administrator", print_format=doc.name)
		legacy.assert_not_called()
		self.assertIn("print-format-doc", html)
		self.assertIn("print-format-doc", out["html"])

	def test_attach_print_weasyprint_from_background_job(self):
		doc = self.make_beta("WeasyPrint")
		frappe.local.form_dict = frappe._dict()
		with (
			self.change_settings("Print Settings", send_print_as_pdf=1),
			self.patch_legacy_render() as render,
			patch("frappe.utils.pdf.get_pdf") as wkhtmltopdf,
		):
			out = frappe.attach_print("User", "Administrator", print_format=doc.name)
		self.assertEqual(out["fcontent"], b"%PDF-probe")
		self.assertEqual(render.call_args.args[0].print_format.name, doc.name)
		wkhtmltopdf.assert_not_called()
		self.assertFalse(frappe.form_dict.get("doctype"))

	def test_download_multi_pdf_with_password_keeps_pages(self):
		from io import BytesIO

		from pypdf import PdfReader

		from frappe.utils.print_format import download_multi_pdf

		doc = self.make_beta("WeasyPrint")
		frappe.local.form_dict = frappe._dict()
		download_multi_pdf(
			"User",
			frappe.as_json(["Administrator"]),
			format=doc.name,
			no_letterhead=True,
			options=frappe.as_json({"password": "secret"}),
		)
		pdf = frappe.local.response.filecontent
		self.assertTrue(pdf.startswith(b"%PDF"))
		reader = PdfReader(BytesIO(pdf))
		self.assertTrue(reader.is_encrypted)
		self.assertTrue(reader.decrypt("secret"))
		self.assertEqual(len(reader.pages), 1)

	def test_get_print_context_is_cleaned_up(self):
		from frappe.utils.print_format_generator import get_print_context

		doc = self.make_beta("WeasyPrint")
		frappe.local.form_dict = frappe._dict()
		with self.patch_legacy_render():
			frappe.get_print("User", "Administrator", print_format=doc.name, as_pdf=True, no_letterhead=1)
		self.assertIsNone(get_print_context())

	def test_legacy_blockers(self):
		from frappe.utils.weasyprint_legacy import legacy_blockers

		doc = self.make_beta("WeasyPrint")
		self.assertEqual(legacy_blockers(doc, frappe.parse_json(doc.format_data)), [])
		layout = beta_layout(
			{
				"label": "First Name",
				"fieldname": "first_name",
				"fieldtype": "Data",
				"custom_style": "color: red",
			},
			{"fieldname": "note", "fieldtype": "Static Text", "text": "Hi", "custom": 1},
			{
				"label": "Roles",
				"fieldname": "roles",
				"fieldtype": "Table",
				"table_header_bg": "#eee",
				"table_columns": [{"fieldname": "role", "column_condition": "doc.name"}],
			},
		)
		layout["sections"][0]["background"] = "#fafafa"
		blockers = legacy_blockers(doc, layout)
		for reason in (
			"Static Text block",
			"Table styling",
			"Table column conditions",
			"Section background, padding, radius or custom CSS",
			"Custom CSS on fields: First Name",
		):
			self.assertIn(reason, blockers)
		self.assertIn("Custom HTML format", legacy_blockers(frappe._dict(custom_format=1), layout))

	def test_weasyprint_rejects_new_blocks(self):
		doc = self.make_beta("WeasyPrint")
		doc.format_data = frappe.as_json(
			beta_layout({"fieldname": "note", "fieldtype": "Static Text", "text": "Hi", "custom": 1})
		)
		with self.assertRaises(frappe.ValidationError) as cm:
			doc.save()
		self.assertIn("Static Text block", str(cm.exception))

		doc.reload()
		doc.pdf_generator = "chrome"
		doc.format_data = frappe.as_json(
			beta_layout({"fieldname": "note", "fieldtype": "Static Text", "text": "Hi", "custom": 1})
		)
		doc.save()
		self.assertEqual(doc.pdf_generator, "chrome")

	def test_weasyprint_keeps_unchanged_layout_with_blockers(self):
		doc = self.make_beta("WeasyPrint")
		doc.db_set(
			"format_data",
			frappe.as_json(
				beta_layout({"fieldname": "note", "fieldtype": "Static Text", "text": "Hi", "custom": 1})
			),
			update_modified=False,
		)
		doc.reload()
		doc.margin_top = 12
		doc.save()
		self.assertEqual(frappe.db.get_value("Print Format", doc.name, "pdf_generator"), "WeasyPrint")

	def test_download_pdf_accepts_every_renderer(self):
		from frappe.utils.print_format import download_pdf

		for generator in ("Typst", "WeasyPrint", "chrome"):
			with patch("frappe.get_print", return_value=b"%PDF") as get_print:
				frappe.call(download_pdf, doctype="User", name="Administrator", pdf_generator=generator)
			self.assertEqual(get_print.call_args.kwargs["pdf_generator"], generator)


class TestPrintFormatPicker(IntegrationTestCase):
	"""The print view lists formats whose print_format_for was never set."""

	PRINT_PAGE_FILTERS: ClassVar = {"doc_type": "User", "print_format_for": ["in", ["DocType", ""]]}

	def make_unset(self):
		doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Test Unset For {frappe.generate_hash(length=6)}",
				"doc_type": "User",
				"print_format_builder_beta": 1,
				"format_data": frappe.as_json(beta_layout()),
			}
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", doc.name, force=True)
		doc.db_set("print_format_for", None, update_modified=False)
		self.assertIsNone(frappe.db.get_value("Print Format", doc.name, "print_format_for"))
		return doc

	def test_null_print_format_for_is_listed(self):
		doc = self.make_unset()
		self.assertIn(doc.name, frappe.get_all("Print Format", filters=self.PRINT_PAGE_FILTERS, pluck="name"))
		self.assertNotIn(
			doc.name,
			frappe.get_all(
				"Print Format", filters={"doc_type": "User", "print_format_for": "DocType"}, pluck="name"
			),
		)

	def test_patch_sets_doctype(self):
		from frappe.patches.v16_0.set_print_format_for_doctype import execute

		doc = self.make_unset()
		modified = frappe.db.get_value("Print Format", doc.name, "modified")
		execute()
		execute()
		self.assertEqual(frappe.db.get_value("Print Format", doc.name, "print_format_for"), "DocType")
		self.assertEqual(frappe.db.get_value("Print Format", doc.name, "modified"), modified)
