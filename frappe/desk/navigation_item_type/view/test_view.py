# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The `View` navigation item type, `frappe/desk/navigation_item_type/view/view.py`, through `save_arrangement`."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.desk.navigation_item_type.view.view import can_see, mark_rows
from frappe.shell.arrangement import get_arrangement, save_arrangement
from frappe.shell.navigation import resolve_navigation
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_navigation_arrangement import (
	APP,
	OwnRowsTestCase,
	a_person,
	own_stored,
	rail_keys,
	showing,
	shown,
	stored,
)
from frappe.tests.test_shell_navigation import doctype_item, make_sidebar

KEY = "user:k3f9a2"
SITE_KEY = "site:k3f9a2"
VIEW_KEY_APPLIES = "frappe.desk.doctype.doctype_view.key_space.applies_to"


def a_view_row(doctype: str, payload, key: str = KEY, **kwargs) -> dict:
	return {
		"key": key,
		"item_type": "View",
		"link_doctype": "DocType",
		"link_to": doctype,
		"payload": payload,
		"label": "A view",
		**kwargs,
	}


def make_view(label: str, doctype: str = "ToDo", user: str = "", type: str = "List"):
	"""A saved view; a blank `user` is the site's."""
	return frappe.get_doc(
		{
			"doctype": "Doctype View",
			"reference_doctype": doctype,
			"label": label,
			"user": user,
			"type": type,
			"settings": {},
		}
	).insert(ignore_permissions=True)


def a_payload_of_key_length(length: int) -> dict:
	return {"view": "a" * length}


class ViewTestCase(OwnRowsTestCase):
	def setUp(self):
		super().setUp()
		# A set-up that runs as the Desk User cannot insert; the views are the site's or their own.
		self.other = a_person("view_row_other@example.com", role="Desk User")

	def made(self, label: str, **kwargs) -> str:
		"""Make a saved view as Administrator and return its key."""
		with set_user("Administrator"):
			return make_view(label, **kwargs).key

	def save(self, *added: dict, scope: str = "user"):
		return save_arrangement("Rail", APP, showing(shown("todo"), shown("note"), *added), scope=scope)

	def refused(self, row: dict, pattern: str | None = None, scope: str = "user"):
		with self.assertRaisesRegex(frappe.ValidationError, pattern or ""):
			self.save(row, scope=scope)

		self.assertFalse(stored())


class TestCanSee(ViewTestCase):
	def rows(self, *targets: tuple[str, str]) -> list[dict]:
		return [
			a_view_row(doctype, {"view": key}, key=f"user:r{idx}")
			for idx, (doctype, key) in enumerate(targets)
		]

	def seen(self, *targets: tuple[str, str], user: str | None = None) -> list[tuple[str, str]]:
		context = SimpleNamespace(
			user=user or self.user, may_read=lambda doctype: frappe.has_permission(doctype)
		)
		items = self.rows(*targets)

		return [
			(
				item["link_to"],
				json.loads(item["payload"])["view"]
				if isinstance(item["payload"], str)
				else item["payload"]["view"],
			)
			for item in can_see(items, context)
		]

	def test_a_plain_list_and_cards_row_is_kept(self):
		targets = [("ToDo", "list"), ("ToDo", "cards")]

		self.assertEqual(self.seen(*targets), targets)

	def test_a_plain_row_whose_type_does_not_apply_is_dropped(self):
		with patch(VIEW_KEY_APPLIES, return_value=False):
			self.assertEqual(self.seen(("ToDo", "cards")), [])

	def test_a_person_s_own_view_is_kept_for_them_and_dropped_for_another_user(self):
		key = self.made("Mine", user=self.user)

		self.assertEqual(self.seen(("ToDo", key)), [("ToDo", key)])
		self.assertEqual(self.seen(("ToDo", key), user=self.other), [])

	def test_a_site_view_and_an_app_view_are_kept(self):
		key = self.made("Shared")

		targets = [("ToDo", key), ("ToDo", "open")]
		self.assertEqual(self.seen(*targets), targets)

	def test_a_deleted_view_s_row_is_dropped(self):
		key = self.made("Doomed", user=self.user)
		frappe.db.delete("Doctype View", {"reference_doctype": "ToDo", "key": key})

		self.assertEqual(self.seen(("ToDo", key)), [])

	def test_a_doctype_the_person_cannot_read_is_dropped(self):
		self.assertEqual(self.seen(("System Settings", "list")), [])

	def test_one_call_with_several_saved_keys_makes_one_doctype_view_query(self):
		keys = [self.made(label, user=self.user) for label in ("One", "Two", "Three")]
		context = SimpleNamespace(user=self.user, may_read=lambda doctype: True)
		items = self.rows(*[("ToDo", key) for key in keys])

		with self.assertQueryCount(1):
			self.assertEqual(len(can_see(items, context)), 3)


