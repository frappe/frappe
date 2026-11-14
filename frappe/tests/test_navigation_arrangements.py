# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The navigation editor's one read and one write, `frappe/shell/arrangement_editor.py`."""

import hashlib
import json
from unittest.mock import patch

import frappe
from frappe.shell.arrangement import (
	_target,
	get_arrangements,
	get_default_arrangements,
	save_arrangement,
	save_arrangements,
	save_navigation_layout,
)
from frappe.shell.navigation import resolve_navigation
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_navigation_arrangement import (
	OwnRowsTestCase,
	a_person,
	own,
	own_stored,
	shown,
	stored,
)
from frappe.tests.test_shell_navigation import (
	ADDRESS_KEY,
	APP,
	NavigationTestCase,
	doctype_item,
	item,
	keys,
	make_own_sidebar,
	make_rail,
	make_sidebar,
)

OWN_SIDEBAR = "user:abc123"


def save(rail=None, sidebars=None, version=None, scope="user"):
	"""One editor save; the version defaults to the one the editor would hold."""
	containers = {"sidebars": sidebars or {}}
	if rail is not None:
		containers["rail"] = rail

	if version is None:
		version = get_arrangements(APP, scope)["version"]

	return save_arrangements(APP, scope, containers, version)


class EditorTestCase(OwnRowsTestCase):
	def setUp(self):
		super().setUp()
		make_sidebar([doctype_item("sb_todo", "ToDo"), doctype_item("sb_note", "Note")], standard=1)


