# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""The desk v2 navigation resolver: `frappe/shell/navigation.py`.

Every test here is about the merge and the payload, not about anyone's real navigation, so
which app the layers belong to does not matter. They belong to `frappe` because it is
certainly installed wherever this runs.
"""

import contextlib
import json
from unittest.mock import patch

import frappe
from frappe.shell.navigation import resolve_navigation
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user
from frappe.utils import set_request

APP = "frappe"

# The address of the sidebar these tests ship. `Core` is a module on every site, and the
# name its address produces is `module_def_core` — which is both the standard record's name
# and the key the payload uses, and the test below is that those two agree by construction
# rather than by luck.
ADDRESS = ("Module Def", "Core")
ADDRESS_KEY = "module_def_core"


@contextlib.contextmanager
def shipping():
	"""Place app content on the site the way an install does.

	Developer mode, because `Sidebar.validate_standard` refuses a standard row it could not
	write a file for, and it asks that question outright rather than through the flags. And
	`in_import`, which is what makes both `export_rail` and `export_sidebar` return early --
	otherwise the fixture writes a JSON file into the working tree, where the database
	rollback cannot reach it.
	"""
	developer_mode = frappe.conf.get("developer_mode")
	frappe.conf.developer_mode = 1
	frappe.flags.in_import = True
	try:
		yield
	finally:
		frappe.flags.in_import = False
		frappe.conf.developer_mode = developer_mode


class NavigationTestCase(IntegrationTestCase):
	"""Roll the database back after every test, not after the class.

	`IntegrationTestCase` rolls back once the whole class has run, which is enough for tests
	that read. These write layers, and a standard `Rail` is named after its app -- so a
	second test in the same class would collide on the primary key instead of starting from
	a site with no rails, which is the state every one of them assumes.
	"""

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("navigation_test")
		self.addCleanup(lambda: frappe.db.rollback(save_point="navigation_test"))


def item(key: str, **kwargs) -> dict:
	return {"doctype": "Navigation Item", "item_type": "DocType", "key": key, **kwargs}


def doctype_item(key: str, doctype: str, **kwargs) -> dict:
	return item(key, link_doctype="DocType", link_to=doctype, **kwargs)


def make_rail(items: list[dict], *, standard: int = 0, user: str | None = None):
	doc = frappe.get_doc(doctype="Rail", app=APP, standard=standard, user=user or "", items=items)
	with shipping():
		return doc.insert(ignore_permissions=True)


def make_sidebar(items: list[dict], *, standard: int = 0, user: str | None = None, **kwargs):
	doc = frappe.get_doc(
		doctype="Sidebar",
		app=APP,
		standard=standard,
		user=user or "",
		link_doctype=kwargs.pop("link_doctype", ADDRESS[0]),
		link_to=kwargs.pop("link_to", ADDRESS[1]),
		navigation_items=items,
		**kwargs,
	)
	with shipping():
		return doc.insert(ignore_permissions=True)


def keys(items: list[dict]) -> list[str]:
	return [entry["key"] for entry in items]


class TestDerivedRail(NavigationTestCase):
	"""An app that ships no `Rail` record still gets one.

	Not a corner case: no app on the branch ships a `Rail` record, so this is the path every
	app takes until the walking skeleton converts one. Without it, landing the resolver
	would have blanked five apps' rails at once.
	"""

	def test_an_app_with_no_rail_gets_its_own_doctypes(self):
		rail = resolve_navigation(APP)["rail"]

		self.assertTrue(rail)
		self.assertTrue(all(entry["item_type"] == "DocType" for entry in rail))
		self.assertIn("User", keys(rail))

	def test_a_derived_item_is_keyed_on_the_doctype_name(self):
		"""The key is what a delta is filed against, so it has to survive a slug change and
		the app's eventual conversion to shipped rows. The doctype name is already what the
		address table is keyed on."""
		entry = next(entry for entry in resolve_navigation(APP)["rail"] if entry["key"] == "User")

		self.assertEqual(entry["link_to"], "User")
		self.assertEqual(entry["link_doctype"], "DocType")

	def test_a_derived_item_carries_no_label(self):
		"""Nobody authored one. A renderer falls back to the destination, which is what the
		rail showed before this landed — so the appearance changes when an app ships rows,
		not when the resolver does."""
		entry = next(entry for entry in resolve_navigation(APP)["rail"] if entry["key"] == "User")

		self.assertNotIn("label", entry)
		self.assertNotIn("icon", entry)

	def test_a_derived_rail_is_permission_filtered(self):
		with set_user("Guest"):
			self.assertNotIn("User", keys(resolve_navigation(APP)["rail"]))

	def test_derivation_produces_a_rail_and_no_sidebars(self):
		"""A derived doctype sidebar would be saved views, which are out of this map's
		scope, and deriving only module sidebars would make the fallback behave differently
		for a doctype-primary app and a module-primary one."""
		self.assertEqual(resolve_navigation(APP)["sidebars"], {})

	def test_a_derived_rail_goes_through_the_merge(self):
		"""The decision with the widest blast radius: derivation synthesizes a base layer and
		passes it through `resolve_layers` rather than short-circuiting.

		Under a short-circuit an unconverted app's rail could not be reordered or hidden by
		anyone, so the whole per-user overlay would apply to converted apps only — and
		whether a person may arrange their own rail would depend on their app's conversion
		status rather than on anything they can see.
		"""
		make_rail([item("User", added=1, link_to="User", label="Everyone")], user=frappe.session.user)

		entry = next(entry for entry in resolve_navigation(APP)["rail"] if entry["key"] == "User")
		self.assertEqual(entry["label"], "Everyone")


class TestShippedRail(NavigationTestCase):
	def test_a_shipped_rail_replaces_derivation(self):
		make_rail([doctype_item("user", "User", label="People")], standard=1)

		rail = resolve_navigation(APP)["rail"]
		self.assertEqual(keys(rail), ["user"])
		self.assertEqual(rail[0]["label"], "People")

	def test_an_app_that_ships_an_empty_rail_gets_an_empty_rail(self):
		"""Shipping no rail and shipping an empty one are different statements, and only the
		first derives a base."""
		make_rail([], standard=1)

		self.assertEqual(resolve_navigation(APP)["rail"], [])

	def test_the_site_layer_then_the_users(self):
		make_rail(
			[doctype_item("user", "User"), doctype_item("role", "Role")],
			standard=1,
		)
		make_rail([item("role"), item("user")])
		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["role", "user"])

		make_rail([item("user"), item("role")], user=frappe.session.user)
		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user", "role"])

	def test_a_hidden_item_never_reaches_the_payload(self):
		"""`resolve_layers` returns the hidden map unapplied because the surface decides.
		Desk v2's payload is for rendering and has no manager UI, so a row the client cannot
		use would be bytes spent against boot's budget."""
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		make_rail([item("role", hidden=1)])

		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])

	def test_a_user_can_unhide_what_the_site_hid(self):
		"""Which is why hiding is resolved across every layer before anything acts on it: a
		user's `hidden: 0` has to find the item the site hid still in the list."""
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		make_rail([item("role", hidden=1)])
		make_rail([item("role", hidden=0)], user=frappe.session.user)

		self.assertIn("role", keys(resolve_navigation(APP)["rail"]))

	def test_a_delta_naming_an_item_the_app_removed_is_inert(self):
		"""#42229: a delta whose base is gone is left inert rather than deleted, so
		reinstalling an app restores the layout. What it must not do is reappear as an
		unlabelled button, since a delta need carry no label at all."""
		make_rail([doctype_item("user", "User")], standard=1)
		make_rail([item("gone"), item("user")])

		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])

	def test_a_layer_added_row_is_the_item(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_rail([item("note", added=1, link_to="Note", label="Notes")])

		rail = resolve_navigation(APP)["rail"]
		self.assertIn("note", keys(rail))
		self.assertEqual(next(e for e in rail if e["key"] == "note")["label"], "Notes")

	def test_a_row_with_no_key_names_nothing(self):
		"""Until the write endpoints mint one, a keyless layer row is malformed. Merging
		every keyless row under one key would let two of them silently become one."""
		make_rail([doctype_item("user", "User")], standard=1)
		make_rail([item(None, added=1, link_to="Note", label="Notes")])

		self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])


