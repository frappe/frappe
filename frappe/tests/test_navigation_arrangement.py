# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The overlay write endpoints: `frappe/shell/arrangement.py`.

Desk v2's first user-state write. Every test here is about what a person's edit stores and what
it resolves back to, so the layers belong to `frappe`, which is certainly installed wherever this
runs, and the doctypes they point at are ones every site has.

The helpers come from `test_shell_navigation`, which already knows how to place app content on a
site the way an install does. What is added here is the other side of that: a person editing it.
"""

import json

import frappe
from frappe.exceptions import FrappeTypeError
from frappe.shell.arrangement import (
	_as_items,
	_target,
	anchors_for,
	get_arrangement,
	reduce_arrangement,
	reset_arrangement,
	save_arrangement,
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


def showing(*items: dict) -> list[dict]:
	"""What a client sends: the whole ordered list it is showing, hidden rows and all."""
	return list(items)


def shown(key: str, **kwargs) -> dict:
	return {"key": key, **kwargs}


def a_person(email: str = OTHER, role: str = "System Manager") -> str:
	"""Somebody other than the session user, so "a colleague sees their own" has somebody to be.

	`System Manager` by default because that is the site scope's gate. The test that is about
	the gate asks for `Desk User` instead: `has_app_permission` defaults to "is a System User",
	so a Desk User is somebody who may enter the prefix and arrange their own rail, and may not
	arrange everyone's.
	"""
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
		"""The reason `overrides` is a list of fieldnames rather than "whatever is non-blank"."""
		rows = reduce_arrangement([shown("a", label="Accounts")], [shown("a", label="")])

		self.assertEqual(json.loads(rows[0]["overrides"]), ["label"])
		self.assertEqual(rows[0]["label"], "")

	def test_clearing_an_already_blank_field_says_nothing(self):
		"""The resolved list omits a blank field rather than sending `null`, so a field nobody
		touched comes back absent and a field somebody cleared comes back as `""`. Reading those
		as two different values would write a row that says nothing."""
		self.assertEqual(reduce_arrangement([shown("a")], [shown("a", label="")]), [])

	def test_a_hide_is_written_and_an_unhide_is_written(self):
		self.assertEqual(reduce_arrangement([shown("a")], [shown("a", hidden=1)])[0]["hidden"], 1)
		self.assertEqual(reduce_arrangement([shown("a", hidden=1)], [shown("a")])[0]["hidden"], 0)

	def test_a_key_or_parent_that_is_not_a_name_is_dropped(self):
		"""Both are read as dictionary keys from here on, and a list is not hashable — so one
		arriving in either column would end a whitelisted save in an uncaught `TypeError`."""
		base = [shown("a"), shown("b")]

		self.assertEqual(reduce_arrangement(base, _as_items([{"key": ["!=", ""]}, shown("a")])), [])

		# And a parent that is not a name drops the row rather than being read as blank. Blank
		# means the top level, which is a placement nobody asked for and one the reduction would
		# faithfully write down; dropping the row says nothing about it, so it stays put.
		# Blank means `None` or `""` and nothing else. A truthiness test would let the *falsy*
		# non-names through and read each of them as the top level, which is the reparenting
		# this exists to refuse.
		for parent in ({"x": 1}, ["s"], 0, False, [], {}):
			self.assertEqual(_as_items([shown("a", parent_key=parent)]), [], f"parent {parent!r}")

		for blank in ("", None):
			self.assertEqual(_as_items([shown("a", parent_key=blank)])[0]["parent_key"], None)

	def test_a_malformed_parent_does_not_move_a_row_to_the_top_level(self):
		make_rail(
			[
				item("people", item_type="Section", label="People"),
				doctype_item("user", "User", parent_key="people"),
			],
			standard=1,
		)

		for parent in (["oops"], 0, []):
			save_arrangement("Rail", APP, showing(shown("people"), shown("user", parent_key=parent)))

		entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")
		self.assertEqual(entry["parent_key"], "people")

	def test_a_key_the_base_does_not_hold_is_dropped(self):
		"""An app removed an item while somebody had the editor open. Refusing would lose the
		rest of a save over a row they never touched, and writing it would author an item into a
		layer from values a browser supplied."""
		rows = reduce_arrangement([shown("a")], [shown("gone"), shown("a")])

		self.assertEqual([row["key"] for row in rows], [])

	def test_order_is_compared_per_parent(self):
		"""The payload is a flat list the client renders as a tree, so where one section's
		children sit relative to another section's is not something anybody can see or intend."""
		base = [shown("s1"), shown("a", parent_key="s1"), shown("s2"), shown("b", parent_key="s2")]
		desired = [shown("s1"), shown("s2"), shown("b", parent_key="s2"), shown("a", parent_key="s1")]

		self.assertEqual(reduce_arrangement(base, desired), [])

	def test_a_row_moved_to_the_front_names_a_row_that_is_not_also_moving(self):
		"""Anchors resolve in the order the rows are written, so naming a row that has yet to
		move would place this one against a position that is about to change."""
		base = [shown(key) for key in "abcde"]
		anchors = anchors_for(base, [shown(key) for key in "deabc"])

		# `d` has nothing before it, so it names the first row ahead of it that is staying put --
		# not `e`, which is about to move out from under it.
		self.assertEqual(anchors["d"], [{"before": "a"}])
		self.assertEqual(anchors["e"], [{"after": "d"}])

	def test_a_key_sent_twice_keeps_its_first_position(self):
		"""And is only compared once. The order comparison is quadratic in a parent's list, so a
		body that repeated one key ten thousand times would size the work by the request rather
		than by the site's navigation."""
		base = [shown("a"), shown("b")]
		rows = reduce_arrangement(base, [shown("b")] * 5000 + [shown("a")])

		# One row, not five thousand: the repeats are gone before anything compares orders, and
		# what is left is the same single move `[b, a]` reduces to.
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows, reduce_arrangement(base, [shown("b"), shown("a")]))

	def test_an_override_that_is_not_a_scalar_is_read_as_blank(self):
		"""The rows come off a request body, where the endpoint's type annotations do not
		reach: a `label` can arrive as a list."""
		self.assertEqual(reduce_arrangement([shown("a")], [shown("a", label=["x"])]), [])

		row = reduce_arrangement([shown("a", label="Accounts")], [shown("a", label={"x": 1})])[0]
		self.assertIsNone(row["label"])

	def test_the_fewest_possible_rows_move(self):
		"""One item dragged to the end is one row, not the whole list re-positioned."""
		base = [shown(key) for key in "abcdef"]
		desired = [shown(key) for key in "bcdefa"]

		self.assertEqual([row["key"] for row in reduce_arrangement(base, desired)], ["a"])


