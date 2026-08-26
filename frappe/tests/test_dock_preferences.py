# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
import os
import shutil
import tempfile
import typing
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import frappe
from frappe.boot import get_app_modules, get_module_sidebars
from frappe.desk.doctype.dock.dock import (
	Dock,
	check_dock_hooks,
	create_module,
	destination,
	dock_key,
	get_app_dock,
	get_site_dock,
	get_site_dock_layer,
	get_user_dock,
	get_user_dock_layer,
	mark_as_standard,
	render_dock_hook,
	resolve_dock,
	save_site_dock,
	save_user_dock,
	stored_row,
	unmark_as_standard,
)
from frappe.desk.doctype.sidebar.sidebar import (
	DEFAULT_HEADER_ICON,
	SYSTEM_WRITE_FLAGS,
	resolve_sidebar,
)
from frappe.desk.doctype.sidebar.test_sidebar import (
	developer_mode,
	make_sidebar,
	no_developer_mode,
	sidebarless_module,
	system_write,
)
from frappe.model.sync import remove_orphan_entities
from frappe.tests import IntegrationTestCase

USER = "test-dock-prefs@example.com"

# The modules these suites arrange -- their own, rather than three of the framework's. An app
# fragment is free to name the framework's modules, and once an app ships one every site has a
# base that does, so borrowing them made every assertion here depend on what somebody else had
# shipped. These three are created by the suite and named by nothing else.
# The app these suites arrange the dock of. A `Dock` layer is per app, so every read and every
# write names one; the suite's three modules are frappe's, so frappe's is the dock they are on.
APP = "frappe"

ALPHA = "Test Dock Alpha"
BETA = "Test Dock Beta"
GAMMA = "Test Dock Gamma"
TRIO = [ALPHA, BETA, GAMMA]


def sidebar(module, hidden=None, **kwargs) -> dict:
	"""One row naming a module's shell -- the shape a layer stores and a client sends.

	A shell row fills `sidebar` and nothing else: the button selects that shell and opens its own
	landing route. A sidebar's name defaults to its module's name, so the module is the whole of it.
	"""
	row = {"sidebar": module, **kwargs}
	if hidden is not None:
		row["hidden"] = hidden
	return row


def workspace(name, hidden=None, **kwargs) -> dict:
	"""One row opening a workspace. The shell it selects is derived from the module that owns it
	unless the row names one."""
	row = {"link_type": "Workspace", "link_to": name, **kwargs}
	if hidden is not None:
		row["hidden"] = hidden
	return row


def hook_sidebar(module, hidden=None) -> dict:
	"""The same row in the `add_to_dock` spelling -- the typed pair the hook still speaks, which
	every reader translates on the way in until 08 drops the columns."""
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


def stored(row, **overrides) -> dict:
	"""One row as a layer stores and reads it back: the whole destination, how it reads, and
	whether it is hidden. Filled out here rather than in each assertion, so a column added to the
	schema shows up as one edit rather than thirty."""
	return {
		"sidebar": None,
		"link_type": None,
		"link_to": None,
		"url": None,
		"icon": None,
		"title": None,
		"added": 0,
		"hidden": 0,
		**row,
		**overrides,
	}


def entry(row, **overrides) -> dict:
	"""One row as the rail is handed it: the destination and how it reads, with no `added` flag --
	that one says how the row got here, which is a fact about the layer rather than about the
	button."""
	shaped = stored(row, **overrides)
	shaped.pop("added")
	return shaped


def names(rows) -> list[str]:
	"""What each row points at, as one readable string: the shell it names, else its target."""
	return [row.get("sidebar") or row.get("link_to") or row.get("url") for row in rows]


def hidden_by_name(rows) -> dict[str, int]:
	return dict(zip(names(rows), [row["hidden"] for row in rows], strict=True))


def dock_for(email=None, among=TRIO, app=APP):
	"""One app's resolved rail as `email` sees it, narrowed to the modules a test named.

	Three things this hides. `resolve_dock` answers for the session user, so the only way to ask
	about somebody else is to be them for a moment. It answers for every app at once, keyed by
	app, and a suite arranges one. And the base is whatever the site's apps ship, which is not a
	suite about the site and user layers to control -- narrowing to the suite's own modules keeps
	the order it asserts while leaving the rest of the rail alone.
	"""
	if email:
		frappe.set_user(email)
	try:
		rows = resolve_dock().get(app, [])
	finally:
		if email:
			frappe.set_user("Administrator")

	if among is None:
		return rows
	return [row for row in rows if row.get("sidebar") in set(among)]


def clear_arrangements():
	"""The site's layer and every person's own, gone -- at every app.

	These suites reuse the same addresses, so a layer left standing is the next test's mystery
	entry. Deleting the *user* is not enough on its own here, since these layers belong to
	`Administrator`, who is never deleted.

	**Standard rows are left alone.** Those are what an app ships, they are backed by files in
	the working tree, and sweeping them would delete frappe's own dock from the site -- which no
	suite here means to do and only `TestTheExportRoad` ever creates.
	"""
	clear_arrangements_for(standard=0)


def clear_arrangements_for(app=None, standard=None):
	"""Dock rows matching an address, gone. Deleted through the document so each one invalidates
	the boot cache it belongs to."""
	filters = {}
	if app is not None:
		filters["app"] = app
	if standard is not None:
		filters["standard"] = standard

	for name in frappe.get_all("Dock", filters=filters, pluck="name"):
		frappe.delete_doc("Dock", name, force=True, ignore_permissions=True)


