# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The extension merge, `frappe/shell/extensions.py`: pure list operations, no site."""

import json

from frappe.shell.extensions import extend
from frappe.tests import UnitTestCase

HOST = "erpnext"
APP = "telephony"
OTHER = "payments"


def item(key: str, **kwargs) -> dict:
	return {"key": key, "item_type": "DocType", "link_doctype": "DocType", **kwargs}


def anchored(key: str, *anchors: dict, **kwargs) -> dict:
	return item(key, anchors=json.dumps(list(anchors)), **kwargs)


def keys(items: list[dict]) -> list[str]:
	return [entry["key"] for entry in items]


class TestKeyNamespacing(UnitTestCase):
	def test_a_contributed_key_is_namespaced_and_the_hosts_are_not(self):
		merged = extend([item("leads")], [(APP, [item("leads")])], anchorable=True)

		self.assertEqual(keys(merged), ["leads", "telephony:leads"])

	def test_two_apps_may_ship_the_same_key(self):
		merged = extend([], [(APP, [item("calls")]), (OTHER, [item("calls")])], anchorable=True)

		self.assertEqual(keys(merged), ["telephony:calls", "payments:calls"])

	def test_a_contributed_subtree_keeps_its_own_shape(self):
		merged = extend([], [(APP, [item("calls"), item("missed", parent_key="calls")])], anchorable=True)

		self.assertEqual(merged[1]["parent_key"], "telephony:calls")

	def test_a_keyless_row_is_skipped(self):
		"""It would namespace to a bare `telephony:` shared with every other keyless row."""
		merged = extend([], [(APP, [{"item_type": "DocType"}, item("calls")])], anchorable=True)

		self.assertEqual(keys(merged), ["telephony:calls"])


class TestAnchors(UnitTestCase):
	def base(self) -> list[dict]:
		return [item("customers"), item("orders"), item("settings")]

	def test_after_puts_the_row_next_to_the_key_it_names(self):
		merged = extend(self.base(), [(APP, [anchored("calls", {"after": "customers"})])], anchorable=True)

		self.assertEqual(keys(merged), ["customers", "telephony:calls", "orders", "settings"])

	def test_before_puts_it_on_the_other_side(self):
		merged = extend(self.base(), [(APP, [anchored("calls", {"before": "orders"})])], anchorable=True)

		self.assertEqual(keys(merged), ["customers", "telephony:calls", "orders", "settings"])

	def test_the_first_anchor_that_resolves_wins(self):
		merged = extend(
			self.base(),
			[(APP, [anchored("calls", {"after": "invoices"}, {"after": "orders"})])],
			anchorable=True,
		)

		self.assertEqual(keys(merged), ["customers", "orders", "telephony:calls", "settings"])

	def test_an_item_that_resolves_nothing_is_appended_and_never_dropped(self):
		merged = extend(self.base(), [(APP, [anchored("calls", {"after": "invoices"})])], anchorable=True)

		self.assertEqual(keys(merged)[-1], "telephony:calls")

	def test_an_anchor_naming_both_sides_names_neither(self):
		merged = extend(
			self.base(),
			[(APP, [anchored("calls", {"after": "customers", "before": "orders"})])],
			anchorable=True,
		)

		self.assertEqual(keys(merged)[-1], "telephony:calls")

	def test_an_unreadable_anchor_list_is_no_anchors(self):
		"""The item still appears, where an app with no anchors would have put it."""
		merged = extend(self.base(), [(APP, [item("calls", anchors="{not json")])], anchorable=True)

		self.assertEqual(keys(merged)[-1], "telephony:calls")

	def test_a_derived_base_offers_no_anchor_targets(self):
		merged = extend(self.base(), [(APP, [anchored("calls", {"after": "customers"})])], anchorable=False)

		self.assertEqual(keys(merged)[-1], "telephony:calls")

	def test_an_anchor_may_name_the_apps_own_row_without_writing_its_own_name(self):
		merged = extend(
			self.base(),
			[(APP, [item("calls"), anchored("missed", {"after": "calls"})])],
			anchorable=True,
		)

		self.assertEqual(keys(merged)[-2:], ["telephony:calls", "telephony:missed"])

	def test_a_host_key_wins_over_the_apps_own(self):
		merged = extend(
			[item("calls")],
			[(APP, [item("calls"), anchored("missed", {"after": "calls"})])],
			anchorable=True,
		)

		self.assertEqual(keys(merged), ["calls", "telephony:missed", "telephony:calls"])