class TestGetArrangements(EditorTestCase):
	def test_it_returns_every_container_with_hidden_rows_kept(self):
		save_arrangement("Rail", APP, [shown("todo", hidden=1), shown("note")])

		result = get_arrangements(APP)

		self.assertEqual(
			set(result), {"version", "can_edit_site", "has_saved", "navigation_layouts", "rail", "sidebars"}
		)
		self.assertEqual(keys(result["rail"]), ["todo", "note"])
		self.assertEqual(result["rail"][0]["hidden"], 1)
		self.assertEqual(keys(result["sidebars"][ADDRESS_KEY]), ["sb_todo", "sb_note"])
		self.assertEqual(result["navigation_layouts"], {"standard": "", "site": "", "user": ""})

	def test_hidden_by_says_which_level_hid_a_row(self):
		with set_user("Administrator"):
			save_arrangement("Rail", APP, [shown("todo", hidden=1), shown("note")], "site")
		save_arrangement("Rail", APP, [shown("todo", hidden=1), shown("note", hidden=1)])

		rows = {row["key"]: row for row in get_arrangements(APP)["rail"]}

		self.assertEqual(rows["todo"]["hidden_by"], "site")
		self.assertEqual(rows["note"]["hidden_by"], "user")

	def test_a_person_can_show_a_row_the_site_hid(self):
		with set_user("Administrator"):
			save_arrangement("Rail", APP, [shown("todo", hidden=1), shown("note")], "site")
		save_arrangement("Rail", APP, [shown("todo"), shown("note")])

		self.assertNotIn("hidden", get_arrangements(APP)["rail"][0])

	def test_no_access_marks_an_own_row_the_person_can_no_longer_open(self):
		make_rail([item("user:k3f9a2", link_doctype="DocType", link_to="Role", added=1)], user=self.user)

		rows = get_arrangements(APP)["rail"]

		self.assertEqual(rows[-1]["key"], "user:k3f9a2")
		self.assertEqual(rows[-1]["no_access"], 1)

	def test_a_marker_hook_is_called_once_per_type_with_that_types_rows(self):
		calls = []

		def mark_rows(rows, scope):
			calls.append(([row["key"] for row in rows], scope))
			return {"todo": {"view_deleted": 1}}

		hooks = {"navigation_item_markers": {"DocType": ["frappe.tests.test_navigation_arrangements.marker"]}}
		with (
			patch("frappe.get_hooks", side_effect=lambda hook, **kw: hooks.get(hook, {})),
			patch("frappe.tests.test_navigation_arrangements.marker", mark_rows, create=True),
		):
			result = get_arrangements(APP)

		self.assertEqual(len(calls), 1)
		self.assertEqual(calls[0][1], "user")
		self.assertEqual(result["rail"][0]["view_deleted"], 1)
		self.assertNotIn("view_deleted", result["rail"][1])

	def test_no_registered_marker_marks_nothing(self):
		self.assertFalse(any("view_deleted" in row for row in get_arrangements(APP)["rail"]))

	def test_a_save_that_sends_the_markers_back_stores_nothing(self):
		make_rail([item("user:k3f9a2", link_doctype="DocType", link_to="Role", added=1)], user=self.user)
		rows = [{**row, "hidden_by": "site", "view_deleted": 1} for row in get_arrangements(APP)["rail"]]

		save(rail=rows)

		self.assertFalse(
			any(
				field in row.as_dict()
				for row in stored()
				for field in ("view_deleted", "hidden_by", "no_access")
			)
		)

	def test_the_version_changes_after_a_write_at_this_level_only(self):
		before = get_arrangements(APP)["version"]
		self.assertEqual(before, hashlib.sha1(b"[]").hexdigest())

		with set_user("Administrator"):
			save_arrangement("Rail", APP, [shown("note"), shown("todo")], "site")
		self.assertEqual(get_arrangements(APP)["version"], before)

		save_arrangement("Rail", APP, [shown("todo"), shown("note")])
		self.assertNotEqual(get_arrangements(APP)["version"], before)

	def test_can_edit_site_is_for_a_system_manager(self):
		self.assertFalse(get_arrangements(APP)["can_edit_site"])

		with set_user(a_person()):
			self.assertTrue(get_arrangements(APP, "site")["can_edit_site"])

	def test_the_site_scope_needs_a_system_manager(self):
		with self.assertRaises(frappe.PermissionError):
			get_arrangements(APP, "site")

	def test_a_persons_own_sidebar_is_listed_for_them_and_not_at_site_scope(self):
		make_own_sidebar(
			OWN_SIDEBAR,
			[item("user:aaaaaa", link_doctype="DocType", link_to="ToDo", added=1)],
			user=self.user,
		)

		self.assertIn(OWN_SIDEBAR, get_arrangements(APP)["sidebars"])

		with set_user(a_person()):
			self.assertNotIn(OWN_SIDEBAR, get_arrangements(APP, "site")["sidebars"])


