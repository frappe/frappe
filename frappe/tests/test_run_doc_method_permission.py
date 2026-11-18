import frappe
from frappe.api.v2 import run_doc_method as run_doc_method_v2
from frappe.handler import run_doc_method
from frappe.tests import IntegrationTestCase


class TestRunDocMethodPermission(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")

		self.author = self.make_user()
		self.reader = self.make_user()

		frappe.set_user(self.author.name)
		self.private_note = self.make_note(public=0)
		self.public_note = self.make_note(public=1)
		frappe.set_user(self.reader.name)

		previous_request = getattr(frappe.local, "request", None)

		def restore_request():
			if previous_request is None:
				if hasattr(frappe.local, "request"):
					delattr(frappe.local, "request")
			else:
				frappe.local.request = previous_request

		self.addCleanup(restore_request)
		frappe.local.request = frappe._dict(method="POST")

	def make_user(self):
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": f"{frappe.generate_hash()}@example.com",
				"first_name": "Note",
				"send_welcome_email": 0,
				"roles": [{"role": "Desk User"}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("User", user.name, force=True, ignore_permissions=True))
		return user

	def make_note(self, public):
		note = frappe.get_doc({"doctype": "Note", "title": frappe.generate_hash(), "public": public}).insert(
			ignore_permissions=True
		)
		self.addCleanup(lambda: frappe.delete_doc("Note", note.name, force=True, ignore_permissions=True))
		return note

	def forged(self, note):
		return {
			"doctype": "Note",
			"name": note.name,
			"owner": self.reader.name,
			"modified": str(note.modified),
		}

	def test_v2_checks_write_against_stored_row(self):
		self.assertRaises(
			frappe.PermissionError, run_doc_method_v2, "discard", self.forged(self.private_note)
		)

	def test_handler_checks_read_against_stored_row(self):
		self.assertRaises(
			frappe.PermissionError, run_doc_method, "discard", docs=self.forged(self.private_note)
		)

	def test_discard_checks_write_against_stored_row(self):
		self.assertRaises(
			frappe.PermissionError, run_doc_method, "discard", docs=self.forged(self.public_note)
		)
