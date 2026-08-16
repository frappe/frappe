# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from contextlib import ExitStack

import frappe
from frappe.desk.doctype.dock.dock import (
	get_site_dock,
	get_site_dock_layer,
	get_user_dock,
	get_user_dock_layer,
	resolve_dock,
	save_site_dock,
	save_user_dock,
)
from frappe.desk.doctype.sidebar.test_sidebar import make_sidebar, sidebarless_module
from frappe.tests import IntegrationTestCase

USER = "test-dock-prefs@example.com"

# The modules these suites arrange -- their own, rather than three of the framework's. An app
# fragment is free to name the framework's modules, and once an app ships one every site has a
# base that does, so borrowing them made every assertion here depend on what somebody else had
# shipped. These three are created by the suite and named by nothing else.
ALPHA = "Test Dock Alpha"
BETA = "Test Dock Beta"
GAMMA = "Test Dock Gamma"
TRIO = [ALPHA, BETA, GAMMA]


def dock_for(email=None, among=TRIO):
	"""The resolved dock as `email` sees it, narrowed to the modules a test named.

	Two things this hides. `resolve_dock` answers for the session user, so the only way to ask
	about somebody else is to be them for a moment. And the base is whatever the site's apps
	ship, which is not a suite about the site and user layers to control -- narrowing to the
	suite's own modules keeps the order it asserts while leaving the rest of the dock alone.
	"""
	if email:
		frappe.set_user(email)
	try:
		rows = resolve_dock()
	finally:
		if email:
			frappe.set_user("Administrator")

	if among is None:
		return rows
	return [row for row in rows if row.get("module") in set(among)]


def clear_arrangements():
	"""The site's layer and every person's own, gone. App fragments are left standing.

	A layer outlives the person it belongs to -- `Dock` is in `ignore_links_on_delete`, so
	deleting a User leaves theirs behind, the same way `Custom Sidebar` does -- and these suites
	reuse the same addresses, so one left standing is the next test's mystery entry.

	App fragments are not a suite's to remove. They are ordinary site data that somebody else
	authored, and reaping them here once quietly deleted one.
	"""
	for row in frappe.get_all("Dock", fields=["name", "app"]):
		if not row.app:
			frappe.delete_doc("Dock", row.name, force=True, ignore_permissions=True)


class DockTestCase(IntegrationTestCase):
	"""A suite with three modules of its own, and no opinion about anybody else's."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls._modules = ExitStack()
		for module in TRIO:
			cls._modules.enter_context(sidebarless_module(module))

	@classmethod
	def tearDownClass(cls):
		cls._modules.close()
		super().tearDownClass()


class TestDockPreferences(DockTestCase):
	"""The user's own layer, on a site whose own layer names nothing."""

	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": USER,
					"first_name": "Dock",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert()
		frappe.set_user(USER)

	def tearDown(self):
		frappe.set_user("Administrator")
		clear_arrangements()
		frappe.delete_doc("User", USER, force=True, ignore_missing=True)

	def test_order_round_trips(self):
		save_user_dock(json.dumps([GAMMA, ALPHA, BETA]))
		self.assertEqual([r["module"] for r in dock_for()], [GAMMA, ALPHA, BETA])

	def test_hidden_is_stored_not_omitted(self):
		"""An explicitly hidden module has to persist as a row. Storing "hidden" as mere
		absence would let it reappear the moment its app adds another module."""
		save_user_dock(json.dumps([{"module": ALPHA, "hidden": 0}, {"module": GAMMA, "hidden": 1}]))
		rows = {r["module"]: r["hidden"] for r in dock_for()}
		self.assertEqual(rows[ALPHA], 0)
		self.assertEqual(rows[GAMMA], 1)

	def test_plain_names_and_dicts_both_accepted(self):
		save_user_dock(json.dumps([ALPHA, {"module": BETA, "hidden": 1}]))
		rows = {r["module"]: r["hidden"] for r in dock_for()}
		self.assertEqual(rows, {ALPHA: 0, BETA: 1})

	def test_duplicates_are_collapsed(self):
		save_user_dock(json.dumps([ALPHA, ALPHA, BETA]))
		self.assertEqual([r["module"] for r in dock_for()], [ALPHA, BETA])

	def test_unknown_module_is_dropped(self):
		save_user_dock(json.dumps([ALPHA, "No Such Module"]))
		self.assertEqual([r["module"] for r in dock_for()], [ALPHA])

	def test_curation_cannot_resurface_a_blocked_module(self):
		"""A dock arrangement is a preference, never a way around module visibility."""
		frappe.set_user("Administrator")
		user = frappe.get_doc("User", USER)
		user.append("block_modules", {"module": GAMMA})
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=USER)
		frappe.set_user(USER)

		save_user_dock(json.dumps([ALPHA, GAMMA]))
		self.assertEqual([r["module"] for r in dock_for()], [ALPHA])

	def test_saving_replaces_rather_than_appends(self):
		"""The client sends the whole arrangement, not a delta -- the shape a Sortable makes."""
		save_user_dock(json.dumps([ALPHA, BETA, GAMMA]))
		save_user_dock(json.dumps([BETA]))
		self.assertEqual([r["module"] for r in dock_for()], [BETA])

	def test_boot_exposes_the_curation(self):
		from frappe.boot import get_bootinfo

		save_user_dock(json.dumps([BETA, ALPHA]))
		carried = [r["module"] for r in get_bootinfo().get("dock") if r["module"] in set(TRIO)]
		self.assertEqual(carried, [BETA, ALPHA])


