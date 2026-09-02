# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The extension merge: `frappe/shell/extensions.py`.

Pure list operations, so these are unit tests with no site behind them. That is the point of
the module being separable at all — the ordering rules below are where #42364's design lives,
and they are worth reading and exercising without a rail, a layer or a user in the way. What
the merge does inside the resolver is `test_shell_navigation.py`'s.

`erpnext` is the host and `telephony` the extender throughout. Neither has to be installed:
nothing here resolves an app name, and the one place that does — dropping a disabled app's
contribution — is a query in `navigation.py`.
"""

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
		"""The key is what every user edit is filed against (#42229), so a host key that changed
		when a second app was installed would silently detach the site's arrangement. Namespacing
		the newcomer is the only direction that leaves existing identities alone."""
		merged = extend([item("leads")], [(APP, [item("leads")])], anchorable=True)

		self.assertEqual(keys(merged), ["leads", "telephony:leads"])

	def test_two_apps_may_ship_the_same_key(self):
		"""`validate_item_keys` checks one record, so it never could have caught this. The merge
		is where it has to hold, and it holds by construction rather than by a check."""
		merged = extend([], [(APP, [item("calls")]), (OTHER, [item("calls")])], anchorable=True)

		self.assertEqual(keys(merged), ["telephony:calls", "payments:calls"])

	def test_a_contributed_subtree_keeps_its_own_shape(self):
		"""`parent_key` names a sibling in the app's own list, so it is namespaced with the key
		and the subtree travels as a unit. Nesting into the *host* is an anchor's job — reading
		one column as sometimes-mine-sometimes-theirs would break an app's own hierarchy the day
		a host happened to ship a row with the same key."""
		merged = extend([], [(APP, [item("calls"), item("missed", parent_key="calls")])], anchorable=True)

		self.assertEqual(merged[1]["parent_key"], "telephony:calls")

	def test_a_keyless_row_is_skipped(self):
		"""It would namespace to a bare `telephony:` that every other keyless row also produced."""
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
		"""Which is how an app says "beside Invoices, or failing that beside Orders" without
		knowing which version of the host is installed."""
		merged = extend(
			self.base(),
			[(APP, [anchored("calls", {"after": "invoices"}, {"after": "orders"})])],
			anchorable=True,
		)

		self.assertEqual(keys(merged), ["customers", "orders", "telephony:calls", "settings"])

	def test_an_item_that_resolves_nothing_is_appended_and_never_dropped(self):
		"""An app writes anchors against a host it does not ship and cannot pin, so a missing
		anchor is the expected case. Landing in the wrong place is cosmetic; vanishing is a bug
		report filed against the wrong app."""
		merged = extend(self.base(), [(APP, [anchored("calls", {"after": "invoices"})])], anchorable=True)

		self.assertEqual(keys(merged)[-1], "telephony:calls")

	def test_an_anchor_naming_both_sides_names_neither(self):
		"""Two positions is no position. Resolving it by precedence would turn a typo into a
		silent placement nobody wrote."""
		merged = extend(
			self.base(),
			[(APP, [anchored("calls", {"after": "customers", "before": "orders"})])],
			anchorable=True,
		)

		self.assertEqual(keys(merged)[-1], "telephony:calls")

	def test_an_unreadable_anchor_list_is_no_anchors(self):
		"""The rows are authored by an app against a host it cannot see, so the reader of any
		complaint would be the wrong person. The item still appears, where an app with no
		anchors would have put it."""
		merged = extend(self.base(), [(APP, [item("calls", anchors="{not json")])], anchorable=True)

		self.assertEqual(keys(merged)[-1], "telephony:calls")

	def test_a_derived_base_offers_no_anchor_targets(self):
		"""A derived rail's keys are doctype names nobody authored, and one of them is a side
		effect of what the reader happens to be allowed to see. An anchor cannot name one."""
		merged = extend(self.base(), [(APP, [anchored("calls", {"after": "customers"})])], anchorable=False)

		self.assertEqual(keys(merged)[-1], "telephony:calls")

	def test_an_anchor_may_name_the_apps_own_row_without_writing_its_own_name(self):
		"""Written-first is what makes the common case — aiming at the host — resolve to the
		host. The own-namespace fallback is only reached when the host has no such key, so it
		can never shadow one."""
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
		"""Beside means beside. A sibling that landed at a different depth would be somewhere
		else entirely."""
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
		"""Where a contributed subtree sits is its root's business. An anchor on a child would
		tear the subtree apart to satisfy a row that never had a say in where it went."""
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
	"""Placing and anchoring in one pass would make an anchor that names another extender's item
	resolve or not depending on which app was installed first — a property of a bench rather than
	of either app. So every row is placed first, and only then does anything look for a key.
	"""

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

	def test_a_contributed_row_records_which_app_contributed_it(self):
		"""Which is the one thing `switches_app` needs and the only thing that can supply it: a
		merged item is otherwise indistinguishable from a host row, deliberately."""
		merged = extend([], [(APP, [item("calls")])], anchorable=True)

		self.assertEqual(merged[0]["app"], APP)