class TestSavingAnArrangement(NavigationTestCase):
	def test_a_reorder_survives_a_re_resolve(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)

		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		self.assertEqual(rail_keys(), ["role", "user"])

	def test_the_save_hands_back_the_whole_prefix(self):
		"""Not the one list that changed. Hiding a rail item of type `Sidebar` changes which
		sidebars are reachable, so a scoped response would be a half-truth."""
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)

		navigation = save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		self.assertEqual(keys(navigation["rail"]), ["role", "user"])
		self.assertIn("sidebars", navigation)

	def test_arranging_it_back_leaves_no_row(self):
		"""An empty layer and no layer resolve identically, so keeping one would be a row that
		means nothing -- and it is what makes "drag it back" and "reset" end in one state."""
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
		"""#42229's sparse move-list, which is the whole reason a move is an anchor. A layer
		that recorded positions would pin the list, and the item an app ships next would have
		nowhere to land but the end."""
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
	"""#42363 decision 9, which is the one thing this build changed rather than added."""

	def section_rail(self):
		make_rail(
			[
				item("people", item_type="Section", label="People"),
				doctype_item("user", "User", parent_key="people"),
				doctype_item("role", "Role"),
			],
			standard=1,
		)

	def test_hiding_a_section_takes_its_children_with_it(self):
		self.section_rail()

		save_arrangement(
			"Rail",
			APP,
			showing(shown("people", hidden=1), shown("user", parent_key="people"), shown("role")),
		)

		self.assertEqual(rail_keys(), ["role"])

	def test_an_app_removing_a_section_still_promotes_its_children(self):
		"""The same flat list by the time it is resolved, and the opposite answer. A person
		hiding a section means the branch; an app withdrawing one must not silently withdraw
		everything under it."""
		make_rail([doctype_item("user", "User", parent_key="people")], standard=1)

		entry = resolve_navigation(APP)["rail"][0]
		self.assertNotIn("parent_key", entry)

	def test_a_section_nested_in_a_hidden_one_goes_too(self):
		make_rail(
			[
				item("outer", item_type="Section"),
				item("inner", item_type="Section", parent_key="outer"),
				doctype_item("user", "User", parent_key="inner"),
			],
			standard=1,
		)

		save_arrangement(
			"Rail",
			APP,
			showing(
				shown("outer", hidden=1),
				shown("inner", parent_key="outer"),
				shown("user", parent_key="inner"),
			),
		)

		self.assertEqual(rail_keys(), [])


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
		"""A save reads one scope below its own, so a person's anchors name the list they were
		actually looking at rather than the one the app ships."""
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
		"""There is no `user` argument in this module, so "write somebody else's arrangement" is
		not a request that can be made and does not need refusing."""
		import inspect

		self.assertNotIn("user", inspect.signature(save_arrangement).parameters)


