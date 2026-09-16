# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.desk.doctype.tag.tag import add_tag, remove_tag
from frappe.desk.form.load import get_tags
from frappe.tests import IntegrationTestCase
from frappe.tests.utils import queued_docinfo_updates

EXTRA_TEST_RECORD_DEPENDENCIES = ["User"]


class TestTagLink(IntegrationTestCase):
	def test_tag_changes_reach_the_document_room(self):
		"""A tag added or removed by a plain user announces itself to open record pages."""
		user = "test@example.com"
		todo = frappe.get_doc(doctype="ToDo", description="tag me", allocated_to=user).insert()
		seen = len(queued_docinfo_updates("tags"))

		with self.set_user(user):
			add_tag("urgent", "ToDo", todo.name)
			self.assertEqual(get_tags("ToDo", todo.name), "urgent")
			remove_tag("urgent", "ToDo", todo.name)
			self.assertEqual(get_tags("ToDo", todo.name), "")
		self.assertFalse(frappe.db.exists("Comment", {"reference_doctype": "Tag Link"}))

		updates = queued_docinfo_updates("tags")[seen:]
		self.assertEqual([u["action"] for u in updates], ["add", "delete"])
		for update in updates:
			self.assertEqual(update["doc"]["reference_doctype"], "ToDo")
			self.assertEqual(update["doc"]["reference_name"], todo.name)
			self.assertEqual(update["doc"]["tag"], "urgent")
