# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

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


def sidebar(module, hidden=None) -> dict:
	"""One typed row naming a module's `Sidebar` -- the shape a layer stores and a client sends.

	A sidebar's name *is* its module's name, so the module is the whole of the row's second half.
	"""
	row = {"type": "Sidebar", "name": module}
	if hidden is not None:
		row["hidden"] = hidden
	return row


def payload(*rows) -> str:
	"""The JSON a client sends for an arrangement: typed rows, one per entry.

	A bare module name is spelled out into its `Sidebar` row here rather than by the endpoint --
	the untyped shorthand went with the untyped row, because a name on its own no longer says
	what kind of thing it names.
	"""
	return json.dumps([sidebar(row) if isinstance(row, str) else row for row in rows])


def names(rows) -> list[str]:
	return [row["name"] for row in rows]


def hidden_by_name(rows) -> dict[str, int]:
	return {row["name"]: row["hidden"] for row in rows}


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
	return [row for row in rows if row["type"] == "Sidebar" and row["name"] in set(among)]


def clear_arrangements():
	"""The site's layer and every person's own, gone.

	A layer outlives the person it belongs to -- `Dock` is in `ignore_links_on_delete`, so
	deleting a User leaves theirs behind, the same way `Custom Sidebar` does -- and these suites
	reuse the same addresses, so one left standing is the next test's mystery entry.

	Nothing an app ships is touched: an app's fragment is a hook, not a document, and a suite
	that wants one declares it with `shipped_dock`.
	"""
	for name in frappe.get_all("Dock", pluck="name"):
		frappe.delete_doc("Dock", name, force=True, ignore_permissions=True)


