import frappe
from frappe.api.v2 import run_doc_method as run_doc_method_v2
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.handler import run_doc_method
from frappe.tests.utils import FrappeTestCase, patch_hooks


def approved_only(doc, ptype=None, user=None, debug=False):
	return ptype == "read" or bool(doc.approved)


class TestRunDocMethodPermission(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.doctype = (
			new_doctype(
				is_submittable=1,
				allow_rename=1,
				fields=[{"label": "Approved", "fieldname": "approved", "fieldtype": "Check"}],
				permissions=[{"role": "Desk User", "read": 1, "write": 1, "submit": 1, "cancel": 1}],
			)
			.insert()
			.name
		)
		cls.approval_hooks = {
			"has_permission": {cls.doctype: ["frappe.tests.test_run_doc_method_permission.approved_only"]}
		}

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")

		self.author = self.make_user()
		self.reader = self.make_user()

		frappe.set_user(self.author.name)
		self.private_note = self.make_note(public=0)
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

	def forged_approval(self):
		record = frappe.get_doc({"doctype": self.doctype}).insert(ignore_permissions=True)
		return {**record.as_dict(), "approved": 1}

	def test_v2_checks_write_against_stored_row(self):
		self.assertRaises(
			frappe.PermissionError, run_doc_method_v2, "add_comment", self.forged(self.private_note)
		)

	def test_handler_checks_read_against_stored_row(self):
		self.assertRaises(
			frappe.PermissionError,
			run_doc_method,
			"add_comment",
			docs=self.forged(self.private_note),
			args={"comment_type": "Comment"},
		)

	def test_submit_checks_permission_against_stored_row(self):
		with patch_hooks(self.approval_hooks):
			self.assertRaises(frappe.PermissionError, run_doc_method, "submit", docs=self.forged_approval())

	def test_rename_checks_write_against_stored_row(self):
		with patch_hooks(self.approval_hooks):
			self.assertRaises(
				frappe.PermissionError,
				run_doc_method,
				"rename",
				docs=self.forged_approval(),
				args={"name": frappe.generate_hash()},
			)
