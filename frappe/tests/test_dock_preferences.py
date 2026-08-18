# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
import typing
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import frappe
from frappe.desk.doctype.dock.dock import (
	check_dock_hooks,
	get_site_dock,
	get_site_dock_layer,
	get_user_dock,
	get_user_dock_layer,
	render_dock_hook,
	resolve_dock,
	save_site_dock,
	save_user_dock,
)
from frappe.desk.doctype.sidebar.test_sidebar import developer_mode, make_sidebar, sidebarless_module
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

	These suites reuse the same addresses, so a layer left standing is the next test's mystery
	entry. Deleting the *user* is not enough on its own here, since these layers belong to
	`Administrator`, who is never deleted.

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

	# -- the base may hide ---------------------------------------------------------------

	def test_a_base_row_shipped_hidden_resolves_hidden(self):
		"""The base hides on the same terms as every layer above it. It used to be the one layer
		whose hiding was thrown away, which made "off by default" inexpressible."""
		with shipped_dock({self.APP: [sidebar(ALPHA), sidebar(BETA, hidden=1)]}):
			hidden = hidden_by_name(dock_for(self.USER))

		self.assertEqual(hidden[ALPHA], 0)
		self.assertEqual(hidden[BETA], 1)

	def test_a_person_un_hides_what_the_app_ships_off(self):
		"""Off by default is a default, not a decision the app made for everyone -- and one row
		naming the entry with hiding off is the whole of bringing it back."""
		with shipped_dock({self.APP: [sidebar(BETA, hidden=1)]}):
			frappe.set_user(self.USER)
			save_user_dock(payload(sidebar(BETA, hidden=0)))
			frappe.set_user("Administrator")

			self.assertEqual(hidden_by_name(dock_for(self.USER))[BETA], 0)

	def test_a_hidden_entry_stays_in_the_payload_carrying_its_flag(self):
		"""The dock keeps a hidden entry and the client drops it from the rail -- forced by the
		manager's Hidden pane, which cannot render what the payload has already discarded."""
		with shipped_dock({self.APP: [sidebar(BETA, hidden=1)]}):
			self.assertEqual(dock_for(self.USER), [{"type": "Sidebar", "name": BETA, "hidden": 1}])

	def test_a_base_entry_no_layer_names_trails_the_named_ones_in_base_order(self):
		"""The class the two-class rule had no room for. An entry in the base that no layer
		mentions is *present*, at its real index -- behind everything the layers named and ahead
		of everything nothing names. It is what makes a shipped order apply to the entries nobody
		rearranged.
		"""
		with shipped_dock({self.APP: [sidebar(GAMMA), sidebar(BETA), sidebar(ALPHA)]}):
			save_site_dock(payload(ALPHA))

			# ALPHA is named; GAMMA and BETA are in the base and named by nobody, so they trail
			# it in the order the app shipped them
			self.assertEqual(names(dock_for(self.USER)), [ALPHA, GAMMA, BETA])

	def test_the_walked_case(self):
		"""Ten shipped entries arriving beneath a site that reordered four and hid one."""
		shipped = [f"Test Dock Walk {n}" for n in range(1, 11)]
		with ExitStack() as modules:
			for module in shipped:
				modules.enter_context(sidebarless_module(module))

			with shipped_dock({self.APP: [sidebar(module) for module in shipped]}):
				save_site_dock(
					payload(
						shipped[3],
						shipped[1],
						sidebar(shipped[7], hidden=1),
						shipped[0],
					)
				)
				resolved = dock_for(self.USER, among=shipped)

		self.assertEqual(
			names(resolved),
			# the site's four in the site's order, then the six it never named in base order
			[shipped[3], shipped[1], shipped[7], shipped[0], *[shipped[i] for i in (2, 4, 5, 6, 8, 9)]],
		)
		self.assertEqual(hidden_by_name(resolved)[shipped[7]], 1)

	def test_the_app_layer_read_carries_the_hidden_flag(self):
		"""What the manager reads to say *who* hid a row. `declared_by` stays behind: which app
		declared an entry is the projection Ship needs, not the editor."""
		from frappe.desk.doctype.dock.dock import get_app_dock_layer

		with shipped_dock({self.APP: [sidebar(ALPHA), sidebar(BETA, hidden=1)]}):
			self.assertEqual(
				get_app_dock_layer(),
				[
					{"type": "Sidebar", "name": ALPHA, "hidden": 0},
					{"type": "Sidebar", "name": BETA, "hidden": 1},
				],
			)

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


