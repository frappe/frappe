# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The overlay write endpoints, `frappe/shell/arrangement.py`."""

import json
from unittest.mock import patch

import frappe
from frappe.desk.doctype.navigation_item.navigation_item import validate_item_keys
from frappe.exceptions import FrappeTypeError
from frappe.shell.arrangement import (
	OWN_ROWS_PER_APP,
	OWN_ROWS_PER_CONTAINER,
	_as_items,
	_target,
	anchors_for,
	get_arrangement,
	get_navigation_layouts,
	reduce_arrangement,
	reset_arrangement,
	save_arrangement,
	save_navigation_layout,
)
from frappe.shell.extensions import _reported, extend
from frappe.shell.navigation import resolve_navigation
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_navigation_filter import a_desk_user
from frappe.tests.test_shell_navigation import (
	ADDRESS,
	ADDRESS_KEY,
	APP,
	NavigationTestCase,
	doctype_item,
	item,
	keys,
	make_rail,
	make_sidebar,
	shipping,
)

OTHER = "test_arranger@example.com"


def rail_keys() -> list[str]:
	return keys(resolve_navigation(APP)["rail"])


def sidebar_keys() -> list[str]:
	return keys(resolve_navigation(APP)["sidebars"][ADDRESS_KEY])


def showing(*items: dict) -> list[dict]:
	"""What a client sends: the whole ordered list it is showing, hidden rows and all."""
	return list(items)


def shown(key: str, **kwargs) -> dict:
	return {"key": key, **kwargs}


def a_person(email: str = OTHER, role: str = "System Manager") -> str:
	"""Somebody other than the session user; `System Manager` by default, the site scope's gate."""
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			doctype="User",
			email=email,
			first_name="Arranger",
			user_type="System User",
			roles=[{"role": role}],
		).insert(ignore_permissions=True)

	return email


class TestReduction(NavigationTestCase):
	"""The reduction on its own: a whole ordered list in, the smallest layer that produces it out."""

	def test_an_unchanged_list_writes_nothing(self):
		base = [shown("a"), shown("b"), shown("c")]

		self.assertEqual(reduce_arrangement(base, base, "user"), [])

	def test_only_the_rows_that_moved_are_written(self):
		base = [shown("a"), shown("b"), shown("c")]
		rows = reduce_arrangement(base, [shown("c"), shown("a"), shown("b")], "user")

		self.assertEqual([row["key"] for row in rows], ["c"])
		self.assertEqual(json.loads(rows[0]["anchors"]), [{"before": "a"}])

	def test_a_rename_is_a_field_level_override(self):
		base = [shown("a", label="Accounts")]
		rows = reduce_arrangement(base, [shown("a", label="Money")], "user")

		self.assertEqual(rows[0]["label"], "Money")
		self.assertEqual(json.loads(rows[0]["overrides"]), ["label"])

	def test_clearing_a_label_the_app_shipped_is_expressible(self):
		rows = reduce_arrangement([shown("a", label="Accounts")], [shown("a", label="")], "user")

		self.assertEqual(json.loads(rows[0]["overrides"]), ["label"])
		self.assertEqual(rows[0]["label"], "")

	def test_clearing_an_already_blank_field_says_nothing(self):
		self.assertEqual(reduce_arrangement([shown("a")], [shown("a", label="")], "user"), [])

	def test_a_hide_is_written_and_an_unhide_is_written(self):
		self.assertEqual(reduce_arrangement([shown("a")], [shown("a", hidden=1)], "user")[0]["hidden"], 1)
		self.assertEqual(reduce_arrangement([shown("a", hidden=1)], [shown("a")], "user")[0]["hidden"], 0)

	def test_a_key_or_parent_that_is_not_a_name_is_dropped(self):
		base = [shown("a"), shown("b")]

		self.assertEqual(reduce_arrangement(base, _as_items([{"key": ["!=", ""]}, shown("a")]), "user"), [])

		# A parent that is not a name drops the row; blank means `None` or `""` only.
		for parent in ({"x": 1}, ["s"], 0, False, [], {}):
			self.assertEqual(_as_items([shown("a", parent_key=parent)]), [], f"parent {parent!r}")

		for blank in ("", None):
			self.assertEqual(_as_items([shown("a", parent_key=blank)])[0]["parent_key"], None)

	def test_a_malformed_parent_does_not_move_a_row_to_the_top_level(self):
		make_sidebar(
			[
				item("people", item_type="Section", label="People"),
				doctype_item("user", "User", parent_key="people"),
			],
			standard=1,
		)

		for parent in (["oops"], 0, []):
			save_arrangement(
				"Sidebar", ADDRESS_KEY, showing(shown("people"), shown("user", parent_key=parent))
			)

		entry = next(e for e in resolve_navigation(APP)["sidebars"][ADDRESS_KEY] if e["key"] == "user")
		self.assertEqual(entry["parent_key"], "people")

	def test_a_key_the_base_does_not_hold_is_dropped(self):
		rows = reduce_arrangement([shown("a")], [shown("gone"), shown("a")], "user")

		self.assertEqual([row["key"] for row in rows], [])

	def test_order_is_compared_per_parent(self):
		base = [shown("s1"), shown("a", parent_key="s1"), shown("s2"), shown("b", parent_key="s2")]
		desired = [shown("s1"), shown("s2"), shown("b", parent_key="s2"), shown("a", parent_key="s1")]

		self.assertEqual(reduce_arrangement(base, desired, "user"), [])

	def test_a_row_moved_to_the_front_names_a_row_that_is_not_also_moving(self):
		base = [shown(key) for key in "abcde"]
		anchors = anchors_for(base, [shown(key) for key in "deabc"])

		# `d` names the first row ahead of it that is staying put, not `e`, which is about to move.
		self.assertEqual(anchors["d"], [{"before": "a"}])
		self.assertEqual(anchors["e"], [{"after": "d"}])

	def test_a_key_sent_twice_keeps_its_first_position(self):
		base = [shown("a"), shown("b")]
		rows = reduce_arrangement(base, [shown("b")] * 5000 + [shown("a")], "user")

		# The repeats are gone before anything compares orders.
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows, reduce_arrangement(base, [shown("b"), shown("a")], "user"))

	def test_an_override_that_is_not_a_scalar_is_read_as_blank(self):
		self.assertEqual(reduce_arrangement([shown("a")], [shown("a", label=["x"])], "user"), [])

		row = reduce_arrangement([shown("a", label="Accounts")], [shown("a", label={"x": 1})], "user")[0]
		self.assertIsNone(row["label"])

	def test_the_fewest_possible_rows_move(self):
		base = [shown(key) for key in "abcdef"]
		desired = [shown(key) for key in "bcdefa"]

		self.assertEqual([row["key"] for row in reduce_arrangement(base, desired, "user")], ["a"])


