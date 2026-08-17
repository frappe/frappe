# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Parity guards between the two print surfaces.

The builder canvas (Vue) and the server render (Jinja) share one stylesheet
(templates/print_format/print_format_doc.css) and must emit the same markup
language: same class names, same data attributes, same inline-style inputs.
These tests fail when one surface learns a word the other doesn't know.
"""

import functools
import json
import re
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

APP_PATH = Path(frappe.get_app_path("frappe"))
SHARED_CSS = APP_PATH / "templates" / "print_format" / "print_format_doc.css"

SERVER_SOURCES = [
	APP_PATH / "templates" / "print_format" / "print_format.html",
	APP_PATH / "templates" / "print_format" / "print_format.css",
	APP_PATH / "templates" / "print_format" / "print_header.html",
	APP_PATH / "templates" / "print_format" / "print_footer.html",
	APP_PATH / "templates" / "print_format" / "macros.html",
	*sorted((APP_PATH / "templates" / "print_format" / "macros").glob("*.html")),
	APP_PATH / "templates" / "print_formats" / "chrome_pdf_header_footer.html",
]

BUILDER_DIR = APP_PATH / "public" / "js" / "print_format_builder"
# utils.js holds class names the components render from, so it speaks the markup too
CANVAS_SOURCES = [*sorted(BUILDER_DIR.rglob("*.vue")), BUILDER_DIR / "utils.js"]

# Classes that legitimately exist on only one surface.
SERVER_ONLY_CLASSES = {
	# letterhead HTML is user-authored and rendered server-side only
	"letter-head",
	# per-section "keep together" is page-break-inside:avoid — a pure pagination
	# concern with no effect on the non-paginated canvas, so it's print-only
	"keep-together",
	# per-section "page break" is page-break-after:always — likewise pagination-only;
	# the canvas renders a separate .page-break-indicator element, not this class
	"page-break",
}
CANVAS_ONLY_CLASSES = set()


@functools.cache
def _server_text():
	return "\n".join(p.read_text() for p in SERVER_SOURCES)


@functools.cache
def _canvas_text():
	return "\n".join(p.read_text() for p in CANVAS_SOURCES)


@functools.cache
def _field_vue_text():
	return (BUILDER_DIR / "components" / "editor" / "Field.vue").read_text()


@functools.cache
def _canvas_logic_text():
	"""The preview surface that reads df.* — Field.vue dispatches to the
	FieldPreview* components, which lean on the composables; a df prop handled
	in any of them is mirrored, so the check spans .vue markup + composables."""
	js = "\n".join(p.read_text() for p in sorted((BUILDER_DIR / "composables").glob("*.js")))
	return _canvas_text() + "\n" + js


@functools.cache
def _shared_css_selector_tokens():
	"""Class names and data-* attributes used by the shared stylesheet's selectors."""
	css = SHARED_CSS.read_text()
	css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
	selectors = " ".join(re.findall(r"(?:^|})([^{}@]*?){", css, flags=re.S))
	classes = set(re.findall(r"\.([A-Za-z][\w-]*)", selectors))
	data_attrs = set(re.findall(r"\[(data-[\w-]+)", selectors))
	classes.discard("print-format-doc")  # the scope itself is asserted separately
	return classes, data_attrs


# Variant suffixes interpolated from field properties on both surfaces
VARIANT_PREFIXES = (
	"child-table--",
	"field-align-",
	"field-justify-",
	"cell-line--",
	"section--grid-",
)


def _present(token, haystack):
	if token in haystack:
		return True
	return any(token.startswith(p) and p in haystack for p in VARIANT_PREFIXES)


