# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The overlay write endpoints, `frappe/shell/arrangement.py`."""

import json

import frappe
from frappe.exceptions import FrappeTypeError
from frappe.shell.arrangement import (
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
from frappe.shell.navigation import resolve_navigation
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_shell_navigation import (
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

		self.assertEqual(reduce_arrangement(base, base), [])

	def test_only_the_rows_that_moved_are_written(self):
		base = [shown("a"), shown("b"), shown("c")]
		rows = reduce_arrangement(base, [shown("c"), shown("a"), shown("b")])

		self.assertEqual([row["key"] for row in rows], ["c"])
		self.assertEqual(json.loads(rows[0]["anchors"]), [{"before": "a"}])

	def test_a_rename_is_a_field_level_override(self):
		base = [shown("a", label="Accounts")]
		rows = reduce_arrangement(base, [shown("a", label="Money")])

		self.assertEqual(rows[0]["label"], "Money")
		self.assertEqual(json.loads(rows[0]["overrides"]), ["label"])

	def test_clearing_a_label_the_app_shipped_is_expressible(self):
		rows = reduce_arrangement([shown("a", label="Accounts")], [shown("a", label="")])

		self.assertEqual(json.loads(rows[0]["overrides"]), ["label"])
		self.assertEqual(rows[0]["label"], "")

	def test_clearing_an_already_blank_field_says_nothing(self):
		self.assertEqual(reduce_arrangement([shown("a")], [shown("a", label="")]), [])

	def test_a_hide_is_written_and_an_unhide_is_written(self):
		self.assertEqual(reduce_arrangement([shown("a")], [shown("a", hidden=1)])[0]["hidden"], 1)
		self.assertEqual(reduce_arrangement([shown("a", hidden=1)], [shown("a")])[0]["hidden"], 0)

	def test_a_key_or_parent_that_is_not_a_name_is_dropped(self):
		base = [shown("a"), shown("b")]

		self.assertEqual(reduce_arrangement(base, _as_items([{"key": ["!=", ""]}, shown("a")])), [])

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
		rows = reduce_arrangement([shown("a")], [shown("gone"), shown("a")])

		self.assertEqual([row["key"] for row in rows], [])

	def test_order_is_compared_per_parent(self):
		base = [shown("s1"), shown("a", parent_key="s1"), shown("s2"), shown("b", parent_key="s2")]
		desired = [shown("s1"), shown("s2"), shown("b", parent_key="s2"), shown("a", parent_key="s1")]

		self.assertEqual(reduce_arrangement(base, desired), [])

	def test_a_row_moved_to_the_front_names_a_row_that_is_not_also_moving(self):
		base = [shown(key) for key in "abcde"]
		anchors = anchors_for(base, [shown(key) for key in "deabc"])

		# `d` names the first row ahead of it that is staying put, not `e`, which is about to move.
		self.assertEqual(anchors["d"], [{"before": "a"}])
		self.assertEqual(anchors["e"], [{"after": "d"}])

	def test_a_key_sent_twice_keeps_its_first_position(self):
		base = [shown("a"), shown("b")]
		rows = reduce_arrangement(base, [shown("b")] * 5000 + [shown("a")])

		# The repeats are gone before anything compares orders.
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows, reduce_arrangement(base, [shown("b"), shown("a")]))

	def test_an_override_that_is_not_a_scalar_is_read_as_blank(self):
		self.assertEqual(reduce_arrangement([shown("a")], [shown("a", label=["x"])]), [])

		row = reduce_arrangement([shown("a", label="Accounts")], [shown("a", label={"x": 1})])[0]
		self.assertIsNone(row["label"])

	def test_the_fewest_possible_rows_move(self):
		base = [shown(key) for key in "abcdef"]
		desired = [shown(key) for key in "bcdefa"]

		self.assertEqual([row["key"] for row in reduce_arrangement(base, desired)], ["a"])


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
