# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from unittest.mock import MagicMock, patch

import frappe
from frappe.desk.doctype.tag.tag import add_tag, remove_tag
from frappe.desk.form.load import get_tags
from frappe.tests import IntegrationTestCase
from frappe.tests.utils import queued_docinfo_updates

EXTRA_TEST_RECORD_DEPENDENCIES = ["User"]

wildcard_on_trash = MagicMock()


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

	def test_remove_tag_deletes_rows_without_doc_hooks(self):
		"""Removing a tag deletes only its row, runs no `on_trash` hook and still announces each tag."""
		todo = frappe.get_doc(doctype="ToDo", description="tag me thrice").insert()
		other = frappe.get_doc(doctype="ToDo", description="keep my tag").insert()
		for tag in ("alpha", "beta", "gamma"):
			add_tag(tag, "ToDo", todo.name)
		add_tag("alpha", "ToDo", other.name)
		seen = len(queued_docinfo_updates("tags"))

		wildcard_on_trash.reset_mock()
		hooks = {"*": {"on_trash": [f"{__name__}.wildcard_on_trash"]}}
		with patch.object(frappe, "get_doc_hooks", return_value=hooks):
			remove_tag("alpha", "ToDo", todo.name)
			remove_tag("gamma", "ToDo", todo.name)
		wildcard_on_trash.assert_not_called()

		self.assertEqual(tag_rows(todo.name), ["beta"])
		self.assertEqual(tag_rows(other.name), ["alpha"])
		self.assertFalse(frappe.db.exists("Comment", {"reference_doctype": "Tag Link"}))
		updates = queued_docinfo_updates("tags")[seen:]
		self.assertEqual(
			[(u["action"], u["doc"]["tag"]) for u in updates], [("delete", "alpha"), ("delete", "gamma")]
		)
		for update in updates:
			self.assertEqual(update["doc"]["reference_name"], todo.name)


def tag_rows(name: str) -> list[str]:
	return sorted(
		frappe.get_all("Tag Link", filters={"document_type": "ToDo", "document_name": name}, pluck="tag")
	)
