# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.favourite.favourite import get_favourites, toggle_favourite
from frappe.desk.form.load import get_docinfo
from frappe.tests import IntegrationTestCase

DESK_USER = "favourite-plain@example.com"


class TestFavourite(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# The shared test user is a System Manager here; a favourite's rules need a plain reader.
		if not frappe.db.exists("User", DESK_USER):
			frappe.get_doc(
				doctype="User",
				email=DESK_USER,
				first_name="Plain",
				send_welcome_email=0,
				roles=[{"role": "Desk User"}],
			).insert(ignore_permissions=True)

	def _users(self, todo):
		return [row.user for row in get_favourites("ToDo", todo.name)]

	def _todo(self, description, **fields):
		return frappe.get_doc(doctype="ToDo", description=description, **fields).insert()

	def test_toggle_adds_once_and_removes(self):
		todo = self._todo("favourite me")
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
		todo = self._todo("favourite in docinfo")
		toggle_favourite("ToDo", todo.name, add=True)

		get_docinfo(doctype="ToDo", name=todo.name)
		docinfo = frappe.response["docinfo"]
		self.assertEqual([row.user for row in docinfo.favourites], [frappe.session.user])
		self.assertIn(frappe.session.user, docinfo.user_info)

	def test_deleting_the_record_drops_its_favourites(self):
		todo = self._todo("favourite then delete")
		toggle_favourite("ToDo", todo.name, add=True)
		name = todo.name

		todo.delete()
		self.assertFalse(frappe.db.exists("Favourite", {"reference_doctype": "ToDo", "reference_name": name}))

	def test_rows_go_with_their_user(self):
		gone = "favourite-gone@example.com"
		frappe.get_doc(
			doctype="User",
			email=gone,
			first_name="Gone",
			send_welcome_email=0,
			roles=[{"role": "Desk User"}],
		).insert(ignore_permissions=True)
		todo = self._todo("favourited by a user about to go", allocated_to=gone)
		with self.set_user(gone):
			toggle_favourite("ToDo", todo.name, add=True)
		self.assertTrue(frappe.db.exists("Favourite", {"user": gone}))

		frappe.delete_doc("User", gone, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Favourite", {"user": gone}))

	def test_needs_read_on_the_record(self):
		# A ToDo is visible to its owner and its assignee; a plain user sees neither of these.
		mine = self._todo("private to the admin")
		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, toggle_favourite, "ToDo", mine.name, True)
		with self.set_user(DESK_USER):
			self.assertRaises(frappe.PermissionError, toggle_favourite, "ToDo", mine.name, True)

	def test_a_plain_user_writes_only_through_the_toggle_and_sees_only_their_own(self):
		theirs = self._todo("assigned to the plain user", allocated_to=DESK_USER)
		toggle_favourite("ToDo", theirs.name, add=True)

		with self.set_user(DESK_USER):
			# The happy path: read on the record is enough to favourite it.
			toggle_favourite("ToDo", theirs.name, add=True)
			self.assertEqual(sorted(self._users(theirs)), sorted(["Administrator", DESK_USER]))

			# The list shows the plain user their own row and nobody else's.
			listed = frappe.get_list("Favourite", filters={"reference_name": theirs.name}, pluck="user")
			self.assertEqual(listed, [DESK_USER])

			# And they can neither delete nor read the admin's row.
			admins = frappe.db.get_value(
				"Favourite", {"user": "Administrator", "reference_name": theirs.name}, "name"
			)
			self.assertFalse(frappe.has_permission("Favourite", "delete", doc=admins))
			self.assertFalse(frappe.has_permission("Favourite", "read", doc=admins))
