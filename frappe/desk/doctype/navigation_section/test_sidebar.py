# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from frappe.desk.doctype.navigation_section.sidebar import build_sidebar
from frappe.tests import UnitTestCase


class TestBuildSidebar(UnitTestCase):
	"""The projection rules, without a site. Ordering belongs to `overlay.py`."""

	def test_keeps_the_row_order_it_is_given(self):
		sections = [{"name": "s1", "label": "Views", "items": [{"view": "2"}, {"view": "1"}]}]
		views = {"1": {"name": "1", "label": "First"}, "2": {"name": "2", "label": "Second"}}

		sidebar = build_sidebar(sections, views, (), {})

		self.assertEqual([item["label"] for item in sidebar[0]["items"]], ["Second", "First"])

	def test_carries_hidden_rows_with_the_flag(self):
		"""Edit mode needs them on hand to offer an unhide; the client filters otherwise."""
		sections = [{"name": "s1", "label": "Views", "items": [{"view": "1", "hidden": 1}]}]

		sidebar = build_sidebar(sections, {"1": {"name": "1"}}, (), {})

		self.assertEqual(sidebar[0]["items"][0]["hidden"], 1)

	def test_marks_a_shown_row_as_not_hidden(self):
		sections = [{"name": "s1", "label": "Views", "items": [{"view": "1"}]}]

		sidebar = build_sidebar(sections, {"1": {"name": "1"}}, (), {})

		self.assertEqual(sidebar[0]["items"][0]["hidden"], 0)

	def test_carries_a_hidden_section_with_the_flag(self):
		"""Edit mode shows it so it can be unhidden, the same as a hidden row."""
		sections = [{"name": "s1", "label": "Views", "hidden": 1, "items": []}]

		sidebar = build_sidebar(sections, {}, (), {})

		self.assertEqual(sidebar[0]["hidden"], 1)

	def test_marks_a_shown_section_as_not_hidden(self):
		sidebar = build_sidebar([{"name": "s1", "label": "Views", "items": []}], {}, (), {})

		self.assertEqual(sidebar[0]["hidden"], 0)

	def test_carries_the_own_flag_overlay_resolution_set(self):
		sections = [{"name": "s1", "label": "Views", "items": [{"view": "1", "own": 1}]}]

		sidebar = build_sidebar(sections, {"1": {"name": "1"}}, (), {})

		self.assertEqual(sidebar[0]["items"][0]["own"], 1)

	def test_every_row_of_a_personal_section_is_its_owners_own(self):
		"""The other half of the statement `overlay.py` makes about a shared section: a
		personal section holds nobody else's rows, so a client asking whether it may
		remove one gets its answer from the one field either way."""
		sections = [{"name": "s1", "label": "Mine", "user": "a@example.com", "items": [{"view": "1"}]}]

		sidebar = build_sidebar(sections, {"1": {"name": "1"}}, (), {})

		self.assertEqual(sidebar[0]["items"][0]["own"], 1)

	def test_a_shared_sections_rows_are_nobodys_own(self):
		sections = [{"name": "s1", "label": "Views", "items": [{"view": "1"}]}]

		sidebar = build_sidebar(sections, {"1": {"name": "1"}}, (), {})

		self.assertEqual(sidebar[0]["items"][0]["own"], 0)

	def test_drops_rows_whose_view_is_gone(self):
		sections = [{"name": "s1", "label": "Views", "items": [{"view": "99", "idx": 1}]}]

		sidebar = build_sidebar(sections, {}, (), {})

		self.assertEqual(sidebar[0]["items"], [])

	def test_keeps_an_empty_section(self):
		sidebar = build_sidebar([{"name": "s1", "label": "Views", "items": []}], {}, (), {})

		self.assertEqual(len(sidebar), 1)
		self.assertEqual(sidebar[0]["label"], "Views")

	def test_a_view_row_keeps_no_url_it_was_retyped_out_of(self):
		"""A view routes by its id, so the URL the row carried as a link item would send
		it somewhere else entirely."""
		items = [{"type": "view", "view": "1", "url": "/docs"}]
		sections = [{"name": "s1", "label": "Views", "items": items}]

		sidebar = build_sidebar(sections, {"1": {"name": "1"}}, (), {})

		self.assertEqual(sidebar[0]["items"][0]["url"], "")

	def test_normalizes_integer_link_values(self):
		"""Saved View is autoincrement-named, so a link arrives as an int over some paths."""
		sections = [{"name": "s1", "label": "Views", "items": [{"view": 7}]}]

		sidebar = build_sidebar(sections, {"7": {"name": "7", "label": "Seven"}}, (), {})

		self.assertEqual(sidebar[0]["items"][0]["label"], "Seven")