@contextmanager
def shipped_dock(fragments: dict[str, list[dict]]):
	"""Declare `add_to_dock` for named apps, as if they had it in their `hooks.py`.

	    shipped_dock({"zz-dock-suite": [sidebar(ALPHA)], "zz-dock-suite-companion": [...]})

	The built-in `patch_hooks` is no use here: it ignores `app_name`, so every installed app
	would answer with the same fragment and the base would repeat it once per app. Whose fragment
	a row is in is the whole subject of these suites, so the patcher has to keep the distinction.

	An app named here that is not installed is *invented* for the duration -- it joins the
	installed list and answers every other hook with nothing, because it has no `hooks.py` to
	import. That is what lets a suite own its fragments: the framework's own are patched away
	inside the block, and the assertions do not depend on which apps this bench happens to carry.

	An invented app is deliberately absent from `_ensure_on_bench=True`, which asks for the apps
	that exist as directories. It does not, and callers who ask that question mean it -- the
	template loader imports every app it is handed.
	"""
	real_hooks = frappe.get_hooks
	real_apps = frappe.get_active_apps
	invented = [app for app in fragments if app not in real_apps()]

	def patched_hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if hook == "add_to_dock":
			if app_name:
				return fragments.get(app_name, [])
			return [row for rows in fragments.values() for row in rows]
		if app_name in invented:
			return []
		return real_hooks(hook, default, app_name)

	def patched_apps(*args, _ensure_on_bench=False, **kwargs):
		apps = real_apps(*args, _ensure_on_bench=_ensure_on_bench, **kwargs)
		return apps if _ensure_on_bench else [*apps, *invented]

	with (
		patch.object(frappe, "get_hooks", patched_hooks),
		patch.object(frappe, "get_active_apps", patched_apps),
	):
		yield


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
		save_user_dock(payload(GAMMA, ALPHA, BETA))
		self.assertEqual(names(dock_for()), [GAMMA, ALPHA, BETA])

	def test_the_resolved_dock_carries_the_typed_pair(self):
		"""What an entry points at is a kind and a name together, at every layer and in the
		payload -- never one column whose being filled is the kind."""
		save_user_dock(payload(ALPHA))

		self.assertEqual(dock_for(), [{"type": "Sidebar", "name": ALPHA, "hidden": 0}])
		self.assertEqual(get_user_dock_layer(), [{"type": "Sidebar", "name": ALPHA, "hidden": 0}])

	def test_hidden_is_stored_not_omitted(self):
		"""An explicitly hidden module has to persist as a row. Storing "hidden" as mere
		absence would let it reappear the moment its app adds another module."""
		save_user_dock(payload(sidebar(ALPHA, hidden=0), sidebar(GAMMA, hidden=1)))
		rows = hidden_by_name(dock_for())
		self.assertEqual(rows[ALPHA], 0)
		self.assertEqual(rows[GAMMA], 1)

	def test_a_row_that_names_no_kind_is_dropped(self):
		"""Both halves are the entry, so half of one says nothing at all -- and a bare name is
		half of one. Dropped rather than refused, the way a row naming nothing has always been."""
		save_user_dock(json.dumps([sidebar(ALPHA), {"name": BETA}, GAMMA, {"type": "Sidebar"}]))
		self.assertEqual(names(dock_for()), [ALPHA])

	def test_a_half_that_is_not_a_name_is_dropped(self):
		"""These rows are client JSON, so neither half can be taken on trust. A dict reaching the
		existence lookup would be read as *filters* rather than as a name."""
		save_user_dock(
			json.dumps(
				[
					sidebar(ALPHA),
					{"type": "Sidebar", "name": {"like": "%"}},
					{"type": ["Sidebar"], "name": BETA},
					{"type": "Sidebar", "name": 7},
				]
			)
		)
		self.assertEqual(names(dock_for()), [ALPHA])

	def test_duplicates_are_collapsed(self):
		save_user_dock(payload(ALPHA, ALPHA, BETA))
		self.assertEqual(names(dock_for()), [ALPHA, BETA])

	def test_unknown_module_is_dropped(self):
		save_user_dock(payload(ALPHA, "No Such Module"))
		self.assertEqual(names(dock_for()), [ALPHA])

	def test_a_row_naming_a_kind_the_dock_does_not_have_is_dropped(self):
		"""`type` is an open Link, so the whitelist is what closes the set on the way in."""
		save_user_dock(json.dumps([sidebar(ALPHA), {"type": "User", "name": "Administrator"}]))
		self.assertEqual(names(dock_for()), [ALPHA])
		self.assertEqual(names(get_user_dock_layer()), [ALPHA])

	def test_curation_cannot_resurface_a_blocked_module(self):
		"""A dock arrangement is a preference, never a way around module visibility."""
		frappe.set_user("Administrator")
		user = frappe.get_doc("User", USER)
		user.append("block_modules", {"module": GAMMA})
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=USER)
		frappe.set_user(USER)

		save_user_dock(payload(ALPHA, GAMMA))
		self.assertEqual(names(dock_for()), [ALPHA])

	def test_saving_replaces_rather_than_appends(self):
		"""The client sends the whole arrangement, not a delta -- the shape a Sortable makes."""
		save_user_dock(payload(ALPHA, BETA, GAMMA))
		save_user_dock(payload(BETA))
		self.assertEqual(names(dock_for()), [BETA])

	def test_boot_exposes_the_curation(self):
		from frappe.boot import get_bootinfo

		save_user_dock(payload(BETA, ALPHA))
		carried = [r["name"] for r in get_bootinfo().get("dock") if r["name"] in set(TRIO)]
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

	def set_site_order(self, *rows):
		"""The site layer as a Workspace Manager would leave it. Administrator holds every role."""
		user = frappe.session.user
		frappe.set_user("Administrator")
		save_site_dock(payload(*rows))
		frappe.set_user(user)

	def block_module(self, email, module):
		user = frappe.get_doc("User", email)
		user.append("block_modules", {"module": module})
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=email)

	# -- the merge ----------------------------------------------------------------------

	def test_site_order_applies_to_a_user_who_has_arranged_nothing(self):
		self.set_site_order(BETA, ALPHA)
		self.assertEqual(names(dock_for(self.DESK_USER)), [BETA, ALPHA])

	def test_a_users_own_arrangement_applies_on_top_of_the_sites(self):
		self.set_site_order(BETA, ALPHA, GAMMA)

		frappe.set_user(self.DESK_USER)
		save_user_dock(payload(GAMMA))

		# what they named comes first; the site's arrangement of the rest survives underneath
		self.assertEqual(names(dock_for(self.DESK_USER)), [GAMMA, BETA, ALPHA])

	def test_a_user_can_unhide_what_the_site_hid(self):
		"""Later layers win on hiding too, which is the whole reason to have a second one."""
		self.set_site_order(sidebar(BETA, hidden=1), sidebar(ALPHA, hidden=0))
		self.assertEqual(hidden_by_name(dock_for(self.DESK_USER))[BETA], 1)

		frappe.set_user(self.DESK_USER)
		save_user_dock(payload(sidebar(BETA, hidden=0)))
		self.assertEqual(hidden_by_name(dock_for(self.DESK_USER))[BETA], 0)

	def test_a_module_the_site_never_named_is_absent_rather_than_appended(self):
		"""Absence *is* the answer: the arrangement is what to move, not what to show.

		The client keeps a module no layer names in its app's own order, trailing the ones a
		layer did name -- so nothing has to be re-listed for it to keep its default place.
		"""
		self.set_site_order(BETA, ALPHA)
		self.assertEqual(names(dock_for(self.DESK_USER)), [BETA, ALPHA])

	def test_installing_an_app_surfaces_its_module_on_an_already_ordered_dock(self):
		self.set_site_order(BETA, ALPHA)

		# the newcomer is in `among` on purpose: filtered out, the assertion below that it is
		# absent would hold whether the merge dropped it or not
		newcomer = "Test Dock Newcomer"
		with sidebarless_module(newcomer):
			dock = dock_for(self.DESK_USER, among=[*TRIO, newcomer])

		# the new module is named by neither layer, so nothing hides it and nothing pins it
		# behind the arrangement -- it lands after what the site ordered
		self.assertNotIn(newcomer, names(dock))
		self.assertEqual(names(dock), [BETA, ALPHA])

	def test_a_module_the_user_may_not_reach_is_absent_from_the_dock(self):
		"""The dock is navigation reach, never a way around the module gate -- at either layer."""
		self.block_module(self.DESK_USER, GAMMA)
		self.set_site_order(GAMMA, ALPHA)

		self.assertEqual(names(dock_for(self.DESK_USER)), [ALPHA])

	# -- the gate -----------------------------------------------------------------------

	def test_only_a_workspace_manager_may_write_the_site_layer(self):
		frappe.set_user(self.DESK_USER)
		self.assertRaises(frappe.PermissionError, save_site_dock, payload(ALPHA))

		frappe.set_user(self.MANAGER)
		save_site_dock(payload(ALPHA, BETA))
		frappe.set_user("Administrator")
		self.assertEqual(names(get_site_dock()), [ALPHA, BETA])

	def test_only_a_workspace_manager_may_read_the_site_layer(self):
		self.set_site_order(ALPHA)

		frappe.set_user(self.DESK_USER)
		self.assertRaises(frappe.PermissionError, get_site_dock_layer)

		frappe.set_user(self.MANAGER)
		self.assertEqual(names(get_site_dock_layer()), [ALPHA])

	def test_a_site_save_keeps_rows_for_modules_the_saver_cannot_see(self):
		"""Site intent outlives one manager's blocked module.

		Filtering a site write by the saver's own visibility would let a Workspace Manager who
		happens to be blocked from a module silently delete the site's arrangement of it for
		everyone. Visibility is applied when the dock is resolved instead -- so the row stays,
		and it still does not show up on that manager's own dock.
		"""
		self.block_module(self.MANAGER, GAMMA)

		frappe.set_user(self.MANAGER)
		save_site_dock(payload(GAMMA, ALPHA))
		frappe.set_user("Administrator")

		self.assertEqual(names(get_site_dock()), [GAMMA, ALPHA])
		self.assertEqual(names(dock_for(self.MANAGER)), [ALPHA])
		self.assertEqual(names(dock_for(self.DESK_USER)), [GAMMA, ALPHA])

	# -- the seams the client edits through ---------------------------------------------

	def test_the_editor_reads_the_layer_it_will_overwrite(self):
		"""Each layer's read answers with that layer's own rows, never the resolved dock.

		A save replaces a layer whole. Handed the resolved dock, the dock manager would write
		the site's rows into the user's own layer, freezing them out of every later site change.
		"""
		self.set_site_order(BETA, ALPHA)

		frappe.set_user(self.DESK_USER)
		save_user_dock(payload(ALPHA))

		self.assertEqual(names(get_user_dock_layer()), [ALPHA])
		self.assertEqual(names(get_user_dock()), [ALPHA])
		self.assertEqual(names(dock_for()), [ALPHA, BETA])

	def test_both_writable_layers_round_trip_typed_rows(self):
		"""Written as a pair, read back as a pair -- at the site's layer and at a person's own."""
		self.set_site_order(BETA)

		frappe.set_user(self.DESK_USER)
		save_user_dock(payload(ALPHA))
		frappe.set_user("Administrator")

		self.assertEqual(get_site_dock(), [{"type": "Sidebar", "name": BETA, "hidden": 0}])
		self.assertEqual(get_user_dock(self.DESK_USER), [{"type": "Sidebar", "name": ALPHA, "hidden": 0}])

	def test_boot_carries_the_resolved_dock(self):
		from frappe.boot import get_bootinfo

		self.set_site_order(BETA, ALPHA)

		frappe.set_user(self.DESK_USER)
		carried = [r["name"] for r in get_bootinfo().get("dock") if r["name"] in set(TRIO)]
		self.assertEqual(carried, [BETA, ALPHA])

	def test_every_layer_is_one_shape(self):
		"""One doctype at both stored layers, because the rows are identical -- `user` is the
		whole difference, and the parent is what names the layer."""
		self.set_site_order(ALPHA)

		frappe.set_user(self.DESK_USER)
		save_user_dock(payload(BETA))
		frappe.set_user("Administrator")

		layers = frappe.get_all("Dock", fields=["user"])
		self.assertEqual(sorted(row.user or "" for row in layers), ["", self.DESK_USER])
		self.assertEqual(frappe.get_meta("Dock").get_field("items").options, "Dock Item")
		self.assertIsNone(frappe.get_meta("Dock").get_field("app"), "the app layer is a hook now")

	def test_a_layer_exists_once(self):
		"""Two documents at one address would give the merge two answers for the same layer, so
		the constraint is an index rather than a `validate` hook a bulk write can be talked past.
		"""
		self.set_site_order(ALPHA)
		self.assertRaises(frappe.UniqueValidationError, frappe.new_doc("Dock").insert)


