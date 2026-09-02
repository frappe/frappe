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


def make_rail(
	items: list[dict], *, standard: int = 0, user: str | None = None, app: str = APP, extends: str = ""
):
	doc = frappe.get_doc(
		doctype="Rail",
		app=app,
		extends=extends,
		standard=standard,
		user=user or "",
		items=items,
	)
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


# Extension — one app's rows on another app's rail
#
# No app on any bench ships a v2 rail, let alone one extending somebody else's, so there is
# nothing here to convert and these fixtures are the only consumer the mechanism has (#42398).
# The extending apps are named but never installed, which the resolver has to be told: it drops
# a contribution from an app that is not active, so `active` below is what makes one count.

EXTENDER = "telephony"
OTHER_EXTENDER = "payments"


@contextlib.contextmanager
def active(*apps: str):
	"""Present these apps to the resolver as installed and enabled, in this order.

	`get_active_apps` is what decides whether a contribution counts and where in the appended
	tail it lands, and it is the only thing in the merge that asks about an app at all.
	"""
	with patch("frappe.get_active_apps", return_value=[APP, *apps]):
		yield


def make_extension(items: list[dict], *, app: str = EXTENDER, host: str = APP):
	return make_rail(items, standard=1, app=app, extends=host)


def anchored(key: str, doctype: str, *anchors: dict, **kwargs) -> dict:
	return doctype_item(key, doctype, anchors=json.dumps(list(anchors)), **kwargs)


class TestExtendedRail(NavigationTestCase):
	def test_a_contributed_item_reaches_the_hosts_rail(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role")])

		with active(EXTENDER):
			rail = resolve_navigation(APP)["rail"]

		self.assertEqual(keys(rail), ["user", "telephony:calls"])

	def test_an_apps_own_rail_is_not_its_extension_of_somebody_elses(self):
		"""Both records carry `app = frappe`, so the layer read has to name `extends` as well.
		Without it the extension arrives as a second standard layer and the merge has no way to
		tell it from the first."""
		make_rail([doctype_item("user", "User")], standard=1)
		make_rail([doctype_item("elsewhere", "Role")], standard=1, extends="erpnext")

		with active(EXTENDER):
			self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])

	def test_an_app_that_is_not_active_contributes_nothing(self):
		"""A disabled app must not keep serving anything, which is the rule boot already applies
		to the app list and the prefix registry."""
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role")])

		with active():
			self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])

	def test_extension_merges_into_a_derived_rail(self):
		"""No app ships a `Rail` record, so this is the path every extension takes today. The
		derived base offers no anchor targets, so the contribution appends."""
		make_extension([anchored("calls", "Role", {"after": "User"})])

		with active(EXTENDER):
			rail = resolve_navigation(APP)["rail"]

		self.assertIn("User", keys(rail))
		self.assertEqual(keys(rail)[-1], "telephony:calls")

	def test_a_person_arranges_one_list_and_not_one_per_app(self):
		"""`extends` is standard-rows-only, so a person's arrangement of a host rail is one row
		covering every item on it — including the ones another app put there."""
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		make_extension([doctype_item("calls", "Role")])
		make_rail([item("telephony:calls"), item("user"), item("role")], user=frappe.session.user)

		with active(EXTENDER):
			self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["telephony:calls", "user", "role"])

	def test_a_person_may_hide_a_contributed_item(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role")])
		make_rail([item("telephony:calls", hidden=1)], user=frappe.session.user)

		with active(EXTENDER):
			self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user"])

	def test_a_contribution_is_positioned_and_not_only_appended(self):
		make_rail([doctype_item("user", "User"), doctype_item("role", "Role")], standard=1)
		make_extension([anchored("calls", "Role", {"after": "user"})])

		with active(EXTENDER):
			self.assertEqual(keys(resolve_navigation(APP)["rail"]), ["user", "telephony:calls", "role"])

	def test_two_apps_contribute_in_installation_order(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role")])
		make_extension([doctype_item("invoices", "Role")], app=OTHER_EXTENDER)

		with active(OTHER_EXTENDER, EXTENDER):
			self.assertEqual(
				keys(resolve_navigation(APP)["rail"]),
				["user", "payments:invoices", "telephony:calls"],
			)

	def test_the_stored_columns_never_reach_the_browser(self):
		"""`anchors` is spent at merge and `switches_app` becomes a `url`. Both are read into the
		merge because `overrides` may name any field a layer has an opinion about, and neither is
		anything the client renders — navigation is 88% of a payload with a 40 KB ceiling."""
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([anchored("calls", "Role", {"after": "user"})])

		with active(EXTENDER):
			entry = resolve_navigation(APP)["rail"][1]

		self.assertNotIn("anchors", entry)
		self.assertNotIn("switches_app", entry)
		self.assertNotIn("app", entry)


class TestSwitchingApps(NavigationTestCase):
	"""Following a contributed item keeps you in the host unless its app says otherwise.

	That default needs no code — a contributed row is an ordinary prefix-relative link, because
	addresses are bench-wide. Leaving is the exception, and only the server can build it: the
	client resolves routes through the router this document holds, which cannot reach another
	prefix at all (`routeFor.ts` says so in as many words).
	"""

	@contextlib.contextmanager
	def prefixed(self, prefix: str = "telephony", modular: bool = False):
		with (
			patch("frappe.shell.registry.declared_prefix", return_value=prefix),
			patch("frappe.shell.registry.is_modular", return_value=modular),
		):
			yield

	def test_an_item_that_does_not_switch_carries_no_url(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role")])

		with active(EXTENDER):
			entry = resolve_navigation(APP)["rail"][1]

		self.assertNotIn("url", entry)

	def test_a_switching_item_carries_the_finished_absolute_url(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role", switches_app=1)])

		with active(EXTENDER), self.prefixed():
			entry = resolve_navigation(APP)["rail"][1]

		self.assertEqual(entry["url"], "/apps/telephony/role")

	def test_a_modular_prefix_puts_the_module_in_the_address(self):
		"""The shape is the destination app's, not the host's — which is the whole reason the
		server builds this and the client cannot."""
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([doctype_item("calls", "Role", switches_app=1)])

		with active(EXTENDER), self.prefixed(modular=True):
			entry = resolve_navigation(APP)["rail"][1]

		self.assertEqual(entry["url"], "/apps/telephony/core/role")

	def test_a_record_item_carries_the_record(self):
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension(
			[
				item(
					"admin",
					item_type="Record",
					link_doctype="User",
					link_to="Administrator",
					switches_app=1,
				)
			]
		)

		with active(EXTENDER), self.prefixed():
			entry = resolve_navigation(APP)["rail"][1]

		self.assertEqual(entry["url"], "/apps/telephony/user/Administrator")

	def test_a_kind_with_no_cross_app_address_falls_back_to_the_host(self):
		"""A working link in the wrong app beats no link at all, and `Link` already carries an
		absolute URL of its own, so switching says nothing about it."""
		make_rail([doctype_item("user", "User")], standard=1)
		make_extension([item("docs", item_type="Link", url="https://frappe.io", switches_app=1)])

		with active(EXTENDER), self.prefixed():
			entry = resolve_navigation(APP)["rail"][1]

		self.assertEqual(entry["url"], "https://frappe.io")

	def test_a_host_row_never_switches(self):
		"""Nothing sets `app` on one, because nothing about it is foreign — so the column is
		inert on the rows it cannot mean anything for, rather than guarded against them."""
		make_rail([doctype_item("user", "User", switches_app=1)], standard=1)

		with active(), self.prefixed():
			self.assertNotIn("url", resolve_navigation(APP)["rail"][0])