class TestOverrides(NavigationTestCase):
	"""`overrides` names the fields a delta has an opinion about, explicitly.

	The whole reason it is a list rather than "whatever is non-blank" is that a site
	clearing a value the app shipped — removing an icon, blanking a label — cannot be said
	in an empty-means-inherit encoding.
	"""

	def setUp(self):
		super().setUp()
		make_rail(
			[doctype_item("user", "User", label="People", icon="user")],
			standard=1,
		)

	def resolved(self) -> dict:
		return next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")

	def test_only_the_named_fields_are_overridden(self):
		make_rail([item("user", label="Staff", icon="crown", overrides=json.dumps(["label"]))])

		entry = self.resolved()
		self.assertEqual(entry["label"], "Staff")
		self.assertEqual(entry["icon"], "user")

	def test_a_named_field_can_be_blanked(self):
		make_rail([item("user", icon="", overrides=json.dumps(["icon"]))])

		self.assertNotIn("icon", self.resolved())

	def test_a_row_that_names_nothing_changes_nothing(self):
		make_rail([item("user", label="Staff")])

		self.assertEqual(self.resolved()["label"], "People")

	def test_an_unreadable_overrides_list_is_read_as_no_opinion(self):
		"""Rather than as an opinion about everything, which would let one malformed row
		blank an item's whole presentation."""
		make_rail([item("user", label="Staff", overrides="not json")])

		self.assertEqual(self.resolved()["label"], "People")