@contextmanager
def app_rooted_at(app, root):
	"""Pretend `app` is on this bench with its files under `root`.

	The export road writes into `frappe.get_app_path(app)`, and a suite about that road must not
	write into a real app on the bench -- frappe ships a dock of its own, and a test that marked
	and unmarked it would delete the file from the working tree.

	Four reads are redirected: the path the export writes to, the installed list
	`validate_standard` checks, the active list `check_docked_app` checks, and the hooks read --
	an invented app has no `hooks.py` to import, and asking for one raises.
	`_ensure_on_bench` is deliberately left alone, exactly as `shipped_dock` leaves it: callers
	who ask that question want apps that really are directories, and this one is not.
	"""
	real_path = frappe.get_app_path
	real_installed = frappe.get_installed_apps
	real_active = frappe.get_active_apps
	real_hooks = frappe.get_hooks

	def app_path(app_name, *joins):
		return os.path.join(root, *joins) if app_name == app else real_path(app_name, *joins)

	def installed(*args, **kwargs):
		return [*real_installed(*args, **kwargs), app]

	def active(*args, _ensure_on_bench=False, **kwargs):
		apps = real_active(*args, _ensure_on_bench=_ensure_on_bench, **kwargs)
		return apps if _ensure_on_bench else [*apps, app]

	def hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		return [] if app_name == app else real_hooks(hook, default, app_name)

	with (
		patch.object(frappe, "get_app_path", app_path),
		patch.object(frappe, "get_installed_apps", installed),
		patch.object(frappe, "get_active_apps", active),
		patch.object(frappe, "get_hooks", hooks),
	):
		yield root


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
		save_user_dock(APP, payload(GAMMA, ALPHA, BETA))
		self.assertEqual(names(dock_for()), [GAMMA, ALPHA, BETA])

	def test_the_resolved_dock_carries_the_typed_pair(self):
		"""What an entry points at is a kind and a name together, at every layer and in the
		payload -- never one column whose being filled is the kind."""
		save_user_dock(APP, payload(ALPHA))

		self.assertEqual(dock_for(), [entry(sidebar(ALPHA))])
		self.assertEqual(get_user_dock_layer(APP), [stored(sidebar(ALPHA))])

	def test_hidden_is_stored_not_omitted(self):
		"""An explicitly hidden module has to persist as a row. Storing "hidden" as mere
		absence would let it reappear the moment its app adds another module."""
		save_user_dock(APP, payload(sidebar(ALPHA, hidden=0), sidebar(GAMMA, hidden=1)))
		rows = hidden_by_name(dock_for())
		self.assertEqual(rows[ALPHA], 0)
		self.assertEqual(rows[GAMMA], 1)

	def test_a_row_that_names_nothing_is_dropped(self):
		"""A row names a shell, a page, or both. One that names neither says nothing at all --
		and a `link_type` with no target is as anchorless as a blank row. Dropped rather than
		refused, the way a row naming nothing has always been."""
		save_user_dock(
			APP,
			json.dumps([sidebar(ALPHA), {}, GAMMA, {"link_type": "Workspace"}, {"link_type": "URL"}]),
		)
		self.assertEqual(names(dock_for()), [ALPHA])

	def test_a_destination_column_that_is_not_a_string_is_dropped(self):
		"""These rows are client JSON, so no column can be taken on trust. A dict reaching the
		existence lookup would be read as *filters* rather than as a name."""
		save_user_dock(
			APP,
			json.dumps(
				[
					sidebar(ALPHA),
					{"sidebar": {"like": "%"}},
					{"link_type": ["Workspace"], "link_to": BETA},
					{"sidebar": 7},
				]
			),
		)
		self.assertEqual(names(dock_for()), [ALPHA])

	def test_duplicates_are_collapsed(self):
		save_user_dock(APP, payload(ALPHA, ALPHA, BETA))
		self.assertEqual(names(dock_for()), [ALPHA, BETA])

	def test_unknown_module_is_dropped(self):
		save_user_dock(APP, payload(ALPHA, "No Such Module"))
		self.assertEqual(names(dock_for()), [ALPHA])

	def test_a_row_opening_a_kind_the_dock_does_not_have_is_dropped(self):
		"""Only a `Workspace` or a web address. A Report or a DocType list belongs inside a
		module's sidebar, not on a rail of roughly a dozen destinations."""
		save_user_dock(APP, json.dumps([sidebar(ALPHA), {"link_type": "Report", "link_to": "ToDo"}]))
		self.assertEqual(names(dock_for()), [ALPHA])
		self.assertEqual(names(get_user_dock_layer(APP)), [ALPHA])

	def test_curation_cannot_resurface_a_blocked_module(self):
		"""A dock arrangement is a preference, never a way around module visibility."""
		frappe.set_user("Administrator")
		user = frappe.get_doc("User", USER)
		user.append("block_modules", {"module": GAMMA})
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=USER)
		frappe.set_user(USER)

		save_user_dock(APP, payload(ALPHA, GAMMA))
		self.assertEqual(names(dock_for()), [ALPHA])

	def test_saving_replaces_rather_than_appends(self):
		"""The client sends the whole arrangement, not a delta -- the shape a Sortable makes."""
		save_user_dock(APP, payload(ALPHA, BETA, GAMMA))
		save_user_dock(APP, payload(BETA))
		self.assertEqual(names(dock_for()), [BETA])

	def test_boot_exposes_the_curation(self):
		from frappe.boot import get_bootinfo

		save_user_dock(APP, payload(BETA, ALPHA))
		carried = [r["sidebar"] for r in get_bootinfo().get("dock")[APP] if r["sidebar"] in set(TRIO)]
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
		save_site_dock(APP, payload(*rows))
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
		save_user_dock(APP, payload(GAMMA))

		# what they named comes first; the site's arrangement of the rest survives underneath
		self.assertEqual(names(dock_for(self.DESK_USER)), [GAMMA, BETA, ALPHA])

	def test_a_user_can_unhide_what_the_site_hid(self):
		"""Later layers win on hiding too, which is the whole reason to have a second one."""
		self.set_site_order(sidebar(BETA, hidden=1), sidebar(ALPHA, hidden=0))
		self.assertEqual(hidden_by_name(dock_for(self.DESK_USER))[BETA], 1)

		frappe.set_user(self.DESK_USER)
		save_user_dock(APP, payload(sidebar(BETA, hidden=0)))
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
		self.assertRaises(frappe.PermissionError, save_site_dock, APP, payload(ALPHA))

		frappe.set_user(self.MANAGER)
		save_site_dock(APP, payload(ALPHA, BETA))
		frappe.set_user("Administrator")
		self.assertEqual(names(get_site_dock(APP)), [ALPHA, BETA])

	def test_only_a_workspace_manager_may_read_the_site_layer(self):
		self.set_site_order(ALPHA)

		frappe.set_user(self.DESK_USER)
		self.assertRaises(frappe.PermissionError, get_site_dock_layer, APP)

		frappe.set_user(self.MANAGER)
		self.assertEqual(names(get_site_dock_layer(APP)), [ALPHA])

	def test_a_site_save_keeps_rows_for_modules_the_saver_cannot_see(self):
		"""Site intent outlives one manager's blocked module.

		Filtering a site write by the saver's own visibility would let a Workspace Manager who
		happens to be blocked from a module silently delete the site's arrangement of it for
		everyone. Visibility is applied when the dock is resolved instead -- so the row stays,
		and it still does not show up on that manager's own dock.
		"""
		self.block_module(self.MANAGER, GAMMA)

		frappe.set_user(self.MANAGER)
		save_site_dock(APP, payload(GAMMA, ALPHA))
		frappe.set_user("Administrator")

		self.assertEqual(names(get_site_dock(APP)), [GAMMA, ALPHA])
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
		save_user_dock(APP, payload(ALPHA))

		self.assertEqual(names(get_user_dock_layer(APP)), [ALPHA])
		self.assertEqual(names(get_user_dock(APP)), [ALPHA])
		self.assertEqual(names(dock_for()), [ALPHA, BETA])

	def test_both_writable_layers_round_trip_typed_rows(self):
		"""Written as a pair, read back as a pair -- at the site's layer and at a person's own."""
		self.set_site_order(BETA)

		frappe.set_user(self.DESK_USER)
		save_user_dock(APP, payload(ALPHA))
		frappe.set_user("Administrator")

		self.assertEqual(get_site_dock(APP), [stored(sidebar(BETA))])
		self.assertEqual(get_user_dock(APP, self.DESK_USER), [stored(sidebar(ALPHA))])

	def test_boot_carries_the_resolved_dock(self):
		from frappe.boot import get_bootinfo

		self.set_site_order(BETA, ALPHA)

		frappe.set_user(self.DESK_USER)
		carried = [r["sidebar"] for r in get_bootinfo().get("dock")[APP] if r["sidebar"] in set(TRIO)]
		self.assertEqual(carried, [BETA, ALPHA])

	def test_every_layer_is_one_shape(self):
		"""One doctype at all three layers, because the rows are identical -- `app`, `user` and
		`standard` are the whole difference, and the parent is what names the layer."""
		self.set_site_order(ALPHA)

		frappe.set_user(self.DESK_USER)
		save_user_dock(APP, payload(BETA))
		frappe.set_user("Administrator")

		# the two writable layers, which is what "every layer is one shape" is about -- the app's
		# own row is in this same table and is told apart by `standard`
		layers = frappe.get_all("Dock", filters={"standard": 0}, fields=["app", "user"])
		self.assertEqual(sorted(row.user or "" for row in layers), ["", self.DESK_USER])
		self.assertEqual({row.app for row in layers}, {APP})
		self.assertEqual(frappe.get_meta("Dock").get_field("items").options, "Dock Item")

	def test_a_layer_exists_once(self):
		"""Two documents at one address would give the merge two answers for the same layer, so
		the constraint is an index rather than a `validate` hook a bulk write can be talked past.
		"""
		self.set_site_order(ALPHA)

		duplicate = frappe.new_doc("Dock")
		duplicate.app = APP
		self.assertRaises(frappe.UniqueValidationError, duplicate.insert)


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
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [BETA, ALPHA])

	def test_the_hook_still_answers_for_an_app_that_ships_no_record(self):
		"""The expand half of the pair 07 contracts: an app that has re-exported its dock is read
		from the document, and one that has not keeps its fragment working meanwhile."""
		with self.ship(BETA, ALPHA):
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [BETA, ALPHA])
			self.assertFalse(
				frappe.get_all("Dock", filters={"app": self.APP}),
				"this app ships no record, so its base is the hook and stores nothing",
			)

	def test_each_apps_fragment_is_its_own_rail(self):
		"""A fragment says nothing about another app's, and now nothing concatenates them either:
		a rail is one app's, so the two are resolved apart and keyed apart in the payload."""
		with shipped_dock({self.APP: [sidebar(BETA), sidebar(ALPHA)], self.OTHER_APP: [sidebar(GAMMA)]}):
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [BETA, ALPHA])
			self.assertEqual(names(dock_for(self.USER, app=self.OTHER_APP)), [GAMMA])

	def test_one_fragment_naming_one_module_twice_renders_it_once(self):
		"""The base is copied into the merge whole, so a duplicate there is never deduped above
		it. The first row to name an entry keeps it, as a layer does for a row it sees twice."""
		with shipped_dock({self.APP: [sidebar(BETA), sidebar(ALPHA), sidebar(BETA)]}):
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [BETA, ALPHA])

	def test_two_apps_arrangements_do_not_touch_each_other(self):
		"""The whole of what a per-app record buys: arranging one rail leaves the other alone,
		and neither save has to carry the other app's rows through untouched."""
		with shipped_dock(
			{self.APP: [sidebar(BETA), sidebar(ALPHA)], self.OTHER_APP: [sidebar(GAMMA), sidebar(ALPHA)]}
		):
			save_site_dock(self.APP, payload(ALPHA))

			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [ALPHA, BETA])
			self.assertEqual(names(dock_for(self.USER, app=self.OTHER_APP)), [GAMMA, ALPHA])
			self.assertEqual(names(get_site_dock(self.OTHER_APP)), [])

	def test_the_site_arranges_what_the_app_shipped(self):
		with self.ship(BETA, ALPHA, GAMMA):
			save_site_dock(self.APP, payload(GAMMA))

			# what the site named comes first; the app's order of the rest survives underneath
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [GAMMA, BETA, ALPHA])

	def test_a_person_arranges_what_the_site_left(self):
		with self.ship(BETA, ALPHA, GAMMA):
			save_site_dock(self.APP, payload(GAMMA))

			frappe.set_user(self.USER)
			save_user_dock(self.APP, payload(ALPHA))
			frappe.set_user("Administrator")

			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [ALPHA, GAMMA, BETA])

	def test_a_module_the_app_added_later_still_reaches_someone_who_has_arranged(self):
		"""An entry no layer names trails the ones they did, rather than dropping out."""
		with self.ship(BETA, ALPHA, GAMMA):
			save_site_dock(self.APP, payload(GAMMA, BETA))

			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [GAMMA, BETA, ALPHA])

	def test_hiding_survives_the_app_adding_a_module(self):
		"""Hiding is a decision, not the absence of a row -- so a later fragment cannot undo it."""
		with self.ship(BETA, ALPHA):
			save_site_dock(self.APP, payload(sidebar(BETA, hidden=1)))

			hidden = hidden_by_name(dock_for(self.USER, app=self.APP))
			self.assertEqual(hidden[BETA], 1)
			self.assertEqual(hidden[ALPHA], 0)

	def test_a_row_naming_a_kind_the_dock_does_not_have_is_dropped_from_the_base(self):
		"""`type` is an open Link to `DocType`, so the whitelist is what closes the set at every
		layer -- including the one an app writes by hand."""
		with shipped_dock({self.APP: [{"link_type": "Report", "link_to": "ToDo"}, sidebar(ALPHA)]}):
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [ALPHA])

	def test_a_base_row_naming_nothing_says_nothing(self):
		"""A row names a shell, a page, or both. One that names neither is not an entry."""
		with shipped_dock({self.APP: [sidebar(ALPHA), {}, {"link_type": "Workspace"}, BETA]}):
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [ALPHA])

	def test_a_module_with_no_sidebar_document_is_still_nameable(self):
		"""Most modules have a computed base and no `Sidebar` document at all, so a row is proved
		by the module rather than by the record its `type` names -- and link validation on a
		`Dock` row is a deliberate no-op for the same reason."""
		self.assertFalse(frappe.db.exists("Sidebar", ALPHA), "sanity: this module ships no sidebar")

		with self.ship(ALPHA):
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [ALPHA])

			save_site_dock(self.APP, payload(ALPHA))
			self.assertEqual(names(get_site_dock(self.APP)), [ALPHA])

	# -- the base may hide ---------------------------------------------------------------

	def test_a_base_row_shipped_hidden_resolves_hidden(self):
		"""The base hides on the same terms as every layer above it. It used to be the one layer
		whose hiding was thrown away, which made "off by default" inexpressible."""
		with shipped_dock({self.APP: [sidebar(ALPHA), sidebar(BETA, hidden=1)]}):
			hidden = hidden_by_name(dock_for(self.USER, app=self.APP))

		self.assertEqual(hidden[ALPHA], 0)
		self.assertEqual(hidden[BETA], 1)

	def test_a_person_un_hides_what_the_app_ships_off(self):
		"""Off by default is a default, not a decision the app made for everyone -- and one row
		naming the entry with hiding off is the whole of bringing it back."""
		with shipped_dock({self.APP: [sidebar(BETA, hidden=1)]}):
			frappe.set_user(self.USER)
			save_user_dock(self.APP, payload(sidebar(BETA, hidden=0)))
			frappe.set_user("Administrator")

			self.assertEqual(hidden_by_name(dock_for(self.USER, app=self.APP))[BETA], 0)

	def test_a_hidden_entry_stays_in_the_payload_carrying_its_flag(self):
		"""The dock keeps a hidden entry and the client drops it from the rail -- forced by the
		manager's Hidden pane, which cannot render what the payload has already discarded."""
		with shipped_dock({self.APP: [sidebar(BETA, hidden=1)]}):
			self.assertEqual(dock_for(self.USER, app=self.APP), [entry(sidebar(BETA), hidden=1)])

	def test_a_base_entry_no_layer_names_trails_the_named_ones_in_base_order(self):
		"""The class the two-class rule had no room for. An entry in the base that no layer
		mentions is *present*, at its real index -- behind everything the layers named and ahead
		of everything nothing names. It is what makes a shipped order apply to the entries nobody
		rearranged.
		"""
		with shipped_dock({self.APP: [sidebar(GAMMA), sidebar(BETA), sidebar(ALPHA)]}):
			save_site_dock(self.APP, payload(ALPHA))

			# ALPHA is named; GAMMA and BETA are in the base and named by nobody, so they trail
			# it in the order the app shipped them
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [ALPHA, GAMMA, BETA])

	def test_the_walked_case(self):
		"""Ten shipped entries arriving beneath a site that reordered four and hid one."""
		shipped = [f"Test Dock Walk {n}" for n in range(1, 11)]
		with ExitStack() as modules:
			for module in shipped:
				modules.enter_context(sidebarless_module(module))

			with shipped_dock({self.APP: [sidebar(module) for module in shipped]}):
				save_site_dock(
					self.APP,
					payload(
						shipped[3],
						shipped[1],
						sidebar(shipped[7], hidden=1),
						shipped[0],
					),
				)
				resolved = dock_for(self.USER, among=shipped, app=self.APP)

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
				get_app_dock_layer(self.APP),
				[entry(sidebar(ALPHA)), entry(sidebar(BETA), hidden=1)],
			)

	def test_a_site_whose_apps_declare_nothing_resolves_an_empty_base(self):
		"""Adopting the hook is a choice: an app that declares none leaves the site layer as the
		first there is, exactly as it was before the base existed."""
		with shipped_dock({self.APP: []}):
			self.assertEqual(dock_for(self.USER, among=None, app=self.APP), [])

			save_site_dock(self.APP, payload(BETA, ALPHA))
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [BETA, ALPHA])

	def test_a_sidebar_and_a_workspace_of_the_same_name_are_different_entries(self):
		"""Identity is the pair, so one name under two kinds is two entries rather than one."""
		from frappe.desk.doctype.dock.dock import dock_key

		self.assertNotEqual(dock_key(sidebar("Stock")), dock_key(workspace("Stock")))

	def test_a_workspace_entry_round_trips_beside_a_sidebar_of_the_same_name(self):
		"""The destination all the way through: stored, resolved and read back as two entries."""
		page = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": ALPHA,
				"label": ALPHA,
				"module": ALPHA,
				"public": 1,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", page.name, force=True, ignore_missing=True)

		with shipped_dock({self.APP: []}):
			save_site_dock(self.APP, payload(workspace(ALPHA), sidebar(ALPHA)))

			self.assertEqual(get_site_dock(self.APP), [stored(workspace(ALPHA)), stored(sidebar(ALPHA))])
			self.assertEqual(
				[
					(r["sidebar"], r["link_to"])
					for r in dock_for(among=None, app=self.APP)
					if ALPHA in (r["sidebar"], r["link_to"])
				],
				[(None, ALPHA), (ALPHA, None)],
			)


