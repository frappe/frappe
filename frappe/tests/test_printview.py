import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.tests import IntegrationTestCase
from frappe.www.printview import get_html_and_style


class PrintViewTest(IntegrationTestCase):
	def test_print_view_without_errors(self):
		user = frappe.get_last_doc("User")

		messages_before = frappe.get_message_log()
		ret = get_html_and_style(doc=user.as_json(), print_format="Standard", no_letterhead=1)
		messages_after = frappe.get_message_log()

		if len(messages_after) > len(messages_before):
			new_messages = messages_after[len(messages_before) :]
			self.fail("Print view showing error/warnings: \n" + "\n".join(str(msg) for msg in new_messages))

		# html should exist
		self.assertTrue(bool(ret["html"]))

	def _make_attachment_fields_doctype(self):
		return new_doctype(
			fields=[
				{"label": "Attach Field", "fieldname": "attach_field", "fieldtype": "Attach"},
				{
					"label": "Attach Image Field",
					"fieldname": "attach_image_field",
					"fieldtype": "Attach Image",
				},
				{"label": "Signature Field", "fieldname": "signature_field", "fieldtype": "Signature"},
				{"label": "Barcode Field", "fieldname": "barcode_field", "fieldtype": "Barcode"},
			]
		).insert()

	def _make_doc(self, doctype, suffix):
		return frappe.get_doc(
			doctype=doctype,
			attach_field="/files/doc" + suffix,
			attach_image_field="/files/img" + suffix,
			signature_field="/files/sig" + suffix,
			barcode_field="1234" + suffix,
		).insert()

	def test_attach_image_signature_barcode_values_are_escaped(self):
		"""Values reach src/data-* attributes; unescaped values break attribute
		context. "Standard" resolves to the beta renderer (macros/*.html)."""
		doctype = self._make_attachment_fields_doctype()

		benign = self._make_doc(doctype.name, ".png")
		html = get_html_and_style(doc=benign.as_json(), print_format="Standard", no_letterhead=1)["html"]
		self.assertIn('src="/files/img.png"', html)
		self.assertIn('data-barcode-value="1234.png"', html)

		evil = self._make_doc(doctype.name, '.png" onerror="alert(1)')
		html = get_html_and_style(doc=evil.as_json(), print_format="Standard", no_letterhead=1)["html"]
		self.assertNotIn('onerror="alert(1)"', html)
		self.assertIn("&#34;", html)

	def test_classic_print_format_escapes_attachment_fields(self):
		"""Same, for the older Jinja engine, still reachable via custom Print
		Format docs whose stored html imports it directly."""
		doctype = self._make_attachment_fields_doctype()
		print_format = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(length=10),
			doc_type=doctype.name,
			custom_format=1,
			html="""
				{% import "templates/print_formats/standard_macros.html" as standard_macros %}
				{% for df in meta.fields %}{{ standard_macros.print_value(df, doc) }}{% endfor %}
			""",
		).insert()

		benign = self._make_doc(doctype.name, ".png")
		html = get_html_and_style(doc=benign.as_json(), print_format=print_format.name, no_letterhead=1)[
			"html"
		]
		self.assertIn('src="/files/img.png"', html)
		self.assertIn('data-barcode-value="1234.png"', html)

		evil = self._make_doc(doctype.name, '.png" onerror="alert(1)')
		html = get_html_and_style(doc=evil.as_json(), print_format=print_format.name, no_letterhead=1)["html"]
		self.assertNotIn('onerror="alert(1)"', html)
		self.assertIn("&#34;", html)

	def test_print_error(self):
		"""Print failures shouldn't generate PDF with failure message but instead escalate the error"""
		doctype = new_doctype(is_submittable=1).insert()

		doc = frappe.new_doc(doctype.name)
		doc.insert()
		doc.submit()
		doc.cancel()

		# cancelled doc can't be printed by default
		self.assertRaises(frappe.PermissionError, frappe.attach_print, doc.doctype, doc.name)

	def test_before_print_runs_in_builder_renderer(self):
		from frappe.utils.print_format_generator import PrintFormatGenerator

		note = frappe.get_doc(doctype="Note", title=frappe.generate_hash()).insert()
		print_format = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(),
			doc_type="Note",
			print_format_builder_beta=1,
			pdf_generator="chrome",
			format_data="{}",
		).insert()

		self.assertNotEqual(note.get("print_heading"), note.name)

		PrintFormatGenerator(print_format, note)

		self.assertEqual(note.print_heading, note.name)
		self.assertTrue(note.flags.in_print)

	def test_unresolvable_format_falls_back_to_the_doctype_default(self):
		"""Callers interpolate a missing name into the url ("format=None"), and formats
		get renamed — either way the doctype's default wins over the built-in one."""
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter
		from frappe.www.printview import get_print_format_doc

		default = frappe.get_doc(
			doctype="Print Format",
			name=f"_Test Default {frappe.generate_hash(length=6)}",
			doc_type="Note",
			custom_format=1,
			html="<div>default</div>",
		).insert()

		def drop_default():
			frappe.db.delete("Property Setter", {"doc_type": "Note", "property": "default_print_format"})
			frappe.clear_cache(doctype="Note")

		self.addCleanup(drop_default)
		make_property_setter("Note", None, "default_print_format", default.name, "Data", for_doctype=True)
		frappe.clear_cache(doctype="Note")
		meta = frappe.get_meta("Note")

		self.assertEqual(get_print_format_doc("None", meta).name, default.name)
		self.assertEqual(get_print_format_doc("_No Such Format ZZZ", meta).name, default.name)
		self.assertEqual(get_print_format_doc(None, meta).name, default.name)
		# an explicit "Standard" still means the built-in format
		self.assertIsNone(get_print_format_doc("Standard", meta))

		# without a doctype default it still degrades to the built-in format
		drop_default()
		self.assertIsNone(get_print_format_doc("None", frappe.get_meta("Note")))