class TestGetDefaultArrangements(EditorTestCase):
	def test_has_saved_says_whether_this_level_stored_a_rail_or_a_sidebar(self):
		self.assertFalse(get_arrangements(APP)["has_saved"])

		save_arrangement("Rail", APP, [shown("note"), shown("todo")])
		self.assertTrue(get_arrangements(APP)["has_saved"])

		with set_user("Administrator"):
			self.assertFalse(get_arrangements(APP, "site")["has_saved"])

	def test_has_saved_counts_a_sidebar_alone(self):
		save_arrangement("Sidebar", ADDRESS_KEY, [shown("sb_note"), shown("sb_todo")])

		self.assertTrue(get_arrangements(APP)["has_saved"])

	def test_has_saved_counts_a_layout_alone(self):
		save_navigation_layout(APP, "sidebar_only")

		self.assertTrue(get_arrangements(APP)["has_saved"])

		with set_user("Administrator"):
			self.assertFalse(get_arrangements(APP, "site")["has_saved"])

	def test_has_saved_counts_a_site_layout_alone_at_the_site_level(self):
		with set_user("Administrator"):
			save_navigation_layout(APP, "floating_rail", scope="site")

			self.assertTrue(get_arrangements(APP, "site")["has_saved"])

		self.assertFalse(get_arrangements(APP)["has_saved"])

	def test_a_person_gets_the_site_level_with_their_own_changes_gone(self):
		with set_user("Administrator"):
			save_arrangement("Rail", APP, [shown("note"), shown("todo", hidden=1)], "site")
		save_arrangement("Rail", APP, [shown("todo"), shown("note")])

		result = get_default_arrangements(APP)

		self.assertEqual(set(result), {"rail", "sidebars"})
		self.assertEqual(keys(result["rail"]), ["note", "todo"])
		self.assertEqual(result["rail"][1]["hidden"], 1)
		self.assertEqual(result["rail"][1]["hidden_by"], "site")
		self.assertEqual(keys(result["sidebars"][ADDRESS_KEY]), ["sb_todo", "sb_note"])

	def test_the_site_level_gets_what_the_apps_ship(self):
		with set_user("Administrator"):
			save_arrangement("Rail", APP, [shown("note"), shown("todo", hidden=1)], "site")

			result = get_default_arrangements(APP, "site")

		self.assertEqual(keys(result["rail"]), ["todo", "note"])
		self.assertFalse(any(row.get("hidden") for row in result["rail"]))

	def test_the_level_below_has_no_row_or_sidebar_this_level_added(self):
		make_rail([item("user:k3f9a2", link_doctype="DocType", link_to="Role", added=1)], user=self.user)
		make_own_sidebar(
			OWN_SIDEBAR,
			[item("user:aaaaaa", link_doctype="DocType", link_to="ToDo", added=1)],
			user=self.user,
		)

		result = get_default_arrangements(APP)

		self.assertNotIn("user:k3f9a2", keys(result["rail"]))
		self.assertNotIn(OWN_SIDEBAR, result["sidebars"])
		self.assertIn(OWN_SIDEBAR, get_arrangements(APP)["sidebars"])

	def test_it_stores_nothing(self):
		get_default_arrangements(APP)

		self.assertEqual(stored(), [])

	def test_the_site_scope_needs_a_system_manager(self):
		with self.assertRaises(frappe.PermissionError):
			get_default_arrangements(APP, "site")

	def test_a_bad_scope_is_a_validation_error(self):
		for scope in ("everyone", "base", ""):
			with (
				self.subTest(scope=scope),
				self.assertRaisesRegex(frappe.ValidationError, "not an arrangement scope"),
			):
				get_default_arrangements(APP, scope)