class TestTheWire(NavigationTestCase):
	def test_the_stored_flags_do_not_travel(self):
		"""`hidden`, `added` and `overrides` say how a layer was stored. Once the layers are
		merged they say nothing about the item on screen."""
		make_rail([doctype_item("user", "User")], standard=1)
		make_rail([item("user", added=0, overrides="[]")])

		entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")
		for field in ("hidden", "added", "overrides"):
			self.assertNotIn(field, entry)

	def test_a_blank_field_is_omitted_rather_than_sent_as_null(self):
		make_rail([doctype_item("user", "User")], standard=1)

		entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")
		self.assertEqual(set(entry), {"key", "item_type", "link_doctype", "link_to"})

	def test_a_payload_arrives_parsed(self):
		"""So the type-specific tail is an object on both sides of the wire and no renderer
		parses it a second time."""
		make_rail([doctype_item("user", "User", payload=json.dumps({"open_in_new_tab": 1}))], standard=1)

		entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")
		self.assertEqual(entry["payload"], {"open_in_new_tab": 1})

	def test_an_unreadable_payload_is_dropped_and_logged(self):
		make_rail([doctype_item("user", "User", payload="{not json")], standard=1)

		with patch("frappe.log_error") as log_error:
			entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")

		self.assertNotIn("payload", entry)
		self.assertTrue(log_error.called)

	def test_an_item_whose_parent_is_gone_is_promoted(self):
		"""A `parent_key` naming a row that is no longer there promotes the child rather than
		taking it with it, so an app removing a section never silently removes everything
		under it."""
		make_rail([doctype_item("user", "User", parent_key="people")], standard=1)

		entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")
		self.assertNotIn("parent_key", entry)

	def test_a_parent_that_is_present_is_kept(self):
		make_rail(
			[
				item("people", item_type="Section", label="People"),
				doctype_item("user", "User", parent_key="people"),
			],
			standard=1,
		)

		entry = next(e for e in resolve_navigation(APP)["rail"] if e["key"] == "user")
		self.assertEqual(entry["parent_key"], "people")