class TestItemLabelAndIcon(UnitTestCase):
	"""A view item may carry its own label and icon as an override; every other type
	carries them as the only source there is."""

	def test_a_view_item_borrows_the_views_label_and_icon(self):
		sidebar = build_sidebar(
			[{"name": "s1", "label": "Views", "items": [{"type": "view", "view": "1"}]}],
			{"1": {"name": "1", "label": "All Open Deals", "icon": "list"}},
			(),
			{},
		)

		item = sidebar[0]["items"][0]
		self.assertEqual((item["label"], item["icon"]), ("All Open Deals", "list"))

	def test_a_view_items_own_label_and_icon_win(self):
		sidebar = build_sidebar(
			[
				{
					"name": "s1",
					"label": "Views",
					"items": [{"type": "view", "view": "1", "label": "Open", "icon": "star"}],
				}
			],
			{"1": {"name": "1", "label": "All Open Deals", "icon": "list"}},
			(),
			{},
		)

		item = sidebar[0]["items"][0]
		self.assertEqual((item["label"], item["icon"]), ("Open", "star"))

	def test_an_empty_label_falls_back_rather_than_blanking_the_row(self):
		sidebar = build_sidebar(
			[{"name": "s1", "label": "Views", "items": [{"type": "view", "view": "1", "label": ""}]}],
			{"1": {"name": "1", "label": "All Open Deals"}},
			(),
			{},
		)

		self.assertEqual(sidebar[0]["items"][0]["label"], "All Open Deals")

	def test_a_link_item_keeps_its_own_label_and_icon(self):
		sidebar = build_sidebar(
			[
				{
					"name": "s1",
					"label": "More",
					"items": [
						{
							"name": "row1",
							"type": "link",
							"label": "Settings",
							"icon": "settings",
							"url": "#settings/general",
						}
					],
				}
			],
			{},
			(),
			{},
		)

		self.assertEqual(
			sidebar[0]["items"],
			[
				{
					"name": "row1",
					"type": "link",
					"label": "Settings",
					"icon": "settings",
					"dt": "",
					"url": "#settings/general",
					"new_tab": 0,
					"hidden": 0,
					"own": 0,
					"view": None,
				}
			],
		)

	def test_a_link_item_survives_an_empty_view_map(self):
		"""It points at no view, so nothing about it is looked up — the row that would
		have been dropped for a missing view stays."""
		sections = [{"name": "s1", "label": "More", "items": [{"type": "link", "url": "/help"}]}]

		self.assertEqual(len(build_sidebar(sections, {}, (), {})[0]["items"]), 1)


class TestDoctypeItems(UnitTestCase):
	"""A doctype item stores what it points at; its route and whether it is shown at
	all are settled here, out of the row."""

	def sidebar(self, row, readable=("Note",)):
		return build_sidebar([{"name": "s1", "label": "Apps", "items": [row]}], {}, readable, {})

	def test_the_route_is_resolved_from_the_doctype(self):
		items = self.sidebar({"type": "doctype", "label": "Notes", "dt": "Note"})[0]["items"]

		self.assertEqual(items[0]["url"], "/Note")

	def test_a_stored_url_does_not_win_over_the_resolved_route(self):
		"""Nothing writes one, but a row carrying both must not route by the stale half."""
		row = {"type": "doctype", "label": "Notes", "dt": "Note", "url": "/old"}

		self.assertEqual(self.sidebar(row)[0]["items"][0]["url"], "/Note")

	def test_the_doctype_rides_along_so_a_client_can_mark_the_active_one(self):
		items = self.sidebar({"type": "doctype", "label": "Notes", "dt": "Note"})[0]["items"]

		self.assertEqual(items[0]["dt"], "Note")

	def test_a_doctype_the_user_cannot_read_is_dropped(self):
		row = {"type": "doctype", "label": "Salaries", "dt": "Salary Slip"}

		self.assertEqual(self.sidebar(row)[0]["items"], [])

	def test_a_doctype_item_carries_no_view(self):
		items = self.sidebar({"type": "doctype", "label": "Notes", "dt": "Note"})[0]["items"]

		self.assertIsNone(items[0]["view"])

	def test_a_link_item_keeps_no_doctype_it_was_retyped_out_of(self):
		"""The column still holds the `dt` the row carried as a doctype item; reading it
		out would leave a link claiming a list it no longer opens."""
		row = {"type": "link", "label": "Docs", "url": "/docs", "dt": "Note"}

		item = self.sidebar(row)[0]["items"][0]

		self.assertEqual((item["dt"], item["url"]), ("", "/docs"))

	def test_a_link_item_is_never_filtered_by_readability(self):
		"""The server cannot know what is behind a URL, so it judges none of them."""
		row = {"type": "link", "label": "Docs", "url": "/docs"}

		self.assertEqual(len(self.sidebar(row, readable=())[0]["items"]), 1)


class TestAppAddedItems(UnitTestCase):
	"""A type the framework does not ship — CRM's `page` — resolves in the app that
	added it, and reaches here only as a route keyed by row name."""

	def sidebar(self, row, targets):
		sections = [{"name": "s1", "label": "Apps", "items": [row]}]
		return build_sidebar(sections, {}, (), targets)

	def test_the_route_the_app_resolved_is_what_the_item_leads_to(self):
		row = {"name": "row1", "type": "page", "label": "Reports"}

		items = self.sidebar(row, {"row1": "/reports"})[0]["items"]

		self.assertEqual(items[0]["url"], "/reports")

	def test_a_row_no_app_answered_for_is_dropped(self):
		"""Unreachable is the app's to decide, and it says so by staying silent — an
		unpublished page is left out rather than drawn and then refused on click."""
		row = {"name": "row1", "type": "page", "label": "Drafts"}

		self.assertEqual(self.sidebar(row, {})[0]["items"], [])

	def test_a_stored_url_does_not_stand_in_for_a_missing_target(self):
		row = {"name": "row1", "type": "page", "label": "Drafts", "url": "/stale"}

		self.assertEqual(self.sidebar(row, {})[0]["items"], [])

	def test_an_app_item_carries_its_own_label_and_icon(self):
		row = {"name": "row1", "type": "page", "label": "Reports", "icon": "chart"}

		item = self.sidebar(row, {"row1": "/reports"})[0]["items"][0]

		self.assertEqual((item["label"], item["icon"], item["view"]), ("Reports", "chart", None))

	def test_the_framework_types_ignore_the_targets_they_are_given(self):
		row = {"name": "row1", "type": "link", "label": "Docs", "url": "/docs"}

		self.assertEqual(self.sidebar(row, {"row1": "/reports"})[0]["items"][0]["url"], "/docs")
