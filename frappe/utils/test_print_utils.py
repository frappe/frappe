# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import io

from pypdf import PdfReader, PdfWriter

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.print_utils import run_after_print


def blank_pdf(page_count=1) -> bytes:
	writer = PdfWriter()
	for _ in range(page_count):
		writer.add_blank_page(width=72, height=72)
	stream = io.BytesIO()
	writer.write(stream)
	return stream.getvalue()


def add_blank_page(doc, method, pdf):
	frappe.flags.after_print_pages.append(len(PdfReader(io.BytesIO(pdf)).pages))
	writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
	writer.add_blank_page(width=72, height=72)
	stream = io.BytesIO()
	writer.write(stream)
	return stream.getvalue()


def return_pdf(doc, method, pdf):
	frappe.flags.after_print_pages.append(len(PdfReader(io.BytesIO(pdf)).pages))
	return pdf


def mark_before_print(doc, method, print_settings=None):
	doc.flags.prepared_for_print = doc.name


def replace_pdf_after_print(doc, method, pdf=None):
	frappe.flags.print_hook = {
		"marker": doc.flags.get("prepared_for_print"),
	}
	if doc.flags.get("prepared_for_print") != doc.name:
		return pdf
	return blank_pdf(page_count=3)


class TestPrintUtils(IntegrationTestCase):
	def _make_todo(self):
		doc = frappe.get_doc({"doctype": "ToDo", "description": "print utils test"})
		doc.insert(ignore_permissions=True)
		self.addCleanup(doc.delete, ignore_permissions=True)
		return doc

	def test_after_print_handlers_see_the_previous_result(self):
		"""When two apps both handle after_print, each handler gets the latest PDF,
		so the first app's change is not silently lost."""
		todo = self._make_todo()
		frappe.flags.after_print_pages = []
		self.addCleanup(lambda: setattr(frappe.local, "doc_events_hooks", None))

		with self.patch_hooks(
			{
				"doc_events": {
					"ToDo": {
						"after_print": [
							"frappe.utils.test_print_utils.add_blank_page",
							"frappe.utils.test_print_utils.return_pdf",
						]
					}
				}
			}
		):
			frappe.local.doc_events_hooks = None
			pdf = run_after_print(todo, blank_pdf())

		self.assertEqual(frappe.flags.after_print_pages, [1, 2])
		self.assertEqual(len(PdfReader(io.BytesIO(pdf)).pages), 2)

	def test_print_and_attachment_use_the_loaded_doc(self):
		"""A print and a mail attachment run before_print and after_print on the document they load."""
		todo = self._make_todo()
		frappe.flags.print_hook = {}
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(lambda: setattr(frappe.local, "doc_events_hooks", None))
		frappe.set_user("test@example.com")

		with self.patch_hooks(
			{
				"doc_events": {
					"ToDo": {
						"before_print": "frappe.utils.test_print_utils.mark_before_print",
						"after_print": "frappe.utils.test_print_utils.replace_pdf_after_print",
					}
				}
			}
		):
			frappe.local.doc_events_hooks = None

			pdf = frappe.get_print("ToDo", todo.name, as_pdf=True)
			self.assertEqual(frappe.flags.print_hook["marker"], todo.name)
			self.assertEqual(len(PdfReader(io.BytesIO(pdf)).pages), 3)

			frappe.flags.print_hook = {}
			attachment = frappe.attach_print("ToDo", todo.name)
			self.assertEqual(frappe.flags.print_hook["marker"], todo.name)
			self.assertEqual(len(PdfReader(io.BytesIO(attachment["fcontent"])).pages), 3)

	def test_after_print_runs_before_encryption(self):
		"""A handler sees the plain PDF, and the encrypted result contains its change."""
		todo = self._make_todo()
		frappe.flags.after_print_pages = []
		self.addCleanup(lambda: setattr(frappe.local, "doc_events_hooks", None))

		with self.patch_hooks(
			{"doc_events": {"ToDo": {"after_print": "frappe.utils.test_print_utils.add_blank_page"}}}
		):
			frappe.local.doc_events_hooks = None
			pdf = run_after_print(todo, blank_pdf(), password="s3cret")

		self.assertEqual(frappe.flags.after_print_pages, [1])
		reader = PdfReader(io.BytesIO(pdf))
		self.assertTrue(reader.is_encrypted)
		reader.decrypt("s3cret")
		self.assertEqual(len(reader.pages), 2)

	def test_print_methods_encrypt_when_password_is_set(self):
		"""print methods encrypt the PDF when a password is set.
		On get_print, attach_print, and _download_multi_pdf, the PDF can be encrypted.
		"""

		password = "s3cret"
		todo = self._make_todo()
		other = self._make_todo()

		def assert_encrypted(pdf):
			reader = PdfReader(io.BytesIO(pdf))
			self.assertTrue(reader.is_encrypted)
			reader.decrypt(password)

		assert_encrypted(frappe.get_print("ToDo", todo.name, as_pdf=True, password=password))
		assert_encrypted(frappe.attach_print("ToDo", todo.name, password=password)["fcontent"])

		from frappe.utils.print_format import _download_multi_pdf

		_download_multi_pdf("ToDo", [todo.name, other.name], options={"password": password})
		assert_encrypted(frappe.local.response.filecontent)