class TestEmitDockHook(DockTestCase):
	"""Ship: the arrangement on screen, rendered as the block that would produce it.

	Nothing is written. The target is `hooks.py` -- hand-authored Python with comments and
	conditionals, which the framework writes exactly once, at `bench new-app`.
	"""

	APP = "frappe"
	COMPANION = "zz-dock-emit-companion"

	def setUp(self):
		frappe.set_user("Administrator")
		# emit is gated on developer mode at both ends, and a test site is not a developer's
		# site -- the one test that asserts the gate turns it back off for itself
		self.enterContext(developer_mode())

	def tearDown(self):
		frappe.set_user("Administrator")
		clear_arrangements()

	def emit(self, *rows, app=None):
		from frappe.desk.doctype.dock.dock import emit_dock_hook

		return emit_dock_hook(app=app or self.APP, items=json.dumps(list(rows)))

	def test_the_block_names_every_entry_the_manager_showed(self):
		"""Left pane as positions, right pane as hidden -- which is what makes ship round-trip."""
		emitted = self.emit(sidebar(BETA), sidebar(ALPHA), sidebar(GAMMA, hidden=1))

		self.assertEqual(
			emitted["code"],
			"add_to_dock = [\n"
			'\t{"type": "Sidebar", "name": "Test Dock Beta"},\n'
			'\t{"type": "Sidebar", "name": "Test Dock Alpha"},\n'
			'\t{"type": "Sidebar", "name": "Test Dock Gamma", "hidden": 1},\n'
			"]",
		)
		self.assertEqual(emitted["path"], "apps/frappe/frappe/hooks.py")
		self.assertEqual(emitted["dropped"], [])

	def test_the_block_round_trips_through_the_hook(self):
		"""Paste, restart, and the dock renders the screen it was taken from."""
		emitted = self.emit(sidebar(GAMMA), sidebar(BETA), sidebar(ALPHA, hidden=1))

		# what the author would have in `hooks.py` after pasting, read back as a fragment
		fragment = [
			{"type": "Sidebar", "name": GAMMA},
			{"type": "Sidebar", "name": BETA},
			{"type": "Sidebar", "name": ALPHA, "hidden": 1},
		]
		self.assertEqual(emitted["code"], render_dock_hook(fragment))

		with shipped_dock({self.APP: fragment}):
			resolved = dock_for(among=TRIO)

		self.assertEqual(names(resolved), [GAMMA, BETA, ALPHA])
		self.assertEqual(hidden_by_name(resolved)[ALPHA], 1)

	def test_a_foreign_row_is_dropped_and_named(self):
		"""A projection, not a refusal: the pin is already declared in the companion's own
		`hooks.py`, and where it sits on screen is layer business no block can state."""
		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "Test Dock Emit Pin",
				"label": "Test Dock Emit Pin",
				"module": ALPHA,
				"public": 1,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", workspace.name, force=True, ignore_missing=True)

		pin = {"type": "Workspace", "name": workspace.name, "app": self.APP}
		with shipped_dock({self.COMPANION: [pin], self.APP: [sidebar(BETA), sidebar(ALPHA)]}):
			emitted = self.emit(sidebar(BETA), {"type": "Workspace", "name": workspace.name}, sidebar(ALPHA))

		self.assertEqual(
			emitted["code"],
			"add_to_dock = [\n"
			'\t{"type": "Sidebar", "name": "Test Dock Beta"},\n'
			'\t{"type": "Sidebar", "name": "Test Dock Alpha"},\n'
			"]",
		)
		self.assertEqual(
			emitted["dropped"],
			[{"type": "Workspace", "name": workspace.name, "declared_by": self.COMPANION}],
		)

	def test_a_multi_app_screen_is_legal(self):
		"""The old "one app, else throw" guard is not carried over -- a pin makes a multi-app
		screen legal, and refusing one would refuse exactly the case this exists for."""
		emitted = self.emit(sidebar(ALPHA), sidebar(BETA), sidebar(GAMMA))
		self.assertEqual(emitted["app"], "frappe")

	def test_the_app_is_resolved_from_the_rows_not_the_client(self):
		"""`app` names the screen and decides nothing: it is the apps-screen title key, which an
		app may set to something other than the app its files live in."""
		emitted = self.emit(sidebar(ALPHA), app="Not An App At All")
		self.assertEqual(emitted["app"], "frappe")
		self.assertEqual(emitted["path"], "apps/frappe/frappe/hooks.py")

	def test_an_empty_screen_is_refused(self):
		from frappe.desk.doctype.dock.dock import emit_dock_hook

		self.assertRaises(frappe.ValidationError, emit_dock_hook, app=self.APP, items="[]")

	def test_a_non_developer_site_is_refused(self):
		from frappe.desk.doctype.dock.dock import emit_dock_hook

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			self.assertRaises(frappe.ValidationError, emit_dock_hook, app=self.APP, items=payload(ALPHA))