class TestSidebars(NavigationTestCase):
	def test_a_sidebar_is_keyed_by_its_scrubbed_address(self):
		"""Not by the name of any record. A resolved sidebar merges up to three rows with
		three different names, since a standard row is named after its address and the site
		and user layers are hash-named. The address is what all three share — and it is the
		string a rail item of type `Sidebar` already carries in `link_to`.
		"""
		shipped = make_sidebar([doctype_item("user", "User")], standard=1)
		mine = make_sidebar(
			[item("user", label="Me", overrides=json.dumps(["label"]))], user=frappe.session.user
		)

		sidebars = resolve_navigation(APP)["sidebars"]

		# The standard record's own name agrees with the key by construction...
		self.assertEqual(shipped.name, ADDRESS_KEY)
		# ...and the user's layer, which is hash-named, still merges into it.
		self.assertNotEqual(mine.name, ADDRESS_KEY)
		self.assertEqual(sidebars[ADDRESS_KEY][0]["label"], "Me")

	def test_a_v2_resolver_never_reads_v1s_rows(self):
		"""One `Sidebar` document holds desk v1's `items` beside desk v2's
		`navigation_items`, so a resolver reading the document rather than the child table it
		wants gets v1's sidebar. This is the live hazard that read-by-column exists for."""
		sidebar = make_sidebar([doctype_item("user", "User")], standard=1)
		with shipping():
			sidebar.append("items", {"type": "Link", "label": "A desk v1 row", "link_type": "DocType"})
			sidebar.save(ignore_permissions=True)

		items = resolve_navigation(APP)["sidebars"][ADDRESS_KEY]
		self.assertEqual(keys(items), ["user"])

	def test_an_address_that_resolves_to_nothing_is_absent(self):
		"""The payload is read by key, so an absent key and an empty list mean the same thing
		— and a linked rail item whose sidebar has no rows renders as an independent one."""
		make_sidebar([], standard=1)

		self.assertNotIn(ADDRESS_KEY, resolve_navigation(APP)["sidebars"])

	def test_a_sidebar_nobody_ships_is_not_resolved(self):
		"""An app layer is what makes a sidebar exist. A site delta over an address no app
		ships is inert, the same rule as a delta over an item the app removed."""
		make_sidebar([item("user", added=1, link_to="User")])

		self.assertEqual(resolve_navigation(APP)["sidebars"], {})

	def test_desk_v1s_own_sidebars_are_not_in_the_payload(self):
		"""They carry no address, and never will. That one column separates the two desks
		with no migration having to stamp the rows."""
		make_sidebar([doctype_item("user", "User")], standard=1)

		self.assertEqual(list(resolve_navigation(APP)["sidebars"]), [ADDRESS_KEY])


class TestNavigationInBoot(NavigationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		set_request(method="GET", path="/apps/desk")

	def tearDown(self):
		if hasattr(frappe.local, "request"):
			delattr(frappe.local, "request")

	def test_boot_carries_the_resolved_navigation(self):
		from frappe.shell.boot import get_boot

		boot = get_boot("/apps/desk")

		self.assertIn("navigation", boot)
		self.assertIn("User", keys(boot["navigation"]["rail"]))
		self.assertEqual(boot["navigation"]["sidebars"], {})

	def test_the_index_has_no_navigation(self):
		"""It belongs to no app, so there is no prefix whose navigation it could carry."""
		from frappe.shell.boot import get_boot

		self.assertNotIn("navigation", get_boot("/apps"))

	def test_navigation_is_a_framework_key_a_contribution_cannot_overwrite(self):
		"""Apps shape navigation through the rows and item types they ship. A code-level
		second route in would be two mechanisms for one thing."""
		from frappe.shell.boot import get_boot

		with patch("frappe.shell.boot.app_boot", return_value={"navigation": "mine"}):
			boot = get_boot("/apps/desk")

		self.assertIsInstance(boot["navigation"], dict)

	def test_boot_stays_under_the_ceiling_with_navigation_in_it(self):
		"""The framework's own prefix is the biggest one, and Administrator is the worst
		case: every doctype on the site is readable, so the derived rail is as long as it
		can get."""
		from frappe.shell.boot import get_boot

		self.assertLess(len(json.dumps(get_boot("/apps/desk"), default=str)), 40_000)
