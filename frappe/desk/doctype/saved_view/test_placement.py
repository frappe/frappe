# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from frappe.desk.doctype.saved_view.placement import placed_names, unplaced_views, without_view
from frappe.tests import UnitTestCase


class TestPlacement(UnitTestCase):
	"""The pool and row-removal rules, without a site."""

	def test_placed_names_normalizes_integer_links(self):
		sections = [{"items": [{"view": 7}]}, {"items": [{"view": "8"}]}]

		self.assertEqual(placed_names(sections), {"7", "8"})

	def test_placed_names_of_nothing_is_empty(self):
		self.assertEqual(placed_names([]), set())

	def test_unplaced_views_keeps_only_what_no_section_holds(self):
		views = [{"name": 1}, {"name": 2}]

		self.assertEqual(unplaced_views(views, {"1"}), [{"name": 2}])

	def test_unplaced_views_preserves_given_order(self):
		views = [{"name": 3}, {"name": 1}, {"name": 2}]

		self.assertEqual([view["name"] for view in unplaced_views(views, set())], [3, 1, 2])

	def test_without_view_drops_every_row_for_that_view(self):
		rows = [{"view": "1"}, {"view": "2"}, {"view": 1}]

		self.assertEqual(without_view(rows, "1"), [{"view": "2"}])

	def test_without_view_leaves_other_rows_untouched(self):
		rows = [{"view": "2"}]

		self.assertEqual(without_view(rows, "1"), rows)