class TestTheAppsEntrySet(IntegrationTestCase):
	"""The order an app's modules take when nothing arranges them.

	Not the arrangement: where a module *sits* is `add_to_dock`, an ordered list in the app's
	`hooks.py`. This is the entry set that list orders, and an entry it never names trails the
	ones it does, in this order.
	"""

	def app_order(self, app: str = "frappe") -> list[str]:
		from frappe.boot import get_app_modules

		return get_app_modules(app)

	def test_modules_txt_position_leads_and_the_name_breaks_the_tie(self):
		"""Two tiers, not three. Collapsing to name alone would alphabetise the trailing set,
		which would be a behaviour change smuggled into a field deletion."""
		declared = frappe.get_module_list("frappe")
		order = self.app_order()

		in_txt = [module for module in order if module in declared]
		self.assertEqual(in_txt, sorted(in_txt, key=declared.index))

		with (
			sidebarless_module("Test Entry Set B") as second,
			sidebarless_module("Test Entry Set A") as first,
		):
			# neither is in modules.txt, so both land in the trailing tier and the name decides
			order = self.app_order()
			self.assertLess(order.index(first), order.index(second))

	def test_a_module_with_no_sidebar_document_is_in_the_set(self):
		"""Most modules have a computed base and no document at all. Stating where one sits no
		longer needs a stub `Sidebar` to carry a float -- an ordered list needs no document."""
		with sidebarless_module("Test Entry Set Computed") as module:
			self.assertFalse(frappe.db.exists("Sidebar", {"module": module}))
			self.assertIn(module, self.app_order())

	def test_the_sidebar_no_longer_carries_a_sequence(self):
		"""`Sidebar.sequence_id` did not order a sidebar -- it ordered modules on the dock, from
		a document homed on something else. It and its middle default came out together, because
		they are one mechanism."""
		import frappe.boot as boot

		self.assertIsNone(frappe.get_meta("Sidebar").get_field("sequence_id"))
		self.assertFalse(hasattr(boot, "DEFAULT_MODULE_SEQUENCE_ID"))
		# the apps-screen one stays: it orders the thing it lives on
		self.assertTrue(hasattr(boot, "DEFAULT_APP_SEQUENCE_ID"))


