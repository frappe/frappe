import frappe
from frappe.boot import get_unseen_notes
from frappe.desk.doctype.note.note import mark_as_seen
from frappe.tests.utils import FrappeTestCase


class TestBootData(FrappeTestCase):
	def test_get_unseen_notes(self):
		frappe.db.delete("Note")
		frappe.db.delete("Note Seen By")
		note = frappe.get_doc(
			{
				"doctype": "Note",
				"title": "Test Note",
				"notify_on_login": 1,
				"content": "Test Note 1",
				"public": 1,
			}
		)
		note.insert()

		frappe.set_user("test@example.com")
		unseen_notes = [d.title for d in get_unseen_notes()]
		self.assertListEqual(unseen_notes, ["Test Note"])

		mark_as_seen(note.name)
		unseen_notes = [d.title for d in get_unseen_notes()]
		self.assertListEqual(unseen_notes, [])
