# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The depth cap, `frappe.desk.doctype.navigation_item.nesting.py`, and every place it binds."""

import json
from pathlib import Path

import frappe
from frappe.desk.doctype.navigation_item.nesting import cap_depth, nesting_errors
from frappe.shell.arrangement import save_arrangement
from frappe.shell.navigation import SITE_LAYER, resolve_navigation
from frappe.tests.classes.context_managers import set_user
from frappe.tests.test_navigation_arrangement import a_person, shown
from frappe.tests.test_shell_navigation import (
	ADDRESS_KEY,
	APP,
	NavigationTestCase,
	doctype_item,
	item,
	make_rail,
	make_sidebar,
	moved,
)

# One list of cases for both languages: `navigation/tests/nesting.test.ts` reads it too.
CASES = json.loads(
	(
		Path(frappe.get_app_path("frappe")).parent / "frontend/src/navigation/tests/nesting.cases.json"
	).read_text()
)["cases"]


def sidebar_rows() -> list[dict]:
	return resolve_navigation(APP)["sidebars"][ADDRESS_KEY]


def a_shipped_act(key: str) -> dict:
	return item(key, item_type="Act", payload=json.dumps({"act": "shell.theme"}))


def a_sidebar_to_arrange():
	"""section `s` > `a` > `b`, and `c` at the top level: the deepest a list may go."""
	make_sidebar(
		[
			item("s", item_type="Section"),
			doctype_item("a", "User", parent_key="s"),
			doctype_item("b", "Role", parent_key="a"),
			doctype_item("c", "DocType"),
		],
		standard=1,
	)


class TestTheRule(NavigationTestCase):
	def test_nesting_errors_names_the_rows_past_the_cap(self):
		for case in CASES:
			with self.subTest(case["name"]):
				self.assertEqual(nesting_errors(case["items"], case["container"]), case["errors"])

	def test_cap_depth_lifts_a_row_to_its_parents_parent_and_keeps_the_order(self):
		for case in CASES:
			with self.subTest(case["name"]):
				capped = cap_depth(case["items"], case["container"])

				self.assertEqual([row["key"] for row in capped], [row["key"] for row in case["items"]])
				self.assertEqual({row["key"]: row.get("parent_key") for row in capped}, case["capped"])
				self.assertEqual(nesting_errors(capped, case["container"]), [])

	def test_cap_depth_does_not_edit_the_list_it_is_given(self):
		items = [{"key": "a"}, {"key": "b", "parent_key": "a"}, {"key": "c", "parent_key": "b"}]

		cap_depth(items, "Sidebar")

		self.assertEqual(items[2]["parent_key"], "b")

	def test_the_moves_the_editor_may_offer_are_the_ones_that_add_no_row_past_the_cap(self):
		for case in CASES:
			for move in case["moves"]:
				with self.subTest(f"{case['name']}: {move['key']} under {move['parent']}"):
					before = set(nesting_errors(case["items"], case["container"]))
					after = nesting_errors(
						[
							{**row, "parent_key": move["parent"]} if row["key"] == move["key"] else row
							for row in case["items"]
						],
						case["container"],
					)

					self.assertEqual(not set(after) - before, move["allowed"])

	def test_a_shipped_record_holds_documents_and_is_read_the_same_way(self):
		doc = frappe.get_doc(
			doctype="Sidebar",
			navigation_items=[item("a"), item("b", parent_key="a"), item("c", parent_key="b")],
		)

		self.assertEqual(nesting_errors(doc.navigation_items, "Sidebar"), ["c"])


