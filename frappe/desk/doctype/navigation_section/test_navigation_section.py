# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.doctype.navigation_section.counts import view_counts
from frappe.desk.doctype.navigation_section.navigation_section import get_sidebar
from frappe.desk.doctype.navigation_section.scope import DEFAULT_APP, Scope
from frappe.tests import IntegrationTestCase


def make_user(email, roles):
	if frappe.db.exists("User", email):
		return email

	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"roles": [{"role": role} for role in roles],
		}
	).insert(ignore_permissions=True)
	return email


def make_view(label):
	return frappe.get_doc(
		{"doctype": "Saved View", "label": label, "reference_doctype": "Note", "type": "list"}
	).insert()


def make_default(source, user="Administrator"):
	"""The record `set_as_default` writes: a per-user copy of the chosen view, pointing
	back at it through `source_view`. A `None` source is the shape `save_landing_state`
	leaves — a default with no view behind it."""
	return frappe.get_doc(
		{
			"doctype": "Saved View",
			"label": "Default",
			"reference_doctype": "Note",
			"type": "list",
			"user": user,
			"is_default": 1,
			"source_view": source.name if source else None,
		}
	).insert()


def make_section(
	label,
	views,
	user=None,
	overrides=None,
	sequence=0,
	app=DEFAULT_APP,
	reference_doctype="Note",
	items=None,
):
	return frappe.get_doc(
		{
			"doctype": "Navigation Section",
			"label": label,
			"app": app,
			"reference_doctype": reference_doctype,
			"user": user,
			"overrides": overrides,
			"sequence": sequence,
			"items": items if items is not None else [{"type": "view", "view": view.name} for view in views],
		}
	).insert()


def make_link_section(url, label="Docs"):
	return make_section("Views", [], items=[{"type": "link", "label": label, "url": url}])


def clear_app(section):
	"""The state a section seeded before `app` existed is in. `app` is required, so
	this is only reachable by writing the column."""
	frappe.db.set_value("Navigation Section", section.name, "app", "", update_modified=False)


def section(label):
	return next(entry for entry in get_sidebar("Note")["sections"] if entry["label"] == label)


