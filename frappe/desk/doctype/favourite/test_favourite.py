# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.desk.doctype.favourite.favourite import get_favourites, list_favourites, toggle_favourite
from frappe.patches.v17_0 import address_saved_views_by_key
from frappe.tests import IntegrationTestCase
from frappe.tests.utils import queued_docinfo_updates

DESK_USER = "favourite-plain@example.com"
# A list every Desk User reads, and one only a System Manager reads.
READABLE = "Note"
PRIVATE = "Error Log"


def make_plain_user():
	# The shared test user is a System Manager here; a favourite's rules need a plain reader.
	if not frappe.db.exists("User", DESK_USER):
		frappe.get_doc(
			doctype="User",
			email=DESK_USER,
			first_name="Plain",
			send_welcome_email=0,
			roles=[{"role": "Desk User"}],
		).insert(ignore_permissions=True)


class TestFavourite(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_plain_user()

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

	def test_rows_follow_a_renamed_user(self):
		# `user` is a Link, so the rename rewrites it as it does every Link to the record.
		old, new = "favourite-old@example.com", "favourite-new@example.com"
		frappe.get_doc(
			doctype="User",
			email=old,
			first_name="Renamed",
			send_welcome_email=0,
			roles=[{"role": "Desk User"}],
		).insert(ignore_permissions=True)
		todo = self._todo("favourited by a user about to be renamed", allocated_to=old)
		with self.set_user(old):
			toggle_favourite("ToDo", todo.name, add=True)

		frappe.rename_doc("User", old, new, force=True)
		self.assertFalse(frappe.db.exists("Favourite", {"user": old}))
		self.assertEqual(self._users(todo), [new])

	def test_toggles_reach_the_record_room(self):
		"""A plain user's favourite announces itself to open record pages, add and remove alike."""
		theirs = self._todo("watched by the plain user", allocated_to=DESK_USER)
		seen = len(queued_docinfo_updates("favourites"))

		with self.set_user(DESK_USER):
			toggle_favourite("ToDo", theirs.name, add=True)
			toggle_favourite("ToDo", theirs.name, add=False)
		self.assertEqual(self._users(theirs), [])
		self.assertFalse(frappe.db.exists("Comment", {"reference_doctype": "Favourite"}))

		updates = queued_docinfo_updates("favourites")[seen:]
		self.assertEqual([u["action"] for u in updates], ["add", "delete"])
		for update in updates:
			self.assertEqual(update["doc"]["reference_doctype"], "ToDo")
			self.assertEqual(update["doc"]["reference_name"], theirs.name)
			self.assertEqual(update["doc"]["user"], DESK_USER)

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


class TestListAndViewFavourites(IntegrationTestCase):
	"""A list is stored as its DocType record, and a saved view as the list plus its key; read comes from the doctype."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_plain_user()

	def _starred(self, doctype, name, user=DESK_USER, view=""):
		return frappe.db.exists(
			"Favourite", {"user": user, "reference_doctype": doctype, "reference_name": name, "view": view}
		)

	def _view(self, doctype=READABLE, user=""):
		label = frappe.generate_hash(length=8)
		return frappe.get_doc(
			doctype="Doctype View",
			reference_doctype=doctype,
			type="List",
			user=user,
			label=label,
			settings={},
		).insert(ignore_permissions=True)

	def test_a_plain_user_stars_and_unstars_a_list(self):
		self.assertFalse(frappe.has_permission("DocType", "read", doc=READABLE, user=DESK_USER))

		with self.set_user(DESK_USER):
			toggle_favourite("DocType", READABLE, add=True)
			self.assertTrue(self._starred("DocType", READABLE))
			self.assertEqual(list_favourites(READABLE), {"list": True, "views": []})

			toggle_favourite("DocType", READABLE, add=False)
			self.assertFalse(self._starred("DocType", READABLE))

	def test_a_list_needs_read_on_its_doctype(self):
		with self.set_user(DESK_USER):
			self.assertRaises(frappe.PermissionError, toggle_favourite, "DocType", PRIVATE, True)
			self.assertRaises(frappe.DoesNotExistError, toggle_favourite, "DocType", "No Such Doctype", True)

	def test_a_list_has_one_row_whatever_case_the_name_comes_in(self):
		with self.set_user(DESK_USER):
			toggle_favourite("DocType", READABLE.lower(), add=True)
			self.assertTrue(self._starred("DocType", READABLE))
			self.assertEqual(list_favourites(READABLE), {"list": True, "views": []})
			toggle_favourite("DocType", READABLE.upper(), add=False)
		self.assertFalse(self._starred("DocType", READABLE))
		self.assertFalse(self._starred("DocType", PRIVATE))

	def test_a_plain_user_stars_and_unstars_a_saved_view_by_its_key(self):
		view = self._view()

		with self.set_user(DESK_USER):
			toggle_favourite("DocType", READABLE, add=True, view=view.key)
			self.assertTrue(self._starred("DocType", READABLE, view=view.key))
			self.assertEqual(list_favourites(READABLE), {"list": False, "views": [view.key]})

			toggle_favourite("DocType", READABLE, add=False, view=view.key)
			self.assertFalse(self._starred("DocType", READABLE, view=view.key))

	def test_a_star_on_a_view_survives_a_new_label_and_goes_with_the_view(self):
		view = self._view()
		with self.set_user(DESK_USER):
			toggle_favourite("DocType", READABLE, add=True, view=view.key)

		view.label = "Renamed"
		view.save(ignore_permissions=True)
		with self.set_user(DESK_USER):
			self.assertEqual(list_favourites(READABLE)["views"], [view.key])

		view.delete(ignore_permissions=True)
		self.assertFalse(self._starred("DocType", READABLE, view=view.key))

	def test_a_saved_view_must_be_seen_by_the_person_on_a_list_they_read(self):
		someone_elses = self._view(user="Administrator").key
		of_a_private_doctype = self._view(doctype=PRIVATE).key

		with self.set_user(DESK_USER):
			self.assertRaises(
				frappe.DoesNotExistError, toggle_favourite, "DocType", READABLE, True, someone_elses
			)
			self.assertRaises(
				frappe.PermissionError, toggle_favourite, "DocType", PRIVATE, True, of_a_private_doctype
			)
			self.assertRaises(
				frappe.DoesNotExistError, toggle_favourite, "DocType", READABLE, True, "no-such-view"
			)
			self.assertRaises(frappe.ValidationError, toggle_favourite, "ToDo", "anything", True, "a-view")
		self.assertFalse(frappe.db.exists("Favourite", {"user": DESK_USER, "view": ("!=", "")}))


class TestAddressSavedViewsByKey(IntegrationTestCase):
	"""The patch keys each saved view and moves each star on one to its list and key."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_plain_user()

	def _old_star(self, view_name):
		return (
			frappe.get_doc(
				doctype="Favourite",
				user=DESK_USER,
				reference_doctype="Doctype View",
				reference_name=view_name,
			)
			.insert(ignore_permissions=True, ignore_links=True)
			.name
		)

	def _unkeyed_view(self, user=""):
		view = frappe.get_doc(
			doctype="Doctype View",
			reference_doctype=READABLE,
			type="List",
			label="Probe Patch View",
			user=user,
			settings={},
		).insert(ignore_permissions=True)
		frappe.db.set_value("Doctype View", view.name, "key", "")
		return view

	def _patch(self):
		# The index swap is DDL, which would commit the test's rows.
		with (
			patch.object(address_saved_views_by_key, "drop_unique"),
			patch.object(address_saved_views_by_key, "add_view_address"),
		):
			address_saved_views_by_key.execute()

	def test_a_view_gets_a_key_and_its_star_moves_while_a_star_on_a_gone_view_goes(self):
		view = self._unkeyed_view()
		self._old_star(view.name)
		self._old_star("no-such-view-row")

		self._patch()

		key = frappe.db.get_value("Doctype View", view.name, "key")
		self.assertTrue(key.startswith("probe-patch-view"))
		self.assertEqual(
			frappe.get_all(
				"Favourite",
				filters={"user": DESK_USER},
				fields=["reference_doctype", "reference_name", "view"],
			),
			[{"reference_doctype": "DocType", "reference_name": READABLE, "view": key}],
		)

	def test_two_people_s_views_with_one_label_get_two_keys(self):
		first, second = self._unkeyed_view("Administrator"), self._unkeyed_view(DESK_USER)

		self._patch()

		keys = {frappe.db.get_value("Doctype View", view.name, "key") for view in (first, second)}
		self.assertEqual(len(keys), 2)

	def test_a_star_on_another_person_s_view_goes(self):
		star = self._old_star(self._unkeyed_view("Administrator").name)

		self._patch()

		self.assertFalse(frappe.db.exists("Favourite", star))