class TestPrintSurfaceMarkupContract(UnitTestCase):
	def test_shared_stylesheet_classes_exist_on_both_surfaces(self):
		classes, data_attrs = _shared_css_selector_tokens()
		server = _server_text()
		canvas = _canvas_text()

		missing_server = sorted(
			t for t in classes | data_attrs if t not in CANVAS_ONLY_CLASSES and not _present(t, server)
		)
		missing_canvas = sorted(
			t for t in classes | data_attrs if t not in SERVER_ONLY_CLASSES and not _present(t, canvas)
		)

		self.assertFalse(
			missing_server,
			f"print_format_doc.css styles {missing_server}, but no server template emits them. "
			"Either emit them in templates/print_format/ or add them to CANVAS_ONLY_CLASSES "
			"with a comment saying why the PDF render can never produce them.",
		)
		self.assertFalse(
			missing_canvas,
			f"print_format_doc.css styles {missing_canvas}, but the builder canvas never emits them. "
			"Either emit them in public/js/print_format_builder/ (preview mode must mirror the "
			"server markup) or add them to SERVER_ONLY_CLASSES with a comment saying why.",
		)

	def test_scope_class_applied_on_both_surfaces(self):
		self.assertIn("print-format-doc", _server_text())
		self.assertIn("print-format-doc", _canvas_text())

	def test_bordered_child_table_bottom_edge_owned_by_the_foot_cap(self):
		"""A bordered child table closes its outline through the repeating
		.table-foot cap, never through the last body row. This has regressed
		several times, each time by changing one of the three rules below in
		isolation, so they are pinned together:

		* the cap draws border-bottom -> every page the table spans is closed,
		  not just the final one;
		* no body row draws border-bottom -> the last page isn't doubled;
		* the cap is radius-tall and its outer cells carry the rounded corners
		  -> the curve has room (and collapses to nothing at radius 0);
		* the cap is one cell per column, each drawing border-right -> the
		  column dividers reach the closing line instead of stopping short.
		"""
		css = re.sub(r"/\*.*?\*/", "", SHARED_CSS.read_text(), flags=re.S)

		def block(selector):
			match = re.search(
				re.escape(selector) + r"\s*\{(.*?)\}",
				css,
				flags=re.S,
			)
			self.assertIsNotNone(match, f"missing rule for {selector}")
			return match.group(1)

		cap = block(".print-format-doc .child-table--bordered .table .table-foot")
		self.assertIn("border-bottom:", cap)
		self.assertIn("border-right:", cap)

		first = block(".print-format-doc .child-table--bordered .table .table-foot:first-child")
		self.assertIn("border-left:", first)
		self.assertIn("border-bottom-left-radius: var(--pfb-radius", first)

		last = block(".print-format-doc .child-table--bordered .table .table-foot:last-child")
		self.assertIn("border-bottom-right-radius: var(--pfb-radius", last)

		geometry = block(".print-format-doc .child-table .table .table-foot")
		self.assertIn("height: var(--pfb-radius", geometry)

		# nothing may re-close the outline on the last body row
		self.assertNotRegex(
			css,
			r"\.child-table--bordered[^{}]*tbody\s+tr:last-child\s+td\s*\{[^}]*border-bottom:\s*1px",
		)

		# a single colspan cap cell has no interior edges to carry the dividers
		for source in (
			APP_PATH / "templates" / "print_format" / "macros" / "Table.html",
			BUILDER_DIR / "components" / "editor" / "FieldPreviewTable.vue",
		):
			foot = re.search(r"<tfoot>(.*?)</tfoot>", source.read_text(), flags=re.S).group(1)
			self.assertNotIn("colspan", foot, f"{source.name}: cap must be one cell per column")

	def test_canvas_table_body_holds_only_data_rows(self):
		"""The shared stylesheet decides where a table's bottom edge lives with
		`tbody tr:last-child`. The canvas used to append its "No rows" / "+N more
		rows" note as a <tr> inside <tbody>, so the note became the last row and the
		real last row kept a border the print surface drops -- a preview-only border
		break that survived four fixes because every fix was made against the server
		markup. Notes render after </table>; <tbody> carries data rows only.
		"""
		self.assertRegex(SHARED_CSS.read_text(), r"tbody\s+tr:last-child\s+td")

		for source in (
			BUILDER_DIR / "components" / "editor" / "FieldPreviewTable.vue",
			BUILDER_DIR / "components" / "editor" / "FieldPreviewRepeater.vue",
		):
			text = source.read_text()
			body = re.search(r"<tbody>(.*?)</tbody>", text, flags=re.S).group(1)
			rows = re.findall(r"<tr\b[^>]*>", body)
			self.assertEqual(len(rows), 1, f"{source.name}: <tbody> must hold only the data row")
			self.assertIn("v-for", rows[0], f"{source.name}: the <tbody> row must be the data row")
			self.assertNotIn("pfb-table-note", body, f"{source.name}: row notes belong outside the table")
			self.assertIn("pfb-table-note", text, f"{source.name}: the note itself must survive")

	def test_data_html_field_properties_mirrored_in_canvas(self):
		"""Every df.* property the regular-field macro reads must be handled by Field.vue."""
		self._assert_df_props_mirrored(APP_PATH / "templates" / "print_format" / "macros" / "Data.html")

	def test_table_macro_properties_mirrored_in_canvas(self):
		"""Every df.* property the child-table macro reads (cell padding, border
		colour, header background, ...) must be handled by Field.vue — these are
		inline styles, so the stylesheet can't catch drift here."""
		self._assert_df_props_mirrored(APP_PATH / "templates" / "print_format" / "macros" / "Table.html")

	def test_repeater_macro_properties_mirrored_in_canvas(self):
		self._assert_df_props_mirrored(APP_PATH / "templates" / "print_format" / "macros" / "Repeater.html")

	def test_rating_macro_properties_mirrored_in_canvas(self):
		self._assert_df_props_mirrored(APP_PATH / "templates" / "print_format" / "macros" / "Rating.html")

	def test_rating_star_svg_matches_on_both_surfaces(self):
		"""The star SVG can't come from a shared helper (the desk sprite star is a
		different shape and sprites don't exist in the PDF render), so Field.vue
		hand-mirrors macros/Rating.html — this pins the path and colours together."""
		macro = (APP_PATH / "templates" / "print_format" / "macros" / "Rating.html").read_text()
		canvas = _field_vue_text()
		path_d = re.search(r'd="(M11\.5[^"]+)"', macro).group(1)
		self.assertIn(path_d, canvas)
		for color in ("#f6c35e", "#dce0e3"):
			self.assertIn(color, macro)
			self.assertIn(color, canvas)

	def _assert_df_props_mirrored(self, macro_path):
		# properties that are server-render concerns, not canvas inputs
		skip = {"get", "renderer", "section", "html"}
		macro = macro_path.read_text()
		props = set(re.findall(r"df\.([a-z_]+)", macro)) - skip
		missing = sorted(p for p in props if f"df.{p}" not in _canvas_logic_text())
		self.assertFalse(
			missing,
			f"{macro_path.name} reads df properties {missing} that the canvas preview never handles — "
			"the preview will silently ignore them. Mirror them in Field.vue or its FieldPreview* components.",
		)