class TestNavigationSection(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_sidebar_returns_shared_sections_in_child_order(self):
		first, second = make_view("First"), make_view("Second")
		make_section("Views", [second, first])

		self.assertEqual(labels_in("Views"), ["Second", "First"])

	def test_sidebar_marks_hidden_rows_rather_than_dropping_them(self):
		view = make_view("Hidden")
		shared = make_section("Views", [view])
		shared.items[0].hidden = 1
		shared.save()

		items = section("Views")["items"]

		self.assertEqual([(item["label"], item["hidden"]) for item in items], [("Hidden", 1)])

	def test_sidebar_includes_the_session_users_own_section(self):
		make_section("Personal", [make_view("Mine")], user="Administrator")

		sidebar = get_sidebar("Note")["sections"]

		self.assertIn("Personal", [section["label"] for section in sidebar])

	def test_sidebar_excludes_another_users_section(self):
		make_section("Theirs", [make_view("Theirs")], user="Guest")

		sidebar = get_sidebar("Note")["sections"]

		self.assertNotIn("Theirs", [section["label"] for section in sidebar])

	def test_sidebar_excludes_overlays(self):
		"""An overlay is not a section of its own; resolving it lands with the reorder slice."""
		shared = make_section("Views", [])
		make_section("Views", [], user="Administrator", overrides=shared.name)

		sidebar = get_sidebar("Note")["sections"]

		self.assertEqual(len([section for section in sidebar if section["label"] == "Views"]), 1)

	def test_sidebar_is_scoped_to_the_doctype(self):
		make_section("Views", [make_view("Note view")])

		self.assertEqual(get_sidebar("ToDo")["sections"], [])

	def test_overlay_requires_a_user(self):
		shared = make_section("Views", [])

		with self.assertRaises(frappe.ValidationError):
			make_section("Overlay", [], overrides=shared.name)

	def test_overlay_cannot_target_a_personal_section(self):
		personal = make_section("Personal", [], user="Administrator")

		with self.assertRaises(frappe.ValidationError):
			make_section("Overlay", [], user="Administrator", overrides=personal.name)

	def test_overlay_of_a_missing_section_fails_as_a_link_error(self):
		"""`validate` runs before link checks, so a dangling target must not blow up."""
		with self.assertRaises(frappe.LinkValidationError):
			make_section("Overlay", [], user="Administrator", overrides="Does Not Exist")

	def test_personal_overlay_of_a_shared_section_is_allowed(self):
		shared = make_section("Views", [])

		overlay = make_section("Views", [], user="Administrator", overrides=shared.name)

		self.assertEqual(overlay.overrides, shared.name)

	def test_deleting_a_shared_section_takes_its_overlays_with_it(self):
		"""The overlays of other users are the ones that block the delete, and the ones
		the manager doing the deleting cannot see to clear out first."""
		shared = make_section("Views", [])
		mine = make_section("Views", [], user="Administrator", overrides=shared.name)
		theirs = make_section("Views", [], user="Guest", overrides=shared.name)

		frappe.delete_doc("Navigation Section", shared.name)

		self.assertFalse(frappe.db.exists("Navigation Section", mine.name))
		self.assertFalse(frappe.db.exists("Navigation Section", theirs.name))

	def test_sections_follow_sequence_before_creation(self):
		make_section("Second", [make_view("b")], sequence=2)
		make_section("First", [make_view("a")], sequence=1)

		labels = [section["label"] for section in get_sidebar("Note")["sections"]]

		self.assertEqual(labels, ["First", "Second"])

	def test_one_sequence_interleaves_personal_and_shared_sections(self):
		"""No halves: a personal section sits wherever its sequence puts it, above or
		between the shared ones."""
		make_section("Personal", [make_view("Mine")], user="Administrator", sequence=1)
		make_section("Views", [make_view("Ours")], sequence=2)

		labels = [section["label"] for section in get_sidebar("Note")["sections"]]

		self.assertEqual(labels, ["Personal", "Views"])


class TestLinkItems(IntegrationTestCase):
	"""A link is the item type with no record behind it: it carries its own label and
	URL, and derives whether it leaves the app."""

	def tearDown(self):
		frappe.db.rollback()

	def test_a_link_item_renders_beside_a_view(self):
		make_section("Views", [], items=[{"type": "link", "label": "Docs", "url": "/docs"}])

		self.assertEqual(labels_in("Views"), ["Docs"])

	def test_a_link_item_needs_a_label(self):
		with self.assertRaises(frappe.MandatoryError):
			make_section("Views", [], items=[{"type": "link", "url": "/docs"}])

	def test_a_link_item_needs_a_url(self):
		with self.assertRaises(frappe.MandatoryError):
			make_section("Views", [], items=[{"type": "link", "label": "Docs"}])

	def test_a_view_item_needs_a_view(self):
		with self.assertRaises(frappe.MandatoryError):
			make_section("Views", [], items=[{"type": "view", "label": "Nothing"}])

	def test_a_foreign_origin_defaults_to_a_new_tab(self):
		self.assertEqual(make_link_section("https://frappe.io/docs").items[0].new_tab, 1)

	def test_a_settings_hash_stays_in_place(self):
		self.assertEqual(make_link_section("#settings/general").items[0].new_tab, 0)

	def test_a_stored_new_tab_survives_a_later_save(self):
		"""The derivation is the default, not the rule — an author who turns it off keeps
		it off."""
		shared = make_link_section("https://frappe.io")

		shared.items[0].new_tab = 0
		shared.save()

		shared.reload()
		self.assertEqual(shared.items[0].new_tab, 0)

	def test_moving_a_link_off_this_site_re_derives_the_new_tab(self):
		shared = make_link_section("/docs")

		shared.items[0].url = "https://frappe.io/docs"
		shared.save()

		self.assertEqual(shared.items[0].new_tab, 1)

	def test_moving_a_link_back_into_the_app_re_derives_the_new_tab(self):
		shared = make_link_section("https://frappe.io/docs")

		shared.items[0].url = "/docs"
		shared.save()

		self.assertEqual(shared.items[0].new_tab, 0)

	def test_a_new_url_does_not_revoke_an_override(self):
		"""A stored flag disagreeing with its own URL is somebody's decision, and pointing
		the link somewhere else is not them changing their mind."""
		shared = make_link_section("/docs")
		shared.items[0].new_tab = 1
		shared.save()

		shared.items[0].url = "/help"
		shared.save()

		self.assertEqual(shared.items[0].new_tab, 1)

	def test_a_link_item_carries_no_count(self):
		view = make_view("All")
		make_section(
			"Views",
			[],
			items=[
				{"type": "view", "view": view.name},
				{"type": "link", "label": "Docs", "url": "/docs"},
			],
		)

		self.assertEqual(list(view_counts(Scope(DEFAULT_APP, "Note"), refresh=True)), [str(view.name)])


class TestDoctypeItems(IntegrationTestCase):
	"""A doctype item points at a list rather than at a URL, so the server owns both
	the route it resolves to and whether its owner sees it at all."""

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_a_doctype_item_routes_to_the_list(self):
		make_section("Views", [], items=[{"type": "doctype", "label": "To-dos", "dt": "ToDo"}])

		self.assertEqual(section("Views")["items"][0]["url"], "/ToDo")

	def test_a_doctype_item_needs_a_doctype(self):
		with self.assertRaises(frappe.MandatoryError):
			make_section("Views", [], items=[{"type": "doctype", "label": "Nothing"}])

	def test_a_doctype_item_needs_a_label(self):
		with self.assertRaises(frappe.MandatoryError):
			make_section("Views", [], items=[{"type": "doctype", "dt": "ToDo"}])

	def test_a_single_has_no_list_to_link_to(self):
		with self.assertRaises(frappe.ValidationError):
			make_section(
				"Views", [], items=[{"type": "doctype", "label": "Settings", "dt": "System Settings"}]
			)

	def test_a_child_table_has_no_list_to_link_to(self):
		with self.assertRaises(frappe.ValidationError):
			make_section("Views", [], items=[{"type": "doctype", "label": "Fields", "dt": "DocField"}])

	def test_a_missing_doctype_fails_as_a_link_error(self):
		"""`validate` runs before link checks, so an unknown doctype must not blow up
		on a meta that is not there."""
		with self.assertRaises(frappe.LinkValidationError):
			make_section("Views", [], items=[{"type": "doctype", "label": "Gone", "dt": "Not A DocType"}])

	def test_a_doctype_the_user_cannot_read_never_reaches_them(self):
		"""`new_doctype` is readable by a System Manager alone, so a plain Desk User is
		refused it — the item is left out of the response rather than drawn and then
		refused on click."""
		restricted = new_doctype().insert(ignore_permissions=True).name
		make_section(
			"Views",
			[],
			items=[
				{"type": "doctype", "label": "To-dos", "dt": "ToDo"},
				{"type": "doctype", "label": "Theirs", "dt": restricted},
			],
		)

		frappe.set_user(make_user("navigation-member@example.com", ["Desk User"]))

		self.assertEqual(labels_in("Views"), ["To-dos"])

	def test_a_deleted_doctype_takes_its_item_off_the_sidebar(self):
		"""Deleting a DocType is the one delete that runs no link check, so the Link
		cannot hold an item's target in place. The row is dropped on read instead,
		exactly as a view row whose view is gone is."""
		doctype = new_doctype().insert(ignore_permissions=True).name
		make_section("Views", [], items=[{"type": "doctype", "label": "Theirs", "dt": doctype}])

		frappe.delete_doc("DocType", doctype)

		self.assertEqual(labels_in("Views"), [])


class TestSectionScope(IntegrationTestCase):
	"""A section belongs to an app, and inside it to one doctype or to the app itself.
	Two apps on one site keep entirely separate navigation."""

	def tearDown(self):
		frappe.db.rollback()

	def test_another_apps_section_stays_out_of_the_sidebar(self):
		make_section("Theirs", [make_view("Theirs")], app="helpdesk")

		self.assertEqual(get_sidebar("Note", app=DEFAULT_APP)["sections"], [])

	def test_each_app_keeps_its_own_sections_for_the_same_doctype(self):
		make_section("Ours", [make_view("Ours")])
		make_section("Theirs", [make_view("Theirs")], app="helpdesk")

		self.assertEqual([entry["label"] for entry in get_sidebar("Note")["sections"]], ["Ours"])
		self.assertEqual(
			[entry["label"] for entry in get_sidebar("Note", app="helpdesk")["sections"]],
			["Theirs"],
		)

	def test_an_app_level_section_is_left_out_of_a_doctype_sidebar(self):
		"""It is the app's own navigation — the rail — not this doctype's panel."""
		make_section("Rail", [make_view("Somewhere")], reference_doctype=None)

		self.assertEqual(get_sidebar("Note")["sections"], [])

	def test_naming_no_doctype_reads_the_app_level_sections(self):
		"""How the rail reads its own navigation: the scope with no doctype in it."""
		make_section("Rail", [make_view("Somewhere")], reference_doctype=None)

		self.assertEqual([entry["label"] for entry in get_sidebar("")["sections"]], ["Rail"])

	def test_a_doctypes_sections_stay_out_of_the_app_level_read(self):
		make_section("Views", [make_view("Note view")])

		self.assertEqual(get_sidebar("")["sections"], [])

	def test_the_app_level_read_names_no_default_view(self):
		"""A default is the view the plain list route opens with, and app-level
		navigation has no list route to open."""
		make_section("Rail", [make_view("Somewhere")], reference_doctype=None)

		sidebar = get_sidebar("")

		self.assertIsNone(sidebar["default_view"])
		self.assertFalse(sidebar["default_view_is_stored"])

	def test_a_section_needs_no_reference_doctype(self):
		section = make_section("Rail", [], reference_doctype=None)

		self.assertFalse(section.reference_doctype)

	def test_a_section_needs_an_app(self):
		with self.assertRaises(frappe.MandatoryError):
			make_section("Orphan", [], app=None)

	def test_an_overlay_cannot_target_another_apps_section(self):
		theirs = make_section("Views", [], app="helpdesk")

		with self.assertRaises(frappe.ValidationError):
			make_section("Views", [], user="Administrator", overrides=theirs.name)

	def test_an_overlay_cannot_target_a_section_with_no_app(self):
		"""A blank `app` is nobody's scope, so it matches nobody's overlay either."""
		orphan = make_section("Views", [])
		clear_app(orphan)

		with self.assertRaises(frappe.ValidationError):
			make_section("Views", [], user="Administrator", overrides=orphan.name)

	def test_an_overlay_cannot_target_another_doctypes_section(self):
		other = make_section("Views", [], reference_doctype="ToDo")

		with self.assertRaises(frappe.ValidationError):
			make_section("Views", [], user="Administrator", overrides=other.name)

	def test_an_app_level_section_can_be_overlaid(self):
		shared = make_section("Rail", [], reference_doctype=None)

		overlay = make_section(
			"Rail", [], user="Administrator", overrides=shared.name, reference_doctype=None
		)

		self.assertEqual(overlay.overrides, shared.name)

	def test_an_overlay_written_for_another_app_leaves_this_ones_order_alone(self):
		first, second = make_view("First"), make_view("Second")
		theirs = make_section("Views", [first, second], app="helpdesk")
		overlay_of(theirs, [second, first], app="helpdesk")
		make_section("Views", [first, second])

		self.assertEqual(labels_in("Views"), ["First", "Second"])


class TestSidebarOverlays(IntegrationTestCase):
	"""Ticket 03's reconciliation, end to end: the endpoint hands back the final
	arrangement, so a client never merges a shared section with its overlay."""

	def tearDown(self):
		frappe.db.rollback()

	def test_an_overlay_reorders_the_shared_section_for_its_owner(self):
		first, second = make_view("First"), make_view("Second")
		shared = make_section("Views", [first, second])
		overlay_of(shared, [second, first])

		self.assertEqual(labels_in("Views"), ["Second", "First"])

	def test_an_overlay_hides_a_shared_view_for_its_owner_only(self):
		kept, unwanted = make_view("Kept"), make_view("Unwanted")
		shared = make_section("Views", [kept, unwanted])
		overlay = overlay_of(shared, [kept, unwanted])
		overlay.items[1].hidden = 1
		overlay.save()

		self.assertEqual(
			[(item["label"], item["hidden"]) for item in section("Views")["items"]],
			[("Kept", 0), ("Unwanted", 1)],
		)

	def test_a_hidden_row_in_someone_elses_overlay_leaves_the_shared_section_alone(self):
		kept, unwanted = make_view("Kept"), make_view("Unwanted")
		shared = make_section("Views", [kept, unwanted])
		overlay = overlay_of(shared, [kept, unwanted], user="Guest")
		overlay.items[1].hidden = 1
		overlay.save()

		self.assertEqual([item["hidden"] for item in section("Views")["items"]], [0, 0])

	def test_a_manager_added_view_appears_at_the_end_for_an_overlay_owner(self):
		first, second = make_view("First"), make_view("Second")
		shared = make_section("Views", [first, second])
		overlay_of(shared, [second, first])

		shared.append("items", {"type": "view", "view": make_view("Added").name})
		shared.save()

		self.assertEqual(labels_in("Views"), ["Second", "First", "Added"])

	def test_a_manager_deleted_view_disappears_from_an_overlay(self):
		kept, doomed = make_view("Kept"), make_view("Doomed")
		shared = make_section("Views", [kept, doomed])
		overlay_of(shared, [doomed, kept])

		shared.items = [row for row in shared.items if str(row.view) != str(doomed.name)]
		shared.save()

		self.assertEqual(labels_in("Views"), ["Kept"])

	def test_a_manager_reorder_reaches_a_user_without_an_overlay(self):
		first, second = make_view("First"), make_view("Second")
		shared = make_section("Views", [first, second])

		reorder(shared, [second, first])

		self.assertEqual(labels_in("Views"), ["Second", "First"])

	def test_a_manager_reorder_leaves_an_overlay_owners_order_alone(self):
		first, second = make_view("First"), make_view("Second")
		shared = make_section("Views", [first, second])
		overlay_of(shared, [second, first])

		reorder(shared, [second, first])

		self.assertEqual(labels_in("Views"), ["Second", "First"])

	def test_an_overlay_never_becomes_a_section_of_its_own(self):
		shared = make_section("Views", [make_view("Only")])
		overlay_of(shared, [])

		self.assertEqual([section["label"] for section in get_sidebar("Note")["sections"]], ["Views"])

	def test_another_users_overlay_does_not_reach_the_session_user(self):
		first, second = make_view("First"), make_view("Second")
		shared = make_section("Views", [first, second])
		make_section("Views", [second, first], user="Guest", overrides=shared.name)

		self.assertEqual(labels_in("Views"), ["First", "Second"])

	def test_an_overlay_reorders_a_link_item_like_any_other(self):
		"""A link has no view to be matched on, which is why overlay rows name the shared
		row itself."""
		shared = make_section(
			"Views",
			[],
			items=[
				{"type": "view", "view": make_view("All").name},
				{"type": "link", "label": "Docs", "url": "/docs"},
			],
		)
		overlay_rows(shared, [shared.items[1].name, shared.items[0].name])

		self.assertEqual(labels_in("Views"), ["Docs", "All"])

	def test_an_overlay_hides_a_link_item(self):
		shared = make_section("Views", [], items=[{"type": "link", "label": "Docs", "url": "/docs"}])
		overlay_rows(shared, [shared.items[0].name], hidden={shared.items[0].name})

		self.assertEqual([item["hidden"] for item in section("Views")["items"]], [1])


class TestSharedSidebar(IntegrationTestCase):
	"""`for_everyone`: the arrangement a manager edits while their editor says Everyone,
	which is the shared one as it stands before anybody's overlay reaches it."""

	def tearDown(self):
		frappe.db.rollback()

	def test_the_shared_read_ignores_the_callers_own_order(self):
		first, second = make_view("First"), make_view("Second")
		shared = make_section("Views", [first, second])
		overlay_of(shared, [second, first])

		self.assertEqual(shared_labels_in("Views"), ["First", "Second"])

	def test_the_shared_read_ignores_the_callers_own_naming(self):
		shared = make_section("Views", [], items=[{"type": "link", "label": "Docs", "url": "/docs"}])
		overlay = overlay_rows(shared, [shared.items[0].name])
		overlay.items[0].label = "My docs"
		overlay.save()

		self.assertEqual(shared_labels_in("Views"), ["Docs"])

	def test_the_shared_read_leaves_out_a_row_of_the_callers_own(self):
		shared = make_section("Views", [], items=[{"type": "link", "label": "Docs", "url": "/docs"}])
		overlay = overlay_rows(shared, [shared.items[0].name])
		overlay.append("items", {"type": "link", "label": "Mine", "url": "/mine"})
		overlay.save()

		self.assertEqual(shared_labels_in("Views"), ["Docs"])

	def test_the_shared_read_leaves_out_the_callers_own_sections(self):
		make_section("Views", [make_view("All")])
		make_section("Personal", [make_view("Mine")], user="Administrator")

		self.assertEqual([entry["label"] for entry in shared_sidebar_sections()], ["Views"])

	def test_a_row_the_caller_hid_is_still_shown_by_the_shared_read(self):
		"""Hiding is personal, so it is no part of what everyone gets."""
		shared = make_section("Views", [make_view("Hidden")])
		overlay_rows(shared, [shared.items[0].name], hidden={shared.items[0].name})

		items = shared_section("Views")["items"]

		self.assertEqual([(item["label"], item["hidden"]) for item in items], [("Hidden", 0)])

	def test_every_row_of_the_shared_read_is_everybodys(self):
		"""`own` is what the editor lets a personal edit through on; nothing here is one."""
		shared = make_section("Views", [make_view("All")])
		overlay_rows(shared, [shared.items[0].name])

		self.assertEqual([item["own"] for item in shared_section("Views")["items"]], [0])

	def test_a_section_the_caller_moved_keeps_its_shared_position(self):
		make_section("Views", [make_view("All")], sequence=2)
		moved = make_section("More", [make_view("Other")], sequence=3)
		make_section("More", [], user="Administrator", overrides=moved.name, sequence=1)

		self.assertEqual([entry["label"] for entry in get_sidebar("Note")["sections"]], ["More", "Views"])
		self.assertEqual([entry["label"] for entry in shared_sidebar_sections()], ["Views", "More"])


class TestDefaultView(IntegrationTestCase):
	"""The default the plain list route opens with, and the difference between one the
	user chose and the stand-in that fills in for it."""

	def tearDown(self):
		frappe.db.rollback()

	def test_the_first_shared_view_stands_in_when_nothing_is_stored(self):
		first, second = make_view("First"), make_view("Second")
		make_section("Views", [first, second])

		sidebar = get_sidebar("Note")

		self.assertEqual(str(sidebar["default_view"]), str(first.name))
		self.assertFalse(sidebar["default_view_is_stored"])

	def test_the_stand_in_moves_with_the_order_and_stays_unstored(self):
		"""The bug this flag exists for: nothing but position picks the stand-in, so a
		reorder hands it to whichever view is now on top. Reporting that as the user's
		default made a drag look like it had reassigned a setting."""
		first, second = make_view("First"), make_view("Second")
		shared = make_section("Views", [first, second])

		reorder(shared, [second, first])
		sidebar = get_sidebar("Note")

		self.assertEqual(str(sidebar["default_view"]), str(second.name))
		self.assertFalse(sidebar["default_view_is_stored"])

	def test_a_stored_default_survives_a_reorder(self):
		first, second = make_view("First"), make_view("Second")
		shared = make_section("Views", [first, second])
		make_default(second)

		reorder(shared, [second, first])
		sidebar = get_sidebar("Note")

		self.assertEqual(str(sidebar["default_view"]), str(second.name))
		self.assertTrue(sidebar["default_view_is_stored"])

	def test_a_stored_default_is_not_the_first_view_merely_by_position(self):
		first, second = make_view("First"), make_view("Second")
		make_section("Views", [first, second])
		make_default(second)

		sidebar = get_sidebar("Note")

		self.assertEqual(str(sidebar["default_view"]), str(second.name))
		self.assertTrue(sidebar["default_view_is_stored"])

	def test_a_default_with_no_source_view_is_not_stored(self):
		"""What `save_landing_state` leaves behind: a default record with no view behind
		it. There is nothing to point at, so the stand-in takes over unmarked."""
		first = make_view("First")
		make_section("Views", [first])
		make_default(None)

		sidebar = get_sidebar("Note")

		self.assertEqual(str(sidebar["default_view"]), str(first.name))
		self.assertFalse(sidebar["default_view_is_stored"])

	def test_a_default_pointing_off_the_sidebar_is_not_stored(self):
		"""A chosen view that has since left the sidebar cannot be what the list opens
		with, so the stand-in fills in — and is marked as the stand-in it is."""
		first, unplaced = make_view("First"), make_view("Unplaced")
		make_section("Views", [first])
		make_default(unplaced)

		sidebar = get_sidebar("Note")

		self.assertEqual(str(sidebar["default_view"]), str(first.name))
		self.assertFalse(sidebar["default_view_is_stored"])

	def test_no_view_on_the_sidebar_names_no_default(self):
		make_link_section("https://frappe.io")

		sidebar = get_sidebar("Note")

		self.assertIsNone(sidebar["default_view"])
		self.assertFalse(sidebar["default_view_is_stored"])


def shared_sidebar_sections():
	return get_sidebar("Note", for_everyone=True)["sections"]


def shared_section(label):
	return next(entry for entry in shared_sidebar_sections() if entry["label"] == label)


def shared_labels_in(label):
	return [item["label"] for item in shared_section(label)["items"]]


def overlay_of(shared, views, user="Administrator", app=DEFAULT_APP):
	"""An overlay names the shared rows it deltas, so an order is given as views and
	translated to the rows holding them."""
	row_of = {str(row.view): row.name for row in shared.items}
	return overlay_rows(shared, [row_of[str(view.name)] for view in views], user=user, app=app)


def overlay_rows(shared, rows, user="Administrator", hidden=(), app=DEFAULT_APP):
	return make_section(
		shared.label,
		[],
		user=user,
		overrides=shared.name,
		app=app,
		items=[{"overrides": row, "hidden": 1 if row in hidden else 0} for row in rows],
	)


def reorder(section, views):
	"""What `api.reorder_rows` does, without the endpoint: a row's name is what every
	overlay points at, so the rows are repositioned rather than rebuilt."""
	position = {str(view.name): index for index, view in enumerate(views, start=1)}
	for row in section.items:
		row.idx = position[str(row.view)]
	section.items.sort(key=lambda row: row.idx)
	return section.save()


def labels_in(label):
	return [item["label"] for item in section(label)["items"]]