class TestDockSiteLayer(DockTestCase):
	"""The site's arrangement, the user's own on top of it, and what the merge is for.

	Same rule as the sidebar's layers: a layer moves what it names to the front, in its order,
	and leaves everything else following in the order it inherited. What that buys here is the
	thing per-user curation cannot express -- "Accounts first, for everyone" -- without making
	an app's newly installed modules disappear from every site that has used it.
	"""

	MANAGER = "test-dock-manager@example.com"
	DESK_USER = "test-dock-desk-user@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		self.make_user(self.MANAGER, ["Desk User", "Workspace Manager"])
		self.make_user(self.DESK_USER, ["Desk User"])

	def tearDown(self):
		frappe.set_user("Administrator")
		clear_arrangements()
		for email in (self.MANAGER, self.DESK_USER):
			frappe.delete_doc("User", email, force=True, ignore_missing=True)

	def make_user(self, email, roles):
		if frappe.db.exists("User", email):
			frappe.delete_doc("User", email, force=True, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
			}
		).insert(ignore_permissions=True)

	def set_site_order(self, modules):
		"""The site layer as a Workspace Manager would leave it. Administrator holds every role."""
		user = frappe.session.user
		frappe.set_user("Administrator")
		save_site_dock(json.dumps(modules))
		frappe.set_user(user)

	def block_module(self, email, module):
		user = frappe.get_doc("User", email)
		user.append("block_modules", {"module": module})
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=email)

	# -- the merge ----------------------------------------------------------------------

	def test_site_order_applies_to_a_user_who_has_arranged_nothing(self):
		self.set_site_order([BETA, ALPHA])
		self.assertEqual([r["module"] for r in dock_for(self.DESK_USER)], [BETA, ALPHA])

	def test_a_users_own_arrangement_applies_on_top_of_the_sites(self):
		self.set_site_order([BETA, ALPHA, GAMMA])

		frappe.set_user(self.DESK_USER)
		save_user_dock(json.dumps([GAMMA]))

		# what they named comes first; the site's arrangement of the rest survives underneath
		self.assertEqual([r["module"] for r in dock_for(self.DESK_USER)], [GAMMA, BETA, ALPHA])

	def test_a_user_can_unhide_what_the_site_hid(self):
		"""Later layers win on hiding too, which is the whole reason to have a second one."""
		self.set_site_order([{"module": BETA, "hidden": 1}, {"module": ALPHA, "hidden": 0}])
		self.assertEqual({r["module"]: r["hidden"] for r in dock_for(self.DESK_USER)}[BETA], 1)

		frappe.set_user(self.DESK_USER)
		save_user_dock(json.dumps([{"module": BETA, "hidden": 0}]))
		self.assertEqual({r["module"]: r["hidden"] for r in dock_for(self.DESK_USER)}[BETA], 0)

	def test_a_module_the_site_never_named_is_absent_rather_than_appended(self):
		"""Absence *is* the answer: the arrangement is what to move, not what to show.

		The client keeps a module no layer names in its app's own order, trailing the ones a
		layer did name -- so nothing has to be re-listed for it to keep its default place.
		"""
		self.set_site_order([BETA, ALPHA])
		self.assertEqual([r["module"] for r in dock_for(self.DESK_USER)], [BETA, ALPHA])

	def test_installing_an_app_surfaces_its_module_on_an_already_ordered_dock(self):
		self.set_site_order([BETA, ALPHA])

		# the newcomer is in `among` on purpose: filtered out, the assertion below that it is
		# absent would hold whether the merge dropped it or not
		newcomer = "Test Dock Newcomer"
		with sidebarless_module(newcomer):
			dock = dock_for(self.DESK_USER, among=[*TRIO, newcomer])

		# the new module is named by neither layer, so nothing hides it and nothing pins it
		# behind the arrangement -- it lands after what the site ordered
		self.assertNotIn(newcomer, [r["module"] for r in dock])
		self.assertEqual([r["module"] for r in dock], [BETA, ALPHA])

	def test_a_module_the_user_may_not_reach_is_absent_from_the_dock(self):
		"""The dock is navigation reach, never a way around the module gate -- at either layer."""
		self.block_module(self.DESK_USER, GAMMA)
		self.set_site_order([GAMMA, ALPHA])

		self.assertEqual([r["module"] for r in dock_for(self.DESK_USER)], [ALPHA])

	# -- the gate -----------------------------------------------------------------------

	def test_only_a_workspace_manager_may_write_the_site_layer(self):
		frappe.set_user(self.DESK_USER)
		self.assertRaises(frappe.PermissionError, save_site_dock, json.dumps([ALPHA]))

		frappe.set_user(self.MANAGER)
		save_site_dock(json.dumps([ALPHA, BETA]))
		frappe.set_user("Administrator")
		self.assertEqual([r["module"] for r in get_site_dock()], [ALPHA, BETA])

	def test_only_a_workspace_manager_may_read_the_site_layer(self):
		self.set_site_order([ALPHA])

		frappe.set_user(self.DESK_USER)
		self.assertRaises(frappe.PermissionError, get_site_dock_layer)

		frappe.set_user(self.MANAGER)
		self.assertEqual([r["module"] for r in get_site_dock_layer()], [ALPHA])

	def test_a_site_save_keeps_rows_for_modules_the_saver_cannot_see(self):
		"""Site intent outlives one manager's blocked module.

		Filtering a site write by the saver's own visibility would let a Workspace Manager who
		happens to be blocked from a module silently delete the site's arrangement of it for
		everyone. Visibility is applied when the dock is resolved instead -- so the row stays,
		and it still does not show up on that manager's own dock.
		"""
		self.block_module(self.MANAGER, GAMMA)

		frappe.set_user(self.MANAGER)
		save_site_dock(json.dumps([GAMMA, ALPHA]))
		frappe.set_user("Administrator")

		self.assertEqual([r["module"] for r in get_site_dock()], [GAMMA, ALPHA])
		self.assertEqual([r["module"] for r in dock_for(self.MANAGER)], [ALPHA])
		self.assertEqual([r["module"] for r in dock_for(self.DESK_USER)], [GAMMA, ALPHA])

	# -- the seams the client edits through ---------------------------------------------

	def test_the_editor_reads_the_layer_it_will_overwrite(self):
		"""Each layer's read answers with that layer's own rows, never the resolved dock.

		A save replaces a layer whole. Handed the resolved dock, the dock manager would write
		the site's rows into the user's own layer, freezing them out of every later site change.
		"""
		self.set_site_order([BETA, ALPHA])

		frappe.set_user(self.DESK_USER)
		save_user_dock(json.dumps([ALPHA]))

		self.assertEqual([r["module"] for r in get_user_dock_layer()], [ALPHA])
		self.assertEqual([r["module"] for r in get_user_dock()], [ALPHA])
		self.assertEqual([r["module"] for r in dock_for()], [ALPHA, BETA])

	def test_boot_carries_the_resolved_dock(self):
		from frappe.boot import get_bootinfo

		self.set_site_order([BETA, ALPHA])

		frappe.set_user(self.DESK_USER)
		carried = [r["module"] for r in get_bootinfo().get("dock") if r["module"] in set(TRIO)]
		self.assertEqual(carried, [BETA, ALPHA])

	def test_every_layer_is_one_shape(self):
		"""One doctype at all three layers, because the rows are identical -- `app` and `user`
		are the whole difference, and the parent is what names the layer."""
		self.set_site_order([ALPHA])

		frappe.set_user(self.DESK_USER)
		save_user_dock(json.dumps([BETA]))
		frappe.set_user("Administrator")

		layers = frappe.get_all("Dock", fields=["app", "user"])
		self.assertEqual(
			sorted((row.app or "", row.user or "") for row in layers if not row.app),
			[("", ""), ("", self.DESK_USER)],
		)
		self.assertEqual(frappe.get_meta("Dock").get_field("items").options, "Dock Item")

	def test_a_layer_belongs_to_an_app_or_a_person_never_both(self):
		doc = frappe.new_doc("Dock").update({"app": "frappe", "user": self.DESK_USER})
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_a_layer_exists_once(self):
		"""Two documents at one address would give the merge two answers for the same layer."""
		self.set_site_order([ALPHA])
		self.assertRaises(frappe.DuplicateEntryError, frappe.new_doc("Dock").insert)