class TestPrintSurfaceParity(IntegrationTestCase):
	def _make_contact_format(self):
		name = f"_Test PFP {frappe.generate_hash(length=6)}"
		doc = frappe.get_doc(
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
								"label": "Details",
								"columns": [
									{
										"label": "",
										"fields": [
											{
												"fieldtype": "Data",
												"fieldname": "first_name",
												"label": "First Name",
											},
											{
												"fieldtype": "Table",
												"fieldname": "email_ids",
												"label": "Emails",
												"table_columns": [
													{
														"fieldtype": "Int",
														"fieldname": "idx",
														"label": "No.",
														"width": 10,
													},
													{
														"fieldtype": "Data",
														"fieldname": "email_id",
														"label": "Email",
														"width": 90,
													},
												],
											},
										],
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
		doc.insert(ignore_permissions=True)
		self.addCleanup(doc.delete, ignore_permissions=True)
		return doc

	def _make_contact(self):
		doc = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "Parity",
				"email_ids": [{"email_id": "parity@example.com", "is_primary": 1}],
			}
		)
		doc.insert(ignore_permissions=True)
		self.addCleanup(doc.delete, ignore_permissions=True)
		return doc

	def _doc_body(self, html):
		from bs4 import BeautifulSoup

		el = BeautifulSoup(html, "html.parser").find(class_="print-format-doc")
		self.assertIsNotNone(el, "render is missing the .print-format-doc body")
		return self.normalize_html(str(el))

	def test_preview_and_pdf_bodies_are_identical(self):
		"""The builder preview (get_html_preview) and the PDF pipeline
		(_build_html_for_chrome) must emit the same .print-format-doc body. Both
		go through get_main_html(), so any divergence is a regression that would
		make the on-screen preview lie about the printed output."""
		from frappe.utils.print_format_generator import PrintFormatGenerator

		fmt = self._make_contact_format()
		contact = self._make_contact()

		preview = PrintFormatGenerator(fmt, contact).get_html_preview()
		pdf = PrintFormatGenerator(fmt, contact)._build_html_for_chrome()

		self.assertEqual(self._doc_body(preview), self._doc_body(pdf))

	def test_builder_preview_endpoint_matches_saved_render(self):
		"""render_builder_preview() renders an UNSAVED in-memory format; its body
		must match the saved format's print render (which the PDF shares), so a
		live preview of unsaved edits shows exactly what will print."""
		from frappe.utils.print_format_generator import get_html, render_builder_preview

		fmt = self._make_contact_format()
		contact = self._make_contact()

		saved = get_html("Contact", contact.name, fmt.name)
		live = render_builder_preview(frappe.as_json(fmt.as_dict()), "Contact", name=contact.name)

		self.assertEqual(self._doc_body(saved), self._doc_body(live))

	def test_formatted_field_values_match_print(self):
		"""The canvas sources values from get_formatted_field_values; each value must
		be the same one the print render emits, so the builder can't reformat it
		differently (the whole point — one formatter, not two)."""
		from frappe.utils.print_format_generator import get_formatted_field_values, get_html

		fmt = self._make_contact_format()
		contact = self._make_contact()

		result = get_formatted_field_values("Contact", contact.name)
		html = get_html("Contact", contact.name, fmt.name)

		self.assertEqual(result["values"]["first_name"], contact.get_formatted("first_name"))
		self.assertIn(result["values"]["first_name"], html)

		email_rows = result["child"]["email_ids"]
		self.assertEqual(email_rows[0]["email_id"], contact.email_ids[0].get_formatted("email_id"))

	def test_formatted_field_values_respect_permlevel(self):
		"""A reader without permlevel access must not get restricted field values —
		the endpoint returns raw field data, so it has to honour permlevel like the
		render path does."""
		from unittest.mock import patch

		from frappe.utils.print_format_generator import get_formatted_field_values

		contact = self._make_contact()
		restricted = frappe.get_meta("Contact").get_field("first_name")

		with (
			patch.object(restricted, "permlevel", 1),
			patch("frappe.model.document.Document.has_permlevel_access_to", return_value=False),
		):
			result = get_formatted_field_values("Contact", contact.name)

		self.assertNotIn("first_name", result["values"])
		self.assertIn("email_ids", result["child"])

	def test_rendered_html_carries_shared_markup_contract(self):
		"""The server render must produce the markup vocabulary the shared
		stylesheet and the canvas both rely on."""
		from frappe.utils.print_format_generator import get_html

		fmt = self._make_contact_format()
		contact = self._make_contact()
		html = get_html("Contact", contact.name, fmt.name)

		for token in (
			'class="print-format-doc"',
			'class="section-label"',
			'class="label"',
			'class="value"',
			'data-fieldname="first_name"',
			'data-fieldtype="Data"',
			"child-table child-table--lined",
			"child-table--bordered",
			'<table class="table">',
			"column-header",
			'data-fieldname="idx"',
			'data-fieldname="email_id"',
			"section-columns row",
		):
			self.assertIn(token, html)