class TestTheRowShape(DockTestCase):
	"""What a dock row can say, now that it has real columns.

	A click does two things -- it opens a page and it swaps the shell -- and each exists without
	the other. That is the whole reason `sidebar` and `link_type`/`link_to`/`url` are separate
	columns rather than one typed pair whose being filled was the kind.
	"""

	USER = "test-dock-row-shape@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("User", self.USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self.USER,
					"first_name": "Dock Row Shape",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		clear_arrangements()

	def make_workspace(self, title, module, public=1):
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": title,
				"module": module,
				"public": public,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", doc.name, force=True, ignore_missing=True)
		# `get_workspaces` is request-cached, and a page created after it was first asked would
		# otherwise be one nobody may open for the rest of this request
		frappe.local.request_cache.clear()
		return doc.name

	# -- what a row may say --------------------------------------------------------------

	def test_a_row_may_name_a_shell_a_page_or_both(self):
		page = self.make_workspace("Test Dock Shape Page", ALPHA)

		save_site_dock(
			APP,
			payload(sidebar(ALPHA), workspace(page), sidebar(BETA, link_type="Workspace", link_to=page)),
		)

		self.assertEqual(
			[(r["sidebar"], r["link_to"]) for r in get_site_dock(APP)],
			[(ALPHA, None), (None, page), (BETA, page)],
		)

	def test_two_rows_into_one_module_key_apart(self):
		"""`Stock` and `Stock Analytics`: the module's own button, and a second button into the
		same shell that opens a particular page."""
		page = self.make_workspace("Test Dock Shape Second", ALPHA)

		save_site_dock(APP, payload(sidebar(ALPHA), sidebar(ALPHA, link_type="Workspace", link_to=page)))

		rows = get_site_dock(APP)
		self.assertEqual(len(rows), 2)
		self.assertNotEqual(dock_key(rows[0]), dock_key(rows[1]))

	def test_a_url_row_needs_no_shell(self):
		save_site_dock(
			APP, payload({"link_type": "URL", "url": "https://frappe.io", "title": "Docs", "icon": "book"})
		)

		row = get_site_dock(APP)[0]
		self.assertEqual((row["sidebar"], row["url"], row["title"]), (None, "https://frappe.io", "Docs"))
		# it renders on the rail, and it comes out of the merge carrying its own label
		rendered = next(r for r in dock_for(among=None) if r["url"])
		self.assertEqual(
			(rendered["url"], rendered["title"], rendered["sidebar"]), (row["url"], "Docs", None)
		)

	def test_a_row_may_name_a_shell_other_than_the_one_that_owns_its_page(self):
		"""The override. Left blank, the shell is derived from the module that owns the page --
		which is right for a pin and wrong for a page whose own module is on no rail. Naming one
		is what the second column exists for, and it survives resolution rather than being
		recomputed from the target."""
		page = self.make_workspace("Test Dock Shape Override", ALPHA)

		save_site_dock(APP, payload(sidebar(BETA, link_type="Workspace", link_to=page)))

		rendered = next(r for r in dock_for(among=None) if r["link_to"] == page)
		self.assertEqual(rendered["sidebar"], BETA, "the named shell, not the page's own module")

	def test_the_live_case_for_the_override_is_expressible(self):
		"""`Welcome Workspace`'s module is `Core`, which is code-only and therefore on no rail --
		so deriving its shell would land somewhere the rail refuses to acknowledge. The row is
		storable; whether it *renders* is the ordinary workspace permission question, which a
		bare site answers no to."""
		from frappe.utils.modules import get_code_only_modules

		self.assertIn("Core", get_code_only_modules())
		self.assertEqual(frappe.db.get_value("Workspace", "Welcome Workspace", "module"), "Core")

		save_site_dock(APP, payload(sidebar("Users", link_type="Workspace", link_to="Welcome Workspace")))

		row = get_site_dock(APP)[0]
		self.assertEqual((row["sidebar"], row["link_to"]), ("Users", "Welcome Workspace"))

	# -- identity ------------------------------------------------------------------------

	def test_relabelling_does_not_re_key_a_row(self):
		"""Icon and title are outside the key, so an app renaming a button cannot detach every
		customisation of it."""
		self.assertEqual(
			dock_key(sidebar(ALPHA, icon="box", title="Stock")),
			dock_key(sidebar(ALPHA, icon="table", title="Inventory")),
		)

	def test_changing_a_destination_re_keys_a_row(self):
		"""The other half: the key *is* the destination, so a layer changing any of it has not
		edited the row -- it has named a different one."""
		page = self.make_workspace("Test Dock Shape Repoint", ALPHA)

		self.assertNotEqual(dock_key(sidebar(ALPHA)), dock_key(sidebar(BETA)))
		self.assertNotEqual(
			dock_key(sidebar(ALPHA)), dock_key(sidebar(ALPHA, link_type="Workspace", link_to=page))
		)
		self.assertNotEqual(dock_key(workspace(page)), dock_key(sidebar(ALPHA, **workspace(page))))

	# -- reach ---------------------------------------------------------------------------

	def test_reach_is_conjoined_across_filled_columns(self):
		"""A row passes only if every column it fills passes. A shell the person has blocked,
		with a workspace they may open, would otherwise render the whole sidebar of a module the
		block was supposed to take away -- undone by a row pointing past it."""
		page = self.make_workspace("Test Dock Shape Gated", ALPHA)

		frappe.set_user("Administrator")
		user = frappe.get_doc("User", self.USER)
		user.append("block_modules", {"module": GAMMA})
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=self.USER)

		save_site_dock(APP, payload(sidebar(GAMMA, link_type="Workspace", link_to=page), workspace(page)))

		# the workspace is permitted, the shell is not, so the conjunction refuses the row -- and
		# the bare pin at the same workspace still renders
		rendered = [
			(r["sidebar"], r["link_to"]) for r in dock_for(self.USER, among=None) if r["link_to"] == page
		]
		self.assertEqual(rendered, [(None, page)])

	def test_a_url_row_is_ungated(self):
		"""Nothing proves a web address and nothing gates one. It leaks no permission, and it is
		not new -- a person can already store an arbitrary URL in their own sidebar layer."""
		save_user_dock(APP, payload({"link_type": "URL", "url": "https://example.com", "title": "Out"}))

		self.assertIn("https://example.com", names(dock_for(among=None)))

	def test_a_shell_is_proved_by_a_sidebar_document_or_a_module(self):
		"""Both, because most modules have a computed base and no `Sidebar` row -- and since a
		sidebar may be named something other than its module, asking `Module Def` alone would
		reject exactly the capability 01 added."""
		from frappe.desk.doctype.dock.dock import shell_exists

		self.assertTrue(shell_exists(ALPHA), "a module with no Sidebar document")
		self.assertTrue(shell_exists("Build"), "a Sidebar named something other than its module")
		self.assertFalse(shell_exists("Test Dock Shape Not A Shell"))

	# -- the old form still works --------------------------------------------------------

	def test_a_row_stored_in_the_old_shape_still_resolves(self):
		"""The expand half: 08 drops the columns, and until then a layer written before this
		release keeps rendering. `Dock` is authored by hand here, because the save path only ever
		writes the new columns."""
		doc = frappe.new_doc("Dock")
		doc.app = APP
		doc.append("items", {"type": "Sidebar", "link_name": BETA})
		doc.append("items", {"type": "Sidebar", "link_name": ALPHA})
		doc.save(ignore_permissions=True)

		self.assertEqual(names(dock_for()), [BETA, ALPHA])

	def test_an_old_row_and_a_new_row_pointing_at_one_thing_share_a_key(self):
		"""Which is what lets a layer written in either shape name a base row written in the
		other -- the translation happens on the way in, so both sides key the same."""
		self.assertEqual(
			dock_key(stored_row({"type": "Sidebar", "link_name": ALPHA})), dock_key(sidebar(ALPHA))
		)
		self.assertEqual(
			dock_key(stored_row({"type": "Workspace", "link_name": "GST"})), dock_key(workspace("GST"))
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

	def pin(self, page, host=None):
		"""A companion's pin: a workspace row carrying the host app it joins. Still the hook's
		spelling of `app`, which is the row-level fact ticket 10 moves onto the record."""
		return {**workspace(page), "app": host or self.HOST}

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

		host = next(app for app in app_data if app["app_name"] == self.HOST)
		return host["dock"]

	def test_the_boot_payload_carries_one_entry_list_per_app(self):
		"""Both old fields are gone: the client stops reconciling a module list against a
		workspace list to render a single rail, which is the gap the pin fell into."""
		from frappe.boot import get_bootinfo

		for app in get_bootinfo()["app_data"]:
			self.assertIn("dock", app)
			self.assertNotIn("modules", app)
			self.assertNotIn("workspaces", app)
			for row in app["dock"]:
				self.assertTrue({*row} <= {"sidebar", "link_type", "link_to", "url"})

	def test_a_pin_folds_into_the_hosts_list_behind_its_own_entries(self):
		"""Attribution is forced rather than chosen: a row grouped under the companion would
		never render on the host's dock at all. Appended rather than positioned -- where it sits
		is Layer business, not the companion's to assert."""
		page = self.make_workspace("Test Dock Pinned", ALPHA)

		with shipped_dock({self.COMPANION: [self.pin(page)]}):
			dock = self.host_dock()

		self.assertEqual(dock[-1], {"link_type": "Workspace", "link_to": page})
		self.assertTrue(all(row.get("sidebar") for row in dock[:-1]))

	def test_two_companions_pinning_into_one_host_order_by_installation(self):
		first = self.make_workspace("Test Dock Pin One", ALPHA)
		second = self.make_workspace("Test Dock Pin Two", BETA)

		with shipped_dock(
			{
				self.COMPANION: [self.pin(first)],
				self.OTHER_COMPANION: [self.pin(second)],
			}
		):
			pinned = [row["link_to"] for row in self.host_dock() if row.get("link_type")]

		self.assertEqual(pinned, [first, second])

	def test_a_pinned_workspace_the_person_may_not_open_is_absent(self):
		"""Permission-filtered like any other workspace, so pinning cannot leak a page's
		existence to someone who may not open it."""
		page = self.make_workspace("Test Dock Pin Blocked", ALPHA, roles=["Workspace Manager"])

		with shipped_dock({self.COMPANION: [self.pin(page)]}):
			# `get_workspaces` is request-cached, and this suite asks it as two different people
			# inside one request
			frappe.local.request_cache.clear()
			allowed = [row["link_to"] for row in self.host_dock(self.USER) if row.get("link_type")]

		self.assertNotIn(page, allowed)

	def test_pinning_costs_the_apps_screen_slot_but_declaring_your_own_does_not(self):
		"""The rule reads the rows, not the hook. Every app declares `add_to_dock` now, so a
		presence check would delete each adopting app from the apps screen."""
		from frappe.boot import get_app_rail_host_map

		page = self.make_workspace("Test Dock Pin Slot", ALPHA)

		with shipped_dock(
			{
				self.COMPANION: [self.pin(page)],
				self.OTHER_COMPANION: [sidebar(BETA)],
			}
		):
			hosts = get_app_rail_host_map()

		self.assertEqual(hosts.get(self.COMPANION), self.HOST)
		self.assertNotIn(self.OTHER_COMPANION, hosts)

	def test_a_pin_is_arranged_and_hidden_like_any_other_entry(self):
		page = self.make_workspace("Test Dock Pin Arranged", ALPHA)

		with shipped_dock({self.COMPANION: [self.pin(page)], self.HOST: [sidebar(ALPHA)]}):
			save_site_dock(APP, json.dumps([workspace(page), sidebar(ALPHA)]))
			resolved = [
				(r["sidebar"], r["link_to"], r["hidden"])
				for r in dock_for(self.USER, among=None)
				if page in (r["sidebar"], r["link_to"]) or ALPHA in (r["sidebar"], r["link_to"])
			]

		self.assertEqual(resolved, [(None, page, 0), (ALPHA, None, 0)])

	def test_a_layer_row_naming_a_workspace_outside_the_set_adds_nothing(self):
		"""The layers above the app order and hide; they never add. The entry set is the server's,
		and an arrangement naming something outside it names nothing the dock renders."""
		page = self.make_workspace("Test Dock Pin Unpinned", ALPHA)

		with shipped_dock({}):
			save_site_dock(APP, json.dumps([workspace(page)]))
			pinned = [row["link_to"] for row in self.host_dock() if row.get("link_type")]

		self.assertNotIn(page, pinned)


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

		self.assertEqual(
			emitted["code"],
			render_dock_hook([sidebar(GAMMA), sidebar(BETA), sidebar(ALPHA, hidden=1)]),
		)

		# what the author would have in `hooks.py` after pasting, read back as a fragment -- the
		# block is written in the typed-pair spelling, which is what a `hooks.py` reader speaks
		fragment = [hook_sidebar(GAMMA), hook_sidebar(BETA), hook_sidebar(ALPHA, hidden=1)]

		# Declared for an app that ships no record, because that is the only app a pasted block
		# still answers for: `get_app_dock` prefers a shipped document where there is one, and
		# frappe now ships its own.
		pasted_into = "zz-dock-emit-roundtrip"
		with shipped_dock({pasted_into: fragment}):
			resolved = dock_for(among=TRIO, app=pasted_into)

		self.assertEqual(names(resolved), [GAMMA, BETA, ALPHA])
		self.assertEqual(hidden_by_name(resolved)[ALPHA], 1)

	def test_a_foreign_row_is_dropped_and_named(self):
		"""A projection, not a refusal: the pin is already declared in the companion's own
		`hooks.py`, and where it sits on screen is layer business no block can state."""
		page = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "Test Dock Emit Pin",
				"label": "Test Dock Emit Pin",
				"module": ALPHA,
				"public": 1,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", page.name, force=True, ignore_missing=True)

		pin = {**workspace(page.name), "app": self.APP}
		with shipped_dock({self.COMPANION: [pin], self.APP: [sidebar(BETA), sidebar(ALPHA)]}):
			emitted = self.emit(sidebar(BETA), workspace(page.name), sidebar(ALPHA))

		self.assertEqual(
			emitted["code"],
			"add_to_dock = [\n"
			'\t{"type": "Sidebar", "name": "Test Dock Beta"},\n'
			'\t{"type": "Sidebar", "name": "Test Dock Alpha"},\n'
			"]",
		)
		self.assertEqual(
			emitted["dropped"],
			[{**destination(workspace(page.name)), "name": page.name, "declared_by": self.COMPANION}],
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


class TestTheFrameworksDock(IntegrationTestCase):
	"""The framework shipping its own dock as an exported document.

	Twelve rows, not ten. The hook deliberately left `Geo` and `System` unnamed so they would
	trail in `modules.txt` order; a record has no trailing tier to fall into, so naming them is
	compulsory rather than gratuitous -- and the rail renders the same twelve buttons in the same
	order either way.
	"""

	TWELVE: typing.ClassVar[list[str]] = [
		# the shell, not the module: `Build Tools`' sidebar is titled `Build`
		"Build",
		"Users",
		"Email",
		"Website",
		"Data",
		"Workflow",
		"Printing",
		"Integrations",
		"Contacts",
		"Automation",
		"Geo",
		"System",
	]

	def test_frappe_ships_a_dock_record(self):
		"""A document, exported and re-imported like any other -- not a hook, and not a fixture."""
		dock = frappe.get_doc("Dock", "frappe")

		self.assertTrue(dock.standard)
		self.assertEqual(dock.app, "frappe")
		self.assertEqual([row.sidebar for row in dock.items], self.TWELVE)
		# authored, all twelve: nothing derives an icon or a title, deliberately -- a prefill
		# would make divergence look like inheritance
		self.assertTrue(all(row.icon and row.title for row in dock.items))

	def test_the_record_is_named_after_its_app(self):
		"""The record's name is its path, so it cannot be a hash: a re-export from a fresh bench
		would mint a second file and leave the first a permanent orphan."""
		self.assertEqual(frappe.db.get_value("Dock", {"app": "frappe", "standard": 1}), "frappe")

	def test_the_record_is_the_base_the_layers_are_laid_over(self):
		frappe.set_user("Administrator")
		clear_arrangements()

		self.assertEqual(
			[row["sidebar"] for row in get_app_dock("frappe") if row["sidebar"]],
			self.TWELVE,
		)

	def test_the_walked_case_renders_the_same_dock(self):
		"""Fifteen modules in, twelve named, three code-only never nameable at all."""
		from frappe.utils.modules import get_code_only_modules

		frappe.set_user("Administrator")
		clear_arrangements()

		resolved = [row["sidebar"] for row in resolve_dock()["frappe"] if row["sidebar"]]
		self.assertEqual([name for name in resolved if name in self.TWELVE], self.TWELVE)

		# the three the record cannot name, because they ship no navigation of their own
		self.assertEqual(sorted(get_code_only_modules()), ["Core", "Custom", "Desk"])
		self.assertFalse([name for name in resolved if name in get_code_only_modules()])


class TestTheExportRoad(IntegrationTestCase):
	"""An app's dock as a git-versioned file: promoted in one act, kept current on every Save,
	re-imported by migrate, and reaped when its file goes away.

	The app used here is invented, so nothing is ever written into a real app on the bench: the
	export is pointed at a temporary directory standing in for `frappe.get_app_path(app)`.

	Not a `DockTestCase`, and its modules are its own. `remove_orphan_entities` commits, so
	anything this suite writes outlives the framework's rollback -- which means the fixtures have
	to be torn down by hand, and cannot be the shared class-level ones the other suites lean on.
	"""

	APP = "zz-dock-export"
	ONE = "Test Dock Export One"
	TWO = "Test Dock Export Two"

	def setUp(self):
		frappe.set_user("Administrator")
		self.root = tempfile.mkdtemp(prefix="zz-dock-export-")
		self.addCleanup(shutil.rmtree, self.root, True)
		self.enterContext(app_rooted_at(self.APP, self.root))
		self.enterContext(developer_mode())
		self.make_modules()

	def tearDown(self):
		"""By hand and before the commit, not through `addCleanup`.

		`remove_orphan_entities` commits, so everything this suite has written is already durable
		by the time a test ends -- and cleanups run *after* `tearDown`, so anything deleted there
		would be deleted after the commit that was supposed to make the deletion stick.
		"""
		frappe.set_user("Administrator")
		clear_arrangements_for(self.APP)
		self.drop_modules()
		frappe.db.commit()  # nosemgrep

	def make_modules(self):
		self.drop_modules()
		with no_developer_mode():
			for module in (self.ONE, self.TWO):
				frappe.get_doc(
					{"doctype": "Module Def", "module_name": module, "app_name": "frappe"}
				).insert()

	def drop_modules(self):
		with no_developer_mode():
			for module in (self.ONE, self.TWO):
				frappe.delete_doc("Module Def", module, force=True, ignore_missing=True)

	def exported(self) -> str:
		# `scrub`, because the export road does: the folder and the file are named after the
		# record, snake_cased, and the record here is named after an app with hyphens in it
		scrubbed = frappe.scrub(self.APP)
		return os.path.join(self.root, "dock", scrubbed, f"{scrubbed}.json")

	def author(self, *modules):
		"""The site arranges a rail, which is what an author has in front of them before the
		dock is promoted to app content."""
		save_site_dock(self.APP, payload(*modules))

	def test_marking_standard_writes_the_file_and_sets_the_flag_in_one_act(self):
		self.author(self.TWO, self.ONE)
		mark_as_standard(self.APP)

		self.assertTrue(os.path.exists(self.exported()))
		self.assertTrue(frappe.db.get_value("Dock", {"app": self.APP, "standard": 1}, "standard"))
		self.assertEqual(json.load(open(self.exported()))["name"], self.APP)

	def test_the_promoted_dock_becomes_the_base(self):
		"""The point of promoting: the app's own rows are what the two layers above rearrange."""
		self.author(self.TWO, self.ONE)
		mark_as_standard(self.APP)

		self.assertEqual(names(get_app_dock(self.APP)), [self.TWO, self.ONE])

	def test_a_later_save_keeps_the_file_current(self):
		self.author(self.TWO)
		mark_as_standard(self.APP)

		doc = frappe.get_doc("Dock", frappe.db.get_value("Dock", {"app": self.APP, "standard": 1}))
		doc.append("items", {"sidebar": self.ONE})
		doc.save(ignore_permissions=True)

		on_disk = [row["sidebar"] for row in json.load(open(self.exported()))["items"]]
		self.assertEqual(on_disk, [self.TWO, self.ONE])

	def test_a_mark_that_writes_no_file_leaves_no_row(self):
		"""A standard row with no file is the orphan the next migrate deletes, so a mark that
		did not land must roll the row back rather than create one that deletes itself."""
		self.author(self.ONE)

		with patch.object(Dock, "is_exported", return_value=False):
			self.assertRaises(frappe.ValidationError, mark_as_standard, self.APP)

		self.assertFalse(frappe.db.exists("Dock", {"app": self.APP, "standard": 1}))

	def test_unmarking_deletes_both_the_row_and_the_file(self):
		self.author(self.ONE)
		mark_as_standard(self.APP)

		unmark_as_standard(self.APP)

		self.assertFalse(os.path.exists(self.exported()))
		self.assertFalse(frappe.db.exists("Dock", {"app": self.APP, "standard": 1}))

	def test_unmarking_leaves_the_app_with_no_rail(self):
		"""The asymmetry with `Sidebar`'s unmark, which falls back to a computed base: a dock
		has none, so what is left is no rail at all."""
		self.author(self.ONE)
		mark_as_standard(self.APP)
		# the site's own arrangement is what would otherwise still be answering
		clear_arrangements_for(self.APP, standard=0)

		unmark_as_standard(self.APP)

		self.assertEqual(get_app_dock(self.APP), [])

	def test_deleting_the_file_reaps_the_row(self):
		"""What makes the file the source of truth: a record whose file has gone is an orphan."""
		self.author(self.ONE)
		mark_as_standard(self.APP)

		shutil.rmtree(os.path.dirname(self.exported()))
		remove_orphan_entities(["Dock"])

		self.assertFalse(frappe.db.exists("Dock", {"app": self.APP, "standard": 1}))

	def test_site_and_user_rows_are_never_orphan_candidates(self):
		"""They are backed by no file at all, so a reaper that swept them would delete every
		arrangement on the site the first time it ran."""
		self.author(self.ONE)
		save_user_dock(self.APP, payload(self.TWO))

		remove_orphan_entities(["Dock"])

		self.assertTrue(frappe.db.exists("Dock", {"app": self.APP, "standard": 0, "user": ""}))

	# -- the conditional guard -----------------------------------------------------------

	def test_outside_developer_mode_the_standard_flag_cannot_be_set(self):
		self.author(self.ONE)

		with no_developer_mode():
			self.assertRaises(frappe.ValidationError, mark_as_standard, self.APP)

	def test_outside_developer_mode_the_standard_flag_cannot_be_cleared(self):
		"""The half a blanket guard would cover and a flag-only guard would not: a Workspace
		Manager holds `write` on `Dock`, so without this they could take an app's row, clear the
		flag, and convert git-versioned app content into a site row they own."""
		self.author(self.ONE)
		mark_as_standard(self.APP)
		doc = frappe.get_doc("Dock", frappe.db.get_value("Dock", {"app": self.APP, "standard": 1}))

		with no_developer_mode():
			doc.standard = 0
			self.assertRaises(frappe.ValidationError, doc.save, ignore_permissions=True)

	def test_an_ordinary_site_layer_save_succeeds_outside_developer_mode(self):
		"""Why the guard is conditional rather than blanket: all three layers share this table,
		and a blanket guard would refuse every person saving their own arrangement."""
		with no_developer_mode():
			save_site_dock(self.APP, payload(self.ONE))

		self.assertEqual(names(get_site_dock(self.APP)), [self.ONE])

	def test_each_system_write_flag_lets_app_content_through(self):
		"""Every one of these is a real route by which an app's dock reaches a site. Without the
		escape, installing or updating an app that ships one fails on every customer site."""
		for flag in SYSTEM_WRITE_FLAGS:
			with self.subTest(flag=flag), no_developer_mode(), system_write(flag):
				doc = frappe.new_doc("Dock")
				doc.app = self.APP
				doc.standard = 1
				doc.append("items", {"sidebar": self.ONE})
				doc.save(ignore_permissions=True)

				self.assertTrue(doc.standard)
				frappe.delete_doc("Dock", doc.name, force=True, ignore_permissions=True)


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
			self.assertEqual(self.problems([hook_sidebar(module)]), [])

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
		problems = self.problems([hook_sidebar("Test Module That Is Not Here")])

		self.assertEqual(len(problems), 1)
		self.assertIn("Sidebar or Module Def that does not exist", problems[0])

	def test_a_pin_at_an_app_that_is_not_installed_is_not_a_problem(self):
		"""Silence by design: a companion may be installed before or without its host, and the
		row is correct in both cases."""
		self.assertEqual(self.problems([{"type": "Workspace", "name": "Anything", "app": "not-an-app"}]), [])

	def test_the_frameworks_own_fragment_is_clean(self):
		"""The check is only worth running if what we ship passes it."""
		self.assertEqual(check_dock_hooks(), [])


class TestMakingAModule(IntegrationTestCase):
	"""A module the site adds for itself, from the dock that will list it."""

	NAME = "Test Dock Made Module"

	def setUp(self):
		frappe.set_user("Administrator")
		self.wipe()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.wipe()

	def wipe(self):
		# the page first: a module's page outlives the module, and deleting the module leaves one
		# behind for the next test to trip over
		frappe.delete_doc("Workspace", self.NAME, force=True, ignore_missing=True)
		frappe.delete_doc("Module Def", self.NAME, force=True, ignore_missing=True)
		frappe.clear_cache()

	def test_a_new_module_arrives_with_a_workspace_and_a_sidebar(self):
		"""The workspace is not a nicety: a module whose sidebar comes out empty is dropped from
		the payload entirely, so a module made without one would be a module that never appears
		on the dock it was made from."""
		answer = create_module(self.NAME, app="frappe")

		self.assertTrue(frappe.db.exists("Module Def", self.NAME))
		workspace = frappe.get_doc("Workspace", self.NAME)
		self.assertEqual(workspace.module, self.NAME)
		self.assertTrue(workspace.public)

		# ... which is what makes the module navigable, and so present at all
		sidebar = resolve_sidebar(self.NAME, "Administrator")
		self.assertIsNotNone(sidebar)
		self.assertEqual(
			[(item["link_type"], item["link_to"]) for item in sidebar.items],
			[("Workspace", self.NAME)],
		)

		# and the manager is handed what it needs to draw the module without a reload: the entry
		# the dock now offers, and the desk state the write invalidated -- the workspace list
		# included, since a page the boot has never heard of is one the desk cannot place
		self.assertEqual(answer["entry"], {"sidebar": self.NAME})
		self.assertIn(self.NAME, answer["module_sidebars"])
		self.assertIn(self.NAME, [page.name for page in answer["workspace_pages"]["pages"]])
		self.assertIn(
			{"sidebar": self.NAME},
			next(app["dock"] for app in answer["app_data"] if app["app_name"] == "frappe"),
		)

	def test_the_icon_it_was_given_is_the_icon_the_dock_draws_it_with(self):
		"""A module has nowhere to keep an icon, so the one chosen while adding it is kept on the
		page it opens on -- which is exactly where a computed sidebar reads its header icon."""
		create_module(self.NAME, app="frappe", icon="box")

		self.assertEqual(frappe.db.get_value("Workspace", self.NAME, "icon"), "box")
		self.assertEqual(get_module_sidebars()[self.NAME]["header_icon"], "box")

	def test_a_module_given_no_icon_keeps_the_standard_one(self):
		create_module(self.NAME, app="frappe")

		self.assertEqual(get_module_sidebars()[self.NAME]["header_icon"], DEFAULT_HEADER_ICON)

	def test_the_app_it_was_made_from_is_the_dock_that_lists_it(self):
		"""`app_name` is placement and nothing else, and placement is what a dock is."""
		create_module(self.NAME, app="frappe")

		self.assertIn(self.NAME, get_app_modules("frappe"))

	def test_a_module_made_with_no_app_stands_on_its_own(self):
		"""Nowhere to place it is a real answer -- the module is on the desktop as its own tile
		rather than in somebody's dock."""
		create_module(self.NAME)

		self.assertIsNone(frappe.db.get_value("Module Def", self.NAME, "app_name"))
		self.assertNotIn(self.NAME, get_app_modules("frappe"))

	def test_making_a_module_again_takes_its_old_page_back(self):
		"""Deleting a module leaves its page behind -- `ModuleDef.on_trash` takes navigation and
		leaves content alone -- so the name would otherwise be held by a page nothing can reach,
		and the module could never be made again under the name it had."""
		create_module(self.NAME, app="frappe")
		frappe.db.set_value("Workspace", self.NAME, "content", '[{"type": "header"}]')
		frappe.delete_doc("Module Def", self.NAME, force=True)

		create_module(self.NAME, app="frappe", icon="box")

		# the page it had is the page it has, content and all
		self.assertEqual(frappe.db.count("Workspace", {"name": self.NAME}), 1)
		self.assertEqual(frappe.db.get_value("Workspace", self.NAME, "content"), '[{"type": "header"}]')
		# ... and the icon chosen this time is the module's icon now
		self.assertEqual(frappe.db.get_value("Workspace", self.NAME, "icon"), "box")

	def test_a_page_belonging_to_something_else_still_holds_the_name(self):
		"""Only the module's own page is adopted. Anything else under that name is somebody's
		work, and a module that took it would be taking a page nobody offered."""
		frappe.get_doc(
			{
				"doctype": "Workspace",
				"label": self.NAME,
				"title": self.NAME,
				# `Workspace.module` is mandatory, so a page always belongs to some module -- and
				# one belonging to another module is the case this is about
				"module": "Desk",
				"public": 1,
				"content": "[]",
			}
		).insert()

		self.assertRaises(frappe.ValidationError, create_module, self.NAME, app="frappe")

	def test_a_name_that_is_already_taken_is_refused(self):
		"""Both halves are named after the module, so both names have to be free -- and the
		refusal names the thing rather than the doctype whose key it clashed with."""
		create_module(self.NAME, app="frappe")

		self.assertRaises(frappe.ValidationError, create_module, self.NAME, app="frappe")

	def test_a_module_needs_a_name(self):
		self.assertRaises(frappe.ValidationError, create_module, "   ")

	def test_making_a_module_needs_the_shared_curation_right(self):
		"""It is site content, and everybody boots it -- so it is the same right the site layer
		of every arrangement is behind."""
		user = "test-dock-module@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": user,
					"first_name": "Dock",
					"send_welcome_email": 0,
					"roles": [{"role": "Desk User"}],
				}
			).insert(ignore_permissions=True)

		frappe.set_user(user)
		try:
			self.assertRaises(frappe.PermissionError, create_module, self.NAME, app="frappe")
		finally:
			frappe.set_user("Administrator")
			frappe.delete_doc("User", user, force=True, ignore_missing=True)

		self.assertFalse(frappe.db.exists("Module Def", self.NAME))