class TestSavingPastTheCap(NavigationTestCase):
	def test_a_save_that_nests_too_deeply_is_refused_at_both_levels(self):
		a_sidebar_to_arrange()
		too_deep = [
			shown("s"),
			shown("a", parent_key="s"),
			shown("b", parent_key="a"),
			shown("c", parent_key="b"),
		]

		# Administrator skips the permission filter, so the saves run as a person.
		with set_user(a_person()):
			for scope in ("user", "site"):
				with self.subTest(scope), self.assertRaises(frappe.ValidationError) as caught:
					save_arrangement("Sidebar", ADDRESS_KEY, too_deep, scope)

				self.assertIn("nested too deeply", str(caught.exception))

	def test_the_deepest_row_a_list_may_hold_is_saved(self):
		a_sidebar_to_arrange()
		deepest = [
			shown("s"),
			shown("a", parent_key="s"),
			shown("b", parent_key="a"),
			shown("c", parent_key="a"),
		]

		with set_user(a_person()):
			save_arrangement("Sidebar", ADDRESS_KEY, deepest)
			parents = {row["key"]: row.get("parent_key") for row in sidebar_rows()}

		self.assertEqual(parents, {"s": None, "a": "s", "b": "a", "c": "a"})

	def test_a_row_under_an_act_row_is_refused(self):
		make_sidebar([a_shipped_act("x"), doctype_item("a", "User")], standard=1)

		with set_user(a_person()), self.assertRaises(frappe.ValidationError) as caught:
			save_arrangement("Sidebar", ADDRESS_KEY, [shown("x"), shown("a", parent_key="x")])

		self.assertIn("nested too deeply", str(caught.exception))

	def test_a_row_left_out_of_the_save_still_counts(self):
		a_sidebar_to_arrange()

		# `b` is left out and stays under `a`; moving `a` under `c` would put `b` past the cap.
		with set_user(a_person()), self.assertRaises(frappe.ValidationError):
			save_arrangement("Sidebar", ADDRESS_KEY, [shown("s"), shown("c"), shown("a", parent_key="c")])

	def test_an_inherited_section_cannot_be_nested_by_calling_it_an_item(self):
		a_sidebar_to_arrange()

		with self.assertRaises(frappe.ValidationError):
			save_arrangement(
				"Sidebar", ADDRESS_KEY, [shown("s", parent_key="c", item_type="DocType"), shown("c")]
			)

	def test_a_row_under_a_row_that_is_not_in_the_list_is_not_a_depth(self):
		a_sidebar_to_arrange()

		with set_user(a_person()):
			save_arrangement(
				"Sidebar",
				ADDRESS_KEY,
				[shown("s"), shown("a", parent_key="s"), shown("c", parent_key="gone")],
			)

	def test_a_rail_row_with_a_parent_is_refused(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)

		with self.assertRaises(frappe.ValidationError):
			save_arrangement("Rail", APP, [shown("user"), shown("role", parent_key="user")])


class TestShippingPastTheCap(NavigationTestCase):
	def test_a_shipped_sidebar_past_the_cap_is_refused(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			make_sidebar([item("a"), item("b", parent_key="a"), item("c", parent_key="b")], standard=1)

		self.assertIn("sits too deep", str(caught.exception))

	def test_a_shipped_sidebar_holding_its_deepest_row_is_kept(self):
		a_sidebar_to_arrange()

		self.assertEqual(len(sidebar_rows()), 4)

	def test_a_shipped_rail_with_a_parent_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			make_rail([item("a"), item("b", parent_key="a")], standard=1)

	def test_a_layer_is_not_checked_at_validate(self):
		# A layer is a delta against what is below it: the resolver is where its depth counts.
		make_sidebar([item("a"), item("b", parent_key="a"), item("c", parent_key="b")], standard=0)


class TestComposingPastTheCap(NavigationTestCase):
	def test_a_child_that_layers_put_under_an_act_row_is_lifted(self):
		make_sidebar([a_shipped_act("x"), doctype_item("a", "User")], standard=1)
		make_sidebar([moved("a", {"parent_key": "x"})], user=SITE_LAYER)

		self.assertEqual(
			{row["key"]: row.get("parent_key") for row in sidebar_rows()}, {"x": None, "a": None}
		)

	def test_what_layers_compose_past_the_cap_is_lifted_and_nothing_is_dropped(self):
		make_sidebar(
			[
				doctype_item("a", "User"),
				doctype_item("b", "Role"),
				doctype_item("c", "DocType", parent_key="a"),
			],
			standard=1,
		)
		make_sidebar([moved("a", {"parent_key": "b"})], user=SITE_LAYER)
		self.assertEqual(
			{row["key"]: row.get("parent_key") for row in sidebar_rows()}, {"a": "b", "b": None, "c": "b"}
		)
		self.assertEqual([row["key"] for row in sidebar_rows()], ["b", "a", "c"])
