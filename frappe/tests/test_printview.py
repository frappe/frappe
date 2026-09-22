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

	def _make_barcode_beta_print_format(self):
		doctype = new_doctype(
			fields=[{"label": "Barcode Field", "fieldname": "barcode_field", "fieldtype": "Barcode"}]
		).insert()
		print_format = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(length=10),
			doc_type=doctype.name,
			print_format_builder_beta=1,
			format_data=frappe.as_json(
				{
					"sections": [
						{
							"columns": [
								{
									"fields": [
										{
											"fieldname": "barcode_field",
											"fieldtype": "Barcode",
											"label": "Barcode Field",
											"options": "",
										}
									]
								}
							],
						}
					]
				}
			),
		).insert()
		return doctype, print_format

	def test_print_format_builder_beta_escapes_barcode_field(self):
		"""Beta print formats (macros/*.html) render Barcode fields through a
		dedicated macro; without it, the value falls back to the unescaped
		Data.html macro and injects raw markup into the print HTML."""
		from frappe.utils.weasyprint import get_html

		doctype, print_format = self._make_barcode_beta_print_format()

		evil = frappe.get_doc(doctype=doctype.name, barcode_field='1234"><script>alert(1)</script>').insert()
		html = get_html(doctype=doctype.name, name=evil.name, print_format=print_format.name)
		self.assertNotIn("<script>alert(1)</script>", html)
		self.assertIn("&lt;script&gt;", html)

	def test_print_format_builder_beta_sanitizes_raw_svg_barcode(self):
		"""Barcode fields skip HTML sanitization on save (they may legitimately
		hold raw SVG), so the beta renderer's SVG passthrough branch must
		sanitize the value itself rather than emit it verbatim."""
		from frappe.utils.weasyprint import get_html

		doctype, print_format = self._make_barcode_beta_print_format()

		evil = frappe.get_doc(
			doctype=doctype.name, barcode_field='<svg onload="alert(1)"><circle r="1"/></svg>'
		).insert()
		html = get_html(doctype=doctype.name, name=evil.name, print_format=print_format.name)
		self.assertNotIn("onload", html)
		self.assertIn("<circle", html)

	def test_print_error(self):
		"""Print failures shouldn't generate PDF with failure message but instead escalate the error"""
		doctype = new_doctype(is_submittable=1).insert()

		doc = frappe.new_doc(doctype.name)
		doc.insert()
		doc.submit()
		doc.cancel()

		# cancelled doc can't be printed by default
		self.assertRaises(frappe.PermissionError, frappe.attach_print, doc.doctype, doc.name)
