# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype.navigation_section.api import (
	add_item,
	arrange_items,
	arrange_sections,
	create_section,
	get_item,
	hide_section,
	move_item_to_section,
	move_view_to_section,
	remove_item,
	update_item,
)
from frappe.desk.doctype.navigation_section.navigation_section import get_sidebar
from frappe.desk.doctype.navigation_section.scope import DEFAULT_APP
from frappe.desk.doctype.navigation_section.test_navigation_section import clear_app
from frappe.desk.doctype.saved_view.api import create_view
from frappe.desk.doctype.saved_view.test_api import labels, make_user
from frappe.tests import IntegrationTestCase


def make_view(label, user=None):
	return frappe.get_doc(
		{
			"doctype": "Saved View",
			"label": label,
			"reference_doctype": "Note",
			"type": "list",
			"user": user,
		}
	).insert(ignore_permissions=True)


def make_section(label, views, user=None, sequence=0, app=DEFAULT_APP):
	return frappe.get_doc(
		{
			"doctype": "Navigation Section",
			"label": label,
			"app": app,
			"reference_doctype": "Note",
			"user": user,
			"sequence": sequence,
			"items": [{"type": "view", "view": view.name} for view in views],
		}
	).insert(ignore_permissions=True)


def make_overlay(section, user):
	return frappe.get_doc(
		{
			"doctype": "Navigation Section",
			"label": section.label,
			"app": section.app,
			"reference_doctype": section.reference_doctype,
			"user": user,
			"overrides": section.name,
		}
	).insert(ignore_permissions=True)


def shared_item(section, item):
	"""A row the manager puts on a shared section for everybody. An add without
	`for_everyone` is the caller's own, and lands on their overlay."""
	return add_item(section.name, item, for_everyone=True)


def link(label, url="/docs"):
	return {"type": "link", "label": label, "url": url}


def item_labels(section):
	section.reload()
	return [row.label for row in section.items]


def rows(section, *views, hidden=()):
	"""An arrangement names the section's own child rows, since that is the identity an
	item without a view has — so the views asked for are translated to the rows holding
	them."""
	section.reload()
	row_of = {str(row.view): row.name for row in section.items}
	return [{"name": row_of[str(view.name)], "hidden": 1 if view.label in hidden else 0} for view in views]


def placed(section):
	"""A Saved View link reads back as a string, so compare against `names`."""
	section.reload()
	return [str(row.view) for row in section.items]


def names(*views):
	return [str(view.name) for view in views]


def icons_seen_by(user, section="Views"):
	frappe.set_user(user)
	return [row["icon"] for row in get_section(section)]


def labels_seen_by(user, section="Views"):
	"""The row labels one user reads off the sidebar — the shared row's, or their own
	overlay's where they have named one."""
	frappe.set_user(user)
	return [row["label"] for row in get_section(section)]


def section_names(reference_doctype="Note", app=DEFAULT_APP):
	return [section["label"] for section in get_sidebar(reference_doctype, app=app)["sections"]]


class TestArrangeItems(IntegrationTestCase):
	def setUp(self):
		self.member = make_user("saved-view-member@example.com", ["Desk User"])
		self.manager = make_user("saved-view-manager@example.com", ["Desk User", "System Manager"])
		self.first, self.second = make_view("First"), make_view("Second")
		self.shared = make_section("Views", [self.first, self.second])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_member_rearranging_a_shared_section_writes_an_overlay(self):
		frappe.set_user(self.member)

		arrange_items(self.shared.name, rows(self.shared, self.second, self.first))

		self.assertEqual(labels()["Views"], ["Second", "First"])
		self.assertEqual(placed(self.shared), names(self.first, self.second))

	def test_a_members_overlay_leaves_everyone_else_alone(self):
		frappe.set_user(self.member)
		arrange_items(self.shared.name, rows(self.shared, self.second, self.first))

		frappe.set_user("Administrator")

		self.assertEqual(labels()["Views"], ["First", "Second"])

	def test_a_member_can_hide_a_shared_view_for_themselves(self):
		frappe.set_user(self.member)

		arrange_items(self.shared.name, rows(self.shared, self.first, self.second, hidden=("Second",)))

		hidden = {view["label"]: view["hidden"] for view in get_section("Views")}
		self.assertEqual(hidden, {"First": 0, "Second": 1})

	def test_a_hidden_shared_view_stays_visible_for_everyone_else(self):
		frappe.set_user(self.member)
		arrange_items(self.shared.name, rows(self.shared, self.first, self.second, hidden=("Second",)))

		frappe.set_user("Administrator")

		self.assertEqual([view["hidden"] for view in get_section("Views")], [0, 0])

	def test_a_manager_hiding_a_shared_view_writes_their_overlay(self):
		"""Hiding is a statement about one's own sidebar, so the sidebar never offers a
		manager "for everyone" here — they remove the view from the section instead."""
		frappe.set_user(self.manager)

		arrange_items(self.shared.name, rows(self.shared, self.first, self.second, hidden=("Second",)))

		self.assertEqual([view["hidden"] for view in get_section("Views")], [0, 1])
		self.shared.reload()
		self.assertEqual([row.hidden for row in self.shared.items], [0, 0])

	def test_a_manager_saving_for_everyone_writes_the_shared_section(self):
		frappe.set_user(self.manager)

		arrange_items(self.shared.name, rows(self.shared, self.second, self.first), for_everyone=True)

		self.assertEqual(placed(self.shared), names(self.second, self.first))

	def test_a_member_cannot_save_a_shared_section_for_everyone(self):
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			arrange_items(self.shared.name, rows(self.shared, self.second, self.first), for_everyone=True)

	def test_saving_for_everyone_clears_the_managers_own_overlay(self):
		"""Otherwise the manager is the one user who cannot see what they published."""
		frappe.set_user(self.manager)
		arrange_items(self.shared.name, rows(self.shared, self.second, self.first))

		arrange_items(self.shared.name, rows(self.shared, self.first, self.second), for_everyone=True)

		self.assertEqual(labels()["Views"], ["First", "Second"])

	def test_a_user_rearranges_their_own_section_in_place(self):
		frappe.set_user(self.member)
		mine, also_mine = make_view("Mine", self.member), make_view("Also", self.member)
		personal = make_section("Personal", [mine, also_mine], user=self.member)

		arrange_items(personal.name, rows(personal, also_mine, mine))

		self.assertEqual(labels()["Personal"], ["Also", "Mine"])

	def test_a_user_cannot_rearrange_someone_elses_section(self):
		personal = make_section("Personal", [], user=self.member)
		frappe.set_user(self.manager)

		with self.assertRaises(frappe.PermissionError):
			arrange_items(personal.name, [])

	def test_a_row_list_that_lost_a_view_is_rejected(self):
		frappe.set_user(self.member)

		with self.assertRaises(frappe.ValidationError):
			arrange_items(self.shared.name, rows(self.shared, self.first))

	def test_a_row_list_that_gained_a_row_is_rejected(self):
		frappe.set_user(self.member)
		stray = [{"name": "not-a-row-of-this-section", "hidden": 0}]

		with self.assertRaises(frappe.ValidationError):
			arrange_items(self.shared.name, rows(self.shared, self.first, self.second) + stray)


