# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import re
import unittest
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.typst_emitter import (
	BLOCKER_FIELDTYPES,
	TRANSLATABLE_STYLE_PROPS,
	q,
	translate_custom_style,
	typst_blockers,
)


def has_typst():
	try:
		import typst

		return True
	except ImportError:
		return False


def layout_with(*fields, **extra):
	section = {"label": "", "columns": [{"label": "", "fields": list(fields)}]}
	section.update(extra.pop("section", {}))
	return {
		"sections": [section],
		"header": {"columns": [{"label": "", "fields": []}]},
		"footer": {"columns": [{"label": "", "fields": []}]},
		**extra,
	}


class TestTypstGate(IntegrationTestCase):
	"""typst_blockers is the single authority on what may render through Typst."""

	def pf(self, **kwargs):
		defaults = {"custom_format": 0, "print_format_builder_beta": 1, "css": "", "doc_type": "ToDo"}
		return frappe._dict({**defaults, **kwargs})

	def test_structured_layout_qualifies(self):
		layout = layout_with(
			{"fieldtype": "Data", "fieldname": "description", "label": "D"},
			{"fieldtype": "Divider"},
			{"fieldtype": "Spacer", "height": 10},
			{"fieldtype": "Repeater", "source": "items", "repeater_columns": []},
		)
		self.assertEqual(typst_blockers(self.pf(), layout), [])

	def test_each_blocker_is_named(self):
		cases = {
			"Custom HTML block": {"fieldtype": "HTML", "fieldname": "h", "html": "<b>x</b>"},
			"Field Template (Jinja HTML)": {"fieldtype": "Field Template", "field_template": "T"},
			"Barcode (non-QR)": {"fieldtype": "Barcode", "custom": 1, "barcode_format": "CODE128"},
			"Remote image URL": {"fieldtype": "Image", "custom": 1, "image_url": "https://x.test/a.png"},
		}
		for reason, field in cases.items():
			with self.subTest(reason=reason):
				self.assertIn(reason, typst_blockers(self.pf(), layout_with(field)))

	def test_qr_barcode_qualifies(self):
		field = {"fieldtype": "Barcode", "custom": 1, "barcode_format": "QR", "barcode_value": "X"}
		self.assertEqual(typst_blockers(self.pf(), layout_with(field)), [])

	def test_format_level_blockers(self):
		self.assertIn("Custom HTML format", typst_blockers(self.pf(custom_format=1), layout_with()))
		self.assertIn(
			"Not a builder format", typst_blockers(self.pf(print_format_builder_beta=0), layout_with())
		)
		self.assertIn(
			"Custom CSS on the format", typst_blockers(self.pf(css=".x { color: red }"), layout_with())
		)

	def test_custom_style_blocks_only_untranslatable_properties(self):
		ok = {
			"fieldtype": "Data",
			"fieldname": "x",
			"custom_style": "font-weight: bold; padding-bottom: 10px",
		}
		self.assertEqual(typst_blockers(self.pf(), layout_with(ok)), [])

		bad = {"fieldtype": "Data", "fieldname": "x", "custom_style": "transform: rotate(3deg)"}
		blockers = typst_blockers(self.pf(), layout_with(bad))
		self.assertTrue(any("transform" in b for b in blockers))

	def test_asset_paths_cannot_escape_their_root(self):
		"""Image srcs are document data; a traversal must read nothing."""
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter

		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst Traversal {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": json.dumps(layout_with()),
			}
		).insert()
		self.addCleanup(pf_doc.delete, ignore_permissions=True)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "x"}).insert(ignore_permissions=True)
		self.addCleanup(todo.delete, ignore_permissions=True)
		emitter = TypstEmitter(PrintFormatGenerator(pf_doc, frappe.get_doc("ToDo", todo.name)))
		for hostile in (
			"/assets/../site_config.json",
			"/assets/../../sites/common_site_config.json",
			"/files/../../private/files/secret.txt",
			"/private/files/../../site_config.json",
		):
			with self.subTest(src=hostile):
				self.assertIsNone(emitter._read_site_file(hostile))

	def test_private_files_require_file_permission(self):
		"""A private path that is not a readable File document reads nothing —
		printing doc A must not exfiltrate doc B's attachments."""
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter

		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst Priv {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": json.dumps(layout_with()),
			}
		).insert()
		self.addCleanup(pf_doc.delete, ignore_permissions=True)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "x"}).insert(ignore_permissions=True)
		self.addCleanup(todo.delete, ignore_permissions=True)
		emitter = TypstEmitter(PrintFormatGenerator(pf_doc, frappe.get_doc("ToDo", todo.name)))
		# no File document registered for this path -> refused even if it existed on disk
		self.assertIsNone(emitter._read_site_file("/private/files/unregistered.png"))

	def test_typst_block_qualifies_and_emits_verbatim(self):
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter, has_typst_blocks

		markup = "#box(width: 100%, stroke: 0.5pt)[Raw markup]"
		layout = layout_with(
			{"fieldtype": "Typst", "fieldname": "typst_block_x", "custom": 1, "typst": markup}
		)
		self.assertEqual(typst_blockers(self.pf(), layout), [])
		self.assertTrue(has_typst_blocks(layout))
		self.assertFalse(has_typst_blocks(layout_with({"fieldtype": "Data", "fieldname": "d"})))

		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst Block {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"pdf_generator": "Typst",
				"format_data": json.dumps(layout),
			}
		).insert()
		self.addCleanup(pf_doc.delete, ignore_permissions=True)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "typst block"}).insert(
			ignore_permissions=True
		)
		self.addCleanup(todo.delete, ignore_permissions=True)
		source, _assets = TypstEmitter(PrintFormatGenerator(pf_doc, frappe.get_doc("ToDo", todo.name))).emit()
		self.assertIn(markup, source)

	def test_safe_color_accepts_only_typst_hex_lengths(self):
		from frappe.utils.typst_emitter import safe_color

		for ok in ("#abc", "#abcd", "#aabbcc", "#aabbccdd"):
			self.assertEqual(safe_color(ok), ok)
		# 5/7 digits abort typst.compile with "color string has wrong length"
		for bad in ("#12345", "#1234567", "#red"):
			self.assertIsNone(safe_color(bad))

	def test_remote_letterhead_image_blocks(self):
		from frappe.utils.typst_emitter import letterhead_blockers

		lh = {"source": "Image", "image": "https://x.test/logo.png", "content": "<img>"}
		self.assertIn("Letterhead with a remote image URL", letterhead_blockers(lh))
		self.assertEqual(letterhead_blockers({"source": "Image", "image": "/files/logo.png"}), [])

	def test_empty_typst_block_does_not_pin_renderer(self):
		from frappe.utils.typst_emitter import has_typst_blocks

		layout = layout_with({"fieldtype": "Typst", "fieldname": "t", "custom": 1, "typst": "  "})
		self.assertFalse(has_typst_blocks(layout))

	@unittest.skipUnless(has_typst(), "typst not installed")
	def test_malformed_typst_block_refused_at_save(self):
		layout = layout_with({"fieldtype": "Typst", "fieldname": "t", "custom": 1, "typst": "#unclosed["})
		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst BadBlock {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"pdf_generator": "Typst",
				"format_data": json.dumps(layout),
			}
		)
		self.assertRaisesRegex(frappe.ValidationError, "does not compile", pf_doc.insert)

	def test_typst_block_renders_jinja_with_escaped_values(self):
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter

		layout = layout_with(
			{
				"fieldtype": "Typst",
				"fieldname": "t",
				"custom": 1,
				"typst": "Task: {{ doc.description }}\n{{ '#v(9pt)' | typst_raw }}",
			}
		)
		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst Jinja {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"pdf_generator": "Typst",
				"format_data": json.dumps(layout),
			}
		).insert()
		self.addCleanup(pf_doc.delete, ignore_permissions=True)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "#import *x* [y]"}).insert(
			ignore_permissions=True
		)
		self.addCleanup(todo.delete, ignore_permissions=True)
		source, _assets = TypstEmitter(PrintFormatGenerator(pf_doc, frappe.get_doc("ToDo", todo.name))).emit()
		# the doc value crosses escaped — never interpretable as Typst code
		self.assertIn(r"Task: \#import \*x\* \[y\]", source)
		# typst_raw is the deliberate escape hatch
		self.assertIn("#v(9pt)", source)

	@unittest.skipUnless(has_typst(), "typst not installed")
	def test_typst_block_jinja_error_refused_at_save(self):
		layout = layout_with(
			{"fieldtype": "Typst", "fieldname": "t", "custom": 1, "typst": "{% if %}broken{% endif %}"}
		)
		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst BadJinja {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"pdf_generator": "Typst",
				"format_data": json.dumps(layout),
			}
		)
		self.assertRaisesRegex(frappe.ValidationError, "template error", pf_doc.insert)

	def test_typst_block_requires_typst_renderer(self):
		layout = layout_with({"fieldtype": "Typst", "fieldname": "t", "custom": 1, "typst": "#v(1pt)"})
		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst BlockGate {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": json.dumps(layout),
			}
		)
		self.assertRaisesRegex(frappe.ValidationError, "must be Typst", pf_doc.insert)

	def test_non_hex_colors_block_instead_of_dropping(self):
		"""HTML renders any CSS color; Typst emits only rgb("#..."), so a non-hex
		field/format color is gated (falls back to Chromium) rather than dropped."""
		self.assertIn(
			"Field color Typst can't render: red",
			typst_blockers(
				self.pf(),
				layout_with({"fieldtype": "Data", "fieldname": "x", "label_color": "red"}),
			),
		)
		self.assertEqual(
			typst_blockers(
				self.pf(),
				layout_with({"fieldtype": "Data", "fieldname": "x", "label_color": "#ff0000"}),
			),
			[],
		)
		self.assertTrue(
			any(
				"Format color" in b
				for b in typst_blockers(
					self.pf(value_color="rgb(1,2,3)"),
					layout_with({"fieldtype": "Data", "fieldname": "x"}),
				)
			)
		)

	def test_falsy_field_values_are_hidden_like_html(self):
		"""Data.html gates each field on the raw value ({% if value %}), so 0 / 0.0
		/ False print nothing — Typst must match, not show a formatted zero."""
		from frappe.utils.typst_emitter import TypstEmitter

		em = TypstEmitter(frappe._dict(doc=frappe._dict(), print_format=frappe._dict(), layout={}))

		class Doc:
			def __init__(self, v):
				self.v = v

			def get(self, f, d=None):
				return self.v

			def get_formatted(self, f):
				return str(self.v)

		em.doc = Doc(0)
		self.assertEqual(em._formatted_value({"fieldname": "x", "fieldtype": "Currency"}), "")
		self.assertEqual(em._formatted_value({"fieldname": "c", "fieldtype": "Check"}), "")
		em.doc = Doc(5)
		self.assertEqual(em._formatted_value({"fieldname": "x", "fieldtype": "Currency"}), "5")

	def test_table_header_and_style_mirror_html(self):
		"""table_header is a mode string (none/plain), and lined vs bordered are
		distinct — Typst must not treat the header as a flag or borders as all-or-none."""
		from frappe.utils.typst_emitter import HAIRLINE, TypstEmitter

		em = TypstEmitter(frappe._dict(doc=frappe._dict(), print_format=frappe._dict(), layout={}))

		class Row:
			def get_formatted(self, f):
				return "Widget"

			def get(self, f, d=None):
				return None

		cols = [{"fieldname": "item", "label": "Item"}]

		def tbl(**extra):
			return em._table({"fieldname": "items", "table_columns": cols, "_rows": [Row()], **extra})

		self.assertNotIn("table.header", tbl(table_header="none"))
		plain = tbl(table_header="plain")
		self.assertIn("table.header", plain)
		self.assertNotIn("fill:", plain)
		self.assertIn("fill:", tbl())
		self.assertIn("(_, y) =>", tbl(table_bordered=False, table_style="lined"))
		self.assertIn(f"stroke: {HAIRLINE}", tbl(table_bordered=True))

	def test_page_size_follows_print_settings(self):
		"""Typst must honour pdf_page_size like the Chromium path, or the two
		renderers disagree on page geometry on a non-A4 site."""
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter

		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst PageSize {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": json.dumps(layout_with()),
			}
		).insert()
		self.addCleanup(pf_doc.delete, ignore_permissions=True)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "page size"}).insert(ignore_permissions=True)
		self.addCleanup(todo.delete, ignore_permissions=True)

		def page_setup(size):
			em = TypstEmitter(PrintFormatGenerator(pf_doc, frappe.get_doc("ToDo", todo.name)))
			em.generator.print_settings.pdf_page_size = size
			return em.emit()[0]

		self.assertIn("width: 210mm, height: 297mm", page_setup("A4"))
		self.assertIn("width: 216mm, height: 279mm", page_setup("Letter"))
		self.assertIn("width: 216mm, height: 356mm", page_setup("Legal"))
		# Custom's cross-renderer unit contract is ambiguous — fall back to A4
		self.assertIn("width: 210mm, height: 297mm", page_setup("Custom"))

	def test_custom_margin_overrides_structured_section_margin(self):
		"""The html surface puts custom_style after the structured margin in one
		style attribute, so margin-top replaces it — the emitter must not stack."""
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter

		layout = layout_with(
			{"fieldtype": "Data", "fieldname": "description", "label": "D"},
			section={"margin": {"top": 20}, "custom_style": "margin-top: 10px"},
		)
		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst MarginParity {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": json.dumps(layout),
			}
		).insert()
		self.addCleanup(pf_doc.delete, ignore_permissions=True)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "margin parity"}).insert(
			ignore_permissions=True
		)
		self.addCleanup(todo.delete, ignore_permissions=True)
		source, _assets = TypstEmitter(PrintFormatGenerator(pf_doc, frappe.get_doc("ToDo", todo.name))).emit()
		self.assertIn("#v(7.5pt)", source)
		self.assertNotRegex(source, r"#v\(15\.?0?pt\)")

	def test_section_custom_style_is_emitted(self):
		"""What the gate accepts must reach the output — accepted-but-dropped
		styling is the failure mode this pins."""
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter

		layout = layout_with(
			{"fieldtype": "Data", "fieldname": "description", "label": "D"},
			section={"custom_style": "border-bottom: 1px solid #e5e7eb; margin-top: 20px"},
		)
		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst SecStyle {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": json.dumps(layout),
			}
		).insert()
		self.addCleanup(pf_doc.delete, ignore_permissions=True)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "styled section"}).insert(
			ignore_permissions=True
		)
		self.addCleanup(todo.delete, ignore_permissions=True)
		source, _assets = TypstEmitter(PrintFormatGenerator(pf_doc, frappe.get_doc("ToDo", todo.name))).emit()
		self.assertIn('stroke: (bottom: 0.75pt + rgb("#e5e7eb"))', source)
		self.assertIn("#v(15.0pt)", source)

	def test_bordered_section_ignores_configured_gap_like_html(self):
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter

		layout = layout_with(
			section={
				"field_borders": True,
				"custom_style": "gap: 10px",
				"columns": [
					{
						"label": "",
						"fields": [{"fieldtype": "Data", "fieldname": "description", "label": "D"}],
					},
					{"label": "", "fields": [{"fieldtype": "Data", "fieldname": "status", "label": "S"}]},
				],
			}
		)
		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst BorderGap {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": json.dumps(layout),
			}
		).insert()
		self.addCleanup(pf_doc.delete, ignore_permissions=True)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "gap", "status": "Open"}).insert(
			ignore_permissions=True
		)
		self.addCleanup(todo.delete, ignore_permissions=True)
		source, _assets = TypstEmitter(PrintFormatGenerator(pf_doc, frappe.get_doc("ToDo", todo.name))).emit()
		self.assertIn("column-gutter: 6.0pt", source)
		self.assertIn('stroke: (left: 0.6pt + rgb("#e5e7eb"))', source)

	def test_inline_label_gap_precedence_matches_html(self):
		"""Data.html appends custom_style after the label_gap declaration, so a
		custom gap wins; label_gap applies only when no custom gap is set."""
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter

		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst InlineGap {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": json.dumps(layout_with()),
			}
		).insert()
		self.addCleanup(pf_doc.delete, ignore_permissions=True)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "gap"}).insert(ignore_permissions=True)
		self.addCleanup(todo.delete, ignore_permissions=True)
		emitter = TypstEmitter(PrintFormatGenerator(pf_doc, frappe.get_doc("ToDo", todo.name)))

		df = {
			"fieldtype": "Data",
			"fieldname": "description",
			"label": "D",
			"show_label": "inline",
			"label_gap": 20,
			"custom_style": "gap: 10px",
		}
		self.assertIn("column-gutter: 7.5pt", emitter._data_field({}, df))
		df.pop("custom_style")
		self.assertIn("column-gutter: 15.0pt", emitter._data_field({}, df))

	def test_table_image_cells_embed_thumbnails(self):
		"""Image columns render as images like Table.html, never as path text —
		merged cells get the square cover thumb, plain columns the contained one,
		and a missing image falls back to the coloured initials."""
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter

		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst TableImg {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": json.dumps(layout_with()),
			}
		).insert()
		self.addCleanup(pf_doc.delete, ignore_permissions=True)
		row = frappe.get_doc({"doctype": "ToDo", "description": "Widget"}).insert(ignore_permissions=True)
		self.addCleanup(row.delete, ignore_permissions=True)
		row.item_image = "data:image/png;base64,iVBORw0KGgo="
		emitter = TypstEmitter(PrintFormatGenerator(pf_doc, frappe.get_doc("ToDo", row.name)))

		merged_col = {
			"fieldname": "description",
			"fieldtype": "Data",
			"image_size": 60,
			"merged_fields": [{"fieldname": "item_image", "fieldtype": "Attach Image"}],
		}
		cell = emitter._table_cell(row, merged_col)
		self.assertIn('fit: "cover"', cell)
		self.assertIn("width: 45.0pt, height: 45.0pt", cell)
		self.assertIn("#grid(columns: (auto, 1fr)", cell)
		self.assertNotIn("data:image", cell)
		self.assertTrue(emitter.assets)

		row.item_image = ""
		fallback = emitter._table_cell(row, merged_col)
		self.assertIn("color.hsl(", fallback)
		self.assertIn(q("W"), fallback)

		plain_col = {"fieldname": "item_image", "fieldtype": "Attach Image"}
		row.item_image = "data:image/png;base64,iVBORw0KGgo="
		self.assertIn('fit: "contain"', emitter._table_cell(row, plain_col))
		row.item_image = "/files/does-not-exist.png"
		self.assertEqual(emitter._table_cell(row, plain_col), "")

	def test_image_letterhead_qualifies_and_is_emitted(self):
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter

		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"_typst_lh_{frappe.generate_hash(length=6)}.png",
				# 1x1 transparent png
				"content": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa75\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(file.delete, ignore_permissions=True)
		lh = frappe.get_doc(
			{
				"doctype": "Letter Head",
				"letter_head_name": f"_Typst ImgLH {frappe.generate_hash(length=6)}",
				"source": "Image",
				"image": file.file_url,
				"image_width": 200,
				"align": "Center",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(lh.delete, ignore_permissions=True)

		layout = layout_with({"fieldtype": "Data", "fieldname": "description", "label": "D"})
		layout["letter_head"] = lh.name
		self.assertEqual(typst_blockers(self.pf(), layout), [])

		pf_doc = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst LHEmit {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": json.dumps(layout),
			}
		).insert()
		self.addCleanup(pf_doc.delete, ignore_permissions=True)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "x"}).insert(ignore_permissions=True)
		self.addCleanup(todo.delete, ignore_permissions=True)
		emitter = TypstEmitter(PrintFormatGenerator(pf_doc, frappe.get_doc("ToDo", todo.name), lh.name))
		source, assets = emitter.emit()
		self.assertIn("#align(center)[#image(", source)
		self.assertIn("width: 150.0pt", source)
		self.assertTrue(assets)

	def test_letterhead_with_html_blocks(self):
		lh = frappe.get_doc(
			{
				"doctype": "Letter Head",
				"letter_head_name": f"_Typst LH {frappe.generate_hash(length=6)}",
				"content": "<div>hi</div>",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(lh.delete, ignore_permissions=True)
		layout = layout_with(letter_head=lh.name)
		self.assertIn("Letterhead with HTML content", typst_blockers(self.pf(), layout))


class TestTypstTranslation(IntegrationTestCase):
	def test_string_values_cannot_become_markup(self):
		hostile = 'quotes " hash #eval [bracket] $math$ \\ backslash'
		literal = q(hostile)
		self.assertTrue(literal.startswith('"') and literal.endswith('"'))
		self.assertEqual(json.loads(literal), hostile)

	def test_unicode_crosses_as_raw_text(self):
		"""Typst reads \\uXXXX as literal text, so escaped unicode prints as
		gibberish — non-ASCII must cross unescaped."""
		value = "café ₹1,000 日本語"
		literal = q(value)
		self.assertIn("café", literal)
		self.assertNotIn("\\u", literal)
		self.assertEqual(json.loads(literal), value)

	def test_hostile_colors_are_dropped(self):
		from frappe.utils.typst_emitter import safe_color

		self.assertEqual(safe_color("#ff0000"), "#ff0000")
		self.assertEqual(safe_color(" #ABC "), "#ABC")
		for hostile in ('") #eval', "red; fill: black", 'x" + sys.inputs', "", None, 12):
			with self.subTest(color=hostile):
				self.assertIsNone(safe_color(hostile))
		self.assertEqual(safe_color("bogus", "#6b7280"), "#6b7280")

	def test_translate_known_properties(self):
		effects, unknown = translate_custom_style(
			"font-weight: bold;\nborder-bottom: 1px solid #e5e7eb;\npadding-bottom: 10px;"
		)
		self.assertEqual(unknown, [])
		self.assertTrue(effects["bold"])
		self.assertIn("#e5e7eb", effects["stroke_bottom"])
		self.assertEqual(effects["inset_bottom"], 7.5)
		effects, unknown = translate_custom_style("border-top: 1px solid red; border-bottom: 2px solid #fff")
		self.assertEqual(unknown, [])
		self.assertEqual(effects["stroke_top"], "0.75pt + red")
		self.assertEqual(effects["stroke_bottom"], '1.5pt + rgb("#fff")')

	def test_translate_reports_untranslatable_values(self):
		"""A recognized property with a value the translator cannot express must
		block, never silently drop."""
		for style, reported in (
			("border-bottom: thin solid red", "border-bottom: thin solid red"),
			("border-bottom: 1px solid crimson", "border-bottom: 1px solid crimson"),
			("border-top: 1px solid rgb(255, 0, 0)", "border-top: 1px solid rgb(255, 0, 0)"),
			("gap: 1rem", "gap: 1rem"),
			("font-weight: 300", "font-weight: 300"),
		):
			with self.subTest(style=style):
				effects, unknown = translate_custom_style(style)
				self.assertEqual(effects, {})
				self.assertIn(reported, unknown)

	def test_translate_reports_unknown_properties(self):
		_effects, unknown = translate_custom_style("color: red; font-weight: bold")
		self.assertEqual(unknown, ["color"])

	def test_style_props_match_the_javascript_mirror(self):
		"""The client hint must grey out exactly what the server refuses."""
		source = (Path(frappe.get_app_path("frappe")) / "public/js/print_format_builder/utils.js").read_text()
		block = re.search(r"export const TYPST_STYLE_PROPS = new Set\(\[(.*?)\]\);", source, re.S)
		self.assertIsNotNone(block)
		self.assertEqual(set(re.findall(r'"([^"]+)"', block.group(1))), set(TRANSLATABLE_STYLE_PROPS))

	def test_special_fieldtypes_have_a_deliberate_disposition(self):
		"""Every non-docfield element the builder can drop is either emitted or a
		named blocker — a new element must choose, never fall through silently."""
		emitted = {"Spacer", "Divider", "Table", "Repeater", "Image", "Barcode", "Attach Image"}
		blocked = set(BLOCKER_FIELDTYPES)
		builder_elements = {
			"HTML",
			"Spacer",
			"Divider",
			"Repeater",
			"Image",
			"Barcode",
			"Field Template",
			"Table",
		}
		unhandled = builder_elements - emitted - blocked
		self.assertEqual(unhandled, set(), f"undeclared for typst: {unhandled}")


class TestTypstRender(IntegrationTestCase):
	def make(self, layout, **kwargs):
		pf = frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": f"_Typst Render {frappe.generate_hash(length=6)}",
				"doc_type": "ToDo",
				"print_format_builder_beta": 1,
				"format_data": json.dumps(layout),
				**kwargs,
			}
		).insert()
		self.addCleanup(pf.delete, ignore_permissions=True)
		return pf

	def make_todo(self, **kwargs):
		doc = frappe.get_doc({"doctype": "ToDo", "description": "typst render test", **kwargs}).insert(
			ignore_permissions=True
		)
		self.addCleanup(doc.delete, ignore_permissions=True)
		return frappe.get_doc("ToDo", doc.name)

	def test_typst_choice_survives_save(self):
		pf = self.make(
			layout_with({"fieldtype": "Data", "fieldname": "description", "label": "D"}),
			pdf_generator="Typst",
		)
		pf.reload()
		self.assertEqual(pf.pdf_generator, "Typst")

	def test_save_refuses_typst_with_blockers(self):
		with self.assertRaises(frappe.ValidationError):
			self.make(
				layout_with({"fieldtype": "HTML", "fieldname": "h", "html": "<b>x</b>"}),
				pdf_generator="Typst",
			)

	def test_emission_resolves_conditions_and_values(self):
		from frappe.utils.print_format_generator import PrintFormatGenerator
		from frappe.utils.typst_emitter import TypstEmitter

		layout = layout_with(
			{"fieldtype": "Data", "fieldname": "description", "label": "Description"},
			{"fieldtype": "Data", "fieldname": "priority", "label": "P", "visible_if": "False"},
		)
		pf = self.make(layout)
		todo = self.make_todo(priority="High")
		source, assets = TypstEmitter(PrintFormatGenerator(pf, todo)).emit()
		self.assertIn("typst render test", source)
		self.assertNotIn("High", source, "visible_if=False field must not be emitted")
		self.assertEqual(assets, {})

	@unittest.skipUnless(has_typst(), "typst not installed")
	def test_render_pdf_produces_a_pdf(self):
		pf = self.make(layout_with({"fieldtype": "Data", "fieldname": "description", "label": "D"}))
		pf.pdf_generator = "Typst"
		todo = self.make_todo()
		from frappe.utils.print_format_generator import PrintFormatGenerator

		pdf = PrintFormatGenerator(pf, todo).render_pdf()
		self.assertEqual(pdf[:4], b"%PDF")

		from io import BytesIO

		from pypdf import PdfReader

		text = PdfReader(BytesIO(pdf)).pages[0].extract_text()
		self.assertIn("typst render test", text)

	@unittest.skipUnless(has_typst(), "typst not installed")
	def test_render_refuses_a_blocked_format(self):
		pf = self.make(layout_with({"fieldtype": "HTML", "fieldname": "h", "html": "<b>x</b>"}))
		pf.pdf_generator = "Typst"
		todo = self.make_todo()
		from frappe.utils.print_format_generator import PrintFormatGenerator

		with self.assertRaises(frappe.ValidationError):
			PrintFormatGenerator(pf, todo).render_pdf()
