# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.tests import IntegrationTestCase


class TestPrintFormatGenerator(IntegrationTestCase):
	"""Tests for frappe.utils.print_format_generator — covering the new
	PrintFormatGenerator class and related whitelisted helpers introduced
	by the Print Format Builder UX rewrite."""

	# ------------------------------------------------------------------ #
	# helpers
	# ------------------------------------------------------------------ #

	def _make_print_format(self, **kwargs):
		"""Create a minimal builder-beta Print Format for ToDo and return it."""
		name = f"_Test PFG {frappe.generate_hash(length=6)}"
		doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": name,
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"custom_format": 0,
				"standard": "No",
				"format_data": json.dumps(
					{
						"sections": [
							{
								"label": "Details",
								"columns": [
									{
										"label": "",
										"fields": [
											{
												"fieldtype": "Data",
												"fieldname": "description",
												"label": "Description",
											}
										],
									}
								],
							}
						],
						"header": {"columns": [{"label": "", "fields": []}]},
						"footer": {"columns": [{"label": "", "fields": []}]},
					}
				),
				**kwargs,
			}
		)
		doc.insert(ignore_permissions=True)
		self.addCleanup(doc.delete, ignore_permissions=True)
		return doc

	def _make_todo(self):
		"""Insert a ToDo and schedule cleanup."""
		doc = frappe.get_doc({"doctype": "ToDo", "description": "Generator test task"})
		doc.insert(ignore_permissions=True)
		self.addCleanup(doc.delete, ignore_permissions=True)
		return doc

	# ------------------------------------------------------------------ #
	# before_save: auto-enable builder beta
	# ------------------------------------------------------------------ #

	def test_new_non_custom_format_sets_builder_beta(self):
		"""before_save should set print_format_builder_beta=1 for new non-custom formats."""
		pf = self._make_print_format()
		self.assertEqual(pf.print_format_builder_beta, 1)

	def test_new_non_custom_format_sets_chrome_pdf_generator(self):
		"""before_save should force pdf_generator='chrome' when builder beta is enabled."""
		pf = self._make_print_format()
		self.assertEqual(pf.pdf_generator, "chrome")

	def test_new_custom_format_does_not_set_builder_beta(self):
		"""before_save must NOT enable builder beta for custom HTML formats."""
		# Create the doc directly (without format_data) because _make_print_format
		# always injects format_data, which is in the new dict format and causes
		# extract_images to fail when print_format_builder_beta=0.
		name = f"_Test PFG Custom {frappe.generate_hash(length=6)}"
		pf = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": name,
				"doc_type": "ToDo",
				"print_format_builder_beta": 0,
				"custom_format": 1,
				"standard": "No",
				"html": "<p>custom</p>",
			}
		)
		pf.insert(ignore_permissions=True)
		self.addCleanup(pf.delete, ignore_permissions=True)
		self.assertEqual(pf.print_format_builder_beta, 0)

	def test_existing_builder_beta_format_keeps_chrome(self):
		"""Saving an existing builder-beta format must keep pdf_generator='chrome'."""
		pf = self._make_print_format()
		pf.margin_top = 15
		pf.save(ignore_permissions=True)
		pf.reload()
		self.assertEqual(pf.pdf_generator, "chrome")

	def test_report_format_sets_custom_format(self):
		"""before_save should set custom_format=1 when print_format_for=='Report'."""
		report_name = frappe.db.get_value("Report", {"report_type": "Query Report"}, "name")
		if not report_name:
			self.skipTest("No Query Report found in test database")
		pf = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Test PFG Report {frappe.generate_hash(length=6)}",
				"print_format_for": "Report",
				"report": report_name,
				"custom_format": 0,
				"standard": "No",
				"html": "<p>report</p>",
			}
		)
		pf.insert(ignore_permissions=True)
		self.addCleanup(pf.delete, ignore_permissions=True)
		self.assertEqual(pf.custom_format, 1)

	# ------------------------------------------------------------------ #
	# PrintFormatGenerator: HTML preview
	# ------------------------------------------------------------------ #

	def test_get_html_returns_string(self):
		"""get_html should return a non-empty HTML string for a valid doc."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format()
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIsInstance(html, str)
		self.assertIn("<!DOCTYPE html>", html)

	def test_get_html_contains_field_value(self):
		"""The rendered HTML must include the document field value."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format()
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn(todo.description, html)

	def test_qr_barcode_options(self):
		from frappe.utils.print_format_generator import is_qr_barcode_options

		self.assertTrue(is_qr_barcode_options("qrcode"))
		self.assertTrue(is_qr_barcode_options("QR"))
		self.assertTrue(is_qr_barcode_options('{"format": "qrcode"}'))
		self.assertFalse(is_qr_barcode_options('{"format": "EAN"}'))
		self.assertFalse(is_qr_barcode_options(None))
		self.assertFalse(is_qr_barcode_options("random text"))

	def test_barcode_docfield_with_qr_options_renders_qr(self):
		"""A dragged Barcode docfield whose options ask for a qr code prints one —
		decided by the field, without a barcode_format on the layout element."""
		from frappe.utils.print_format_generator import get_html

		fieldname = f"_test_qr_{frappe.generate_hash(length=6)}"
		custom_field = frappe.get_doc(
			{
				"doctype": "Custom Field",
				"dt": "ToDo",
				"label": "QR",
				"fieldname": fieldname,
				"fieldtype": "Barcode",
				"options": "qrcode",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(custom_field.delete, ignore_permissions=True)

		layout = {
			"sections": [
				{
					"label": "",
					"columns": [
						{
							"label": "",
							"fields": [{"fieldtype": "Barcode", "fieldname": fieldname, "label": "QR"}],
						}
					],
				}
			],
			"header": {"columns": [{"label": "", "fields": []}]},
			"footer": {"columns": [{"label": "", "fields": []}]},
		}
		pf = self._make_print_format(format_data=json.dumps(layout))
		todo = self._make_todo()
		frappe.db.set_value("ToDo", todo.name, fieldname, "HELLO-QR")

		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn("data:image/svg+xml;base64", html)
		self.assertNotIn('data-barcode-value="HELLO-QR"', html)

	def test_get_html_applies_margin(self):
		"""Margin values set on the print format should appear in the rendered CSS."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format(margin_top=20, margin_bottom=20)
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		# The CSS block should encode 20mm top/bottom margins
		self.assertIn("20mm", html)

	def test_screen_preview_is_full_page_width(self):
		"""On screen the preview sheet is the full page width (A4 = 210mm) with the
		margins as padding, so it looks like a page — not the narrow content width."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format()
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn("max-width: 210mm !important", html)
		self.assertIn("box-sizing: border-box", html)

	def test_browser_print_keeps_page_margins_on_every_page(self):
		"""Browser print takes its margins from @page, not from body padding: padding
		only applies to the first/last page, so interior pages would lose them."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format(margin_top=20, margin_bottom=20)
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)

		page_rule = html[html.find("@page") : html.find("html, body {", html.find("@page"))]
		self.assertIn("margin-top: 20mm", page_rule)
		self.assertIn("margin-bottom: 20mm", page_rule)
		self.assertNotIn("margin: 0;", page_rule)
		self.assertLess(html.find("@media screen"), html.find("padding: 20mm"))

	def test_top_page_number_sits_above_the_page_margin(self):
		"""A top page number renders flush to the page edge, not below margin_top.
		The header markup absorbs the margin (padding on everything after the page
		number) and flags it so browser.py drops the header page's own marginTop —
		otherwise the margin would be applied twice and the body would shift."""
		from unittest.mock import patch

		from frappe.utils.print_format_generator import PrintFormatGenerator

		todo = self._make_todo()
		letterhead_doc = self._make_letterhead()

		def chrome_options(letterhead=True, **pf_kwargs):
			pf_kwargs.setdefault("margin_top", 12)
			pf = self._make_print_format(**pf_kwargs)
			generator = PrintFormatGenerator(pf, todo, letterhead=letterhead_doc.name if letterhead else None)
			with patch("frappe.utils.pdf.get_chrome_pdf", return_value=b"%PDF-") as chrome_pdf:
				generator.render_pdf()
			return chrome_pdf.call_args.kwargs

		top = chrome_options(page_number="Top Left")
		self.assertTrue(top["options"]["header-includes-top-margin"])
		self.assertIn("padding-top:12.0mm", top["html"])

		# No letterhead and no header template: the page number is still the only
		# thing above the margin, so the margin must still be reserved below it.
		bare = chrome_options(page_number="Top Left", letterhead=False)
		self.assertTrue(bare["options"]["header-includes-top-margin"])
		self.assertIn("padding-top:12.0mm", bare["html"])

		# repeat_header_footer off routes page numbers through the minimal overlay.
		no_repeat = chrome_options(page_number="Top Left", repeat_header_footer=0)
		self.assertTrue(no_repeat["options"]["header-includes-top-margin"])

		for pos in ("Hide", "Bottom Center"):
			opts = chrome_options(page_number=pos)["options"]
			self.assertNotIn("header-includes-top-margin", opts)

		# margin_top 0 has nothing to reserve.
		self.assertNotIn(
			"header-includes-top-margin",
			chrome_options(page_number="Top Left", margin_top=0)["options"],
		)

	def test_render_pdf_passes_password_to_chrome(self):
		"""Encrypted PDFs (attach_print(password=...)) must stay encrypted on the
		generator path — the chrome pipeline encrypts from options['password']."""
		from unittest.mock import patch

		from frappe.utils.print_format_generator import PrintFormatGenerator

		pf = self._make_print_format()
		todo = self._make_todo()
		generator = PrintFormatGenerator(pf, todo)

		with patch("frappe.utils.pdf.get_chrome_pdf", return_value=b"%PDF-") as chrome_pdf:
			generator.render_pdf(password="s3cret")
		self.assertEqual(chrome_pdf.call_args.kwargs["options"]["password"], "s3cret")

		with patch("frappe.utils.pdf.get_chrome_pdf", return_value=b"%PDF-") as chrome_pdf:
			generator.render_pdf()
		self.assertNotIn("password", chrome_pdf.call_args.kwargs["options"])

	def test_permlevel_restricted_fields_are_dropped(self):
		"""A layout may reference permlevel-restricted fields; readers without access
		to that permlevel must not get them in the print output."""
		from unittest.mock import patch

		from frappe.utils.print_format_generator import PrintFormatGenerator

		pf = self._make_print_format()
		todo = self._make_todo()

		layout = json.loads(pf.format_data)
		layout["sections"][0]["columns"][0]["fields"].append(
			{"fieldtype": "Data", "fieldname": "_secret", "label": "Secret"}
		)
		pf.format_data = json.dumps(layout)

		restricted = frappe._dict(fieldname="_secret", fieldtype="Data", permlevel=1, label="Secret")
		get_field = todo.meta.get_field

		def get_field_with_secret(fieldname):
			return restricted if fieldname == "_secret" else get_field(fieldname)

		with patch.object(todo.meta, "get_field", side_effect=get_field_with_secret):
			with patch.object(todo, "has_permlevel_access_to", return_value=False):
				fieldnames = self._layout_fieldnames(PrintFormatGenerator(pf, todo))
			self.assertNotIn("_secret", fieldnames)
			self.assertIn("description", fieldnames)

			with patch.object(todo, "has_permlevel_access_to", return_value=True):
				fieldnames = self._layout_fieldnames(PrintFormatGenerator(pf, todo))
			self.assertIn("_secret", fieldnames)

	def _layout_fieldnames(self, generator):
		return [
			df.get("fieldname")
			for column in generator.layout_columns(generator.layout)
			for df in column.get("fields", [])
		]

	def test_get_print_degrades_for_deleted_format(self):
		"""A print_format name that no longer exists must not raise DoesNotExistError
		during pdf_generator resolution — it degrades to the Standard render, so
		notifications referencing a removed format still send."""
		from frappe.utils.print_utils import _print_format_doc_or_none

		self.assertIsNone(_print_format_doc_or_none("_No Such Format ZZZ"))
		self.assertIsNone(_print_format_doc_or_none("Standard"))
		self.assertIsNone(_print_format_doc_or_none(None))

	def test_standard_print_follows_print_settings_pdf_generator(self):
		"""Standard (no print format) must honour Print Settings, while a beta format
		stays pinned to chrome — wkhtmltopdf cannot lay out its flexbox columns."""
		from frappe.utils.print_utils import resolve_pdf_generator

		beta = self._make_print_format()
		original = frappe.db.get_single_value("Print Settings", "pdf_generator")
		self.addCleanup(frappe.db.set_single_value, "Print Settings", "pdf_generator", original)

		for setting in ("wkhtmltopdf", "chrome"):
			frappe.db.set_single_value("Print Settings", "pdf_generator", setting)
			self.assertEqual(resolve_pdf_generator(None), setting)
			self.assertEqual(resolve_pdf_generator(beta), "chrome")

		frappe.db.set_single_value("Print Settings", "pdf_generator", "wkhtmltopdf")
		self.assertEqual(resolve_pdf_generator(None, "chrome"), "chrome")

	# ------------------------------------------------------------------ #
	# printpreview: Standard (no format selected) renders the beta default
	# ------------------------------------------------------------------ #

	def test_printpreview_standard_renders_beta_default(self):
		"""With no print_format, /printpreview must render the beta default document
		itself — a full page with a single set of margins — not fall back to the old
		classic wrapper that produced double padding."""
		from frappe.www import printpreview

		todo = self._make_todo()
		frappe.form_dict.doctype = "ToDo"
		frappe.form_dict.name = todo.name
		frappe.form_dict.pop("print_format", None)
		self.addCleanup(lambda: frappe.form_dict.pop("doctype", None))
		self.addCleanup(lambda: frappe.form_dict.pop("name", None))

		context = frappe._dict()
		printpreview.get_context(context)

		self.assertIn("print-format-doc", context.body)
		self.assertNotIn("print-format-preview", context.body)

	# ------------------------------------------------------------------ #
	# render_jinja_template: whitelisted endpoint
	# ------------------------------------------------------------------ #

	def test_render_jinja_template_basic(self):
		"""render_jinja_template should render {{ doc.description }} correctly."""
		from frappe.utils.print_format_generator import render_jinja_template

		todo = self._make_todo()
		result = render_jinja_template("{{ doc.description }}", "ToDo", todo.name)
		self.assertEqual(result, todo.description)

	def test_render_jinja_template_requires_print_permission(self):
		"""render_jinja_template must raise PermissionError for a guest user
		who has no print permission on the document."""
		from frappe.utils.print_format_generator import render_jinja_template

		todo = self._make_todo()
		# Simulate no print permission by checking that check_permission raises
		# when called on a document the user can't print.
		# We patch check_permission to verify it is actually called.
		from frappe.model.document import Document

		called = []
		original = Document.check_permission

		def fake_check(self_doc, *a, **kw):
			called.append(a)
			original(self_doc, *a, **kw)

		Document.check_permission = fake_check
		try:
			render_jinja_template("{{ doc.description }}", "ToDo", todo.name)
		finally:
			Document.check_permission = original

		self.assertTrue(called, "check_permission was never called")
		self.assertIn("print", called[0])

	def test_render_jinja_template_sandbox_blocks_dunder(self):
		"""The Jinja sandbox must reject dunder attribute access (SSTI guard)."""
		from frappe.utils.print_format_generator import render_jinja_template

		todo = self._make_todo()
		with self.assertRaises(Exception):
			# SandboxedEnvironment raises SecurityError on .__class__.__bases__
			render_jinja_template("{{ doc.__class__.__bases__ }}", "ToDo", todo.name)

	# ------------------------------------------------------------------ #
	# PrintFormatGenerator: section / zone rendering
	# ------------------------------------------------------------------ #

	def test_zone_section_renders_field_values(self):
		"""_render_zone_section should produce HTML containing field values from doc."""
		from frappe.utils.print_format_generator import PrintFormatGenerator

		pf = self._make_print_format()
		todo = self._make_todo()
		generator = PrintFormatGenerator(pf.name, todo)

		section = {
			"label": "Test",
			"columns": [
				{
					"fields": [
						{
							"fieldtype": "Data",
							"fieldname": "description",
							"label": "Description",
							"show_label": "show",
						}
					]
				}
			],
		}
		html = generator._render_zone_section(section, todo)
		self.assertIn(todo.description, html)

	def test_zone_section_empty_when_no_fields(self):
		"""_render_zone_section should return empty/falsy when section has no fields."""
		from frappe.utils.print_format_generator import PrintFormatGenerator

		pf = self._make_print_format()
		todo = self._make_todo()
		generator = PrintFormatGenerator(pf.name, todo)

		section = {"label": "", "columns": [{"fields": []}]}
		html = generator._render_zone_section(section, todo)
		self.assertFalse(html.strip())

	def test_letterhead_resolution_precedence(self):
		"""Beta renders resolve a letter head like templates do, with the layout's own choice on top."""
		from frappe.utils.print_format_generator import PrintFormatGenerator

		def make_lh(is_default=0):
			lh = frappe.get_doc(
				{
					"doctype": "Letter Head",
					"letter_head_name": f"_Test LH {frappe.generate_hash(length=6)}",
					"source": "HTML",
					"content": "<p>letterhead</p>",
					"is_default": is_default,
				}
			).insert(ignore_permissions=True)
			self.addCleanup(lh.delete, ignore_permissions=True)
			return lh.name

		site_default, from_layout, explicit = make_lh(is_default=1), make_lh(), make_lh()
		pf = self._make_print_format()
		todo = self._make_todo()

		def resolved(**kwargs):
			return (PrintFormatGenerator(pf.name, todo, **kwargs).letterhead or {}).get("name")

		# nothing named anywhere: the site default, as templates do
		self.assertEqual(resolved(no_letterhead=0), site_default)
		self.assertIsNone(resolved(no_letterhead=1))

		# the document's own field outranks the site default
		todo.letter_head = from_layout
		self.assertEqual(resolved(no_letterhead=0), from_layout)
		todo.letter_head = None

		# a layout that names one outranks the document
		layout = json.loads(pf.format_data)
		layout["letter_head"] = from_layout
		pf.db_set("format_data", json.dumps(layout), update_modified=False)
		frappe.clear_cache()
		self.assertEqual(resolved(no_letterhead=0), from_layout)

		# an explicit argument outranks everything, and "no" still wins
		self.assertEqual(resolved(letterhead=explicit, no_letterhead=0), explicit)
		self.assertIsNone(resolved(letterhead=explicit, no_letterhead=1))

		# a deleted letter head degrades instead of raising
		todo.letter_head = "_Test LH Deleted"
		layout.pop("letter_head")
		pf.db_set("format_data", json.dumps(layout), update_modified=False)
		frappe.clear_cache()
		self.assertIsNone(resolved(no_letterhead=0))

	def test_download_pdf_without_format_uses_the_doctype_default(self):
		"""An omitted print_format means the doctype's default, matching
		frappe.utils.print_format.download_pdf; "Standard" means the built-in one."""
		from unittest.mock import patch

		from frappe.custom.doctype.property_setter.property_setter import make_property_setter
		from frappe.utils.print_format_generator import PrintFormatGenerator, download_pdf

		todo = self._make_todo()
		classic = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Test Default Classic {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"custom_format": 1,
				"html": "<div>classic</div>",
			}
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", classic.name, force=True)
		ps = make_property_setter(
			"ToDo", None, "default_print_format", classic.name, "Data", for_doctype=True
		)
		self.addCleanup(frappe.delete_doc, "Property Setter", ps.name, force=True)
		self.addCleanup(frappe.clear_cache, doctype="ToDo")
		frappe.clear_cache(doctype="ToDo")

		with patch("frappe.utils.print_format.download_pdf") as jinja:
			download_pdf("ToDo", todo.name)
		self.assertEqual(jinja.call_args.kwargs["format"], classic.name)

		with (
			patch("frappe.utils.print_format.download_pdf") as jinja,
			patch.object(PrintFormatGenerator, "render_pdf", return_value=b""),
		):
			download_pdf("ToDo", todo.name, print_format="Standard")
		jinja.assert_not_called()

	def test_section_justify_only_emits_known_modes(self):
		"""justify names a CSS class, so a layout can't smuggle markup through it."""
		from frappe.utils.print_format_generator import get_html

		layout = {
			"sections": [
				{"justify": 'x" onmouseover="alert(1)', "columns": [{"fields": []}]},
				{
					"justify": "space-between",
					"columns": [{"fields": [{"fieldtype": "Data", "fieldname": "description"}]}],
				},
			],
			"header": {"justify": 'x" onmouseover="alert(1)', "columns": [{"fields": []}]},
			"footer": {"columns": [{"fields": []}]},
		}
		pf = self._make_print_format(format_data=json.dumps(layout))
		html = get_html("ToDo", self._make_todo().name, pf.name)

		self.assertNotIn("onmouseover", html)
		self.assertIn("row-col-space-between", html)

	def test_section_background_in_html(self):
		"""A section with a background color should have that style in the HTML output."""
		from frappe.utils.print_format_generator import get_html

		bg_color = "#ffe0b2"
		pf = self._make_print_format(
			format_data=json.dumps(
				{
					"sections": [
						{
							"label": "Styled",
							"background": bg_color,
							"columns": [
								{
									"fields": [
										{
											"fieldtype": "Data",
											"fieldname": "description",
											"label": "Description",
										}
									]
								}
							],
						}
					],
					"header": {"columns": [{"label": "", "fields": []}]},
					"footer": {"columns": [{"label": "", "fields": []}]},
				}
			)
		)
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn(bg_color, html)

	def test_section_padding_in_html(self):
		"""Padding set on a section should appear as an inline style in the HTML."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format(
			format_data=json.dumps(
				{
					"sections": [
						{
							"label": "Padded",
							"padding": {"top": 16, "right": 8, "bottom": 16, "left": 8},
							"columns": [
								{
									"fields": [
										{
											"fieldtype": "Data",
											"fieldname": "description",
											"label": "Description",
										}
									]
								}
							],
						}
					],
					"header": {"columns": [{"label": "", "fields": []}]},
					"footer": {"columns": [{"label": "", "fields": []}]},
				}
			)
		)
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		# Padding values must appear as inline style on the section wrapper
		self.assertIn("16px", html)

	# ------------------------------------------------------------------ #
	# Table layout (field_borders) + font size
	# ------------------------------------------------------------------ #

	def _grid_format_data(self, **section):
		return json.dumps(
			{
				"sections": [
					{
						"label": "Grid",
						"field_borders": True,
						"columns": [
							{
								"fields": [
									{"fieldtype": "Data", "fieldname": "description", "label": "Description"}
								]
							}
						],
						**section,
					}
				],
				"header": {"columns": [{"label": "", "fields": []}]},
				"footer": {"columns": [{"label": "", "fields": []}]},
			}
		)

	def test_field_borders_renders_grid_class(self):
		"""A section with field_borders should render the section--grid class."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format(format_data=self._grid_format_data())
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn("section--grid", html)

	def test_field_borders_renders_cell_padding_var(self):
		"""cell_padding on a grid section should render the --pfb-cell-pad CSS variable."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format(format_data=self._grid_format_data(cell_padding=12))
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn("--pfb-cell-pad:12px", html)

	def test_font_size_rendered_as_px(self):
		"""font_size should be rendered in px so the print output matches the builder preview."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format(font_size=18)
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn("font-size: 18px", html)

	def test_section_style_is_escaped(self):
		"""A crafted section background must be escaped so it cannot break out of the style attribute."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format(
			format_data=self._grid_format_data(field_borders=False, background='red;"><b>PWN</b>')
		)
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn("background:red", html)
		self.assertNotIn('"><b>PWN</b>', html)

	# ------------------------------------------------------------------ #
	# Custom style (per-component inline CSS)
	# ------------------------------------------------------------------ #

	def _custom_style_format_data(self, field_style=None, section_style=None):
		section = {
			"label": "Styled",
			"columns": [
				{
					"fields": [
						{
							"fieldtype": "Data",
							"fieldname": "description",
							"label": "Description",
							**({"custom_style": field_style} if field_style else {}),
						}
					]
				}
			],
		}
		if section_style:
			section["custom_style"] = section_style
		return json.dumps(
			{
				"sections": [section],
				"header": {"columns": [{"label": "", "fields": []}]},
				"footer": {"columns": [{"label": "", "fields": []}]},
			}
		)

	def test_custom_style_in_html(self):
		"""custom_style renders as an inline style on every component root."""
		from frappe.utils.print_format_generator import get_html

		todo = self._make_todo()

		with self.subTest("field"):
			pf = self._make_print_format(
				format_data=self._custom_style_format_data(
					field_style="border: 1px solid #123456; padding: 6px"
				)
			)
			html = get_html("ToDo", todo.name, pf.name)
			self.assertIn("border: 1px solid #123456; padding: 6px", html)

		with self.subTest("section"):
			pf = self._make_print_format(
				format_data=self._custom_style_format_data(section_style="border-radius: 9px")
			)
			html = get_html("ToDo", todo.name, pf.name)
			self.assertIn("border-radius: 9px", html)

		with self.subTest("blocks"):
			pf = self._make_print_format(
				format_data=json.dumps(
					{
						"sections": [
							{
								"label": "Blocks",
								"columns": [
									{
										"fields": [
											{
												"fieldtype": "HTML",
												"fieldname": "_html1",
												"html": "<p>hello</p>",
												"custom_style": "margin-top: 11px",
											},
											{
												"fieldtype": "Spacer",
												"fieldname": "_spacer1",
												"custom_style": "height: 33px",
											},
											{
												"fieldtype": "Divider",
												"fieldname": "_divider1",
												"custom_style": "border-bottom-color: #123456",
											},
										]
									}
								],
							}
						],
						"header": {"columns": [{"label": "", "fields": []}]},
						"footer": {"columns": [{"label": "", "fields": []}]},
					}
				)
			)
			html = get_html("ToDo", todo.name, pf.name)
			self.assertIn("margin-top: 11px", html)
			self.assertIn("height: 1em;height: 33px", html)
			self.assertIn("border-bottom-color: #123456", html)

		contact = self._make_contact_with_email()

		with self.subTest("table"):
			pf = frappe.get_doc(
				{
					"doctype": "Print Format",
					"name": f"_Test PFG Contact {frappe.generate_hash(length=6)}",
					"doc_type": "Contact",
					"print_format_builder_beta": 1,
					"custom_format": 0,
					"standard": "No",
					"format_data": json.dumps(
						{
							"sections": [
								{
									"label": "Emails",
									"columns": [
										{
											"fields": [
												{
													"fieldtype": "Table",
													"fieldname": "email_ids",
													"label": "Emails",
													"custom_style": "margin-top: 27px",
													"table_columns": [
														{
															"fieldname": "email_id",
															"label": "Email",
															"width": 100,
														}
													],
												}
											]
										}
									],
								}
							],
							"header": {"columns": [{"label": "", "fields": []}]},
							"footer": {"columns": [{"label": "", "fields": []}]},
						}
					),
				}
			)
			pf.insert(ignore_permissions=True)
			self.addCleanup(pf.delete, ignore_permissions=True)
			html = get_html("Contact", contact.name, pf.name)
			self.assertIn('style="margin-top: 27px"', html)

		with self.subTest("repeater"):
			pf = self._make_repeater_format(
				columns=[{"template": [{"t": "f", "v": "email_id"}], "align": "left"}],
				custom_style="padding: 13px",
			)
			html = get_html("Contact", contact.name, pf.name)
			self.assertIn('style="padding: 13px"', html)

	def test_custom_style_is_escaped(self):
		"""A crafted custom_style must not break out of the style attribute."""
		from frappe.utils.print_format_generator import get_html

		todo = self._make_todo()

		with self.subTest("field"):
			pf = self._make_print_format(
				format_data=self._custom_style_format_data(field_style='color:red;"><b>PWN</b>')
			)
			html = get_html("ToDo", todo.name, pf.name)
			self.assertIn("color:red", html)
			self.assertNotIn('"><b>PWN</b>', html)

		with self.subTest("section"):
			pf = self._make_print_format(
				format_data=self._custom_style_format_data(section_style='border:1px;"><b>PWN</b>')
			)
			html = get_html("ToDo", todo.name, pf.name)
			self.assertIn("border:1px", html)
			self.assertNotIn('"><b>PWN</b>', html)

	# ------------------------------------------------------------------ #
	# Label / value colors (Format settings)
	# ------------------------------------------------------------------ #

	def test_label_color_rendered_in_css(self):
		"""A label_color set on the print format emits a label color override rule."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format(label_color="#c0392b")
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn(
			".print-format-doc .field .label,\n.print-format-doc .field.left-right .label,\n.print-format-doc .field.field-inline .label {\n\tcolor: #c0392b;\n}",
			html,
		)

	def test_value_color_rendered_in_css(self):
		"""A value_color set on the print format emits a value color override rule."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format(value_color="#1a5fb4")
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn(
			".print-format-doc .field .value,\n.print-format-doc .field.left-right .value,\n.print-format-doc .field.field-inline .value {\n\tcolor: #1a5fb4;\n}",
			html,
		)

	def test_no_color_override_when_colors_unset(self):
		"""Without label/value colors, no color override rule is emitted."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format()
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertNotIn(".field.left-right .label {\n\tcolor:", html)
		self.assertNotIn(".field.left-right .value {\n\tcolor:", html)

	def test_non_hex_color_rejected(self):
		"""Colors that are not #RRGGBB hex codes are rejected on save."""
		with self.assertRaises(frappe.ValidationError):
			self._make_print_format(label_color="red; } * { display: none")

	def test_repeater_column_invalid_color_and_align_ignored(self):
		"""Repeater column color/align values outside the whitelist render nothing."""
		from frappe.utils.print_format_generator import get_html

		contact = self._make_contact_with_email()
		pf = self._make_repeater_format(
			columns=[
				{
					"template": [{"t": "f", "v": "email_id"}],
					"align": "up; position:fixed",
					"color": "red; } * { display: none",
				}
			]
		)
		html = get_html("Contact", contact.name, pf.name)
		self.assertNotIn("position:fixed", html)
		self.assertNotIn("display: none", html)
		self.assertIn('class="pfb-repeater-cell" style="text-align: left"', html)

	def test_blank_table_column_header_falls_back_to_fieldname(self):
		"""A child-table column with an empty label should render its fieldname as the header."""
		import re

		from frappe.utils.print_format_generator import get_html

		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": f"_Test PFG {frappe.generate_hash(length=6)}",
				"email_ids": [{"email_id": "pfg@example.com", "is_primary": 1}],
			}
		)
		contact.insert(ignore_permissions=True)
		self.addCleanup(contact.delete, ignore_permissions=True)

		pf = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Test PFG Contact {frappe.generate_hash(length=6)}",
				"doc_type": "Contact",
				"print_format_builder_beta": 1,
				"custom_format": 0,
				"standard": "No",
				"format_data": json.dumps(
					{
						"sections": [
							{
								"label": "Emails",
								"columns": [
									{
										"fields": [
											{
												"fieldtype": "Table",
												"fieldname": "email_ids",
												"label": "Emails",
												"table_columns": [
													{"fieldname": "email_id", "label": "", "width": 100}
												],
											}
										]
									}
								],
							}
						],
						"header": {"columns": [{"label": "", "fields": []}]},
						"footer": {"columns": [{"label": "", "fields": []}]},
					}
				),
			}
		)
		pf.insert(ignore_permissions=True)
		self.addCleanup(pf.delete, ignore_permissions=True)

		html = get_html("Contact", contact.name, pf.name)
		self.assertRegex(html, r"email_id\s*</th>")

	# ------------------------------------------------------------------ #
	# Repeater block
	# ------------------------------------------------------------------ #

	def _make_contact_with_email(self):
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": f"_Test PFG {frappe.generate_hash(length=6)}",
				"email_ids": [{"email_id": "pfg@example.com", "is_primary": 1}],
			}
		)
		contact.insert(ignore_permissions=True)
		self.addCleanup(contact.delete, ignore_permissions=True)
		return contact

	def _make_repeater_format(
		self, label="", columns=None, omit_repeater_columns=False, section_label="", **field_extra
	):
		name = f"_Test PFG Rep {frappe.generate_hash(length=6)}"
		repeater_field = {
			"fieldtype": "Repeater",
			"fieldname": "rep1",
			"label": label,
			"source": "email_ids",
			**field_extra,
		}
		if not omit_repeater_columns:
			repeater_field["repeater_columns"] = columns or []
		pf = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": name,
				"doc_type": "Contact",
				"print_format_builder_beta": 1,
				"custom_format": 0,
				"standard": "No",
				"format_data": json.dumps(
					{
						"sections": [
							{
								"label": section_label,
								"columns": [{"fields": [repeater_field]}],
							}
						],
						"header": {"columns": [{"label": "", "fields": []}]},
						"footer": {"columns": [{"label": "", "fields": []}]},
					}
				),
			}
		)
		pf.insert(ignore_permissions=True)
		self.addCleanup(pf.delete, ignore_permissions=True)
		return pf

	def test_labeled_section_with_only_repeater(self):
		"""A labeled section whose only field is a repeater renders when the source
		has rows and stays hidden when it does not."""
		from frappe.utils.print_format_generator import get_html

		contact = self._make_contact_with_email()

		with self.subTest("renders when source has rows"):
			pf = self._make_repeater_format(
				columns=[{"template": [{"t": "f", "v": "email_id"}], "align": "left"}],
				section_label="Emails Section",
			)
			html = get_html("Contact", contact.name, pf.name)
			self.assertIn("Emails Section", html)
			self.assertIn('<div class="pfb-repeater"', html)

		with self.subTest("hidden when source is empty"):
			pf = self._make_repeater_format(
				columns=[{"template": [{"t": "f", "v": "number"}], "align": "left"}],
				section_label="Phones Section",
				source="phone_nos",
			)
			html = get_html("Contact", contact.name, pf.name)
			self.assertNotIn("Phones Section", html)

	def test_repeater_renders_templated_rows(self):
		"""A repeater renders each child row via its column token templates."""
		from frappe.utils.print_format_generator import get_html

		contact = self._make_contact_with_email()
		pf = self._make_repeater_format(
			columns=[
				{
					"template": [{"t": "s", "v": "Email: "}, {"t": "f", "v": "email_id"}],
					"align": "left",
				}
			]
		)
		html = get_html("Contact", contact.name, pf.name)
		self.assertIn("pfb-repeater", html)
		self.assertIn("Email: pfg@example.com", html)

	def test_repeater_no_title_when_label_blank(self):
		"""A repeater with a blank label renders no title element."""
		from frappe.utils.print_format_generator import get_html

		contact = self._make_contact_with_email()
		pf = self._make_repeater_format(
			label="", columns=[{"template": [{"t": "f", "v": "email_id"}], "align": "left"}]
		)
		html = get_html("Contact", contact.name, pf.name)
		self.assertNotIn('<div class="label">', html)

	def test_repeater_with_missing_columns_key_does_not_crash(self):
		"""A repeater whose source is set but with no repeater_columns key must not raise."""
		from frappe.utils.print_format_generator import get_html

		contact = self._make_contact_with_email()
		pf = self._make_repeater_format(omit_repeater_columns=True)
		html = get_html("Contact", contact.name, pf.name)
		self.assertIn("pfb-repeater", html)

	def test_repeater_column_values_are_escaped(self):
		"""A crafted column align/text token must be escaped so it cannot inject markup."""
		from frappe.utils.print_format_generator import get_html

		contact = self._make_contact_with_email()
		pf = self._make_repeater_format(
			columns=[
				{
					"template": [{"t": "s", "v": '"><b>PWN</b>'}],
					"align": '"><b>PWN</b>',
				}
			]
		)
		html = get_html("Contact", contact.name, pf.name)
		self.assertNotIn('"><b>PWN</b>', html)

	def test_repeater_column_width_rendered(self):
		"""A repeater column width emits a colgroup <col> with a width percentage."""
		from frappe.utils.print_format_generator import get_html

		contact = self._make_contact_with_email()
		pf = self._make_repeater_format(
			columns=[
				{"template": [{"t": "f", "v": "email_id"}], "align": "left", "width": 40},
				{"template": [{"t": "f", "v": "email_id"}], "align": "left"},
			]
		)
		html = get_html("Contact", contact.name, pf.name)
		self.assertIn("<colgroup>", html)
		self.assertIn("width: 40%", html)

	def test_repeater_column_color_rendered(self):
		"""A repeater column color is rendered as an inline color on the cell."""
		from frappe.utils.print_format_generator import get_html

		contact = self._make_contact_with_email()
		pf = self._make_repeater_format(
			columns=[{"template": [{"t": "f", "v": "email_id"}], "align": "left", "color": "#C0392B"}]
		)
		html = get_html("Contact", contact.name, pf.name)
		self.assertIn('style="text-align: left; color: #C0392B"', html)

	def test_repeater_column_no_color_when_unset(self):
		"""A repeater column without a color emits no inline color on the cell."""
		from frappe.utils.print_format_generator import get_html

		contact = self._make_contact_with_email()
		pf = self._make_repeater_format(
			columns=[{"template": [{"t": "f", "v": "email_id"}], "align": "left"}]
		)
		html = get_html("Contact", contact.name, pf.name)
		self.assertIn('class="pfb-repeater-cell" style="text-align: left"', html)

	# ------------------------------------------------------------------ #
	# Field orientation / spacing
	# ------------------------------------------------------------------ #

	def test_left_right_field_gets_justify_class(self):
		"""A left-right field with label_justify emits the field-justify-* class."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format(
			format_data=json.dumps(
				{
					"sections": [
						{
							"label": "",
							"field_orientation": "left-right",
							"columns": [
								{
									"fields": [
										{
											"fieldtype": "Data",
											"fieldname": "description",
											"label": "Desc",
											"label_justify": "space-between",
										}
									]
								}
							],
						}
					],
					"header": {"columns": [{"label": "", "fields": []}]},
					"footer": {"columns": [{"label": "", "fields": []}]},
				}
			)
		)
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn("field-justify-space-between", html)

	def test_top_orientation_field_is_not_inline(self):
		"""A default (Top) field is not rendered inline — no left-right/field-inline class."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format()
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		body = html.split("<body", 1)[1]
		self.assertNotIn("field-justify-", body)
		self.assertNotIn("field left-right", body)

	# ------------------------------------------------------------------ #
	# draft / cancelled heading + docstatus guard (new renderer)
	# ------------------------------------------------------------------ #

	def _make_submittable_doc(self, target_docstatus=0):
		"""Create a submittable doctype + one document at the requested docstatus."""
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		dt = new_doctype(
			is_submittable=1,
			fields=[{"label": "Title", "fieldname": "title", "fieldtype": "Data"}],
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "DocType", dt.name, force=1)

		doc = frappe.new_doc(dt.name)
		doc.title = "Doc Title"
		doc.insert(ignore_permissions=True)
		if target_docstatus >= 1:
			doc.submit()
		if target_docstatus == 2:
			doc.cancel()
		return doc

	def _render_standard(self, doc):
		from frappe.www.printview import get_html_and_style

		return get_html_and_style(doc=doc.as_json(), print_format="Standard", no_letterhead=1)["html"] or ""

	def test_draft_heading_rendered(self):
		"""A draft submittable document prints the DRAFT heading."""
		with self.change_settings("Print Settings", allow_print_for_draft=1, add_draft_heading=1):
			html = self._render_standard(self._make_submittable_doc(0))
		self.assertIn('document-status="draft"', html)

	def test_draft_heading_suppressed_by_print_setting(self):
		"""add_draft_heading=0 hides the DRAFT heading even for a draft document."""
		with self.change_settings("Print Settings", allow_print_for_draft=1, add_draft_heading=0):
			html = self._render_standard(self._make_submittable_doc(0))
		# bare "document-status" also matches the CSS selector, so assert on the banner markup
		self.assertNotIn('document-status="draft"', html)

	def test_cancelled_heading_rendered(self):
		"""A cancelled document prints the CANCELLED heading (not gated by a setting)."""
		with self.change_settings("Print Settings", allow_print_for_cancelled=1):
			html = self._render_standard(self._make_submittable_doc(2))
		self.assertIn('document-status="cancelled"', html)

	def test_submitted_doc_has_no_status_heading(self):
		"""A submitted document has neither DRAFT nor CANCELLED heading."""
		html = self._render_standard(self._make_submittable_doc(1))
		self.assertNotIn('document-status="draft"', html)
		self.assertNotIn('document-status="cancelled"', html)

	def test_draft_print_blocked_when_not_allowed(self):
		"""The new renderer enforces the draft-print guard on the beta path."""
		with self.change_settings("Print Settings", allow_print_for_draft=0):
			doc = self._make_submittable_doc(0)
			self.assertRaises(frappe.PermissionError, self._render_standard, doc)

	def test_download_pdf_blocked_for_draft(self):
		"""download_pdf refuses to render a draft when printing drafts is disallowed."""
		from frappe.utils.print_format_generator import download_pdf

		with self.change_settings("Print Settings", allow_print_for_draft=0):
			doc = self._make_submittable_doc(0)
			self.assertRaises(frappe.PermissionError, download_pdf, doc.doctype, doc.name, "Standard")

	def test_get_html_blocks_draft(self):
		"""get_html (the printview / printpreview render path) enforces the draft guard."""
		from frappe.utils.print_format_generator import get_html

		with self.change_settings("Print Settings", allow_print_for_draft=0):
			doc = self._make_submittable_doc(0)
			self.assertRaises(frappe.PermissionError, get_html, doc.doctype, doc.name, "Standard")

	def test_attach_print_beta_blocks_draft(self):
		"""attach_print's beta branch enforces the draft guard before rendering."""
		doc = self._make_submittable_doc(0)
		pf = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Test PFG Sub {frappe.generate_hash(length=6)}",
				"doc_type": doc.doctype,
				"print_format_builder_beta": 1,
				"custom_format": 0,
				"standard": "No",
				"format_data": json.dumps(
					{
						"sections": [
							{
								"label": "",
								"columns": [
									{"label": "", "fields": [{"fieldtype": "Data", "fieldname": "title"}]}
								],
							}
						],
						"header": {"columns": [{"label": "", "fields": []}]},
						"footer": {"columns": [{"label": "", "fields": []}]},
					}
				),
			}
		).insert(ignore_permissions=True)
		self.addCleanup(pf.delete, ignore_permissions=True)
		with self.change_settings("Print Settings", allow_print_for_draft=0, send_print_as_pdf=1):
			self.assertRaises(
				frappe.PermissionError, frappe.attach_print, doc.doctype, doc.name, print_format=pf.name
			)

	# ------------------------------------------------------------------ #
	# empty child-table column pruning (new renderer)
	# ------------------------------------------------------------------ #

	def test_empty_child_table_columns_pruned(self):
		"""Columns blank in every row are dropped; populated columns are kept."""
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		child = new_doctype(
			istable=1,
			fields=[
				{"label": "Col A", "fieldname": "col_a", "fieldtype": "Data"},
				{"label": "Col B", "fieldname": "col_b", "fieldtype": "Data"},
			],
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "DocType", child.name, force=1)

		parent = new_doctype(
			fields=[{"label": "Items", "fieldname": "items", "fieldtype": "Table", "options": child.name}],
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "DocType", parent.name, force=1)

		doc = frappe.new_doc(parent.name)
		doc.append("items", {"col_a": "filled", "col_b": ""})
		doc.append("items", {"col_a": "more", "col_b": ""})
		doc.insert(ignore_permissions=True)

		html = self._render_standard(doc)
		self.assertIn("Col A", html)
		self.assertNotIn("Col B", html)

	def test_show_label_colon_setting(self):
		"""Print Format ▸ show_label_colon toggles the classic colon body class."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format()
		todo = self._make_todo()

		body = get_html("ToDo", todo.name, pf.name).split("<body", 1)[1][:200]
		self.assertNotIn("show-label-colon", body)

		pf.db_set("show_label_colon", 1)
		body = get_html("ToDo", todo.name, pf.name).split("<body", 1)[1][:200]
		self.assertIn("show-label-colon", body)

	def test_show_label_colon_is_per_format(self):
		"""One format opting in must not put colons on another."""
		from frappe.utils.print_format_generator import get_html

		plain = self._make_print_format()
		with_colon = self._make_print_format(show_label_colon=1)
		todo = self._make_todo()

		self.assertIn(
			"show-label-colon", get_html("ToDo", todo.name, with_colon.name).split("<body", 1)[1][:200]
		)
		self.assertNotIn(
			"show-label-colon", get_html("ToDo", todo.name, plain.name).split("<body", 1)[1][:200]
		)

	# ------------------------------------------------------------------ #
	# repeating letterhead header / footer (repeat_header_footer setting)
	# ------------------------------------------------------------------ #

	def _make_letterhead(self):
		"""Create a Letter Head with distinct header + footer markers."""
		lh = frappe.get_doc(
			{
				"doctype": "Letter Head",
				"letter_head_name": f"_Test PFG LH {frappe.generate_hash(length=6)}",
				"source": "HTML",
				"content": '<div class="pfg-lh">LETTERHEAD_TOP</div>',
				"footer": '<div class="pfg-lf">LETTERHEAD_BOTTOM</div>',
			}
		)
		lh.insert(ignore_permissions=True)
		self.addCleanup(lh.delete, ignore_permissions=True)
		return lh

	def test_repeat_header_footer_on_repeats_letterhead_every_page(self):
		"""With repeat_header_footer enabled, the letterhead header and footer are placed
		in the #header-html / #footer-html overlay divs that Chrome stamps on every page,
		and are NOT also rendered inline in the body (which would appear once only)."""
		from frappe.utils.print_format_generator import PrintFormatGenerator

		lh = self._make_letterhead()
		pf = self._make_print_format()
		todo = self._make_todo()

		with self.change_settings("Print Settings", repeat_header_footer=1):
			gen = PrintFormatGenerator(pf.name, todo, lh.name)
			gen._build_html_for_chrome()

		self.assertIn('id="header-html"', gen.context.header)
		self.assertIn("LETTERHEAD_TOP", gen.context.header)
		self.assertIn('id="footer-html"', gen.context.footer)
		self.assertIn("LETTERHEAD_BOTTOM", gen.context.footer)
		self.assertEqual(gen.context.chrome_layout_header, "")
		self.assertEqual(gen.context.chrome_layout_footer, "")

	def test_repeat_header_footer_off_renders_letterhead_once(self):
		"""With repeat_header_footer disabled, the letterhead header renders inline once
		(top of body → first page) and the footer inline once (end of body → last page);
		neither goes into the repeating #header-html / #footer-html overlay."""
		from frappe.utils.print_format_generator import PrintFormatGenerator

		lh = self._make_letterhead()
		pf = self._make_print_format()
		todo = self._make_todo()

		with self.change_settings("Print Settings", repeat_header_footer=0):
			gen = PrintFormatGenerator(pf.name, todo, lh.name)
			gen._build_html_for_chrome()

		self.assertIn("LETTERHEAD_TOP", gen.context.chrome_layout_header)
		self.assertIn("LETTERHEAD_BOTTOM", gen.context.chrome_layout_footer)
		self.assertNotIn("LETTERHEAD_TOP", gen.context.header or "")
		self.assertNotIn("LETTERHEAD_BOTTOM", gen.context.footer or "")

	def test_browser_print_wraps_letterhead_in_repeating_frame(self):
		"""With repeat_header_footer on, the browser-print HTML wraps the body in a
		thead/tfoot table (display: table-header-group) so the browser reprints the
		letterhead header in the thead and footer in the tfoot on every page."""
		from frappe.utils.print_format_generator import get_html

		lh = self._make_letterhead()
		pf = self._make_print_format()
		todo = self._make_todo()
		with self.change_settings("Print Settings", repeat_header_footer=1):
			html = get_html("ToDo", todo.name, pf.name, lh.name)

		self.assertIn("print-repeating-frame", html)
		self.assertIn("table-header-group", html)
		# header must sit inside <thead>, footer inside <tfoot> (so the browser repeats them)
		thead = html.split("<thead>", 1)[1].split("</thead>", 1)[0]
		tfoot = html.split("<tfoot>", 1)[1].split("</tfoot>", 1)[0]
		self.assertIn("LETTERHEAD_TOP", thead)
		self.assertNotIn("LETTERHEAD_BOTTOM", thead)
		self.assertIn("LETTERHEAD_BOTTOM", tfoot)

	def test_empty_beta_format_renders_via_beta_renderer(self):
		"""A beta format with empty format_data must route to the beta renderer, not
		fall through to the removed classic standard.html and raise
		TemplateNotFoundError."""
		from frappe.printing.doctype.print_format.classic_converter import uses_beta_renderer
		from frappe.utils.print_format_generator import get_html

		todo = self._make_todo()
		pf = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Test PFG Empty {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": "",
			}
		).insert()
		self.addCleanup(pf.delete, ignore_permissions=True)

		self.assertTrue(pf.print_format_builder_beta)
		self.assertFalse(pf.format_data)
		self.assertTrue(uses_beta_renderer(pf))
		html = get_html("ToDo", todo.name, pf.name)
		self.assertIn("print-format-doc", html)

	def test_new_format_is_seeded_with_the_default_layout(self):
		"""Nothing should print blank before its first Save & Apply."""
		from frappe.printing.doctype.print_format.print_format import create_custom_format

		pf = create_custom_format("ToDo", f"_Test PFG Seeded {frappe.generate_hash(length=6)}")
		self.addCleanup(pf.delete, ignore_permissions=True)
		self.assertTrue(frappe.parse_json(pf.format_data).get("sections"))

	def test_browser_print_no_repeating_frame_when_off(self):
		"""With repeat_header_footer off, the browser-print HTML is not wrapped in the
		repeating table — the letterhead renders inline once."""
		from frappe.utils.print_format_generator import get_html

		lh = self._make_letterhead()
		pf = self._make_print_format()
		todo = self._make_todo()
		with self.change_settings("Print Settings", repeat_header_footer=0):
			html = get_html("ToDo", todo.name, pf.name, lh.name)

		self.assertNotIn("print-repeating-frame", html)
		self.assertIn("LETTERHEAD_TOP", html)

	def _user_beta_format(self, layout, skip_validation=False):
		import json

		pf = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Test PFG {frappe.generate_hash(length=6)}",
				"doc_type": "User",
				"print_format_builder_beta": 1,
				"custom_format": 0,
				"standard": "No",
				"format_data": json.dumps(layout),
			}
		)
		if skip_validation:
			pf.flags.ignore_validate = True
		pf.insert(ignore_permissions=True)
		self.addCleanup(pf.delete, ignore_permissions=True)
		return pf

	def test_repeater_row_condition_filters_rows(self):
		"""A repeater row_condition drops rows where it is falsy; a bad expression
		fails open so a typo never blanks the table."""
		import re

		from frappe.utils.print_format_generator import PrintFormatGenerator

		user = frappe.get_doc("User", "Administrator")
		n = len(user.roles)
		self.assertGreaterEqual(n, 2)

		def rows_for(condition, skip_validation=False):
			df = {
				"fieldtype": "Repeater",
				"fieldname": "_rep",
				"label": "Roles",
				"custom": 1,
				"source": "roles",
				"repeater_columns": [{"template": [{"t": "f", "v": "role"}], "align": "left"}],
			}
			if condition is not None:
				df["row_condition"] = condition
			layout = {
				"sections": [{"label": "", "columns": [{"label": "", "fields": [df]}]}],
				"header": {"columns": [{"label": "", "fields": []}]},
				"footer": {"columns": [{"label": "", "fields": []}]},
			}
			pf = self._user_beta_format(layout, skip_validation=skip_validation)
			html = PrintFormatGenerator(pf, user).get_html_preview()
			block = re.search(r"pfb-repeater-table.*?</table>", html, re.S)
			return len(re.findall(r"<tr>", block.group(0))) if block else 0

		self.assertEqual(rows_for(None), n)
		self.assertEqual(rows_for("row.idx == 1"), 1)
		self.assertEqual(rows_for("False"), 0)
		self.assertEqual(rows_for("this is (( invalid", skip_validation=True), n)
		# print_settings is in scope alongside doc/row
		with self.change_settings("Print Settings", pdf_page_size="A4"):
			self.assertEqual(rows_for("print_settings.pdf_page_size == 'A4'"), n)
			self.assertEqual(rows_for("print_settings.pdf_page_size == 'Letter'"), 0)

	def test_merged_column_direction_emits_class(self):
		"""A merged table column renders .cell-lines--horizontal only when
		merge_direction is 'horizontal'."""
		import re

		from frappe.utils.print_format_generator import PrintFormatGenerator

		user = frappe.get_doc("User", "Administrator")

		def html_for(direction):
			column = {
				"fieldname": "role",
				"fieldtype": "Data",
				"label": "Role",
				"width": 100,
				"merged_fields": [{"fieldname": "role", "fieldtype": "Data", "style": "secondary"}],
			}
			if direction:
				column["merge_direction"] = direction
			layout = {
				"sections": [
					{
						"label": "",
						"columns": [
							{
								"label": "",
								"fields": [
									{
										"fieldtype": "Table",
										"fieldname": "roles",
										"label": "Roles",
										"custom": 1,
										"table_columns": [column],
									}
								],
							}
						],
					}
				],
				"header": {"columns": [{"label": "", "fields": []}]},
				"footer": {"columns": [{"label": "", "fields": []}]},
			}
			return PrintFormatGenerator(self._user_beta_format(layout), user).get_html_preview()

		def cell_lines_class(html):
			# Match the markup, not the .cell-lines--horizontal rule in the embedded stylesheet.
			match = re.search(r'<div class="(cell-lines[^"]*)"', html)
			return match.group(1) if match else ""

		self.assertEqual(cell_lines_class(html_for("horizontal")), "cell-lines cell-lines--horizontal")
		self.assertEqual(cell_lines_class(html_for("vertical")), "cell-lines")
		self.assertEqual(cell_lines_class(html_for(None)), "cell-lines")

	def test_settings_override_does_not_persist(self):
		"""A print-preview settings override (limited to the doctype's own print toggles)
		changes the print_settings the generator renders with, but never writes back to
		the saved single; keys outside the allowlist are ignored."""
		from frappe.utils.print_format_generator import PrintFormatGenerator

		pf = self._make_print_format()
		todo = self._make_todo()
		todo.get_print_settings = lambda: ["repeat_header_footer"]
		saved = frappe.db.get_single_value("Print Settings", "repeat_header_footer")
		saved_draft = frappe.db.get_single_value("Print Settings", "allow_print_for_draft")
		flipped = 0 if saved else 1

		generator = PrintFormatGenerator(
			pf, todo, settings={"repeat_header_footer": flipped, "allow_print_for_draft": 1}
		)
		self.assertEqual(generator.print_settings.repeat_header_footer, flipped)
		self.assertEqual(generator.print_settings.allow_print_for_draft, saved_draft)
		self.assertEqual(frappe.db.get_single_value("Print Settings", "repeat_header_footer"), saved)

	def test_print_settings_override_allowlist(self):
		"""get_allowed_print_settings_override keeps only fields the doctype exposes."""
		from frappe.www.printview import get_allowed_print_settings_override

		todo = self._make_todo()
		self.assertEqual(get_allowed_print_settings_override(todo, None), {})
		self.assertEqual(get_allowed_print_settings_override(todo, {"repeat_header_footer": 1}), {})

		todo.get_print_settings = lambda: ["repeat_header_footer"]
		self.assertEqual(
			get_allowed_print_settings_override(
				todo, {"repeat_header_footer": 1, "allow_print_for_draft": 1}
			),
			{"repeat_header_footer": 1},
		)

	def test_settings_override_reaches_pdf_download(self):
		"""render_pdf (the PDF download path) renders with the overridden print_settings,
		so a print-preview toggle carries into the downloaded file too."""
		from unittest.mock import patch

		from frappe.utils.print_format_generator import PrintFormatGenerator

		pf = self._make_print_format()
		todo = self._make_todo()
		todo.get_print_settings = lambda: ["repeat_header_footer"]
		generator = PrintFormatGenerator(pf, todo, settings={"repeat_header_footer": 1})

		with patch("frappe.utils.pdf.get_chrome_pdf", return_value=b"%PDF-"):
			generator.render_pdf()
		self.assertEqual(generator.print_settings.repeat_header_footer, 1)