class TestMoveViewToSection(IntegrationTestCase):
	def setUp(self):
		self.member = make_user("saved-view-member@example.com", ["Desk User"])
		self.manager = make_user("saved-view-manager@example.com", ["Desk User", "System Manager"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_moving_a_personal_view_into_a_shared_section_shares_it(self):
		frappe.set_user(self.manager)
		view = frappe.get_doc("Saved View", create_view("Note", "Mine"))
		shared = make_section("Views", [])

		move_view_to_section(view.name, shared.name)

		self.assertEqual(frappe.db.get_value("Saved View", view.name, "user"), "")
		self.assertEqual(labels()["Views"], ["Mine"])

	def test_moving_a_shared_view_into_a_personal_section_makes_it_private(self):
		frappe.set_user(self.manager)
		shared_view = make_view("Ours")
		make_section("Views", [shared_view])
		mine = make_section("Personal", [], user=self.manager)

		move_view_to_section(shared_view.name, mine.name)

		self.assertEqual(frappe.db.get_value("Saved View", shared_view.name, "user"), self.manager)

	def test_a_member_cannot_move_their_view_into_the_shared_area(self):
		shared = make_section("Views", [])
		frappe.set_user(self.member)
		view = frappe.get_doc("Saved View", create_view("Note", "Mine"))

		with self.assertRaises(frappe.PermissionError):
			move_view_to_section(view.name, shared.name)

	def test_a_member_cannot_claim_a_shared_view(self):
		shared_view = make_view("Ours")
		make_section("Views", [shared_view])
		frappe.set_user(self.member)
		mine = make_section("Personal", [], user=self.member)

		with self.assertRaises(frappe.PermissionError):
			move_view_to_section(shared_view.name, mine.name)

	def test_a_view_lands_at_the_index_it_was_dropped_on(self):
		frappe.set_user(self.manager)
		first, second = make_view("First"), make_view("Second")
		shared = make_section("Views", [first, second])
		moved = make_view("Moved", self.manager)
		make_section("Personal", [moved], user=self.manager)

		move_view_to_section(moved.name, shared.name, index=1)

		self.assertEqual(labels()["Views"], ["First", "Moved", "Second"])

	def test_a_view_with_no_index_lands_at_the_end(self):
		frappe.set_user(self.manager)
		first = make_view("First")
		shared = make_section("Views", [first])
		moved = make_view("Moved", self.manager)
		make_section("Personal", [moved], user=self.manager)

		move_view_to_section(moved.name, shared.name)

		self.assertEqual(labels()["Views"], ["First", "Moved"])

	def test_a_view_leaves_the_section_it_came_from(self):
		frappe.set_user(self.manager)
		view = make_view("Wanderer")
		origin = make_section("Views", [view])
		destination = make_section("Pipeline", [])

		move_view_to_section(view.name, destination.name)

		origin.reload()
		self.assertEqual(origin.items, [])

	def test_a_view_cannot_be_dropped_into_an_overlay(self):
		shared = make_section("Views", [])
		overlay = frappe.get_doc(
			{
				"doctype": "Navigation Section",
				"label": "Views",
				"app": DEFAULT_APP,
				"reference_doctype": "Note",
				"user": self.manager,
				"overrides": shared.name,
			}
		).insert(ignore_permissions=True)
		frappe.set_user(self.manager)
		view = make_view("Mine", self.manager)

		with self.assertRaises(frappe.ValidationError):
			move_view_to_section(view.name, overlay.name)


class TestItems(IntegrationTestCase):
	"""Adding and dropping the rows themselves. Arranging is the sibling operation and
	deliberately cannot do either — see `validate_same_membership`."""

	def setUp(self):
		self.member = make_user("saved-view-member@example.com", ["Desk User"])
		self.manager = make_user("saved-view-manager@example.com", ["Desk User", "System Manager"])
		self.shared = make_section("Views", [])
		self.mine = make_section("Mine", [], user=self.member)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_an_item_lands_at_the_end_of_the_section(self):
		frappe.set_user(self.member)
		add_item(self.mine.name, link("Docs"))

		add_item(self.mine.name, link("Help"))

		self.assertEqual(item_labels(self.mine), ["Docs", "Help"])

	def test_the_new_rows_name_comes_back(self):
		"""It is what the editor scrolls to and focuses, and what an overlay points at."""
		frappe.set_user(self.member)

		name = add_item(self.mine.name, link("Docs"))

		self.mine.reload()
		self.assertEqual(name, self.mine.items[0].name)

	def test_a_manager_adding_for_everyone_writes_the_shared_section(self):
		frappe.set_user(self.manager)

		add_item(self.shared.name, link("Docs"), for_everyone=True)

		self.assertEqual(item_labels(self.shared), ["Docs"])

	def test_an_add_to_a_shared_section_is_the_callers_own_by_default(self):
		"""Even a manager's: adding something to everybody's sidebar is the deliberate
		act, so the flag is what asks for it and the plain call is one's own item."""
		frappe.set_user(self.manager)

		add_item(self.shared.name, link("Docs"))

		self.assertEqual(item_labels(self.shared), [])
		self.assertEqual(labels_seen_by(self.manager), ["Docs"])

	def test_a_member_adding_to_a_shared_section_writes_their_own_overlay(self):
		"""Their item, in everybody's section — which is what lets it sit among the
		shared rows rather than in a section of their own below them."""
		frappe.set_user(self.member)

		add_item(self.shared.name, link("Docs"))

		self.assertEqual(item_labels(self.shared), [])
		self.assertEqual(labels_seen_by(self.member), ["Docs"])
		self.assertEqual(labels_seen_by(self.manager), [])

	def test_a_member_cannot_add_to_a_shared_section_for_everyone(self):
		"""The toggle that offers this is hidden from them; the rule is here."""
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			add_item(self.shared.name, link("Docs"), for_everyone=True)

	def test_a_member_cannot_add_to_someone_elses_section(self):
		theirs = make_section("Theirs", [], user=self.manager)
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			add_item(theirs.name, link("Docs"))

	def test_an_overlay_cannot_be_named_as_the_section(self):
		"""It holds the caller's own items, but they are put there through the section it
		deltas — nothing outside this module knows the overlay exists."""
		overlay = make_overlay(self.shared, self.member)
		frappe.set_user(self.member)

		with self.assertRaises(frappe.ValidationError):
			add_item(overlay.name, link("Docs"))

	def test_a_link_item_still_needs_a_url(self):
		frappe.set_user(self.member)

		with self.assertRaises(frappe.MandatoryError):
			add_item(self.mine.name, {"type": "link", "label": "Docs"})

	def test_a_view_row_cannot_be_added_this_way(self):
		"""Placement resolves a view the caller may read and unplaces it from wherever it
		sat; writing the link straight into a row would go around both."""
		view = make_view("Theirs")
		frappe.set_user(self.member)

		with self.assertRaises(frappe.ValidationError):
			add_item(self.mine.name, {"type": "view", "view": view.name})

	def test_an_item_with_no_type_is_refused_rather_than_defaulting_to_a_view(self):
		frappe.set_user(self.member)

		with self.assertRaises(frappe.ValidationError):
			add_item(self.mine.name, {"label": "Docs", "url": "/docs"})

	def test_a_view_link_smuggled_onto_a_link_row_is_dropped(self):
		view = make_view("Theirs")
		frappe.set_user(self.member)

		name = add_item(self.mine.name, {**link("Docs"), "view": view.name})

		self.assertFalse(frappe.db.get_value("Navigation Item", name, "view"))

	def test_a_structural_field_in_the_payload_is_ignored(self):
		"""Position and identity are the section's to assign, not the caller's."""
		frappe.set_user(self.member)

		name = add_item(self.mine.name, {**link("Docs"), "hidden": 1, "idx": 9})

		self.assertEqual(frappe.db.get_value("Navigation Item", name, ["hidden", "idx"]), (0, 1))

	def test_removing_an_item_leaves_the_rest_of_the_section(self):
		frappe.set_user(self.member)
		first = add_item(self.mine.name, link("Docs"))
		add_item(self.mine.name, link("Help"))

		remove_item(self.mine.name, first)

		self.assertEqual(item_labels(self.mine), ["Help"])

	def test_a_member_cannot_remove_a_shared_row(self):
		"""Hiding is what they have instead — their own sidebar, not everybody's."""
		frappe.set_user(self.manager)
		row = shared_item(self.shared, link("Docs"))
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			remove_item(self.shared.name, row)


class TestUpdateItem(IntegrationTestCase):
	"""Renaming a row and changing its icon — the two things about an item that are
	content rather than placement."""

	def setUp(self):
		self.member = make_user("saved-view-member@example.com", ["Desk User"])
		self.manager = make_user("saved-view-manager@example.com", ["Desk User", "System Manager"])
		self.shared = make_section("Views", [])
		self.mine = make_section("Mine", [], user=self.member)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_row_takes_the_new_label_and_icon(self):
		frappe.set_user(self.member)
		row = add_item(self.mine.name, link("Docs"))

		update_item(self.mine.name, row, "Handbook", "book")

		self.assertEqual(frappe.db.get_value("Navigation Item", row, ["label", "icon"]), ("Handbook", "book"))

	def test_an_icon_can_be_cleared(self):
		frappe.set_user(self.member)
		row = add_item(self.mine.name, {**link("Docs"), "icon": "book"})

		update_item(self.mine.name, row, "Docs")

		self.assertFalse(frappe.db.get_value("Navigation Item", row, "icon"))

	def test_a_manager_renaming_for_everyone_rewrites_the_shared_row(self):
		frappe.set_user(self.manager)
		row = shared_item(self.shared, link("Docs"))

		update_item(self.shared.name, row, "Handbook", for_everyone=True)

		self.assertEqual(item_labels(self.shared), ["Handbook"])

	def test_a_member_renaming_a_shared_row_writes_their_own_overlay(self):
		"""Their own name for it. The shared row is untouched, so everybody else keeps
		the manager's."""
		frappe.set_user(self.manager)
		row = shared_item(self.shared, link("Docs"))
		frappe.set_user(self.member)

		update_item(self.shared.name, row, "Handbook")

		self.assertEqual(item_labels(self.shared), ["Docs"])
		self.assertEqual(labels_seen_by(self.member), ["Handbook"])

	def test_a_member_cannot_rename_a_shared_row_for_everyone(self):
		"""The toggle that offers this is hidden from them; the rule is here."""
		frappe.set_user(self.manager)
		row = shared_item(self.shared, link("Docs"))
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			update_item(self.shared.name, row, "Handbook", for_everyone=True)

	def test_a_personal_rename_leaves_the_order_alone(self):
		"""Naming something is not moving it. An overlay row is a *mention*, and mentioned
		rows sort before unmentioned ones — so a lone delta would send it to the top."""
		frappe.set_user(self.manager)
		shared_item(self.shared, link("Docs"))
		middle = shared_item(self.shared, link("Help"))
		shared_item(self.shared, link("About"))
		frappe.set_user(self.member)

		update_item(self.shared.name, middle, "Support")

		self.assertEqual(labels_seen_by(self.member), ["Docs", "Support", "About"])

	def test_a_personal_rename_keeps_an_order_the_member_had_already_set(self):
		frappe.set_user(self.manager)
		first = shared_item(self.shared, link("Docs"))
		second = shared_item(self.shared, link("Help"))
		frappe.set_user(self.member)
		arrange_items(self.shared.name, [{"name": second}, {"name": first}])

		update_item(self.shared.name, first, "Handbook")

		self.assertEqual(labels_seen_by(self.member), ["Help", "Handbook"])

	def test_a_personal_rename_keeps_what_the_member_had_hidden(self):
		frappe.set_user(self.manager)
		first = shared_item(self.shared, link("Docs"))
		second = shared_item(self.shared, link("Help"))
		frappe.set_user(self.member)
		arrange_items(self.shared.name, [{"name": first}, {"name": second, "hidden": 1}])

		update_item(self.shared.name, first, "Handbook")

		hidden = {row["label"]: row["hidden"] for row in get_section("Views")}
		self.assertEqual(hidden, {"Handbook": 0, "Help": 1})

	def test_a_second_personal_rename_keeps_the_first(self):
		frappe.set_user(self.manager)
		first = shared_item(self.shared, link("Docs"))
		second = shared_item(self.shared, link("Help"))
		frappe.set_user(self.member)
		update_item(self.shared.name, first, "Handbook")

		update_item(self.shared.name, second, "Support")

		self.assertEqual(labels_seen_by(self.member), ["Handbook", "Support"])

	def test_a_personal_rename_does_not_pin_the_icon(self):
		"""The editor sends the pair, so a rename would otherwise store the icon it read
		back — freezing the row against every icon the manager sets afterwards."""
		frappe.set_user(self.manager)
		row = shared_item(self.shared, {**link("Docs"), "icon": "book"})
		frappe.set_user(self.member)
		update_item(self.shared.name, row, "Handbook", "book")

		frappe.set_user(self.manager)
		update_item(self.shared.name, row, "Docs", "star", for_everyone=True)

		self.assertEqual(icons_seen_by(self.member), ["star"])

	def test_naming_a_row_what_it_is_already_called_stores_no_override(self):
		"""A delta that matches is not a delta — and a user who types the shared name back
		should start following the manager again."""
		frappe.set_user(self.manager)
		row = shared_item(self.shared, link("Docs"))
		frappe.set_user(self.member)
		update_item(self.shared.name, row, "Handbook")

		update_item(self.shared.name, row, "Docs")

		frappe.set_user(self.manager)
		update_item(self.shared.name, row, "Renamed", for_everyone=True)
		self.assertEqual(labels_seen_by(self.member), ["Renamed"])

	def test_a_personal_rename_leaves_every_other_user_alone(self):
		frappe.set_user(self.manager)
		row = shared_item(self.shared, link("Docs"))
		frappe.set_user(self.member)
		update_item(self.shared.name, row, "Handbook")

		self.assertEqual(labels_seen_by(self.manager), ["Docs"])

	def test_a_personal_rename_survives_a_drag(self):
		"""A drag rebuilds the overlay wholesale, and would otherwise undo the rename."""
		frappe.set_user(self.manager)
		first = shared_item(self.shared, link("Docs"))
		shared_item(self.shared, link("Help"))
		frappe.set_user(self.member)
		update_item(self.shared.name, first, "Handbook")

		self.shared.reload()
		arrange_items(self.shared.name, [{"name": row.name} for row in reversed(self.shared.items)])

		self.assertEqual(labels_seen_by(self.member), ["Help", "Handbook"])

	def test_a_later_manager_rename_reaches_a_member_who_only_dragged(self):
		frappe.set_user(self.manager)
		row = shared_item(self.shared, link("Docs"))
		frappe.set_user(self.member)
		arrange_items(self.shared.name, [{"name": row}])
		frappe.set_user(self.manager)

		update_item(self.shared.name, row, "Handbook", for_everyone=True)

		self.assertEqual(labels_seen_by(self.member), ["Handbook"])

	def test_publishing_a_name_clears_the_managers_own_override(self):
		"""They would otherwise be the one user still seeing their private name."""
		frappe.set_user(self.manager)
		row = shared_item(self.shared, link("Docs"))
		update_item(self.shared.name, row, "Mine")

		update_item(self.shared.name, row, "Handbook", for_everyone=True)

		self.assertEqual(labels_seen_by(self.manager), ["Handbook"])

	def test_a_view_row_is_refused(self):
		"""A view's name is the view's own, and the ⋯ menu is where it is changed."""
		view = make_view("Open", user=self.member)
		section = make_section("Views", [view], user=self.member)
		section.reload()
		frappe.set_user(self.member)

		with self.assertRaises(frappe.ValidationError):
			update_item(section.name, section.items[0].name, "Open deals")

	def test_a_row_with_no_type_is_refused_as_the_view_it_reads_as(self):
		"""`type` is defaulted, not required, so a row can carry nothing at all — and
		everything else in the model takes a blank one for a view."""
		frappe.set_user(self.member)
		row = add_item(self.mine.name, link("Docs"))
		frappe.db.set_value("Navigation Item", row, "type", "", update_modified=False)

		with self.assertRaises(frappe.ValidationError):
			update_item(self.mine.name, row, "Handbook")

	def test_an_overlays_row_is_refused(self):
		"""An overlay holds one user's deltas of shared rows; a label written on one is
		a label nothing ever projects."""
		frappe.set_user(self.manager)
		shared_row = shared_item(self.shared, link("Docs"))
		overlay = make_overlay(self.shared, self.member)
		overlay.append("items", {"overrides": shared_row})
		overlay.save(ignore_permissions=True)
		frappe.set_user(self.member)

		with self.assertRaises(frappe.ValidationError):
			update_item(overlay.name, overlay.items[0].name, "Handbook")

	def test_a_blank_label_is_refused(self):
		frappe.set_user(self.member)
		row = add_item(self.mine.name, link("Docs"))

		with self.assertRaises(frappe.ValidationError):
			update_item(self.mine.name, row, "  ")

	def test_a_row_of_another_section_is_refused(self):
		frappe.set_user(self.member)
		other = make_section("Other", [], user=self.member)
		row = add_item(other.name, link("Docs"))

		with self.assertRaises(frappe.ValidationError):
			update_item(self.mine.name, row, "Handbook")

	def test_a_row_in_the_callers_own_section_takes_a_new_target(self):
		"""What the edit form is for: a link typed wrong is fixable rather than only
		removable and typed again."""
		frappe.set_user(self.member)
		row = add_item(self.mine.name, link("Docs"))

		update_item(self.mine.name, row, "Docs", values={"url": "/handbook"})

		self.assertEqual(frappe.db.get_value("Navigation Item", row, "url"), "/handbook")

	def test_a_manager_repoints_a_shared_row_for_everyone(self):
		frappe.set_user(self.manager)
		row = shared_item(self.shared, link("Docs"))

		update_item(self.shared.name, row, "Docs", for_everyone=True, values={"url": "/handbook"})

		self.assertEqual(frappe.db.get_value("Navigation Item", row, "url"), "/handbook")

	def test_a_shared_row_cannot_be_repointed_for_one_user_alone(self):
		"""Where a row leads has no personal form: a delta redirecting it would leave two
		users clicking the same entry and arriving somewhere different."""
		frappe.set_user(self.manager)
		row = shared_item(self.shared, link("Docs"))

		with self.assertRaises(frappe.PermissionError):
			update_item(self.shared.name, row, "Docs", values={"url": "/handbook"})

	def test_a_refused_target_takes_the_rename_down_with_it(self):
		"""One call, one outcome — the form asked for both, so a half-applied edit would
		leave the user reading a new name over the old destination."""
		frappe.set_user(self.manager)
		row = shared_item(self.shared, link("Docs"))

		with self.assertRaises(frappe.PermissionError):
			update_item(self.shared.name, row, "Handbook", values={"url": "/handbook"})

		self.assertEqual(labels_seen_by(self.manager), ["Docs"])

	def test_a_row_cannot_be_retyped_through_its_target(self):
		"""Retyping would leave the old target sitting in a field nothing reads. Adding is
		where a row's type is chosen."""
		frappe.set_user(self.member)
		row = add_item(self.mine.name, link("Docs"))

		update_item(self.mine.name, row, "Docs", values={"type": "doctype", "dt": "Note"})

		self.assertEqual(frappe.db.get_value("Navigation Item", row, "type"), "link")


class TestGetItem(IntegrationTestCase):
	"""What an edit form fills itself from. The sidebar carries the route a row
	*resolved* to, which for a doctype or an app-added type is not what was chosen."""

	def setUp(self):
		self.member = make_user("saved-view-member@example.com", ["Desk User"])
		self.manager = make_user("saved-view-manager@example.com", ["Desk User", "System Manager"])
		self.shared = make_section("Views", [])
		self.mine = make_section("Mine", [], user=self.member)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_rows_stored_target_comes_back(self):
		frappe.set_user(self.member)
		row = add_item(self.mine.name, {**link("Docs", "/handbook"), "icon": "book"})

		stored = get_item(self.mine.name, row)

		self.assertEqual((stored["url"], stored["label"], stored["icon"]), ("/handbook", "Docs", "book"))

	def test_an_own_item_is_read_off_the_overlay_that_holds_it(self):
		"""The client names the section it drew the row under; which record stores it is
		this module's business."""
		frappe.set_user(self.member)
		mine = add_item(self.shared.name, link("Mine", "/mine"))

		self.assertEqual(get_item(self.shared.name, mine)["url"], "/mine")

	def test_a_row_of_another_section_is_refused(self):
		frappe.set_user(self.member)
		other = make_section("Other", [], user=self.member)
		row = add_item(other.name, link("Docs"))

		with self.assertRaises(frappe.ValidationError):
			get_item(self.mine.name, row)


class TestOwnItems(IntegrationTestCase):
	"""An item of the caller's own inside a shared section, carried on their overlay."""

	def setUp(self):
		self.member = make_user("saved-view-member@example.com", ["Desk User"])
		self.manager = make_user("saved-view-manager@example.com", ["Desk User", "System Manager"])
		self.shared = make_section("Views", [])
		self.mine = make_section("Mine", [], user=self.member)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_an_own_item_lands_under_the_shared_rows_rather_than_over_them(self):
		"""An overlay row is a *mention*, and mentioned rows sort above unmentioned ones —
		so a lone row would send the whole shared section to the bottom."""
		frappe.set_user(self.manager)
		shared_item(self.shared, link("Docs"))
		shared_item(self.shared, link("Help"))
		frappe.set_user(self.member)

		add_item(self.shared.name, link("Mine"))

		self.assertEqual(labels_seen_by(self.member), ["Docs", "Help", "Mine"])

	def test_an_own_item_is_arranged_among_the_shared_rows(self):
		frappe.set_user(self.manager)
		first = shared_item(self.shared, link("Docs"))
		frappe.set_user(self.member)
		mine = add_item(self.shared.name, link("Mine"))

		arrange_items(self.shared.name, [{"name": mine}, {"name": first}])

		self.assertEqual(labels_seen_by(self.member), ["Mine", "Docs"])

	def test_an_own_item_survives_the_drag_that_moves_it(self):
		"""A drag rebuilds the deltas wholesale; the caller's own rows are moved instead,
		since rebuilding one would throw away the item."""
		frappe.set_user(self.manager)
		first = shared_item(self.shared, link("Docs"))
		frappe.set_user(self.member)
		mine = add_item(self.shared.name, {**link("Mine", "/mine"), "icon": "star"})

		arrange_items(self.shared.name, [{"name": mine}, {"name": first}])

		row = get_section("Views")[0]
		self.assertEqual(
			(row["name"], row["label"], row["url"], row["icon"]), (mine, "Mine", "/mine", "star")
		)

	def test_an_own_item_can_be_hidden_like_any_other_row(self):
		frappe.set_user(self.member)
		mine = add_item(self.shared.name, link("Mine"))

		arrange_items(self.shared.name, [{"name": mine, "hidden": 1}])

		self.assertEqual([row["hidden"] for row in get_section("Views")], [1])

	def test_an_own_item_is_nobody_elses(self):
		frappe.set_user(self.member)
		add_item(self.shared.name, link("Mine"))

		self.assertEqual(item_labels(self.shared), [])
		self.assertEqual(labels_seen_by(self.manager), [])

	def test_a_member_renames_their_own_item_outright(self):
		"""Not as an override — the name is the item's, and there is nobody else's to
		delta."""
		frappe.set_user(self.member)
		mine = add_item(self.shared.name, link("Mine"))

		update_item(self.shared.name, mine, "Handbook")

		self.assertEqual(labels_seen_by(self.member), ["Handbook"])

	def test_a_member_removes_their_own_item_from_a_shared_section(self):
		"""Removing a shared row takes it off everybody's sidebar and stays a manager's;
		this row is theirs, so it is theirs to drop."""
		frappe.set_user(self.member)
		mine = add_item(self.shared.name, link("Mine"))

		remove_item(self.shared.name, mine)

		self.assertEqual(labels_seen_by(self.member), [])

	def test_a_member_repoints_their_own_item_without_the_shared_scope(self):
		"""Nobody else can see it, so where it leads is nobody else's business — the rule
		that refuses a personal target on a *shared* row says nothing about this one."""
		frappe.set_user(self.member)
		mine = add_item(self.shared.name, link("Mine"))

		update_item(self.shared.name, mine, "Mine", values={"url": "/mine"})

		self.assertEqual(frappe.db.get_value("Navigation Item", mine, "url"), "/mine")

	def test_an_own_item_reaches_the_client_marked_as_the_members_own(self):
		"""What the editor gates its remove on: without the flag, a row inside a shared
		section reads as the section's, and the user cannot take back what they added."""
		frappe.set_user(self.manager)
		shared_item(self.shared, link("Docs"))
		frappe.set_user(self.member)
		add_item(self.shared.name, link("Mine"))

		self.assertEqual(
			[(row["label"], row["own"]) for row in get_section("Views")], [("Docs", 0), ("Mine", 1)]
		)

	def test_a_row_the_manager_adds_later_still_reaches_a_member_who_has_their_own(self):
		frappe.set_user(self.member)
		add_item(self.shared.name, link("Mine"))
		frappe.set_user(self.manager)

		shared_item(self.shared, link("Docs"))

		self.assertEqual(labels_seen_by(self.member), ["Mine", "Docs"])

	def test_publishing_an_order_leaves_the_managers_own_item_where_it_was(self):
		"""The published order says nothing about a row that is not the section's, and
		dropping the overlay wholesale would sweep it to the top."""
		frappe.set_user(self.manager)
		first = shared_item(self.shared, link("Docs"))
		second = shared_item(self.shared, link("Help"))
		mine = add_item(self.shared.name, link("Mine"))

		arrange_items(
			self.shared.name, [{"name": second}, {"name": mine}, {"name": first}], for_everyone=True
		)

		self.assertEqual(item_labels(self.shared), ["Help", "Docs"])
		self.assertEqual(labels_seen_by(self.manager), ["Help", "Mine", "Docs"])

	def test_an_arrangement_that_forgets_an_own_item_is_refused(self):
		"""The caller arranges what they see, and what they see includes their own."""
		frappe.set_user(self.manager)
		first = shared_item(self.shared, link("Docs"))
		frappe.set_user(self.member)
		add_item(self.shared.name, link("Mine"))

		with self.assertRaises(frappe.ValidationError):
			arrange_items(self.shared.name, [{"name": first}])


class TestMoveItemToSection(IntegrationTestCase):
	"""Dragging a row that holds no view from one section to another. A view moves by
	its placement instead — see `move_view_to_section`."""

	def setUp(self):
		self.member = make_user("saved-view-member@example.com", ["Desk User"])
		self.manager = make_user("saved-view-manager@example.com", ["Desk User", "System Manager"])
		self.shared = make_section("Views", [])
		self.mine = make_section("Mine", [], user=self.member)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_an_item_moves_into_a_shared_section_as_the_callers_own(self):
		frappe.set_user(self.manager)
		shared_item(self.shared, link("Docs"))
		frappe.set_user(self.member)
		row = add_item(self.mine.name, link("Mine"))

		move_item_to_section(self.mine.name, row, self.shared.name, 0)

		self.assertEqual(labels_seen_by(self.member), ["Mine", "Docs"])
		self.assertEqual(item_labels(self.shared), ["Docs"])

	def test_the_moved_row_leaves_the_section_it_came_from(self):
		frappe.set_user(self.member)
		row = add_item(self.mine.name, link("Mine"))
		add_item(self.mine.name, link("Other"))

		move_item_to_section(self.mine.name, row, self.shared.name)

		self.assertEqual(item_labels(self.mine), ["Other"])

	def test_the_move_carries_what_the_row_is(self):
		frappe.set_user(self.member)
		row = add_item(self.mine.name, {**link("Mine", "/mine"), "icon": "star"})

		move_item_to_section(self.mine.name, row, self.shared.name)

		moved = get_section("Views")[0]
		self.assertEqual((moved["label"], moved["url"], moved["icon"]), ("Mine", "/mine", "star"))

	def test_a_manager_moving_for_everyone_writes_the_shared_section(self):
		frappe.set_user(self.manager)
		theirs = make_section("Theirs", [], user=self.manager)
		row = add_item(theirs.name, link("Docs"))

		move_item_to_section(theirs.name, row, self.shared.name, for_everyone=True)

		self.assertEqual(item_labels(self.shared), ["Docs"])

	def test_an_own_item_moves_back_out_of_a_shared_section(self):
		frappe.set_user(self.member)
		row = add_item(self.shared.name, link("Mine"))

		move_item_to_section(self.shared.name, row, self.mine.name)

		self.assertEqual(item_labels(self.mine), ["Mine"])
		self.assertEqual(labels_seen_by(self.member), [])

	def test_a_view_row_is_refused(self):
		"""Its row is the placement of a record everybody can reach, so moving it across
		the shared line rewrites the view rather than the row."""
		view = make_view("Open", user=self.member)
		section = make_section("Views", [view], user=self.member)
		section.reload()
		frappe.set_user(self.member)

		with self.assertRaises(frappe.ValidationError):
			move_item_to_section(section.name, section.items[0].name, self.mine.name)

	def test_a_member_cannot_move_an_item_into_a_shared_section_for_everyone(self):
		frappe.set_user(self.member)
		row = add_item(self.mine.name, link("Mine"))

		with self.assertRaises(frappe.PermissionError):
			move_item_to_section(self.mine.name, row, self.shared.name, for_everyone=True)


class TestSections(IntegrationTestCase):
	def setUp(self):
		self.member = make_user("saved-view-member@example.com", ["Desk User"])
		self.manager = make_user("saved-view-manager@example.com", ["Desk User", "System Manager"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_manager_can_create_a_shared_section(self):
		frappe.set_user(self.manager)

		create_section("Pipeline", "Note", shared=True)

		self.assertIn("Pipeline", section_names())

	def test_a_member_cannot_create_a_shared_section(self):
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			create_section("Pipeline", "Note", shared=True)

	def test_a_member_can_create_their_own_section(self):
		frappe.set_user(self.member)

		create_section("Starred", "Note")

		self.assertIn("Starred", section_names())

	def test_a_section_can_be_created_at_the_app_level(self):
		"""Naming no doctype is what the rail's own editor does."""
		frappe.set_user(self.manager)

		create_section("Rail", "", shared=True)

		self.assertEqual(section_names(reference_doctype=""), ["Rail"])

	def test_a_new_section_lands_after_the_existing_ones(self):
		frappe.set_user(self.manager)
		make_section("Views", [], sequence=1)

		create_section("Pipeline", "Note", shared=True)

		self.assertEqual(section_names(), ["Views", "Pipeline"])

	def test_a_new_section_belongs_to_the_app_it_was_created_for(self):
		frappe.set_user(self.manager)

		create_section("Pipeline", "Note", shared=True, app="helpdesk")

		self.assertNotIn("Pipeline", section_names())
		self.assertIn("Pipeline", section_names(app="helpdesk"))

	def test_a_sequence_starts_afresh_in_a_second_app(self):
		"""One sequence orders one sidebar, and another app's is a different sidebar."""
		make_section("Views", [], sequence=1)
		frappe.set_user(self.manager)

		create_section("Theirs", "Note", shared=True, app="helpdesk")

		self.assertEqual(frappe.db.get_value("Navigation Section", {"label": "Theirs"}, "sequence"), 1)

	def test_sections_from_another_app_cannot_be_reordered_together(self):
		ours = make_section("Views", [], sequence=1)
		theirs = make_section("Theirs", [], sequence=2, app="helpdesk")
		frappe.set_user(self.manager)

		with self.assertRaises(frappe.ValidationError):
			arrange_sections([theirs.name, ours.name], "Note", for_everyone=True)

	def test_a_section_with_no_app_cannot_be_reordered(self):
		"""It belongs to no sidebar, so it is nobody's to arrange."""
		ours = make_section("Views", [], sequence=1)
		orphan = make_section("Orphan", [], sequence=2)
		clear_app(orphan)
		frappe.set_user(self.manager)

		with self.assertRaises(frappe.ValidationError):
			arrange_sections([orphan.name, ours.name], "Note", for_everyone=True)

	def test_a_manager_reorders_shared_sections_for_everyone(self):
		first = make_section("Views", [make_view("a")], sequence=1)
		second = make_section("Pipeline", [make_view("b")], sequence=2)
		frappe.set_user(self.manager)

		arrange_sections([second.name, first.name], "Note", for_everyone=True)

		self.assertEqual(section_names(), ["Pipeline", "Views"])
		frappe.set_user(self.member)
		self.assertEqual(section_names(), ["Pipeline", "Views"])

	def test_a_manager_reordering_without_for_everyone_writes_their_overlay(self):
		first = make_section("Views", [make_view("a")], sequence=1)
		second = make_section("Pipeline", [make_view("b")], sequence=2)
		frappe.set_user(self.manager)

		arrange_sections([second.name, first.name], "Note")

		self.assertEqual(section_names(), ["Pipeline", "Views"])
		frappe.set_user(self.member)
		self.assertEqual(section_names(), ["Views", "Pipeline"])

	def test_a_member_reordering_shared_sections_writes_their_overlay(self):
		first = make_section("Views", [make_view("a")], sequence=1)
		second = make_section("Pipeline", [make_view("b")], sequence=2)
		frappe.set_user(self.member)

		arrange_sections([second.name, first.name], "Note")

		self.assertEqual(section_names(), ["Pipeline", "Views"])
		first.reload()
		second.reload()
		self.assertEqual((first.sequence, second.sequence), (1, 2))
		frappe.set_user("Administrator")
		self.assertEqual(section_names(), ["Views", "Pipeline"])

	def test_a_member_cannot_reorder_sections_for_everyone(self):
		first = make_section("Views", [], sequence=1)
		second = make_section("Pipeline", [], sequence=2)
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			arrange_sections([second.name, first.name], "Note", for_everyone=True)

	def test_a_member_moves_their_personal_section_above_shared_ones(self):
		views = make_section("Views", [make_view("a")], sequence=1)
		pipeline = make_section("Pipeline", [make_view("b")], sequence=2)
		mine = make_section("Starred", [], user=self.member, sequence=3)
		frappe.set_user(self.member)

		arrange_sections([mine.name, views.name, pipeline.name], "Note")

		self.assertEqual(section_names(), ["Starred", "Views", "Pipeline"])
		frappe.set_user("Administrator")
		self.assertEqual(section_names(), ["Views", "Pipeline"])

	def test_a_section_never_moved_keeps_following_the_managers_order(self):
		"""Skipping matching positions is what keeps the delta a delta: only the
		sections a user actually displaced get an overlay sequence."""
		views = make_section("Views", [make_view("a")], sequence=1)
		pipeline = make_section("Pipeline", [make_view("b")], sequence=2)
		mine = make_section("Starred", [], user=self.member, sequence=3)
		frappe.set_user(self.member)
		arrange_sections([views.name, pipeline.name, mine.name], "Note")

		frappe.set_user(self.manager)
		arrange_sections([pipeline.name, views.name], "Note", for_everyone=True)

		frappe.set_user(self.member)
		self.assertEqual(section_names(), ["Pipeline", "Views", "Starred"])

	def test_publishing_an_order_clears_the_managers_own_overlay_sequence(self):
		"""Otherwise the manager is the one user who cannot see what they published."""
		first = make_section("Views", [make_view("a")], sequence=1)
		second = make_section("Pipeline", [make_view("b")], sequence=2)
		frappe.set_user(self.manager)
		arrange_sections([second.name, first.name], "Note")

		arrange_sections([first.name, second.name], "Note", for_everyone=True)

		self.assertEqual(section_names(), ["Views", "Pipeline"])

	def test_a_manager_renames_a_shared_section_through_stock_set_value(self):
		frappe.set_user(self.manager)
		section = make_section("Views", [make_view("a")])

		frappe.client.set_value("Navigation Section", section.name, "label", "All deals")

		self.assertIn("All deals", section_names())

	def test_a_member_cannot_rename_a_shared_section(self):
		section = make_section("Views", [])
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			frappe.client.set_value("Navigation Section", section.name, "label", "Mine now")

	def test_deleting_a_shared_section_returns_its_views_to_the_pool(self):
		"""A section is a placement, not a container: losing it unplaces, never deletes."""
		frappe.set_user(self.manager)
		view = make_view("Orphan")
		section = make_section("Views", [view])

		frappe.delete_doc("Navigation Section", section.name)

		self.assertNotIn("Views", section_names())
		self.assertTrue(frappe.db.exists("Saved View", view.name))

	def test_a_member_cannot_delete_a_shared_section(self):
		section = make_section("Views", [])
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Navigation Section", section.name)


class TestHideSection(IntegrationTestCase):
	def setUp(self):
		self.member = make_user("saved-view-member@example.com", ["Desk User"])
		self.manager = make_user("saved-view-manager@example.com", ["Desk User", "System Manager"])
		self.first = make_view("First")
		self.shared = make_section("Views", [self.first])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_member_hides_a_shared_section_on_their_own_overlay(self):
		frappe.set_user(self.member)

		hide_section(self.shared.name)

		self.assertEqual(hidden_seen_by(self.member), {"Views": 1})
		self.shared.reload()
		self.assertEqual(self.shared.hidden, 0)

	def test_a_hidden_shared_section_stays_for_everyone_else(self):
		frappe.set_user(self.member)
		hide_section(self.shared.name)

		self.assertEqual(hidden_seen_by(self.manager), {"Views": 0})

	def test_a_manager_hiding_one_hides_it_for_themselves_alone(self):
		"""Hiding is personal whatever the editor's scope says — a manager who wants a
		section gone for everybody deletes it."""
		frappe.set_user(self.manager)

		hide_section(self.shared.name)

		self.assertEqual(hidden_seen_by(self.manager), {"Views": 1})
		self.assertEqual(hidden_seen_by(self.member), {"Views": 0})

	def test_showing_it_again_puts_it_back(self):
		frappe.set_user(self.member)
		hide_section(self.shared.name)

		hide_section(self.shared.name, hidden=False)

		self.assertEqual(hidden_seen_by(self.member), {"Views": 0})

	def test_a_user_hides_their_own_section_in_place(self):
		frappe.set_user(self.member)
		personal = make_section("Starred", [], user=self.member)

		hide_section(personal.name)

		personal.reload()
		self.assertEqual(personal.hidden, 1)

	def test_a_user_cannot_hide_someone_elses_section(self):
		personal = make_section("Theirs", [], user=self.manager)
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			hide_section(personal.name)

	def test_publishing_an_order_leaves_the_managers_own_hidden_flag(self):
		"""Publishing drops the overlay that was overriding the order — but what it says
		about the section being hidden is not part of that order."""
		frappe.set_user(self.manager)
		second = make_view("Second")
		move_view_to_section(second.name, self.shared.name)
		hide_section(self.shared.name)

		arrange_items(self.shared.name, rows(self.shared, second, self.first), for_everyone=True)

		self.assertEqual(hidden_seen_by(self.manager), {"Views": 1})


def hidden_seen_by(user, reference_doctype="Note"):
	frappe.set_user(user)
	sidebar = get_sidebar(reference_doctype)["sections"]
	return {section["label"]: section["hidden"] for section in sidebar}


def get_section(label, reference_doctype="Note"):
	return next(
		section["items"]
		for section in get_sidebar(reference_doctype)["sections"]
		if section["label"] == label
	)
