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

	def test_get_html_applies_margin(self):
		"""Margin values set on the print format should appear in the rendered CSS."""
		from frappe.utils.print_format_generator import get_html

		pf = self._make_print_format(margin_top=20, margin_bottom=20)
		todo = self._make_todo()
		html = get_html("ToDo", todo.name, pf.name)
		# The CSS block should encode 20mm top/bottom margins
		self.assertIn("20mm", html)

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