class TestTheAppLayer(DockTestCase):
	"""The layer below both writable ones: what an app ships, which the other two rearrange.

	An app declares it as a hook rather than a document, so nothing here is inserted, exported or
	reaped -- the fragments are declared for the length of a `with` block and are gone after it.
	The app names are ones no real app has, and `shipped_dock` invents them for the duration.
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
		frappe.delete_doc("User", self.USER, force=True, ignore_missing=True)

	def ship(self, *items, app=None):
		"""One app's fragment, declared for the length of the `with` block."""
		rows = [item if isinstance(item, dict) else sidebar(item) for item in items]
		return shipped_dock({app or self.APP: rows})

	def test_the_app_layer_is_the_base_the_dock_resolves_from(self):
		with self.ship(BETA, ALPHA):
			self.assertEqual(names(dock_for(self.USER)), [BETA, ALPHA])

	def test_the_base_is_the_hook_rather_than_a_document(self):
		"""Nothing is exported, imported or materialised: an app-layer row accumulates no state a
		hook cannot express, so there is no mirror record to drift and no orphan to reap."""
		with self.ship(BETA, ALPHA):
			self.assertEqual(names(dock_for(self.USER)), [BETA, ALPHA])
			self.assertFalse(frappe.get_all("Dock"), "an app's fragment stores nothing")

	def test_each_apps_fragment_follows_the_one_before_it(self):
		"""A fragment says nothing about another app's, so the base is the fragments concatenated.

		The order is the apps screen's -- the `sequence_id` an app declares in
		`add_to_apps_screen`, then install position. Both of these are invented at the end of the
		installed list, in the order they were named, and each fragment stays whole rather than
		interleaving.
		"""
		with shipped_dock({self.APP: [sidebar(BETA), sidebar(ALPHA)], self.OTHER_APP: [sidebar(GAMMA)]}):
			self.assertEqual(names(dock_for(self.USER)), [BETA, ALPHA, GAMMA])

	def test_two_fragments_naming_one_module_render_it_once(self):
		"""The base is copied into the merge whole, so a duplicate there is never deduped above
		it. The first fragment to name an entry keeps it, as a layer does for a row it sees
		twice."""
		with shipped_dock(
			{
				self.APP: [sidebar(BETA), sidebar(ALPHA)],
				self.OTHER_APP: [sidebar(ALPHA), sidebar(GAMMA)],
			}
		):
			self.assertEqual(names(dock_for(self.USER)), [BETA, ALPHA, GAMMA])

	def test_the_site_arranges_what_the_app_shipped(self):
		with self.ship(BETA, ALPHA, GAMMA):
			save_site_dock(payload(GAMMA))

			# what the site named comes first; the app's order of the rest survives underneath
			self.assertEqual(names(dock_for(self.USER)), [GAMMA, BETA, ALPHA])

	def test_a_person_arranges_what_the_site_left(self):
		with self.ship(BETA, ALPHA, GAMMA):
			save_site_dock(payload(GAMMA))

			frappe.set_user(self.USER)
			save_user_dock(payload(ALPHA))
			frappe.set_user("Administrator")

			self.assertEqual(names(dock_for(self.USER)), [ALPHA, GAMMA, BETA])

	def test_a_module_the_app_added_later_still_reaches_someone_who_has_arranged(self):
		"""An entry no layer names trails the ones they did, rather than dropping out."""
		with self.ship(BETA, ALPHA, GAMMA):
			save_site_dock(payload(GAMMA, BETA))

			self.assertEqual(names(dock_for(self.USER)), [GAMMA, BETA, ALPHA])

	def test_hiding_survives_the_app_adding_a_module(self):
		"""Hiding is a decision, not the absence of a row -- so a later fragment cannot undo it."""
		with self.ship(BETA, ALPHA):
			save_site_dock(payload(sidebar(BETA, hidden=1)))

			hidden = hidden_by_name(dock_for(self.USER))
			self.assertEqual(hidden[BETA], 1)
			self.assertEqual(hidden[ALPHA], 0)

	def test_a_row_naming_a_kind_the_dock_does_not_have_is_dropped_from_the_base(self):
		"""`type` is an open Link to `DocType`, so the whitelist is what closes the set at every
		layer -- including the one an app writes by hand."""
		with shipped_dock({self.APP: [{"type": "User", "name": "Administrator"}, sidebar(ALPHA)]}):
			self.assertEqual(names(dock_for(self.USER)), [ALPHA])

	def test_a_base_row_missing_half_the_pair_says_nothing(self):
		"""Both halves are the entry, so either one missing says nothing at all."""
		with shipped_dock({self.APP: [sidebar(ALPHA), {"type": "Sidebar"}, {"name": BETA}, BETA]}):
			self.assertEqual(names(dock_for(self.USER)), [ALPHA])

	def test_a_module_with_no_sidebar_document_is_still_nameable(self):
		"""Most modules have a computed base and no `Sidebar` document at all, so a row is proved
		by the module rather than by the record its `type` names -- and link validation on a
		`Dock` row is a deliberate no-op for the same reason."""
		self.assertFalse(frappe.db.exists("Sidebar", ALPHA), "sanity: this module ships no sidebar")

		with self.ship(ALPHA):
			self.assertEqual(names(dock_for(self.USER)), [ALPHA])

		save_site_dock(payload(ALPHA))
		self.assertEqual(names(get_site_dock()), [ALPHA])

	def test_a_site_whose_apps_declare_nothing_resolves_an_empty_base(self):
		"""Adopting the hook is a choice: an app that declares none leaves the site layer as the
		first there is, exactly as it was before the base existed."""
		with shipped_dock({}):
			self.assertEqual(dock_for(self.USER, among=None), [])

			save_site_dock(payload(BETA, ALPHA))
			self.assertEqual(names(dock_for(self.USER)), [BETA, ALPHA])

	def test_a_sidebar_and_a_workspace_of_the_same_name_are_different_entries(self):
		"""Identity is the pair, so one name under two kinds is two entries rather than one."""
		from frappe.desk.doctype.dock.dock import dock_key

		self.assertNotEqual(
			dock_key({"type": "Sidebar", "name": "Stock"}),
			dock_key({"type": "Workspace", "name": "Stock"}),
		)

	def test_a_workspace_entry_round_trips_beside_a_sidebar_of_the_same_name(self):
		"""The pair all the way through: stored, resolved and read back as two entries."""
		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": ALPHA,
				"label": ALPHA,
				"module": ALPHA,
				"public": 1,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", workspace.name, force=True, ignore_missing=True)

		save_site_dock(payload({"type": "Workspace", "name": ALPHA}, sidebar(ALPHA)))

		self.assertEqual(
			get_site_dock(),
			[
				{"type": "Workspace", "name": ALPHA, "hidden": 0},
				{"type": "Sidebar", "name": ALPHA, "hidden": 0},
			],
		)
		self.assertEqual(
			[(r["type"], r["name"]) for r in dock_for(among=None) if r["name"] == ALPHA],
			[("Workspace", ALPHA), ("Sidebar", ALPHA)],
		)


