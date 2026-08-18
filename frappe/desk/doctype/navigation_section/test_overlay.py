# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from frappe.desk.doctype.navigation_section.overlay import apply_overlay
from frappe.tests import UnitTestCase


def shared_row(name, idx, **fields):
	return {"name": name, "idx": idx, "type": "view", "view": name, **fields}


def delta(name, idx, hidden=0, **overrides):
	"""An overlay row: the shared row it deltas, where its owner put it, whether they
	hid it, and any label or icon of their own."""
	return {"overrides": name, "idx": idx, "hidden": hidden, **overrides}


def own(name, idx, **fields):
	"""An overlay row that deltas nothing: an item its owner added to the section."""
	return {"name": name, "idx": idx, "type": "link", "label": name, "url": "/docs", **fields}


def names(rows):
	return [row["name"] for row in rows]


class TestApplyOverlay(UnitTestCase):
	"""Delta reconciliation, without a site. Rows are matched on the shared row's own
	name — a link item has no view to match on, and two rows may hold the same view."""

	def test_without_an_overlay_the_shared_order_stands(self):
		shared = [shared_row("a", 2), shared_row("b", 1)]

		self.assertEqual(names(apply_overlay(shared, [])), ["b", "a"])

	def test_an_overlay_reorders_the_shared_rows(self):
		shared = [shared_row("a", 1), shared_row("b", 2)]

		self.assertEqual(names(apply_overlay(shared, [delta("b", 1), delta("a", 2)])), ["b", "a"])

	def test_an_overlay_hides_a_row_the_shared_section_shows(self):
		result = apply_overlay([shared_row("a", 1)], [delta("a", 1, hidden=1)])

		self.assertEqual([row["hidden"] for row in result], [1])

	def test_a_manager_added_row_lands_at_the_end(self):
		"""The overlay predates the addition, so it says nothing about the new row."""
		shared = [shared_row("a", 1), shared_row("new", 2)]

		self.assertEqual(names(apply_overlay(shared, [delta("a", 1)])), ["a", "new"])

	def test_several_manager_added_rows_keep_their_shared_order(self):
		shared = [shared_row("a", 1), shared_row("c", 3), shared_row("b", 2)]

		self.assertEqual(names(apply_overlay(shared, [delta("a", 1)])), ["a", "b", "c"])

	def test_a_manager_deleted_row_vanishes_from_the_overlay(self):
		shared = [shared_row("a", 1)]

		self.assertEqual(names(apply_overlay(shared, [delta("gone", 1), delta("a", 2)])), ["a"])

	def test_an_added_row_is_not_hidden_by_an_unrelated_overlay_row(self):
		shared = [shared_row("a", 1), shared_row("new", 2)]

		result = apply_overlay(shared, [delta("a", 1, hidden=1)])

		self.assertEqual([(row["name"], row["hidden"]) for row in result], [("a", 1), ("new", 0)])

	def test_the_shared_rows_content_survives_the_overlay(self):
		"""Where the overlay names nothing of its own, the shared row's content stands —
		a link item's URL is never a personal matter."""
		shared = [shared_row("a", 1, type="link", view=None, label="Docs", url="/docs")]

		row = apply_overlay(shared, [delta("a", 1)])[0]

		self.assertEqual((row["type"], row["label"], row["url"]), ("link", "Docs", "/docs"))

	def test_an_overlay_reorders_rows_that_hold_no_view(self):
		shared = [
			shared_row("a", 1, type="link", view=None, label="Docs"),
			shared_row("b", 2, type="link", view=None, label="Help"),
		]

		self.assertEqual(names(apply_overlay(shared, [delta("b", 1), delta("a", 2)])), ["b", "a"])

	def test_an_overlay_renames_a_row_for_its_owner_alone(self):
		"""Their own name for a shared row. The shared row is untouched, so everybody
		else keeps the manager's."""
		shared = [shared_row("a", 1, type="link", view=None, label="Documentation")]

		row = apply_overlay(shared, [delta("a", 1, label="Docs")])[0]

		self.assertEqual(row["label"], "Docs")
		self.assertEqual(shared[0]["label"], "Documentation")

	def test_an_overlay_reicons_a_row_for_its_owner_alone(self):
		shared = [shared_row("a", 1, type="link", view=None, label="Docs", icon="book")]

		row = apply_overlay(shared, [delta("a", 1, icon="star")])[0]

		self.assertEqual(row["icon"], "star")

	def test_an_overlay_that_renames_leaves_the_icon_alone(self):
		"""The two are written together but overridden apart, so a rename does not blank
		an icon the manager set."""
		shared = [shared_row("a", 1, type="link", view=None, label="Docs", icon="book")]

		row = apply_overlay(shared, [delta("a", 1, label="Handbook")])[0]

		self.assertEqual((row["label"], row["icon"]), ("Handbook", "book"))

	def test_an_overlays_own_item_sits_where_it_puts_it(self):
		"""The point of carrying it inline: the user's own item lands *between* the shared
		rows rather than in a section of theirs underneath them."""
		shared = [shared_row("a", 1), shared_row("b", 2)]

		result = apply_overlay(shared, [delta("a", 1), own("mine", 2), delta("b", 3)])

		self.assertEqual(names(result), ["a", "mine", "b"])

	def test_an_overlays_own_item_keeps_its_own_content(self):
		"""It deltas nothing, so there is nothing to resolve it against — the row is the
		item."""
		row = apply_overlay([shared_row("a", 1)], [own("mine", 1, label="Docs"), delta("a", 2)])[0]

		self.assertEqual((row["type"], row["label"], row["url"]), ("link", "Docs", "/docs"))

	def test_an_overlays_own_item_can_be_hidden(self):
		result = apply_overlay([shared_row("a", 1)], [own("mine", 1, hidden=1), delta("a", 2)])

		self.assertEqual([(row["name"], row["hidden"]) for row in result], [("mine", 1), ("a", 0)])

	def test_an_overlays_own_item_survives_a_row_the_manager_added(self):
		"""The new shared row appends, and must not carry the user's own item down with it."""
		shared = [shared_row("a", 1), shared_row("new", 2)]

		result = apply_overlay(shared, [own("mine", 1), delta("a", 2)])

		self.assertEqual(names(result), ["mine", "a", "new"])

	def test_an_overlay_of_nothing_but_its_own_items_keeps_the_shared_order(self):
		shared = [shared_row("a", 1), shared_row("b", 2)]

		self.assertEqual(names(apply_overlay(shared, [own("mine", 1)])), ["mine", "a", "b"])

	def test_an_overlays_own_item_is_marked_as_the_users_own(self):
		"""What the editor gates a remove on. Once resolved the row looks like any
		other, so the flag is set here, where the two are still distinguishable."""
		result = apply_overlay([shared_row("a", 1)], [own("mine", 1), delta("a", 2)])

		self.assertEqual([(row["name"], row["own"]) for row in result], [("mine", 1), ("a", 0)])

	def test_a_shared_row_is_nobodys_own_with_or_without_an_overlay(self):
		shared = [shared_row("a", 1)]

		self.assertEqual(apply_overlay(shared, [])[0]["own"], 0)
		self.assertEqual(apply_overlay(shared, [delta("a", 1)])[0]["own"], 0)

	def test_a_manager_rename_reaches_a_user_who_never_renamed_it(self):
		"""An overlay written by a drag carries no label, and must not freeze the one the
		row had when it was written."""
		shared = [shared_row("a", 1, type="link", view=None, label="Renamed by the manager")]

		row = apply_overlay(shared, [delta("a", 1)])[0]

		self.assertEqual(row["label"], "Renamed by the manager")
