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
<<<<<<< HEAD
=======

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
>>>>>>> d6b3f3a (fix: render print format templates with the render-safe flags)