class TestThePin(DockTestCase):
	"""A companion app's workspace reaching the host app's dock.

	The fix the pinning hook was built for and never delivered: the pin used to land in a per-app
	workspace list while the rail rendered a per-app module list, so installing a companion took
	away its apps-screen slot and gave it a dock entry nobody could see.
	"""

	HOST = "frappe"
	COMPANION = "zz-dock-companion"
	OTHER_COMPANION = "zz-dock-companion-two"
	USER = "test-dock-pin@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("User", self.USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self.USER,
					"first_name": "Dock Pin",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		clear_arrangements()
		frappe.delete_doc("User", self.USER, force=True, ignore_missing=True)

	def make_workspace(self, title, module, public=1, roles=None):
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": title,
				"module": module,
				"public": public,
				"content": "[]",
				"roles": [{"role": role} for role in roles or []],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", doc.name, force=True, ignore_missing=True)
		return doc.name

	def pin(self, workspace, app=None, host=None):
		return {"type": "Workspace", "name": workspace, "app": host or self.HOST}

	def host_dock(self, email=None):
		"""The host app's one typed list, as `email` sees it in the boot payload.

		`get_app_data` rather than a whole boot: an invented app is not a directory on the bench,
		and several other things a boot does walk the installed apps and import each one.
		"""
		from frappe.boot import get_app_data
		from frappe.desk.desktop import get_workspaces

		if email:
			frappe.set_user(email)
		try:
			app_data = get_app_data([page.name for page in get_workspaces()["pages"]])
		finally:
			if email:
				frappe.set_user("Administrator")

		entry = next(app for app in app_data if app["app_name"] == self.HOST)
		return entry["dock"]

	def test_the_boot_payload_carries_one_typed_list_per_app(self):
		"""Both old fields are gone: the client stops reconciling a module list against a
		workspace list to render a single rail, which is the gap the pin fell into."""
		from frappe.boot import get_bootinfo

		for app in get_bootinfo()["app_data"]:
			self.assertIn("dock", app)
			self.assertNotIn("modules", app)
			self.assertNotIn("workspaces", app)
			self.assertTrue(all({*row} == {"type", "name"} for row in app["dock"]))

	def test_a_pin_folds_into_the_hosts_list_behind_its_own_entries(self):
		"""Attribution is forced rather than chosen: a row grouped under the companion would
		never render on the host's dock at all. Appended rather than positioned -- where it sits
		is Layer business, not the companion's to assert."""
		workspace = self.make_workspace("Test Dock Pinned", ALPHA)

		with shipped_dock({self.COMPANION: [self.pin(workspace)]}):
			dock = self.host_dock()

		self.assertEqual(dock[-1], {"type": "Workspace", "name": workspace})
		self.assertTrue(all(row["type"] == "Sidebar" for row in dock[:-1]))

	def test_two_companions_pinning_into_one_host_order_by_installation(self):
		first = self.make_workspace("Test Dock Pin One", ALPHA)
		second = self.make_workspace("Test Dock Pin Two", BETA)

		with shipped_dock(
			{
				self.COMPANION: [self.pin(first)],
				self.OTHER_COMPANION: [self.pin(second)],
			}
		):
			pinned = [row["name"] for row in self.host_dock() if row["type"] == "Workspace"]

		self.assertEqual(pinned, [first, second])

	def test_a_pinned_workspace_the_person_may_not_open_is_absent(self):
		"""Permission-filtered like any other workspace, so pinning cannot leak a page's
		existence to someone who may not open it."""
		workspace = self.make_workspace("Test Dock Pin Blocked", ALPHA, roles=["Workspace Manager"])

		with shipped_dock({self.COMPANION: [self.pin(workspace)]}):
			# `get_workspaces` is request-cached, and this suite asks it as two different people
			# inside one request
			frappe.local.request_cache.clear()
			allowed = [row["name"] for row in self.host_dock(self.USER) if row["type"] == "Workspace"]

		self.assertNotIn(workspace, allowed)

	def test_pinning_costs_the_apps_screen_slot_but_declaring_your_own_does_not(self):
		"""The rule reads the rows, not the hook. Every app declares `add_to_dock` now, so a
		presence check would delete each adopting app from the apps screen."""
		from frappe.boot import get_app_rail_host_map

		workspace = self.make_workspace("Test Dock Pin Slot", ALPHA)

		with shipped_dock(
			{
				self.COMPANION: [self.pin(workspace)],
				self.OTHER_COMPANION: [sidebar(BETA)],
			}
		):
			hosts = get_app_rail_host_map()

		self.assertEqual(hosts.get(self.COMPANION), self.HOST)
		self.assertNotIn(self.OTHER_COMPANION, hosts)

	def test_a_pin_is_arranged_and_hidden_like_any_other_entry(self):
		workspace = self.make_workspace("Test Dock Pin Arranged", ALPHA)
		pin_row = {"type": "Workspace", "name": workspace}

		with shipped_dock({self.COMPANION: [self.pin(workspace)], self.HOST: [sidebar(ALPHA)]}):
			save_site_dock(json.dumps([pin_row, sidebar(ALPHA)]))
			resolved = [
				(r["type"], r["name"], r["hidden"])
				for r in dock_for(self.USER, among=None)
				if r["name"] in (workspace, ALPHA)
			]

		self.assertEqual(resolved, [("Workspace", workspace, 0), ("Sidebar", ALPHA, 0)])

	def test_a_layer_row_naming_a_workspace_outside_the_set_adds_nothing(self):
		"""The layers above the app order and hide; they never add. The entry set is the server's,
		and an arrangement naming something outside it names nothing the dock renders."""
		workspace = self.make_workspace("Test Dock Pin Unpinned", ALPHA)

		with shipped_dock({}):
			save_site_dock(json.dumps([{"type": "Workspace", "name": workspace}]))
			pinned = [row["name"] for row in self.host_dock() if row["type"] == "Workspace"]

		self.assertNotIn(workspace, pinned)


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