class TestSavingAnArrangement(NavigationTestCase):
	def test_a_reorder_survives_a_re_resolve(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)

		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		self.assertEqual(rail_keys(), ["role", "user"])

	def test_the_save_hands_back_the_whole_prefix(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)

		navigation = save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		self.assertEqual(keys(navigation["rail"]), ["role", "user"])
		self.assertIn("sidebars", navigation)

	def test_arranging_it_back_leaves_no_row(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)

		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))
		save_arrangement("Rail", APP, showing(shown("user"), shown("role")))

		self.assertFalse(frappe.db.exists("Rail", {"app": APP, "standard": 0}))

	def test_a_rename_reaches_the_payload(self):
		make_rail([doctype_item("user", "User", label="People")], standard=1)

		save_arrangement("Rail", APP, showing(shown("user", label="My People")))

		self.assertEqual(resolve_navigation(APP)["rail"][0]["label"], "My People")

	def test_a_hidden_item_leaves_the_payload(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)

		save_arrangement("Rail", APP, showing(shown("user", hidden=1), shown("role")))

		self.assertEqual(rail_keys(), ["role"])

	def test_a_newly_shipped_item_lands_where_the_app_put_it(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		with shipping():
			rail = frappe.get_doc("Rail", APP)
			rail.append("items", doctype_item("page", "Page"))
			rail.save(ignore_permissions=True)

		self.assertEqual(rail_keys(), ["role", "user", "page"])

	def test_an_item_nobody_moved_is_not_moved(self):
		make_rail(
			[doctype_item("user", "User"), doctype_item("role", "Role"), doctype_item("page", "Page")],
			standard=1,
		)

		save_arrangement("Rail", APP, showing(shown("user", label="People"), shown("role"), shown("page")))

		self.assertEqual(rail_keys(), ["user", "role", "page"])


class TestHidingASection(NavigationTestCase):
	"""Hiding a section means the whole branch."""

	def section_sidebar(self):
		make_sidebar(
			[
				item("people", item_type="Section", label="People"),
				doctype_item("user", "User", parent_key="people"),
				doctype_item("role", "Role"),
			],
			standard=1,
		)

	def test_hiding_a_section_takes_its_children_with_it(self):
		self.section_sidebar()

		save_arrangement(
			"Sidebar",
			ADDRESS_KEY,
			showing(shown("people", hidden=1), shown("user", parent_key="people"), shown("role")),
		)

		self.assertEqual(sidebar_keys(), ["role"])

	def test_an_app_removing_a_section_still_promotes_its_children(self):
		make_sidebar([doctype_item("user", "User", parent_key="people")], standard=1)

		entry = resolve_navigation(APP)["sidebars"][ADDRESS_KEY][0]
		self.assertNotIn("parent_key", entry)

	def test_moving_a_section_takes_its_children_in_the_list_too(self):
		"""The list is flat, and the editor draws it back in order."""
		make_sidebar(
			[
				item("s1", item_type="Section"),
				doctype_item("a", "User", parent_key="s1"),
				item("s2", item_type="Section"),
				doctype_item("b", "Role", parent_key="s2"),
			],
			standard=1,
		)

		shown = showing(
			{"key": "s2"},
			{"key": "b", "parent_key": "s2"},
			{"key": "s1"},
			{"key": "a", "parent_key": "s1"},
		)
		save_arrangement("Sidebar", ADDRESS_KEY, shown)

		self.assertEqual(sidebar_keys(), ["s2", "b", "s1", "a"])

	def test_a_nested_subtree_moves_whole(self):
		make_sidebar(
			[
				item("s1", item_type="Section"),
				doctype_item("s1a", "Role", parent_key="s1"),
				doctype_item("deep", "User", parent_key="s1a"),
				item("s2", item_type="Section"),
				doctype_item("b", "Role", parent_key="s2"),
			],
			standard=1,
		)

		shown = showing(
			{"key": "s2"},
			{"key": "b", "parent_key": "s2"},
			{"key": "s1"},
			{"key": "s1a", "parent_key": "s1"},
			{"key": "deep", "parent_key": "s1a"},
		)
		save_arrangement("Sidebar", ADDRESS_KEY, shown)

		self.assertEqual(sidebar_keys(), ["s2", "b", "s1", "s1a", "deep"])
		self.assertEqual(keys(get_arrangement("Sidebar", ADDRESS_KEY)), [row["key"] for row in shown])

	def test_what_the_editor_saves_is_what_it_reads_back(self):
		make_sidebar(
			[
				item("s1", item_type="Section"),
				doctype_item("a", "User", parent_key="s1"),
				item("s2", item_type="Section"),
				doctype_item("b", "Role", parent_key="s2"),
			],
			standard=1,
		)

		shown = showing(
			{"key": "s2"},
			{"key": "b", "parent_key": "s2"},
			{"key": "s1"},
			{"key": "a", "parent_key": "s1"},
		)
		save_arrangement("Sidebar", ADDRESS_KEY, shown)

		self.assertEqual(keys(get_arrangement("Sidebar", ADDRESS_KEY)), [row["key"] for row in shown])

	def test_an_item_nested_in_a_hidden_section_goes_too(self):
		make_sidebar(
			[
				item("outer", item_type="Section"),
				doctype_item("inner", "Role", parent_key="outer"),
				doctype_item("user", "User", parent_key="inner"),
			],
			standard=1,
		)

		save_arrangement(
			"Sidebar",
			ADDRESS_KEY,
			showing(
				shown("outer", hidden=1),
				shown("inner", parent_key="outer"),
				shown("user", parent_key="inner"),
			),
		)

		self.assertNotIn(ADDRESS_KEY, resolve_navigation(APP)["sidebars"])


class TestScopes(NavigationTestCase):
	def test_a_person_sees_their_own_arrangement_and_not_a_colleagues(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		with set_user(a_person()):
			self.assertEqual(rail_keys(), ["user", "role"])

		self.assertEqual(rail_keys(), ["role", "user"])

	def test_the_site_layer_reaches_everyone(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")), scope="site")

		with set_user(a_person()):
			self.assertEqual(rail_keys(), ["role", "user"])

	def test_a_persons_moves_are_anchored_against_what_the_site_arranged(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")), scope="site")
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		self.assertFalse(frappe.db.exists("Rail", {"app": APP, "standard": 0, "user": frappe.session.user}))

	def test_a_person_can_unhide_what_the_site_hid(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("user", hidden=1), shown("role")), scope="site")

		self.assertEqual(rail_keys(), ["role"])
		self.assertEqual(
			keys(get_arrangement("Rail", APP)),
			["user", "role"],
			"the editor is shown what was hidden, or a hide would be a one-way door",
		)

		save_arrangement("Rail", APP, showing(shown("user"), shown("role")))
		self.assertEqual(rail_keys(), ["user", "role"])

	def test_the_user_scope_is_the_session_user_and_cannot_be_argued(self):
		import inspect

		self.assertNotIn("user", inspect.signature(save_arrangement).parameters)


class TestReset(NavigationTestCase):
	def test_a_reset_deletes_one_layer(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		reset_arrangement("Rail", APP)

		self.assertEqual(rail_keys(), ["user", "role"])

	def test_resetting_your_own_cannot_reach_the_sites(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")), scope="site")
		save_arrangement("Rail", APP, showing(shown("user", label="Mine")))

		reset_arrangement("Rail", APP)

		self.assertEqual(rail_keys(), ["role", "user"])
		self.assertTrue(frappe.db.exists("Rail", {"app": APP, "standard": 0, "user": ""}))

	def test_a_malformed_save_does_not_do_a_resets_work(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		with self.assertRaises(frappe.ValidationError):
			save_arrangement("Rail", APP, showing({"key": ["!=", ""]}, {"nokey": 1}))

		self.assertEqual(rail_keys(), ["role", "user"], "their arrangement survives")

	def test_a_save_of_rows_the_list_no_longer_holds_does_not_do_a_resets_work(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		with self.assertRaises(frappe.ValidationError):
			save_arrangement("Rail", APP, showing(shown("gone"), shown("also_gone")))

		self.assertEqual(rail_keys(), ["role", "user"], "their arrangement survives")

	def test_a_save_that_covers_only_part_of_the_list_does_not_do_a_resets_work(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		with self.assertRaises(frappe.ValidationError):
			save_arrangement("Rail", APP, showing(shown("role"), {"key": ["!=", ""]}))

		self.assertEqual(rail_keys(), ["role", "user"], "their arrangement survives")

	def test_an_incomplete_save_that_has_something_to_say_is_still_kept(self):
		make_rail(
			[doctype_item("user", "User"), doctype_item("role", "Role"), doctype_item("page", "Page")],
			standard=1,
		)

		save_arrangement("Rail", APP, showing(shown("page"), shown("user", label="Mine")))

		# `role` was never mentioned, so it keeps the front.
		self.assertEqual(rail_keys(), ["role", "page", "user"])

	def test_arranging_it_back_still_leaves_no_row(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))
		save_arrangement("Rail", APP, showing(shown("user"), shown("role")))

		self.assertFalse(frappe.db.exists("Rail", {"app": APP, "standard": 0}))

	def test_a_reset_of_a_layer_that_is_not_there_is_not_an_error(self):
		make_rail([doctype_item("user", "User")], standard=1)

		self.assertEqual(keys(reset_arrangement("Rail", APP)["rail"]), ["user"])


class TestTheGate(NavigationTestCase):
	def test_arranging_an_app_you_may_not_enter_is_refused(self):
		make_rail([doctype_item("user", "User")], standard=1)

		with set_user("Guest"), self.assertRaises(frappe.PermissionError):
			save_arrangement("Rail", APP, showing(shown("user")))

	def test_the_site_scope_needs_a_system_manager(self):
		make_rail([doctype_item("user", "User")], standard=1)
		reader = a_person("test_desk_user@example.com", role="Desk User")

		with set_user(reader):
			# Their own is theirs to arrange...
			save_arrangement("Rail", APP, showing(shown("user", label="Mine")))

			# ...and everyone's is not.
			with self.assertRaises(frappe.PermissionError):
				save_arrangement("Rail", APP, showing(shown("user")), scope="site")

	def test_an_app_that_is_not_on_this_bench_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			get_arrangement("Rail", "no_such_app")

	def test_a_body_that_is_not_an_arrangement_is_refused_with_a_sentence(self):
		make_rail([doctype_item("user", "User")], standard=1)

		# A body that is neither a string nor a list is refused by the annotation first.
		for body in ("{not json", '{"key": "a"}'):
			with self.assertRaises(frappe.ValidationError):
				save_arrangement("Rail", APP, body)

	def test_an_argument_that_is_not_a_name_is_refused_at_the_boundary(self):
		for address in (["!=", ""], {"name": "x"}):
			# Inside a request or a test the annotation gets there first, which is the belt...
			with self.assertRaises(FrappeTypeError):
				get_arrangement("Sidebar", address)

			# ...and this is the braces, for callers off a request.
			with self.assertRaises(frappe.ValidationError):
				_target("Sidebar", address, "user")

	def test_a_container_that_is_not_one_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			get_arrangement("Custom Sidebar", APP)

	def test_a_scope_that_is_not_one_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			get_arrangement("Rail", APP, scope="role")


class TestSidebarArrangement(NavigationTestCase):
	def test_a_sidebar_is_arranged_by_its_scrubbed_address(self):
		make_sidebar([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)

		save_arrangement("Sidebar", ADDRESS_KEY, showing(shown("role"), shown("user")))

		self.assertEqual(keys(resolve_navigation(APP)["sidebars"][ADDRESS_KEY]), ["role", "user"])

	def test_a_sidebar_layer_lands_in_the_v2_table(self):
		make_sidebar([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)

		save_arrangement("Sidebar", ADDRESS_KEY, showing(shown("role"), shown("user")))

		layer = frappe.get_doc("Sidebar", {"standard": 0, "user": frappe.session.user})
		self.assertTrue(layer.navigation_items)
		self.assertEqual(layer.items, [])

	def test_an_address_no_app_ships_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			get_arrangement("Sidebar", "module_def_nobody_ships_this")

	def test_a_sidebar_reset_leaves_the_rail_alone(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		make_sidebar([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))
		save_arrangement("Sidebar", ADDRESS_KEY, showing(shown("role"), shown("user")))

		reset_arrangement("Sidebar", ADDRESS_KEY)

		self.assertEqual(rail_keys(), ["role", "user"])
		self.assertEqual(keys(resolve_navigation(APP)["sidebars"][ADDRESS_KEY]), ["user", "role"])


def layout() -> str:
	return resolve_navigation(APP)["navigation_layout"]


def stored_layer(user: str = "") -> str | None:
	return frappe.db.get_value("Rail", {"app": APP, "standard": 0, "extends": "", "user": user})


class TestNavigationLayout(NavigationTestCase):
	def test_it_is_rail_and_sidebar_when_nothing_sets_it(self):
		self.assertEqual(layout(), "rail_and_sidebar")
		self.assertNotIn("pinned", resolve_navigation(APP))

	def test_person_beats_site_beats_app_beats_the_default(self):
		make_rail([], standard=1, navigation_layout="floating_rail")
		self.assertEqual(layout(), "floating_rail")

		save_navigation_layout(APP, "sidebar_only", scope="site")
		self.assertEqual(layout(), "sidebar_only")

		save_navigation_layout(APP, "rail_and_sidebar")
		self.assertEqual(layout(), "rail_and_sidebar")

	def test_a_blank_level_falls_through(self):
		make_rail([], standard=1, navigation_layout="sidebar_only")
		make_rail([doctype_item("user", "User")], user=frappe.session.user)

		self.assertEqual(layout(), "sidebar_only")

	def test_a_derived_rail_takes_a_site_value(self):
		save_navigation_layout(APP, "floating_rail", scope="site")

		self.assertEqual(layout(), "floating_rail")

	def test_an_extension_record_is_never_read(self):
		make_rail([], standard=1, extends="erpnext")
		frappe.db.set_value("Rail", {"app": APP, "extends": "erpnext"}, "navigation_layout", "floating_rail")

		self.assertEqual(layout(), "rail_and_sidebar")

	def test_a_user_write_touches_only_the_session_users_record_and_makes_a_row_less_one(self):
		save_navigation_layout(APP, "sidebar_only")

		mine = frappe.get_doc("Rail", stored_layer(frappe.session.user))
		self.assertEqual((mine.navigation_layout, mine.items), ("sidebar_only", []))
		self.assertIsNone(stored_layer())

	def test_a_site_write_needs_a_system_manager(self):
		reader = a_person("test_desk_user@example.com", role="Desk User")

		with set_user(reader):
			save_navigation_layout(APP, "sidebar_only")

			with self.assertRaises(frappe.PermissionError):
				save_navigation_layout(APP, "sidebar_only", scope="site")

	def test_an_unknown_value_is_refused(self):
		for value in ("dock", "Sidebar Only"):
			with self.assertRaises(frappe.ValidationError):
				save_navigation_layout(APP, value)

		self.assertIsNone(stored_layer(frappe.session.user))

	def test_a_value_equal_to_the_level_below_writes_blank(self):
		save_navigation_layout(APP, "floating_rail", scope="site")
		save_navigation_layout(APP, "sidebar_only")
		self.assertEqual(layout(), "sidebar_only")

		# Unpinning back to what the site says clears the record: a later site change still reaches them.
		save_navigation_layout(APP, "floating_rail")

		self.assertIsNone(stored_layer(frappe.session.user))
		self.assertEqual(layout(), "floating_rail")

	def test_the_default_over_nothing_writes_nothing(self):
		save_navigation_layout(APP, "rail_and_sidebar")

		self.assertIsNone(stored_layer(frappe.session.user))

	def test_it_comes_back_with_the_navigation(self):
		self.assertEqual(save_navigation_layout(APP, "sidebar_only")["navigation_layout"], "sidebar_only")

	def test_a_rows_save_keeps_the_layout(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_navigation_layout(APP, "sidebar_only")

		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		self.assertEqual(layout(), "sidebar_only")

	def test_a_rows_save_that_empties_the_rows_keeps_a_record_that_has_a_layout(self):
		make_rail([doctype_item("user", "User")], standard=1)
		save_arrangement("Rail", APP, showing(shown("user", hidden=1)))
		save_navigation_layout(APP, "sidebar_only")

		save_arrangement("Rail", APP, showing(shown("user")))

		mine = frappe.get_doc("Rail", stored_layer(frappe.session.user))
		self.assertEqual((mine.navigation_layout, mine.items), ("sidebar_only", []))

	def test_a_rows_save_that_empties_the_rows_drops_a_record_with_no_layout(self):
		make_rail([doctype_item("user", "User")], standard=1)
		save_arrangement("Rail", APP, showing(shown("user", hidden=1)))
		save_arrangement("Rail", APP, showing(shown("user")))

		self.assertIsNone(stored_layer(frappe.session.user))

	def test_clearing_the_layout_keeps_a_record_that_has_rows(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))
		save_navigation_layout(APP, "sidebar_only")

		save_navigation_layout(APP, "rail_and_sidebar")

		self.assertEqual(rail_keys(), ["role", "user"])

	def test_a_rail_reset_drops_the_rows_and_the_layout(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))
		save_navigation_layout(APP, "sidebar_only")

		reset_arrangement("Rail", APP)

		self.assertIsNone(stored_layer(frappe.session.user))
		self.assertEqual(layout(), "rail_and_sidebar")
		self.assertEqual(rail_keys(), ["user", "role"])

	def test_a_sidebar_reset_leaves_the_layout_alone(self):
		make_sidebar([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Sidebar", ADDRESS_KEY, showing(shown("role"), shown("user")))
		save_navigation_layout(APP, "sidebar_only")

		reset_arrangement("Sidebar", ADDRESS_KEY)

		self.assertEqual(layout(), "sidebar_only")

	def test_pinned_is_the_persons_own_rail_and_sidebar_over_an_inherited_floating_rail(self):
		make_rail([], standard=1, navigation_layout="floating_rail")
		self.assertNotIn("pinned", resolve_navigation(APP))

		self.assertIs(save_navigation_layout(APP, "rail_and_sidebar")["pinned"], True)

		self.assertNotIn("pinned", save_navigation_layout(APP, "sidebar_only"))
		self.assertNotIn("pinned", save_navigation_layout(APP, "floating_rail"))

	def test_a_colleague_does_not_see_a_pin(self):
		make_rail([], standard=1, navigation_layout="floating_rail")
		save_navigation_layout(APP, "rail_and_sidebar")

		with set_user(a_person()):
			self.assertEqual(layout(), "floating_rail")
			self.assertNotIn("pinned", resolve_navigation(APP))

	def test_get_navigation_layouts_gives_the_three_raw_values(self):
		make_rail([], standard=1, navigation_layout="floating_rail")
		save_navigation_layout(APP, "sidebar_only", scope="site")

		self.assertEqual(
			get_navigation_layouts(APP), {"standard": "floating_rail", "site": "sidebar_only", "user": ""}
		)

		with set_user(a_person()):
			self.assertEqual(get_navigation_layouts(APP)["site"], "sidebar_only")

	def test_get_navigation_layouts_refuses_an_app_the_person_may_not_enter(self):
		with set_user("Guest"), self.assertRaises(frappe.PermissionError):
			get_navigation_layouts(APP)

		with self.assertRaises(frappe.ValidationError):
			get_navigation_layouts("no_such_app")


def own(key: str, doctype: str = "ToDo", **kwargs) -> dict:
	"""A row a level adds: the editor sends the whole item with a key it made."""
	return {"key": key, "item_type": "DocType", "link_doctype": "DocType", "link_to": doctype, **kwargs}


def stored(doctype: str = "Rail", **filters) -> list[dict]:
	"""The rows of the layer the session user's save wrote."""
	name = frappe.db.get_value(doctype, {"standard": 0, "user": frappe.session.user, **filters})
	field = "items" if doctype == "Rail" else "navigation_items"

	return frappe.get_doc(doctype, name).get(field) if name else []


def own_stored(doctype: str = "Rail", **filters) -> list[dict]:
	return [row for row in stored(doctype, **filters) if row.added]


class OwnRowsTestCase(NavigationTestCase):
	"""Run as a Desk User: Administrator skips the permission filter these rows are tested against."""

	# A rail is flat; the tests of sections and parents run on the module's sidebar.
	sidebar = False

	def setUp(self):
		super().setUp()
		self.user = a_desk_user()
		frappe.set_user(self.user)
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.clear_cache, user=self.user)

		(make_sidebar if self.sidebar else make_rail)(self.shipped(), standard=1)

	def shipped(self) -> list[dict]:
		return [doctype_item("todo", "ToDo"), doctype_item("note", "Note")]


class TestOwnRowsSurviveASave(OwnRowsTestCase):
	def test_a_save_keeps_an_own_row_whole(self):
		save_arrangement(
			"Rail", APP, showing(shown("todo"), own("user:k3f9a2", "Note", label="Mine"), shown("note"))
		)

		row = next(row for row in stored() if row.key == "user:k3f9a2")
		self.assertEqual((row.added, row.item_type, row.link_to, row.label), (1, "DocType", "Note", "Mine"))
		self.assertEqual(rail_keys(), ["todo", "user:k3f9a2", "note"])

	def test_a_second_save_of_the_same_list_writes_the_same_layer(self):
		desired = showing(shown("todo"), own("user:k3f9a2"), shown("note"))
		save_arrangement("Rail", APP, desired)
		first = [(row.key, row.anchors) for row in stored()]

		save_arrangement("Rail", APP, desired)

		self.assertEqual([(row.key, row.anchors) for row in stored()], first)
		self.assertEqual(len(stored()), 1)

	def test_an_own_row_stores_no_hidden_overrides_or_switch(self):
		save_arrangement(
			"Rail",
			APP,
			showing(
				shown("todo"),
				own("user:k3f9a2", hidden=1, overrides='["label"]', switches_app=1),
				shown("note"),
			),
		)

		row = stored()[0]
		self.assertEqual((row.hidden, row.overrides, row.switches_app), (0, None, 0))

	def test_an_own_row_is_not_a_delta_in_the_reduction(self):
		base = [shown("a"), shown("b")]

		rows = reduce_arrangement(base, [shown("a"), own("user:k3f9a2"), shown("b")], "user")

		self.assertEqual([(row["key"], row.get("added")) for row in rows], [("user:k3f9a2", 1)])
		self.assertEqual(json.loads(rows[0]["anchors"]), [{"after": "a"}])

	def test_an_own_row_absent_from_the_list_is_deleted(self):
		save_arrangement("Rail", APP, showing(shown("todo"), own("user:k3f9a2"), shown("note")))

		save_arrangement("Rail", APP, showing(shown("note"), shown("todo")))

		self.assertEqual(own_stored(), [])
		self.assertEqual(rail_keys(), ["note", "todo"])

	def test_an_inherited_row_absent_from_the_list_is_not_deleted(self):
		save_arrangement("Rail", APP, showing(shown("note"), shown("todo")))

		save_arrangement("Rail", APP, showing(shown("note"), own("user:k3f9a2")))

		self.assertIn("todo", rail_keys())

	def test_a_bare_key_the_base_does_not_hold_is_still_dropped(self):
		save_arrangement("Rail", APP, showing(shown("todo"), shown("gone"), shown("note")))

		self.assertFalse(stored())


class TestWhereAnOwnRowSits(OwnRowsTestCase):
	sidebar = True

	def shipped(self):
		return [
			item("people", item_type="Section", label="People"),
			doctype_item("todo", "ToDo", parent_key="people"),
			doctype_item("note", "Note"),
		]

	def parents(self) -> dict[str, str | None]:
		return {
			entry["key"]: entry.get("parent_key")
			for entry in resolve_navigation(APP)["sidebars"][ADDRESS_KEY]
		}

	def test_an_own_row_sits_in_an_app_section(self):
		save_arrangement(
			"Sidebar",
			ADDRESS_KEY,
			showing(
				shown("people"),
				shown("todo", parent_key="people"),
				own("user:k3f9a2", parent_key="people"),
				shown("note"),
			),
		)

		self.assertEqual(self.parents()["user:k3f9a2"], "people")

	def test_an_own_row_sits_in_a_site_section(self):
		with set_user(a_person()):
			save_arrangement(
				"Sidebar",
				ADDRESS_KEY,
				showing(
					shown("people"),
					shown("todo", parent_key="people"),
					shown("note"),
					own("site:p81c0d", item_type="Section", label="Shared", link_doctype=None, link_to=None),
					own("site:q1w2e3", parent_key="site:p81c0d"),
				),
				scope="site",
			)

		save_arrangement(
			"Sidebar",
			ADDRESS_KEY,
			showing(
				shown("people"),
				shown("todo", parent_key="people"),
				shown("note"),
				shown("site:p81c0d", label="Shared"),
				shown("site:q1w2e3", parent_key="site:p81c0d"),
				own("user:k3f9a2", parent_key="site:p81c0d"),
			),
		)

		self.assertEqual(self.parents()["user:k3f9a2"], "site:p81c0d")

	def test_an_own_row_sits_at_the_top_level(self):
		save_arrangement(
			"Sidebar",
			ADDRESS_KEY,
			showing(shown("people"), shown("todo", parent_key="people"), shown("note"), own("user:k3f9a2")),
		)

		self.assertEqual(self.parents()["user:k3f9a2"], None)
		self.assertEqual(keys(resolve_navigation(APP)["sidebars"][ADDRESS_KEY])[-1], "user:k3f9a2")

	def test_an_own_row_whose_parent_is_not_in_the_list_moves_to_the_top_level(self):
		rows = reduce_arrangement(
			[shown("a"), shown("b")],
			[
				shown("a"),
				own("user:k3f9a2", parent_key="user:gone00"),
				own("user:k3f9a3", parent_key="user:k3f9a3"),
			],
			"user",
		)

		self.assertEqual([row.get("parent_key") for row in rows], [None, None])

	def test_own_rows_that_are_each_others_parents_go_to_the_top_level(self):
		rows = reduce_arrangement(
			[shown("a")],
			[
				shown("a"),
				own("user:aaaaaa", parent_key="user:bbbbbb"),
				own("user:bbbbbb", parent_key="user:aaaaaa"),
			],
			"user",
		)

		self.assertEqual([row.get("parent_key") for row in rows], [None, None])

	def test_deleting_an_own_section_leaves_its_children_at_the_top_level(self):
		section = own("user:aaaaaa", item_type="Section", label="Mine", link_doctype=None, link_to=None)
		desired = showing(
			shown("people"),
			shown("todo", parent_key="people"),
			shown("note"),
			section,
			own("user:bbbbbb", parent_key="user:aaaaaa"),
		)
		save_arrangement("Sidebar", ADDRESS_KEY, desired)
		self.assertEqual(self.parents()["user:bbbbbb"], "user:aaaaaa")

		save_arrangement("Sidebar", ADDRESS_KEY, [row for row in desired if row["key"] != "user:aaaaaa"])

		self.assertEqual(self.parents()["user:bbbbbb"], None)
		self.assertEqual([row.key for row in own_stored("Sidebar")], ["user:bbbbbb"])

	def test_an_app_removing_the_section_leaves_the_own_row_at_the_top_level(self):
		save_arrangement(
			"Sidebar",
			ADDRESS_KEY,
			showing(
				shown("people"),
				shown("todo", parent_key="people"),
				own("user:k3f9a2", parent_key="people"),
				shown("note"),
			),
		)
		shipped = frappe.db.get_value("Sidebar", {"app": APP, "standard": 1, "link_to": ADDRESS[1]})
		frappe.db.delete("Navigation Item", {"parent": shipped, "parenttype": "Sidebar", "key": "people"})

		self.assertIn("user:k3f9a2", self.parents())
		self.assertEqual(self.parents()["user:k3f9a2"], None)


class TestOwnRowRefusals(OwnRowsTestCase):
	def refused(self, *desired: dict, scope: str = "user"):
		with self.assertRaises(frappe.ValidationError):
			save_arrangement("Rail", APP, showing(shown("todo"), shown("note"), *desired), scope=scope)

		self.assertFalse(stored())

	def test_a_key_of_the_wrong_shape_is_refused(self):
		for key in ("user:", "user:short", "user:toolong1", "user:K3F9A2", "user:k3f9a-", "user:k3f9a2:x"):
			with self.subTest(key=key):
				self.refused(own(key))

	def test_a_key_with_a_trailing_newline_is_refused(self):
		self.refused(own("user:k3f9a2\n"))

	def test_a_key_the_site_level_no_longer_holds_is_dropped_from_a_user_save(self):
		save_arrangement("Rail", APP, showing(shown("todo"), shown("note"), own("site:p81c0d")))

		self.assertFalse(stored())

	def test_a_user_save_keeps_a_site_row_the_site_level_still_holds(self):
		with set_user(a_person()):
			save_arrangement(
				"Rail", APP, showing(shown("todo"), shown("note"), own("site:p81c0d")), scope="site"
			)

		save_arrangement("Rail", APP, showing(shown("todo"), shown("note"), shown("site:p81c0d")))

		self.assertFalse(stored())

	def test_a_link_that_opens_anything_but_a_path_or_http_is_refused(self):
		for url in (
			"javascript:alert(1)",
			"//evil.example",
			"/\\evil.example",
			"/\t/evil.example",
			"ftp://x",
			"data:text/html,x",
			" /a",
			"mailto:a@b.c",
		):
			with self.subTest(url=url):
				self.refused(own("user:k3f9a2", url=url))

	def test_a_link_to_a_path_or_an_http_address_is_kept(self):
		for url in ("/app/todo", "https://example.com/a?b=1", "HTTP://example.com"):
			with self.subTest(url=url):
				save_arrangement(
					"Rail", APP, showing(shown("todo"), shown("note"), own("user:k3f9a2", url=url))
				)
				self.assertEqual(own_stored()[0].url, url)

	def test_a_payload_that_is_not_an_object_is_refused(self):
		for payload in ([1], "[1]", 3, "not json"):
			with self.subTest(payload=payload):
				self.refused(own("user:k3f9a2", payload=payload))

	def test_a_key_the_list_repeats_is_refused(self):
		self.refused(own("user:k3f9a2"), own("user:k3f9a2", "Note"))

	def test_a_user_prefixed_key_is_refused_in_a_site_save(self):
		with set_user(a_person()):
			self.refused(own("user:k3f9a2"), scope="site")

	def shipped_rows(self, *keys: str) -> list[frappe._dict]:
		return [frappe._dict(idx=idx, key=key, item_type="DocType") for idx, key in enumerate(keys, 1)]

	def test_a_shipped_key_with_a_reserved_prefix_is_refused_when_a_person_saves_it(self):
		for prefix in ("user", "site"):
			with self.subTest(prefix=prefix), self.assertRaises(frappe.ValidationError):
				validate_item_keys(self.shipped_rows(f"{prefix}:abcdef"), "Rail")

	def test_a_shipped_key_with_a_reserved_prefix_is_dropped_on_a_migrate(self):
		self.addCleanup(frappe.flags.update, {"in_migrate": frappe.flags.in_migrate})
		frappe.flags.in_migrate = True
		rows = self.shipped_rows("user:abcdef", "note", "site:abcdef", "todo")

		validate_item_keys(rows, "Rail")

		self.assertEqual([(row.key, row.idx) for row in rows], [("note", 1), ("todo", 2)])

	def test_an_app_named_for_a_level_adds_nothing_and_is_logged_once(self):
		row = {"key": "k", "item_type": "DocType"}
		_reported.discard("user")

		with patch("frappe.logger") as logger:
			first = extend([], [("user", [row]), ("crm", [row])], anchorable=True)
			extend([], [("user", [row])], anchorable=True)

		self.assertEqual([entry["key"] for entry in first], ["crm:k"])
		self.assertEqual(logger.return_value.warning.call_count, 1)


class TestTheCaps(OwnRowsTestCase):
	def adding(self, count: int, scope_prefix: str = "user", start: int = 0) -> list[dict]:
		return [own(f"{scope_prefix}:{index:06x}") for index in range(start, start + count)]

	def test_fifty_rows_in_one_container_are_kept_and_the_next_is_refused(self):
		save_arrangement("Rail", APP, showing(*self.adding(OWN_ROWS_PER_CONTAINER)))
		self.assertEqual(len(stored()), OWN_ROWS_PER_CONTAINER)

		with self.assertRaises(frappe.ValidationError) as caught:
			save_arrangement("Rail", APP, showing(*self.adding(OWN_ROWS_PER_CONTAINER + 1)))

		self.assertIn("up to 50", str(caught.exception))
		self.assertEqual(len(stored()), OWN_ROWS_PER_CONTAINER)

	def test_the_hundred_and_first_row_in_one_app_is_refused(self):
		make_sidebar([doctype_item("user", "User")], standard=1)
		make_sidebar([doctype_item("role", "Role")], standard=1, link_to="Desk")

		with set_user(a_person()):
			save_arrangement("Rail", APP, showing(*self.adding(OWN_ROWS_PER_CONTAINER, "site")), scope="site")
			save_arrangement(
				"Sidebar",
				ADDRESS_KEY,
				showing(shown("user"), *self.adding(OWN_ROWS_PER_CONTAINER, "site", 100)),
				scope="site",
			)

			with self.assertRaises(frappe.ValidationError) as caught:
				save_arrangement(
					"Sidebar",
					"module_def_desk",
					showing(shown("role"), *self.adding(1, "site", 200)),
					scope="site",
				)

		self.assertIn(str(OWN_ROWS_PER_APP), str(caught.exception))

	def test_a_sidebar_the_app_no_longer_ships_does_not_count(self):
		make_sidebar([doctype_item("user", "User")], standard=1)
		make_sidebar([doctype_item("role", "Role")], standard=1, link_to="Desk")

		with set_user(a_person()):
			save_arrangement("Rail", APP, showing(*self.adding(OWN_ROWS_PER_CONTAINER, "site")), scope="site")
			save_arrangement(
				"Sidebar",
				ADDRESS_KEY,
				showing(shown("user"), *self.adding(OWN_ROWS_PER_CONTAINER, "site", 100)),
				scope="site",
			)
			frappe.db.delete("Sidebar", {"app": APP, "standard": 1, "link_to": ADDRESS[1]})

			save_arrangement(
				"Sidebar",
				"module_def_desk",
				showing(shown("role"), *self.adding(1, "site", 200)),
				scope="site",
			)

		self.assertEqual(len(stored("Sidebar", user="", link_to="Desk")), 1)

	def test_replacing_a_containers_rows_does_not_count_the_rows_being_replaced(self):
		make_sidebar([doctype_item("user", "User")], standard=1)

		with set_user(a_person()):
			save_arrangement("Rail", APP, showing(*self.adding(OWN_ROWS_PER_CONTAINER, "site")), scope="site")
			save_arrangement(
				"Sidebar",
				ADDRESS_KEY,
				showing(shown("user"), *self.adding(OWN_ROWS_PER_CONTAINER, "site", 100)),
				scope="site",
			)

			save_arrangement(
				"Rail", APP, showing(*self.adding(OWN_ROWS_PER_CONTAINER, "site", 200)), scope="site"
			)

		self.assertEqual(len(stored(user="")), OWN_ROWS_PER_CONTAINER)

	def test_a_levels_rows_do_not_count_against_the_other_levels_cap(self):
		with set_user(a_person()):
			save_arrangement("Rail", APP, showing(*self.adding(OWN_ROWS_PER_CONTAINER, "site")), scope="site")

		save_arrangement("Rail", APP, showing(shown("todo"), *self.adding(OWN_ROWS_PER_CONTAINER)))

		self.assertEqual(len(stored()), OWN_ROWS_PER_CONTAINER)


class TestASectionOnlyAnOwnRowKeeps(OwnRowsTestCase):
	sidebar = True

	def shipped(self):
		return [
			item("people", item_type="Section", label="People"),
			doctype_item("secret", "Role", parent_key="people"),
			doctype_item("note", "Note"),
		]

	def test_a_save_keeps_the_section_and_the_own_row_inside_it(self):
		make_sidebar(
			[item("user:k3f9a2", link_doctype="DocType", link_to="ToDo", added=1, parent_key="people")],
			user=self.user,
		)
		arrangement = get_arrangement("Sidebar", ADDRESS_KEY)
		self.assertEqual([row["key"] for row in arrangement], ["people", "note", "user:k3f9a2"])

		save_arrangement("Sidebar", ADDRESS_KEY, arrangement)

		self.assertEqual(stored("Sidebar")[0].parent_key, "people")
		self.assertEqual(len(stored("Sidebar")), 1)


class TestASectionAnOwnRowYouCannotOpenSitsIn(OwnRowsTestCase):
	sidebar = True

	def shipped(self):
		return [
			item("people", item_type="Section", label="People"),
			doctype_item("secret", "Role", parent_key="people"),
			doctype_item("note", "Note"),
		]

	def test_the_row_keeps_its_parent_through_a_save(self):
		make_sidebar(
			[item("user:k3f9a2", link_doctype="DocType", link_to="Role", added=1, parent_key="people")],
			user=self.user,
		)
		arrangement = get_arrangement("Sidebar", ADDRESS_KEY)
		self.assertEqual([row["key"] for row in arrangement], ["people", "note", "user:k3f9a2"])
		self.assertEqual(arrangement[2]["parent_key"], "people")

		save_arrangement("Sidebar", ADDRESS_KEY, arrangement)

		self.assertEqual(stored("Sidebar")[0].parent_key, "people")


class TestLostAccess(OwnRowsTestCase):
	def shipped(self):
		return [doctype_item("todo", "ToDo"), doctype_item("note", "Note"), doctype_item("secret", "Role")]

	def an_own_row_you_cannot_open(self):
		# Written straight to the layer: this is the row left behind when access was taken away.
		make_rail(
			[
				item(
					"user:k3f9a2",
					link_doctype="DocType",
					link_to="Role",
					added=1,
					anchors=json.dumps([{"after": "note"}]),
				)
			],
			user=self.user,
		)

	def test_an_own_row_you_cannot_open_leaves_boot_and_comes_back_marked(self):
		self.an_own_row_you_cannot_open()

		self.assertNotIn("user:k3f9a2", rail_keys())
		arrangement = get_arrangement("Rail", APP)
		self.assertEqual([row["key"] for row in arrangement], ["todo", "note", "user:k3f9a2"])
		self.assertEqual(arrangement[-1].get("no_access"), 1)
		self.assertFalse(any(row.get("no_access") for row in arrangement[:-1]))

	def test_an_inherited_row_you_cannot_open_stays_out(self):
		self.assertNotIn("secret", keys(get_arrangement("Rail", APP)))

	def test_a_save_keeps_the_row_and_never_stores_the_marker(self):
		self.an_own_row_you_cannot_open()

		save_arrangement("Rail", APP, get_arrangement("Rail", APP)[::-1])

		row = next(row for row in stored() if row.key == "user:k3f9a2")
		self.assertEqual(row.added, 1)
		self.assertFalse(hasattr(row, "no_access") and row.no_access)
		self.assertTrue(frappe.get_meta("Navigation Item").get_field("no_access") is None)

	def test_the_editor_can_delete_it(self):
		self.an_own_row_you_cannot_open()

		save_arrangement(
			"Rail", APP, [row for row in get_arrangement("Rail", APP) if row["key"] != "user:k3f9a2"]
		)

		self.assertFalse(stored())

	def test_the_site_scope_reads_unfiltered_and_needs_no_marker(self):
		with set_user(a_person()):
			arrangement = get_arrangement("Rail", APP, "site")

		self.assertIn("secret", keys(arrangement))
		self.assertFalse(any(row.get("no_access") for row in arrangement))

	def test_own_rows_carry_nothing_of_how_they_were_stored_on_the_wire(self):
		save_arrangement("Rail", APP, showing(shown("todo"), own("user:k3f9a2"), shown("note")))

		wire = next(entry for entry in resolve_navigation(APP)["rail"] if entry["key"] == "user:k3f9a2")

		for stored_only in ("added", "overrides", "no_access", "anchors", "hidden", "switches_app"):
			self.assertNotIn(stored_only, wire)
