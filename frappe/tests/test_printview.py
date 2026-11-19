import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.tests.utils import FrappeTestCase
from frappe.www.printview import get_html_and_style


class PrintViewTest(FrappeTestCase):
	def test_print_view_without_errors(self):
		user = frappe.get_last_doc("User")

		messages_before = frappe.get_message_log()
		ret = get_html_and_style(doc=user.as_json(), print_format="Standard", no_letterhead=1)
		messages_after = frappe.get_message_log()

		if len(messages_after) > len(messages_before):
			new_messages = messages_after[len(messages_before) :]
			self.fail("Print view showing error/warnings: \n" + "\n".join(str(msg) for msg in new_messages))

<<<<<<< HEAD
		# html should exist
		self.assertTrue(bool(ret["html"]))
=======
		params = frappe._dict(doctype=doctype.name, name=doc.name, format=print_format.name)
		with self.set_user("test@example.com"), patch.object(frappe.local, "form_dict", params):
			context = get_context({})

		self.assertFalse(context["standalone"])
		self.assertEqual(context["title"], "A Human Readable Title")
		self.assertEqual(context["print_filename"], doc.name)
		self.assertNotEqual(context["print_filename"], context["title"])

		html = frappe.render_template("frappe/www/printview.html", context)
		self.assertIn(f'<meta name="frappe-print-filename" content="{doc.name}">', html)
		self.assertIn("window.addEventListener('beforeprint'", html)
		self.assertIn("window.addEventListener('afterprint'", html)

	def test_print_preview_displays_link_titles(self):
		from frappe.www.printpreview import get_context

		doc, links = self._make_linked_print_doc()
		custom_format = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(),
			doc_type=doc.doctype,
			custom_format=1,
			html="""
				{{ doc.get_formatted('reference') }}
				{{ doc.entries[0].get_formatted('reference', doc) }}
			""",
		).insert()
		for print_format in ("Standard", custom_format.name):
			with self.subTest(print_format=print_format):
				params = frappe._dict(doctype=doc.doctype, name=doc.name, print_format=print_format)
				with self.set_user("test@example.com"), patch.object(frappe.local, "form_dict", params):
					context = frappe._dict()
					get_context(context)
				self._assert_print_link_titles(context.body, doc, links)

	def test_builder_preview_displays_link_titles(self):
		from frappe.utils.print_format_generator import (
			download_builder_preview_pdf,
			render_builder_preview,
		)
		from frappe.www.printview import resolve_print_format

		doc, links = self._make_linked_print_doc()
		print_format, _ = resolve_print_format("Standard", doc.meta)
		print_format.pdf_generator = "chrome"
		with self.set_user("test@example.com"):
			html = render_builder_preview(print_format.as_dict(), doc.doctype, doc.name)
			self._assert_print_link_titles(html, doc, links)
			with (
				patch("frappe.utils.pdf.get_chrome_pdf", return_value=b"pdf") as render_pdf,
				patch.object(frappe.local, "response", frappe._dict()),
			):
				download_builder_preview_pdf(print_format.as_dict(), doc.doctype, doc.name)
				self.assertEqual(frappe.local.response.filecontent, b"pdf")
			self._assert_print_link_titles(render_pdf.call_args.kwargs["html"], doc, links)

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
		self.assertIn('<img src="data:image/svg+xml;base64,', html)

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

	def test_markdown_editor_values_are_sanitized(self):
		doctype = new_doctype(
			fields=[{"label": "Notes", "fieldname": "notes", "fieldtype": "Markdown Editor"}]
		).insert()
		doc = frappe.get_doc(
			doctype=doctype.name, notes="[Docs](https://example.com) [Run](javascript:alert(1))"
		).insert()

		with self.set_user("test@example.com"):
			html = get_html_and_style(doc=doc.as_json(), print_format="Standard", no_letterhead=1)["html"]

		self.assertIn('href="https://example.com"', html)
		self.assertNotIn("javascript:", html)

	def test_classic_print_format_sanitizes_markdown(self):
		print_format = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(length=10),
			doc_type="ToDo",
			custom_format=1,
			html="{{ doc.description }}",
		).insert()
		todo = frappe.get_doc(
			doctype="ToDo",
			description="<!-- markdown -->[Docs](https://example.com) [Run](javascript:alert(1))",
		).insert()

		with self.set_user("test@example.com"):
			html = get_html_and_style(doc=todo.as_json(), print_format=print_format.name, no_letterhead=1)[
				"html"
			]

		self.assertIn('href="https://example.com"', html)
		self.assertNotIn("javascript:", html)

	def test_absolute_value_print_format_prints_positive_numbers(self):
		"""Print Format's "Show Absolute Values" should flip negative Currency/Int
		fields positive at render time."""
		doctype = new_doctype(
			fields=[
				{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency"},
				{"label": "Qty", "fieldname": "qty", "fieldtype": "Int"},
			]
		).insert()
		doc = frappe.get_doc(doctype=doctype.name, amount=-543.21, qty=-9).insert()

		print_format = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(length=10),
			doc_type=doctype.name,
			print_format_builder_beta=1,
			absolute_value=1,
		).insert()
		html = get_html_and_style(doc=doc.as_json(), print_format=print_format.name, no_letterhead=1)["html"]
		self.assertIn("543.21", html)
		self.assertNotIn("-543.21", html)
		# ">-9<" (not the bare "-9") — CSS custom properties like var(--gray-900)
		# would otherwise false-positive the substring check
		self.assertNotIn(">-9<", html)
>>>>>>> a80490a (test(print): markdown fields are sanitized in print)

	def test_print_error(self):
		"""Print failures shouldn't generate PDF with failure message but instead escalate the error"""
		doctype = new_doctype(is_submittable=1).insert()

		doc = frappe.new_doc(doctype.name)
		doc.insert()
		doc.submit()
		doc.cancel()

		# cancelled doc can't be printed by default
		self.assertRaises(frappe.PermissionError, frappe.attach_print, doc.doctype, doc.name)

	def test_print_format_template_cannot_run_write_queries(self):
		title = frappe.generate_hash()
		note = frappe.get_doc(doctype="Note", title=title).insert()
		print_format = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(),
			doc_type="Note",
			custom_format=1,
			print_format_type="Jinja",
			html=(
				'{% set note = frappe.qb.DocType("Note") %}'
				'{{ frappe.qb.update(note).set(note.title, "changed").where(note.name == doc.name).run() }}'
			),
		).insert()

		with self.assertRaises(frappe.PrintFormatError):
			get_html_and_style(doc="Note", name=note.name, print_format=print_format.name, no_letterhead=1)

		self.assertEqual(frappe.db.get_value("Note", note.name, "title"), title)