class TestTheAppLayer(DockTestCase):
	"""The layer below both writable ones: what an app ships, which the other two rearrange.

	The fragments are shipped under app names no real app has. A `Dock` is unique per app, so
	shipping one as `frappe` would collide the day the framework ships its own -- and a suite
	that owns a real app's fragment is a suite that deletes it on the way out.
	"""

	APP = "zz-dock-suite"
	OTHER_APP = "zz-dock-suite-companion"
	USER = "test-dock-app-layer@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("User", self.USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self.USER,
					"first_name": "Dock App Layer",
					"send_welcome_email": 0,
					"roles": [{"role": "Desk User"}],
				}
			).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		clear_arrangements()
		for app in (self.APP, self.OTHER_APP):
			for name in frappe.get_all("Dock", filters={"app": app}, pluck="name"):
				frappe.delete_doc("Dock", name, force=True, ignore_permissions=True)
		frappe.delete_doc("User", self.USER, force=True, ignore_missing=True)

	def ship(self, *items, app=None):
		doc = frappe.new_doc("Dock")
		doc.app = app or self.APP
		for item in items:
			doc.append("items", item if isinstance(item, dict) else {"module": item})
		doc.insert(ignore_permissions=True)

	def test_the_app_layer_is_the_base_the_dock_resolves_from(self):
		self.ship(BETA, ALPHA)
		self.assertEqual([r["module"] for r in dock_for(self.USER)], [BETA, ALPHA])

	def test_each_apps_fragment_follows_the_one_before_it(self):
		"""A fragment says nothing about another app's, so the base is the fragments concatenated.

		The order is the apps screen's -- the `sequence_id` an app declares in
		`add_to_apps_screen`, then install position, then name. Neither of these is installed, so
		both take the default sequence and the tie falls to the name: `zz-dock-suite` leads
		`zz-dock-suite-companion`, and each fragment stays whole rather than interleaving.
		"""
		self.ship(BETA, ALPHA)
		self.ship(GAMMA, app=self.OTHER_APP)

		self.assertEqual([r["module"] for r in dock_for(self.USER)], [BETA, ALPHA, GAMMA])

	def test_two_fragments_naming_one_module_render_it_once(self):
		"""The base is copied into the merge whole, so a duplicate there is never deduped above
		it. The first fragment to name an entry keeps it, as a layer does for a row it sees
		twice."""
		self.ship(BETA, ALPHA)
		self.ship(ALPHA, GAMMA, app=self.OTHER_APP)

		self.assertEqual([r["module"] for r in dock_for(self.USER)], [BETA, ALPHA, GAMMA])

	def test_the_site_arranges_what_the_app_shipped(self):
		self.ship(BETA, ALPHA, GAMMA)
		save_site_dock(json.dumps([GAMMA]))

		# what the site named comes first; the app's order of the rest survives underneath
		self.assertEqual([r["module"] for r in dock_for(self.USER)], [GAMMA, BETA, ALPHA])

	def test_a_person_arranges_what_the_site_left(self):
		self.ship(BETA, ALPHA, GAMMA)
		save_site_dock(json.dumps([GAMMA]))

		frappe.set_user(self.USER)
		save_user_dock(json.dumps([ALPHA]))
		frappe.set_user("Administrator")

		self.assertEqual([r["module"] for r in dock_for(self.USER)], [ALPHA, GAMMA, BETA])

	def test_a_module_the_app_added_later_still_reaches_someone_who_has_arranged(self):
		"""An entry no layer names trails the ones they did, rather than dropping out."""
		self.ship(BETA, ALPHA, GAMMA)
		save_site_dock(json.dumps([GAMMA, BETA]))

		self.assertEqual([r["module"] for r in dock_for(self.USER)], [GAMMA, BETA, ALPHA])

	def test_hiding_survives_the_app_adding_a_module(self):
		"""Hiding is a decision, not the absence of a row -- so a later fragment cannot undo it."""
		self.ship(BETA, ALPHA)
		save_site_dock(json.dumps([{"module": BETA, "hidden": 1}]))

		hidden = {r["module"]: r["hidden"] for r in dock_for(self.USER)}
		self.assertEqual(hidden[BETA], 1)
		self.assertEqual(hidden[ALPHA], 0)

	def test_an_entry_names_a_module_or_a_workspace(self):
		"""Which column is filled *is* the kind of entry, so a row filling both has no reading."""
		doc = frappe.new_doc("Dock")
		doc.app = self.APP
		doc.append("items", {"module": ALPHA, "workspace": "Welcome Workspace"})
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_a_row_naming_nothing_is_dropped_rather_than_stored(self):
		doc = frappe.new_doc("Dock")
		doc.app = self.APP
		doc.append("items", {"module": ALPHA})
		doc.append("items", {"hidden": 1})
		doc.insert(ignore_permissions=True)

		self.assertEqual([row.module for row in doc.items], [ALPHA])

	def test_a_module_and_a_workspace_of_the_same_name_are_different_entries(self):
		"""Identity is what an entry points at, and the two kinds do not share a namespace."""
		from frappe.desk.doctype.dock.dock import dock_key

		self.assertNotEqual(dock_key({"module": "Stock"}), dock_key({"workspace": "Stock"}))