class TestReset(NavigationTestCase):
	def test_a_reset_deletes_one_layer(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")))

		reset_arrangement("Rail", APP)

		self.assertEqual(rail_keys(), ["user", "role"])

	def test_resetting_your_own_cannot_reach_the_sites(self):
		"""Desk v1's two blast-radius resets delete the site layer and every user's from one
		call. Neither is ported."""
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		save_arrangement("Rail", APP, showing(shown("role"), shown("user")), scope="site")
		save_arrangement("Rail", APP, showing(shown("user", label="Mine")))

		reset_arrangement("Rail", APP)

		self.assertEqual(rail_keys(), ["role", "user"])
		self.assertTrue(frappe.db.exists("Rail", {"app": APP, "standard": 0, "user": ""}))

	def test_a_reset_of_a_layer_that_is_not_there_is_not_an_error(self):
		make_rail([doctype_item("user", "User")], standard=1)

		self.assertEqual(keys(reset_arrangement("Rail", APP)["rail"]), ["user"])


class TestTheGate(NavigationTestCase):
	def test_arranging_an_app_you_may_not_enter_is_refused(self):
		make_rail([doctype_item("user", "User")], standard=1)

		with set_user("Guest"), self.assertRaises(frappe.PermissionError):
			save_arrangement("Rail", APP, showing(shown("user")))

	def test_the_site_scope_needs_a_system_manager(self):
		"""Unlike the reads, this gate is the boundary rather than a choice of error page: no
		doctype permission stands behind arranging the rail of an app you may not enter."""
		make_rail([doctype_item("user", "User")], standard=1)
		reader = a_person("test_desk_user@example.com", role="Desk User")

		with set_user(reader):
			# Their own is theirs to arrange...
			save_arrangement("Rail", APP, showing(shown("user", label="Mine")))

			# ...and everyone's is not.
			with self.assertRaises(frappe.PermissionError):
				save_arrangement("Rail", APP, showing(shown("user")), scope="site")

	def test_an_app_that_is_not_on_this_bench_is_refused(self):
		"""Checked before the gate, because `has_app_permission` falls back to "is a System
		User" for an app that declares no hook -- and an app that is not here declares none."""
		with self.assertRaises(frappe.ValidationError):
			get_arrangement("Rail", "no_such_app")

	def test_a_body_that_is_not_an_arrangement_is_refused_with_a_sentence(self):
		"""Not with the JSON decoder's own error, which off a whitelisted method is a 500 where
		the caller needs to be told what it sent."""
		make_rail([doctype_item("user", "User")], standard=1)

		# A body that is neither a string nor a list never reaches here: the endpoint's type
		# annotation refuses it first. These two are the cases that do.
		for body in ("{not json", '{"key": "a"}'):
			with self.assertRaises(frappe.ValidationError):
				save_arrangement("Rail", APP, body)

	def test_an_argument_that_is_not_a_name_is_refused_at_the_boundary(self):
		"""Explicitly, not on the annotations alone: they apply only inside a request or a test,
		and Frappe accepts complex values throughout — so a filter list arriving where a name was
		expected turns `{"name": address}` into a different query entirely."""
		for address in (["!=", ""], {"name": "x"}):
			# Inside a request or a test the annotation gets there first, which is the belt...
			with self.assertRaises(FrappeTypeError):
				get_arrangement("Sidebar", address)

			# ...and this is the braces, for the contexts where annotations are not applied:
			# a background job, `bench execute`, or any other caller off a request.
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
		"""The client holds the scrubbed address and nothing else, and unscrubbing is not a
		function -- so the pair is read back from the standard record, whose name is that
		address by construction."""
		make_sidebar([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)

		save_arrangement("Sidebar", ADDRESS_KEY, showing(shown("role"), shown("user")))

		self.assertEqual(keys(resolve_navigation(APP)["sidebars"][ADDRESS_KEY]), ["role", "user"])

	def test_a_sidebar_layer_lands_in_the_v2_table(self):
		"""One `Sidebar` document holds desk v1's `items` beside desk v2's `navigation_items`,
		so a write that named the wrong parentfield would edit v1's sidebar."""
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