class TestSaveArrangements(EditorTestCase):
	def test_the_rail_and_two_sidebars_are_written_in_one_call(self):
		save(
			rail=[shown("todo"), own("user:rrrrrr", "Note", opens_sidebar=OWN_SIDEBAR), shown("note")],
			sidebars={
				ADDRESS_KEY: [shown("sb_note"), shown("sb_todo")],
				OWN_SIDEBAR: [own("user:aaaaaa", "ToDo")],
			},
		)

		navigation = resolve_navigation(APP)
		self.assertEqual(keys(navigation["sidebars"][ADDRESS_KEY]), ["sb_note", "sb_todo"])
		self.assertEqual(keys(navigation["sidebars"][OWN_SIDEBAR]), ["user:aaaaaa"])
		self.assertEqual(navigation["rail"][1]["opens_sidebar"], OWN_SIDEBAR)

	def test_a_refusal_in_the_second_sidebar_leaves_the_first_unwritten(self):
		with self.assertRaises(frappe.ValidationError):
			save(
				sidebars={
					ADDRESS_KEY: [shown("sb_note"), shown("sb_todo")],
					OWN_SIDEBAR: [own("user:aaaaaa", "ToDo", item_type="Nope")],
				}
			)

		self.assertEqual(keys(resolve_navigation(APP)["sidebars"][ADDRESS_KEY]), ["sb_todo", "sb_note"])

	def test_a_stale_version_is_refused(self):
		version = get_arrangements(APP)["version"]
		save_arrangement("Rail", APP, [shown("note"), shown("todo")])

		with self.assertRaises(frappe.TimestampMismatchError):
			save(rail=[shown("todo"), shown("note")], version=version)

	def test_a_sidebar_of_another_app_is_refused(self):
		real = _target

		def elsewhere(container, address, scope, new_in=""):
			target = real(container, address, scope, new_in)
			return target._replace(app="other") if container == "Sidebar" else target

		with (
			patch("frappe.shell.arrangement_editor._target", elsewhere),
			self.assertRaisesRegex(frappe.ValidationError, "is not a sidebar of"),
		):
			save(sidebars={ADDRESS_KEY: []})

	def test_the_caps_count_the_payload_and_the_stored_containers(self):
		stored_rows = [
			item(f"user:s{i:05d}", link_doctype="DocType", link_to="ToDo", added=1) for i in range(60)
		]
		make_own_sidebar("user:storeb", stored_rows, user=self.user)
		make_rail(
			[
				item(
					"user:k3f9a2",
					link_doctype="DocType",
					link_to="ToDo",
					added=1,
					opens_sidebar="user:storeb",
				)
			],
			user=self.user,
		)
		rows = [own(f"user:r{i:05d}", "Note") for i in range(41)]

		with self.assertRaisesRegex(frappe.ValidationError, "up to 100"):
			save(sidebars={ADDRESS_KEY: [shown("sb_todo"), shown("sb_note"), *rows]})

		save(sidebars={ADDRESS_KEY: [shown("sb_todo"), shown("sb_note"), *rows[:39]]})

	def test_an_own_sidebar_row_that_has_a_sidebar_or_children_cannot_cross(self):
		for row in (
			own("user:aaaaaa", "ToDo", opens_sidebar="user:bbbbbb"),
			own("user:aaaaaa", "ToDo", item_type="Sidebar"),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "Remove its sidebar first"):
				save(sidebars={ADDRESS_KEY: [shown("sb_todo"), shown("sb_note"), row]})

		with self.assertRaisesRegex(frappe.ValidationError, "Move its children out first"):
			save(rail=[shown("todo"), shown("note", parent_key="todo")])

	def test_opens_sidebar_must_name_an_own_sidebar_of_this_level(self):
		with self.assertRaises(frappe.ValidationError):
			save(rail=[shown("todo", opens_sidebar="site:abc123"), shown("note")])

		with self.assertRaises(frappe.ValidationError):
			save(rail=[shown("todo", opens_sidebar=OWN_SIDEBAR), shown("note")])

	def test_one_sidebar_opens_from_one_rail_row(self):
		with self.assertRaisesRegex(frappe.ValidationError, "already opens"):
			save(
				rail=[shown("todo", opens_sidebar=OWN_SIDEBAR), shown("note", opens_sidebar=OWN_SIDEBAR)],
				sidebars={OWN_SIDEBAR: [own("user:aaaaaa", "ToDo")]},
			)

	def test_only_a_rail_row_may_open_a_sidebar(self):
		make_own_sidebar(
			"user:bbbbbb",
			[item("user:cccccc", link_doctype="DocType", link_to="Note", added=1)],
			user=self.user,
		)

		with self.assertRaisesRegex(frappe.ValidationError, "Only a rail item"):
			save(sidebars={ADDRESS_KEY: [shown("sb_todo", opens_sidebar="user:bbbbbb"), shown("sb_note")]})

	def test_an_own_sidebar_nothing_opens_is_deleted(self):
		make_own_sidebar(
			OWN_SIDEBAR,
			[item("user:aaaaaa", link_doctype="DocType", link_to="ToDo", added=1)],
			user=self.user,
		)

		save(rail=[shown("todo"), shown("note")])

		self.assertFalse(frappe.db.exists("Sidebar", {"key": OWN_SIDEBAR}))

	def test_deleting_an_own_rail_row_deletes_its_sidebar(self):
		save(
			rail=[shown("todo"), own("user:rrrrrr", "Note", opens_sidebar=OWN_SIDEBAR), shown("note")],
			sidebars={OWN_SIDEBAR: [own("user:aaaaaa", "ToDo")]},
		)
		self.assertTrue(frappe.db.exists("Sidebar", {"key": OWN_SIDEBAR}))

		save(rail=[shown("todo"), shown("note")])

		self.assertFalse(frappe.db.exists("Sidebar", {"key": OWN_SIDEBAR}))
		self.assertEqual(own_stored(), [])

	def test_a_layout_only_record_survives_a_save_that_empties_its_rows(self):
		make_rail([], user=self.user, navigation_layout="sidebar_only")
		save(rail=[own("user:rrrrrr", "Note"), shown("todo"), shown("note")])

		save(rail=[shown("todo"), shown("note")])

		self.assertTrue(frappe.db.exists("Rail", {"user": self.user, "navigation_layout": "sidebar_only"}))

	def test_the_site_scope_needs_a_system_manager(self):
		with self.assertRaises(frappe.PermissionError):
			save(scope="site", version="x")

	def test_a_new_own_key_creates_its_sidebar_record(self):
		save(
			rail=[shown("todo"), own("user:rrrrrr", "Note", opens_sidebar=OWN_SIDEBAR), shown("note")],
			sidebars={OWN_SIDEBAR: [own("user:aaaaaa", "ToDo")]},
		)

		record = frappe.db.get_value(
			"Sidebar", {"key": OWN_SIDEBAR}, ["app", "user", "standard", "link_doctype"], as_dict=True
		)

		self.assertEqual((record.app, record.user, record.standard), (APP, self.user, 0))
		self.assertFalse(record.link_doctype)

	def test_a_site_key_at_user_scope_is_refused_as_a_sidebar_and_as_an_opener(self):
		with self.assertRaises(frappe.ValidationError):
			save(sidebars={"site:abc123": [own("user:aaaaaa", "ToDo")]})

		with self.assertRaises(frappe.ValidationError):
			save(rail=[shown("todo", opens_sidebar="site:abc123"), shown("note")])

		self.assertFalse(frappe.db.exists("Sidebar", {"key": "site:abc123"}))

	def test_a_system_manager_saves_the_site_level_in_one_call(self):
		with set_user("Administrator"):
			version = get_arrangements(APP, "site")["version"]

			save(
				rail=[shown("todo"), own("site:rrrrrr", "Note", opens_sidebar="site:abc123"), shown("note")],
				sidebars={"site:abc123": [own("site:aaaaaa", "ToDo")]},
				scope="site",
				version=version,
			)

			result = get_arrangements(APP, "site")

			self.assertNotEqual(result["version"], version)
			self.assertEqual(keys(result["sidebars"]["site:abc123"]), ["site:aaaaaa"])
			self.assertEqual(frappe.db.get_value("Sidebar", {"key": "site:abc123"}, "user"), "")

			with self.assertRaises(frappe.TimestampMismatchError):
				save(rail=[shown("todo"), shown("note")], scope="site", version=version)

		# A person sees the site's sidebar, and their own level is untouched.
		self.assertIn("site:abc123", resolve_navigation(APP)["sidebars"])
		self.assertEqual(get_arrangements(APP)["version"], hashlib.sha1(b"[]").hexdigest())

	def test_the_caps_leave_out_a_sidebar_this_save_deletes(self):
		make_own_sidebar(
			"user:storeb",
			[item(f"user:s{i:05d}", link_doctype="DocType", link_to="ToDo", added=1) for i in range(60)],
			user=self.user,
		)
		make_rail(
			[
				item(
					"user:k3f9a2",
					link_doctype="DocType",
					link_to="ToDo",
					added=1,
					opens_sidebar="user:storeb",
				)
			],
			user=self.user,
		)
		rows = [own(f"user:r{i:05d}", "Note") for i in range(45)]

		# Nothing opens `user:storeb` after this save, so its rows are not the person's any more.
		save(
			rail=[shown("todo"), shown("note")],
			sidebars={ADDRESS_KEY: [shown("sb_todo"), shown("sb_note"), *rows]},
		)

		self.assertFalse(frappe.db.exists("Sidebar", {"key": "user:storeb"}))
		self.assertEqual(len(own_stored("Sidebar")), 45)

	def test_a_sidebar_sent_with_no_rows_cannot_be_opened(self):
		with self.assertRaisesRegex(frappe.ValidationError, "not a sidebar this level added"):
			save(rail=[shown("todo", opens_sidebar=OWN_SIDEBAR), shown("note")], sidebars={OWN_SIDEBAR: []})

		self.assertFalse(frappe.db.exists("Sidebar", {"key": OWN_SIDEBAR}))

	def test_a_sidebar_cannot_be_emptied_while_a_stored_rail_row_opens_it(self):
		save(
			rail=[shown("todo"), own("user:rrrrrr", "Note", opens_sidebar=OWN_SIDEBAR), shown("note")],
			sidebars={OWN_SIDEBAR: [own("user:aaaaaa", "ToDo")]},
		)

		with self.assertRaisesRegex(frappe.ValidationError, "Remove the item that opens it first"):
			save(sidebars={OWN_SIDEBAR: []})

		with self.assertRaisesRegex(frappe.ValidationError, "not a sidebar this level added"):
			save(
				rail=[shown("todo"), own("user:rrrrrr", "Note", opens_sidebar=OWN_SIDEBAR), shown("note")],
				sidebars={OWN_SIDEBAR: []},
			)

		self.assertTrue(frappe.db.exists("Sidebar", {"key": OWN_SIDEBAR}))

	def test_a_sidebar_named_by_a_non_string_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "named by its key"):
			save(rail=[shown("todo", opens_sidebar=5), shown("note")])

	def test_containers_that_are_no_rail_and_map_of_sidebars_are_refused(self):
		version = get_arrangements(APP)["version"]

		for containers in ("[]", "not json", {"sidebars": []}):
			with self.assertRaisesRegex(frappe.ValidationError, "rail and a map of sidebars"):
				save_arrangements(APP, "user", containers, version)

		with self.assertRaisesRegex(frappe.ValidationError, "named by its address or key"):
			save_arrangements(APP, "user", {"sidebars": {1: []}}, version)

	def test_a_person_saves_their_arrangement_of_a_site_sidebar(self):
		make_own_sidebar(
			"site:abc123",
			[
				item("site:aaaaaa", link_doctype="DocType", link_to="ToDo", added=1),
				item("site:bbbbbb", link_doctype="DocType", link_to="Note", added=1),
			],
			user="",
		)
		rail = [shown("todo"), shown("note")]

		save(rail=rail, sidebars={"site:abc123": [shown("site:bbbbbb"), shown("site:aaaaaa")]})

		self.assertEqual(
			keys(resolve_navigation(APP)["sidebars"]["site:abc123"]), ["site:bbbbbb", "site:aaaaaa"]
		)
		self.assertTrue(frappe.db.exists("Sidebar", {"key": "site:abc123", "user": self.user}))
		self.assertTrue(frappe.db.exists("Sidebar", {"key": "site:abc123", "user": ""}))

	def test_the_site_scope_lists_a_sidebar_the_managers_blocked_modules_hide(self):
		offered = "frappe.shell.arrangement_editor.NavigationContext.address_is_offered"

		with patch(offered, return_value=False), set_user("Administrator"):
			self.assertIn(ADDRESS_KEY, get_arrangements(APP, "site")["sidebars"])

	def test_the_layout_is_saved_after_the_rows_with_the_version_read_before_both(self):
		# The editor saves rows first: the layout write moves the rail's `modified` and stales the version.
		version = get_arrangements(APP)["version"]

		save(rail=[shown("note"), shown("todo")], version=version)
		save_navigation_layout(APP, "sidebar_only")

		self.assertEqual(resolve_navigation(APP)["navigation_layout"], "sidebar_only")
		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["note", "todo"])

		with self.assertRaises(frappe.TimestampMismatchError):
			save(rail=[shown("todo"), shown("note")], version=version)