class TestValidateViewRow(ViewTestCase):
	def test_a_spaced_out_payload_is_stored_compact(self):
		self.save(a_view_row("ToDo", '{ "view": "open" }'))

		self.assertEqual(own_stored()[0].payload, '{"view":"open"}')

	def test_an_object_payload_is_stored_compact(self):
		self.save(a_view_row("ToDo", {"view": "cards"}))

		self.assertEqual(own_stored()[0].payload, '{"view":"cards"}')

	def test_an_extra_key_is_refused(self):
		self.refused(a_view_row("ToDo", {"view": "open", "x": 1}), "needs a view and nothing else")

	def test_a_payload_that_is_not_an_object_is_refused(self):
		for payload in ('["open"]', "not json", "[]", None, ""):
			with self.subTest(payload=payload):
				self.refused(a_view_row("ToDo", payload))

	def test_a_bad_key_is_refused_at_both_scopes(self):
		# At user scope the generic "cannot open the target" check speaks first; at site scope the type does.
		for view in ("Open", "open view", "-open", "open-", "a--b", "", 7, None):
			with self.subTest(view=view):
				self.refused(a_view_row("ToDo", {"view": view}), "cannot open the target")

		with set_user(a_person()):
			for view in ("Open", "open view", "-open", "open-", "a--b", "", 7, None):
				with self.subTest(view=view, scope="site"):
					self.refused(
						a_view_row("ToDo", {"view": view}, key=SITE_KEY), "does not name a view", scope="site"
					)

	def test_a_key_of_65_characters_is_refused_and_one_of_64_is_stored_in_75_bytes(self):
		with set_user(a_person()):
			self.refused(
				a_view_row("ToDo", a_payload_of_key_length(65), key=SITE_KEY),
				"does not name a view",
				scope="site",
			)

		with (
			patch(VIEW_KEY_APPLIES, return_value=True),
			patch("frappe.desk.navigation_item_type.view.view.open_views", return_value={("ToDo", "a" * 64)}),
		):
			self.save(a_view_row("ToDo", a_payload_of_key_length(64)))

		self.assertEqual(len(own_stored()[0].payload.encode()), 75)

	def test_a_single_doctype_is_refused(self):
		with set_user(a_person()):
			self.refused(
				a_view_row("System Settings", {"view": "list"}, key=SITE_KEY),
				"A Single doctype has no views",
				scope="site",
			)

	def test_a_deleted_view_is_refused_at_both_scopes(self):
		self.refused(a_view_row("ToDo", {"view": "no-such-view"}), "cannot open the target")

		with set_user(a_person()):
			self.refused(
				a_view_row("ToDo", {"view": "no-such-view"}, key=SITE_KEY), "no longer exists", scope="site"
			)

	def test_another_person_s_own_view_is_refused_at_user_scope(self):
		key = self.made("Theirs", user=self.other)

		self.refused(a_view_row("ToDo", {"view": key}), "cannot open the target")

		with set_user(a_person()):
			self.refused(
				a_view_row("ToDo", {"view": key}, key=SITE_KEY), "can't open this view", scope="site"
			)

	def test_a_person_s_own_view_is_accepted_at_user_scope(self):
		key = self.made("Mine", user=self.user)

		self.save(a_view_row("ToDo", {"view": key}))

		self.assertEqual(len(own_stored()), 1)

	def test_the_admin_s_own_view_is_refused_at_site_scope(self):
		manager = a_person()
		key = self.made("Admin's", user=manager)

		with set_user(manager):
			self.refused(
				a_view_row("ToDo", {"view": key}, key=SITE_KEY), "Publish this view first", scope="site"
			)

	def test_a_site_view_an_app_view_and_a_plain_view_are_accepted_at_site_scope(self):
		shared = self.made("Shared")

		with set_user(a_person()):
			for view in (shared, "open", "list"):
				with self.subTest(view=view):
					self.save(a_view_row("ToDo", {"view": view}, key=SITE_KEY), scope="site")
					self.assertIn(SITE_KEY, [row["key"] for row in resolve_navigation(APP)["rail"]])