class TestTheShippedModuleOrder(IntegrationTestCase):
	"""The order an app's modules take when no layer arranges them.

	The site's `Dock` and each person's own are site and user intent, and they can only
	rearrange the list they are given. This is that list -- `boot.get_app_modules` -- and until
	`Sidebar.sequence_id` existed the only way an app could state it was the position a
	module happened to occupy in `modules.txt`.
	"""

	def app_order(self, app: str = "frappe") -> list[str]:
		from frappe.boot import get_app_modules

		return get_app_modules(app)

	def position(self, module: str) -> int:
		return self.app_order().index(module)

	def test_a_sequence_pulls_a_module_in_front_of_one_that_declares_none(self):
		with (
			sidebarless_module("Test Sequence Ahead A") as ahead,
			sidebarless_module("Test Sequence Ahead B") as behind,
		):
			# alphabetical to begin with: neither is in modules.txt, so both tie on every key
			# above the name
			self.assertLess(self.position(ahead), self.position(behind))

			make_sidebar(behind, sequence_id=1)
			self.assertLess(self.position(behind), self.position(ahead))

	def test_a_high_sequence_pushes_a_module_behind_one_that_declares_none(self):
		"""What the *middle* default buys: declaring a sequence can say "after the quiet ones"
		as well as "before them". A trailing default could only ever say the first."""
		with (
			sidebarless_module("Test Sequence Behind A") as pushed,
			sidebarless_module("Test Sequence Behind B") as quiet,
		):
			make_sidebar(pushed, sequence_id=500)

			self.assertLess(self.position(quiet), self.position(pushed))

	def test_modules_txt_still_breaks_a_tie(self):
		"""The modules an app says nothing about keep exactly the dock they had, because the
		order it already declared is what the tie falls back to.

		Scoped to the modules with no sidebar document rather than to all of `frappe`'s: the
		ones that *do* have a document are entitled to state a sequence, and asserting over
		them would be asserting that no framework sidebar ever does.
		"""
		declared = frappe.get_module_list("frappe")
		sequenced = set(frappe.get_all("Sidebar", pluck="module"))
		quiet = [m for m in self.app_order() if m in declared and m not in sequenced]

		self.assertTrue(quiet, "sanity: some framework module declares no sequence")
		self.assertEqual(quiet, sorted(quiet, key=declared.index))

	def test_a_module_with_no_sidebar_document_takes_the_default(self):
		"""Most modules have a computed base and no document at all, so the default is the
		common case rather than the edge one."""
		from frappe.boot import DEFAULT_MODULE_SEQUENCE_ID

		with sidebarless_module("Test Sequence Defaulted") as module:
			self.assertFalse(frappe.db.exists("Sidebar", {"module": module}))
			self.assertIn(module, self.app_order())

			# the same position a document stating the default would put it in
			without = self.position(module)
			make_sidebar(module, sequence_id=DEFAULT_MODULE_SEQUENCE_ID)
			self.assertEqual(self.position(module), without)
