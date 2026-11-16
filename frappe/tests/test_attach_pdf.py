import io

from pypdf import PdfReader

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.print_format import attach_pdf

READER = "attach-pdf-reader@example.com"


class TestAttachPdf(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		frappe.set_user("test@example.com")
		self.note = frappe.get_doc(
			doctype="Note", title=frappe.generate_hash(length=8), content="<p>First draft</p>"
		).insert()

	def get_attached_pdfs(self):
		return frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Note", "attached_to_name": self.note.name},
			fields=["name", "file_name", "is_private"],
		)

	def get_text(self, file_name):
		content = frappe.get_doc("File", file_name).get_content()
		return "".join(page.extract_text() for page in PdfReader(io.BytesIO(content)).pages)

	def test_attaches_private_pdf_and_replaces_it_on_reprint(self):
		result = attach_pdf("Note", self.note.name)

		self.assertEqual(result["file_name"], f"{self.note.name} - Standard.pdf")
		files = self.get_attached_pdfs()
		self.assertEqual(len(files), 1)
		self.assertEqual(files[0].is_private, 1)
		self.assertIn("First draft", self.get_text(files[0].name))

		self.note.content = "<p>Second draft</p>"
		self.note.save()
		attach_pdf("Note", self.note.name)

		files = self.get_attached_pdfs()
		self.assertEqual(len(files), 1)
		self.assertIn("Second draft", self.get_text(files[0].name))

	def test_refuses_without_write_permission(self):
		reader = frappe.new_doc("User")
		reader.update({"email": READER, "first_name": "Reader", "send_welcome_email": 0})
		reader.insert(ignore_permissions=True, ignore_if_duplicate=True)
		frappe.get_doc("User", READER).add_roles("Desk User")
		self.assertTrue(frappe.has_permission("Note", "print", self.note, user=READER))

		frappe.set_user(READER)
		self.assertRaises(frappe.PermissionError, attach_pdf, "Note", self.note.name)
		self.assertFalse(self.get_attached_pdfs())