class TestMarkRows(ViewTestCase):
	def row(self, view: str, key: str = KEY) -> dict:
		return a_view_row("ToDo", {"view": view}, key=key)

	def test_a_live_row_has_no_marker_and_a_deleted_view_s_row_has_one(self):
		key = self.made("Mine", user=self.user)
		gone = self.made("Gone", user=self.user)
		frappe.db.delete("Doctype View", {"reference_doctype": "ToDo", "key": gone})

		marks = mark_rows(
			[self.row(key, "user:a"), self.row(gone, "user:b"), self.row("open", "user:c")], "user"
		)

		self.assertEqual(marks, {"user:b": {"view_deleted": 1}})

	def test_a_row_whose_doctype_is_gone_is_marked_at_the_site_scope_and_reads_no_access_at_the_user_scope(
		self,
	):
		row = a_view_row("No Such Doctype", {"view": "list"})

		self.assertEqual(mark_rows([row], "site"), {KEY: {"view_deleted": 1}})
		self.assertEqual(mark_rows([row], "user"), {})

	def test_a_deleted_view_on_a_doctype_the_person_cannot_read_is_left_for_no_access(self):
		key = self.made("Mine", user=self.user)
		frappe.db.delete("Doctype View", {"reference_doctype": "ToDo", "key": key})
		row = self.row(key)

		self.assertEqual(mark_rows([row], "user"), {KEY: {"view_deleted": 1}})

		with patch("frappe.has_permission", return_value=False):
			self.assertEqual(mark_rows([row], "user"), {})
			self.assertEqual(mark_rows([row], "site"), {KEY: {"view_deleted": 1}})

	def test_the_site_scope_marks_a_view_only_the_person_had(self):
		key = self.made("Mine", user=self.user)

		self.assertEqual(mark_rows([self.row(key)], "site"), {KEY: {"view_deleted": 1}})
		self.assertEqual(mark_rows([self.row(key)], "user"), {})

	def test_the_editor_s_read_shows_view_deleted_and_a_save_that_sends_it_back_stores_nothing(self):
		key = self.made("Mine", user=self.user)
		self.save(a_view_row("ToDo", {"view": key}))
		frappe.db.delete("Doctype View", {"reference_doctype": "ToDo", "key": key})

		row = next(row for row in get_arrangement("Rail", APP) if row["key"] == KEY)
		self.assertEqual(row.get("view_deleted"), 1)

		save_arrangement("Rail", APP, showing(shown("todo"), shown("note"), row))

		self.assertFalse(any("view_deleted" in row.as_dict() for row in own_stored()))


class TestAShippedViewRow(ViewTestCase):
	def rows(self, payload):
		return [
			doctype_item("todo", "ToDo"),
			{
				"doctype": "Navigation Item",
				"key": "a-view",
				"item_type": "View",
				"link_doctype": "DocType",
				"link_to": "ToDo",
				"payload": payload,
			},
		]

	def test_a_sidebar_with_a_bad_view_payload_is_refused_in_developer_mode(self):
		for payload in ('{"view":"open","x":1}', "not json", '{"view":"Not A Key"}'):
			with (
				self.subTest(payload=payload),
				self.assertRaisesRegex(
					frappe.ValidationError, "needs a view|not an object|does not name a view"
				),
			):
				make_sidebar(self.rows(payload), standard=1)

	def test_a_sidebar_with_a_good_view_payload_is_accepted(self):
		make_sidebar(self.rows('{"view":"open"}'), standard=1)


class TestBoot(ViewTestCase):
	def test_the_row_is_in_the_navigation_and_leaves_it_after_the_view_is_deleted(self):
		key = self.made("Mine", user=self.user)
		self.save(a_view_row("ToDo", {"view": key}))
		self.assertIn(KEY, rail_keys())

		frappe.db.delete("Doctype View", {"reference_doctype": "ToDo", "key": key})
		frappe.clear_cache(user=self.user)

		self.assertNotIn(KEY, rail_keys())


class TestTwoSidebarsShareAKey(ViewTestCase):
	def test_a_key_two_containers_share_is_marked_in_the_container_that_holds_the_deleted_view(self):
		from frappe.shell.arrangement_editor import mark

		live = a_view_row("ToDo", {"view": "open"}, key="site:abc123")
		gone = a_view_row("ToDo", {"view": "no-such-view"}, key="site:abc123")
		rail, sidebar = [dict(live)], [dict(gone)]

		mark([rail, sidebar], "user")

		self.assertNotIn("view_deleted", rail[0])
		self.assertEqual(sidebar[0]["view_deleted"], 1)