class TestNesting(UnitTestCase):
	def test_a_parent_key_anchor_nests_the_row_under_a_host_row(self):
		merged = extend(
			[item("sales"), item("customers", parent_key="sales"), item("settings")],
			[(APP, [anchored("calls", {"parent_key": "sales"})])],
			anchorable=True,
		)

		self.assertEqual(merged[2]["key"], "telephony:calls")
		self.assertEqual(merged[2]["parent_key"], "sales")

	def test_sitting_beside_a_row_means_sitting_at_its_depth(self):
		merged = extend(
			[item("sales"), item("customers", parent_key="sales")],
			[(APP, [anchored("calls", {"after": "customers"})])],
			anchorable=True,
		)

		self.assertEqual(merged[2]["parent_key"], "sales")

	def test_an_explicit_parent_wins_over_the_one_beside_implies(self):
		merged = extend(
			[item("sales"), item("customers", parent_key="sales"), item("support")],
			[(APP, [anchored("calls", {"after": "customers", "parent_key": "support"})])],
			anchorable=True,
		)

		self.assertEqual(merged[2]["parent_key"], "support")

	def test_an_anchor_is_read_on_a_root_and_ignored_on_a_child(self):
		merged = extend(
			[item("sales"), item("settings")],
			[
				(
					APP,
					[
						item("calls"),
						anchored("missed", {"after": "sales"}, parent_key="calls"),
					],
				)
			],
			anchorable=True,
		)

		self.assertEqual(keys(merged), ["sales", "settings", "telephony:calls", "telephony:missed"])
		self.assertEqual(merged[3]["parent_key"], "telephony:calls")


class TestTwoPasses(UnitTestCase):
	"""Every row is placed first, then anchored, so install order cannot decide an anchor."""

	def test_an_anchor_may_name_another_extenders_item_whichever_went_on_first(self):
		calls = [(APP, [item("calls")])]
		invoices = [(OTHER, [anchored("invoices", {"after": "telephony:calls"})])]

		for order in (calls + invoices, invoices + calls):
			merged = extend([item("customers")], order, anchorable=True)
			self.assertEqual(
				keys(merged)[-2:], ["telephony:calls", "payments:invoices"], msg=str(keys(merged))
			)

	def test_two_apps_naming_each_other_fall_back_rather_than_pick_a_winner(self):
		merged = extend(
			[item("customers")],
			[
				(APP, [anchored("calls", {"after": "payments:invoices"})]),
				(OTHER, [anchored("invoices", {"after": "telephony:calls"})]),
			],
			anchorable=True,
		)

		self.assertEqual(len(merged), 3)
		self.assertIn("telephony:calls", keys(merged))
		self.assertIn("payments:invoices", keys(merged))


class TestTheBaseIsLeftAlone(UnitTestCase):
	def test_nothing_is_contributed_and_the_base_comes_back(self):
		base = [item("customers")]
		merged = extend(base, [], anchorable=True)

		self.assertEqual(keys(merged), ["customers"])
		self.assertIsNot(merged[0], base[0], "the base rows are copied, not handed out")

	def test_two_rows_that_look_alike_are_told_apart_by_identity(self):
		"""`list.remove` takes the first row that compares equal, so a move must go by identity."""
		merged = extend(
			[item("customers")],
			[(APP, [item("calls"), anchored("calls", {"after": "customers"})])],
			anchorable=True,
		)

		self.assertEqual(len(merged), 3)
		self.assertEqual(keys(merged).count("telephony:calls"), 2)

	def test_a_contributed_row_records_which_app_contributed_it(self):
		merged = extend([], [(APP, [item("calls")])], anchorable=True)

		self.assertEqual(merged[0]["app"], APP)