class TestTheFrameworksTen(IntegrationTestCase):
	"""The framework declaring its own dock order as ten typed rows.

	A transcription, not an extension: the ten are what the framework already declared through
	eleven exported `Sidebar` documents, and `Geo` and `System` stay unnamed and trail exactly as
	they did -- System's exported value read as the default, so it trailed beside Geo. The dock
	renders identically before and after.
	"""

	TEN: typing.ClassVar[list[str]] = [
		"Build Tools",
		"Users",
		"Email",
		"Website",
		"Data",
		"Workflow",
		"Printing",
		"Integrations",
		"Contacts",
		"Automation",
	]

	def test_frappe_declares_its_ten(self):
		self.assertEqual(
			frappe.get_hooks("add_to_dock", app_name="frappe"),
			[{"type": "Sidebar", "name": module} for module in self.TEN],
		)

	def test_the_walked_case_renders_the_same_dock(self):
		"""Fifteen modules in, ten named, three code-only dropped by the client, Geo and System
		trailing -- in `modules.txt` order, which is where they already were."""
		from frappe.boot import get_app_modules
		from frappe.utils.modules import get_code_only_modules

		frappe.set_user("Administrator")
		clear_arrangements()

		resolved = [row["name"] for row in resolve_dock() if row["type"] == "Sidebar"]
		entry_set = get_app_modules("frappe")

		# the ten lead, in the order the hook declares them
		self.assertEqual([name for name in resolved if name in self.TEN], self.TEN)

		# ...and the entries nothing names are absent from the arrangement, so the client keeps
		# them in the app's own order behind the ten. Code-only modules are filtered client-side,
		# as they already were, so they are still in the entry set here.
		#
		# Narrowed to the modules `modules.txt` declares: a bench that has run the full suite
		# carries stray `Module Def` rows, and this is an assertion about the framework's fifteen.
		declared = set(frappe.get_module_list("frappe"))
		unnamed = [name for name in entry_set if name in declared and name not in self.TEN]
		self.assertEqual([name for name in resolved if name in unnamed], [])
		self.assertEqual([name for name in unnamed if name not in get_code_only_modules()], ["Geo", "System"])


class TestTheHookIsChecked(IntegrationTestCase):
	"""What an app author is told when a row they wrote will never render.

	The boot leaves out a row it does not understand, which is right at boot -- one bad row must
	not cost an app its whole rail -- but on its own it means a typo produces no error and no
	button. `check_dock_hooks` is the other half, run at migrate.
	"""

	def problems(self, rows) -> list[str]:
		with shipped_dock({"frappe": rows}):
			return check_dock_hooks()

	def test_a_good_fragment_says_nothing(self):
		with sidebarless_module("Test Checked Module") as module:
			self.assertEqual(self.problems([sidebar(module)]), [])

	def test_a_bare_name_is_not_a_row(self):
		problems = self.problems(["Test Checked Module"])

		self.assertEqual(len(problems), 1)
		self.assertIn("not a row", problems[0])

	def test_an_unknown_kind_is_named(self):
		problems = self.problems([{"type": "Module", "name": "Users"}])

		self.assertEqual(len(problems), 1)
		self.assertIn("Module", problems[0])

	def test_a_row_naming_nothing_is_reported(self):
		problems = self.problems([{"type": "Sidebar"}])

		self.assertEqual(len(problems), 1)
		self.assertIn("names nothing", problems[0])

	def test_a_module_that_does_not_exist_is_reported(self):
		"""The typo an author is most likely to make, and the one the boot is quietest about:
		the row is well formed, so it survives every shape check and then resolves to nothing."""
		problems = self.problems([sidebar("Test Module That Is Not Here")])

		self.assertEqual(len(problems), 1)
		self.assertIn("Module Def that does not exist", problems[0])

	def test_a_pin_at_an_app_that_is_not_installed_is_not_a_problem(self):
		"""Silence by design: a companion may be installed before or without its host, and the
		row is correct in both cases."""
		self.assertEqual(self.problems([{"type": "Workspace", "name": "Anything", "app": "not-an-app"}]), [])

	def test_the_frameworks_own_fragment_is_clean(self):
		"""The check is only worth running if what we ship passes it."""
		self.assertEqual(check_dock_hooks(), [])
