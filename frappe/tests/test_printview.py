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
