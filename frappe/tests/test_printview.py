from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.tests import IntegrationTestCase
from frappe.www.printview import get_html_and_style

EXTRA_TEST_RECORD_DEPENDENCIES = ["User"]


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

	def test_print_error(self):
		"""Print failures shouldn't generate PDF with failure message but instead escalate the error"""
		doctype = new_doctype(is_submittable=1).insert()

		doc = frappe.new_doc(doctype.name)
		doc.insert()
		doc.submit()
		doc.cancel()

		# cancelled doc can't be printed by default
		self.assertRaises(frappe.PermissionError, frappe.attach_print, doc.doctype, doc.name)

	def test_preview_from_form_values_sees_native_types(self):
		doctype = new_doctype(
			fields=[
				{"fieldname": "some_date", "fieldtype": "Date", "label": "Some Date"},
				{"fieldname": "some_time", "fieldtype": "Time", "label": "Some Time"},
			]
		).insert()
		doc = frappe.get_doc(doctype=doctype.name, some_date="2026-01-31", some_time="10:30:00").insert()
		pf = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(length=10),
			doc_type=doctype.name,
			custom_format=1,
			print_format_type="Jinja",
			html="date:{{ doc.some_date is string }} time:{{ doc.some_time is string }}",
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", pf.name, force=True)

		html = get_html_and_style(doc=doc.as_json(), print_format=pf.name, no_letterhead=1)["html"]
		self.assertIn("date:False", html)
		self.assertIn("time:False", html)

	def test_preview_with_an_uncastable_value_leaves_no_message_behind(self):
		doctype = new_doctype(
			fields=[{"fieldname": "some_date", "fieldtype": "Date", "label": "Some Date"}]
		).insert()
		doc = frappe.get_doc(doctype=doctype.name, some_date="2026-01-31").insert()
		pf = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(length=10),
			doc_type=doctype.name,
			custom_format=1,
			print_format_type="Jinja",
			html="{{ doc.name }}",
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", pf.name, force=True)
		posted = doc.as_dict()
		posted["some_date"] = "not-a-date"

		messages_before = len(frappe.get_message_log())
		html = get_html_and_style(doc=frappe.as_json(posted), print_format=pf.name, no_letterhead=1)["html"]

		self.assertIn(doc.name, html)
		self.assertEqual(len(frappe.get_message_log()), messages_before)

	def test_get_print_leaves_form_dict_as_it_found_it(self):
		note = frappe.get_doc(doctype="Note", title=frappe.generate_hash()).insert()
		print_format = self._beta_format("Note", pdf_generator="chrome", format_data="{}")
		seen = []

		def fake_chrome_pdf(print_format, html, options, output, pdf_generator=None):
			seen.append((frappe.form_dict.doctype, frappe.form_dict.name, pdf_generator))
			return b"pdf"

		with patch.object(frappe.local, "form_dict", frappe._dict(cmd="x")):
			with patch("frappe.utils.pdf.get_chrome_pdf", side_effect=fake_chrome_pdf):
				pdf = frappe.get_print("Note", note.name, print_format.name, as_pdf=True)
			self.assertEqual(pdf, b"pdf")
			self.assertEqual(seen, [("Note", note.name, "chrome")])
			self.assertEqual(frappe.local.form_dict, {"cmd": "x"})

			frappe.get_print("Note", note.name, "Standard")
			self.assertEqual(frappe.local.form_dict, {"cmd": "x"})

	def test_print_settings_font_size_wins_over_print_style(self):
		from frappe.www.printview import get_print_style

		original = frappe.db.get_single_value("Print Settings", "font_size")
		self.addCleanup(frappe.db.set_single_value, "Print Settings", "font_size", original)
		frappe.db.set_single_value("Print Settings", "font_size", 80)

		css = get_print_style(style="Redesign")
		style_css = frappe.db.get_value("Print Style", "Redesign", "css").strip()
		self.assertIn(style_css, css)
		self.assertGreater(css.rfind("font-size: 80.0pt"), css.find(style_css))

	def _beta_format(self, doctype, **kwargs):
		pf = frappe.get_doc(
			doctype="Print Format",
			name=frappe.generate_hash(length=10),
			doc_type=doctype,
			print_format_builder_beta=1,
			**kwargs,
		).insert()
		self.addCleanup(frappe.delete_doc, "Print Format", pf.name, force=True)
		return pf

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
		beta_format = self._beta_format(doc.doctype)
		for print_format in ("Standard", custom_format.name, beta_format.name):
			with self.subTest(print_format=print_format):
				params = frappe._dict(doctype=doc.doctype, name=doc.name, print_format=print_format)
				with self.set_user("test@example.com"), patch.object(frappe.local, "form_dict", params):
					context = frappe._dict()
					get_context(context)
				self._assert_print_link_titles(context.body, doc, links)

	def test_standard_print_keeps_the_classic_template(self):
		doc, _links = self._make_linked_print_doc()
		params = frappe._dict(doctype=doc.doctype, name=doc.name)
		with patch.object(frappe.local, "form_dict", params):
			html = get_html_and_style(
				doc=doc.doctype, name=doc.name, print_format="Standard", no_letterhead=1
			)
		self.assertNotIn("print-format-doc", html["html"])
		self.assertTrue(html["style"])

	def test_builder_preview_displays_link_titles(self):
		from frappe.utils.print_format_generator import (
			download_builder_preview_pdf,
			render_builder_preview,
		)
		from frappe.www.printview import resolve_print_format

		doc, links = self._make_linked_print_doc()
		beta_format = self._beta_format(doc.doctype)
		print_format, is_beta = resolve_print_format(beta_format.name, doc.meta)
		self.assertTrue(is_beta)
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
		context. A builder format renders through macros/*.html."""
		doctype = self._make_attachment_fields_doctype()
		pf = self._beta_format(doctype.name)

		benign = self._make_doc(doctype.name, ".png")
		html = get_html_and_style(doc=benign.as_json(), print_format=pf.name, no_letterhead=1)["html"]
		self.assertIn('src="/files/img.png"', html)
		self.assertIn('data-barcode-value="1234.png"', html)

		evil = self._make_doc(doctype.name, '.png" onerror="alert(1)')
		html = get_html_and_style(doc=evil.as_json(), print_format=pf.name, no_letterhead=1)["html"]
		self.assertNotIn('onerror="alert(1)"', html)
		self.assertIn("&#34;", html)

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

		print_format = self._beta_format(doctype.name, absolute_value=1)
		html = get_html_and_style(doc=doc.as_json(), print_format=print_format.name, no_letterhead=1)["html"]
		self.assertIn("543.21", html)
		self.assertNotIn("-543.21", html)
		self.assertNotIn(">-9<", html)

	def test_before_print_runs_in_builder_renderer(self):
		from frappe.utils.print_format_generator import PrintFormatGenerator

		note = frappe.get_doc(doctype="Note", title=frappe.generate_hash()).insert()
		print_format = self._beta_format("Note", pdf_generator="chrome", format_data="{}")

		self.assertNotEqual(note.get("print_heading"), note.name)

		PrintFormatGenerator(print_format, note)

		self.assertEqual(note.print_heading, note.name)
		self.assertTrue(note.flags.in_print)

	def _make_linked_print_doc(self):
		linked_doctype = new_doctype(title_field="some_fieldname", show_title_field_in_link=1).insert()
		link_field = {
			"fieldname": "reference",
			"label": "Reference",
			"fieldtype": "Link",
			"options": linked_doctype.name,
			"in_list_view": 1,
		}
		child_doctype = new_doctype(istable=1, fields=[link_field]).insert()
		doctype = new_doctype(
			fields=[
				link_field,
				{
					"fieldname": "entries",
					"label": "Entries",
					"fieldtype": "Table",
					"options": child_doctype.name,
				},
			]
		).insert()
		links = [
			frappe.get_doc(doctype=linked_doctype.name, some_fieldname=title).insert()
			for title in ("Parent Link Title", "Child Link Title")
		]
		doc = frappe.get_doc(
			doctype=doctype.name,
			reference=links[0].name,
			entries=[{"reference": links[1].name}],
		).insert()
		return doc, links

	def _assert_print_link_titles(self, html, doc, links):
		for link in links:
			self.assertIn(link.some_fieldname, html)
			self.assertNotIn(link.name, html)
		stored_doc = frappe.get_doc(doc.doctype, doc.name)
		self.assertEqual(stored_doc.reference, links[0].name)
		self.assertEqual(stored_doc.entries[0].reference, links[1].name)
