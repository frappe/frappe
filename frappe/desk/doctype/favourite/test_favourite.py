# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.favourite.favourite import get_favourites, toggle_favourite
from frappe.desk.form.load import get_docinfo
from frappe.tests import IntegrationTestCase


class TestFavourite(IntegrationTestCase):
	def _users(self, todo):
		return [row.user for row in get_favourites("ToDo", todo.name)]

	def test_toggle_adds_once_and_removes(self):
		todo = frappe.get_doc(doctype="ToDo", description="favourite me").insert()
		modified = frappe.db.get_value("ToDo", todo.name, "modified")

		toggle_favourite("ToDo", todo.name, add=True)
		toggle_favourite("ToDo", todo.name, add="Yes")
		self.assertEqual(self._users(todo), [frappe.session.user])

		toggle_favourite("ToDo", todo.name, add=False)
		self.assertEqual(self._users(todo), [])

		# A favourite is the reader's own: no timestamp bump, no like, nothing on the timeline.
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "modified"), modified)
		self.assertFalse(frappe.db.get_value("ToDo", todo.name, "_liked_by"))
		self.assertFalse(
			frappe.db.exists("Comment", {"reference_doctype": "ToDo", "reference_name": todo.name})
		)

	def test_docinfo_carries_favourites_and_names_them(self):
		todo = frappe.get_doc(doctype="ToDo", description="favourite in docinfo").insert()
		toggle_favourite("ToDo", todo.name, add=True)

		get_docinfo(doctype="ToDo", name=todo.name)
		docinfo = frappe.response["docinfo"]
		self.assertEqual([row.user for row in docinfo.favourites], [frappe.session.user])
		self.assertIn(frappe.session.user, docinfo.user_info)

	def test_deleting_the_record_drops_its_favourites(self):
		todo = frappe.get_doc(doctype="ToDo", description="favourite then delete").insert()
		toggle_favourite("ToDo", todo.name, add=True)
		name = todo.name

		todo.delete()
		self.assertFalse(frappe.db.exists("Favourite", {"reference_doctype": "ToDo", "reference_name": name}))

	def test_needs_read_on_the_record(self):
		todo = frappe.get_doc(doctype="ToDo", description="private").insert()
		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, toggle_favourite, "ToDo", todo.name, True)
