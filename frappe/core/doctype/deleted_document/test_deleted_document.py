# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.core.doctype.deleted_document.deleted_document import restore
from frappe.tests import IntegrationTestCase


class TestDeletedDocument(IntegrationTestCase):
	def test_metadata_retention(self):
		frappe.set_user("Administrator")
		doc = frappe.get_doc({"doctype": "Note", "title": "Test Note", "content": "Test Content"}).insert()
		orig_owner = doc.owner
		orig_creation = doc.creation
		orig_modified = doc.modified
		orig_modified_by = doc.modified_by

		frappe.delete_doc("Note", doc.name, force=True)
		self.assertFalse(frappe.db.exists("Note", doc.name))

		log_name = frappe.db.get_value("Deleted Document", {"deleted_name": doc.name, "restored": 0})
		restore(log_name, alert=False)

		new_restored_name = frappe.db.get_value("Deleted Document", log_name, "new_name")

		restored_doc = frappe.get_doc("Note", new_restored_name)

		self.assertEqual(restored_doc.owner, orig_owner)
		self.assertEqual(str(restored_doc.creation), str(orig_creation))
		self.assertEqual(str(restored_doc.modified), str(orig_modified))
		self.assertEqual(restored_doc.modified_by, orig_modified_by)
