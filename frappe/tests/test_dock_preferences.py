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
	DOCK_ITEM_FIELDS,
	Dock,
	destination,
	dock_key,
	get_app_dock,
	get_app_dock_layer,
	get_app_entry_set,
	get_site_dock,
	get_site_dock_layer,
	get_user_dock,
	get_user_dock_layer,
	mark_as_standard,
	mounted_apps,
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

# The modules these suites arrange -- their own, rather than three of the framework's. An app's
# dock is free to name the framework's modules, and once an app ships one every site has a
# base that does, so borrowing them made every assertion here depend on what somebody else had
# shipped. These three are created by the suite and named by nothing else.
# The app these suites arrange the dock of. A `Dock` layer is per app, so every read and every
# write names one -- and an app's dock is exactly the record it ships, so the suite ships one
# naming its own three modules rather than borrowing frappe's twelve. An arrangement is then a
# *reference* to rows that are really there, which is the ordinary case; a row naming something
# the base does not hold is an **add**, and adds are `TestALayerMayAdd`'s subject.
APP = "zz-dock-suite-app"

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


def added(row, title=None) -> dict:
	"""A row that **adds** an entry rather than referencing one a layer below holds.

	An add carries its own icon and title, because nothing below it has either -- leaving them
	blank would put a label-less button on the rail, which is what the refusal at Save exists to
	prevent.
	"""
	name = row.get("sidebar") or row.get("link_to") or row.get("url")
	return {"icon": "box", "title": title or name, **row}


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
def shipped_dock(records: dict[str, list[dict]]):
	"""Ship a standard `Dock` for each named app, for the length of the `with` block.

	    shipped_dock({"zz-dock-suite": [sidebar(ALPHA)], "zz-dock-suite-companion": [...]})

	An app's dock is a document now, so this writes one rather than patching a hook. Written
	under `in_import`, which is the truthful flag: this is the system placing app content on a
	site, exactly as migrate does, and it is also what keeps the write from touching the working
	tree -- `export_dock` returns early on it.

	An app named here that is not installed is *invented* for the duration -- it joins the
	installed and active lists, and answers every other hook with nothing, because it has no
	`hooks.py` to import. That is what lets a suite own the docks under test: the assertions do
	not depend on which apps this bench happens to carry.

	An invented app is deliberately absent from `_ensure_on_bench=True`, which asks for the apps
	that exist as directories. It does not, and callers who ask that question mean it -- the
	template loader imports every app it is handed.
	"""
	real_hooks = frappe.get_hooks
	real_installed = frappe.get_installed_apps
	real_active = frappe.get_active_apps
	real_path = frappe.get_app_path
	invented = [app for app in records if app not in real_active()]
	# Somewhere to point an invented app's files, which is a real directory that stays empty.
	# `get_desktop_icon_urls` and the orphan reaper both walk `get_app_path` for every active
	# app, and an invented one has no python module for the real function to resolve.
	nowhere = tempfile.mkdtemp(prefix="zz-invented-app-")

	def patched_hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		return [] if app_name in invented else real_hooks(hook, default, app_name)

	def patched_path(app_name, *joins):
		return (
			os.path.join(nowhere, app_name, *joins) if app_name in invented else real_path(app_name, *joins)
		)

	def patched_installed(*args, **kwargs):
		return [*real_installed(*args, **kwargs), *invented]

	def patched_active(*args, _ensure_on_bench=False, **kwargs):
		apps = real_active(*args, _ensure_on_bench=_ensure_on_bench, **kwargs)
		return apps if _ensure_on_bench else [*apps, *invented]

	with (
		patch.object(frappe, "get_hooks", patched_hooks),
		patch.object(frappe, "get_installed_apps", patched_installed),
		patch.object(frappe, "get_active_apps", patched_active),
		patch.object(frappe, "get_app_path", patched_path),
	):
		shipped, displaced = [], {}
		for app, spec in records.items():
			rows, mount_on = (spec, None) if isinstance(spec, list) else (spec["items"], spec.get("mount_on"))
			# A dock this block replaces is put back afterwards. Suites nest these -- the class
			# ships one for its own app and a test ships a different one over it -- and without
			# the restore the inner block would leave the app dock-less for every later test,
			# which turns every reference into an add and fails a long way from the cause.
			if standing := frappe.db.get_value("Dock", {"app": app, "standard": 1}):
				doc = frappe.get_doc("Dock", standing)
				displaced[app] = [{field: row.get(field) for field in DOCK_ITEM_FIELDS} for row in doc.items]
				frappe.delete_doc("Dock", standing, force=True, ignore_permissions=True)
			shipped.append(ship_dock(app, rows, mount_on))
		try:
			yield
		finally:
			for name in shipped:
				frappe.delete_doc("Dock", name, force=True, ignore_permissions=True)
			for app, rows in displaced.items():
				ship_dock(app, rows)
			shutil.rmtree(nowhere, ignore_errors=True)


def ship_dock(app: str, rows: list, mount_on: str | None = None) -> str:
	"""One app's `Dock` record, as if its file had just been imported. Returns its name."""
	doc = frappe.new_doc("Dock")
	doc.app = app
	doc.standard = 1
	doc.mount_on = mount_on
	for row in rows:
		if isinstance(row, dict):
			doc.append("items", {field: row.get(field) for field in DOCK_ITEM_FIELDS})

	with system_write("in_import"):
		doc.save(ignore_permissions=True)
	return doc.name


class DockTestCase(IntegrationTestCase):
	"""A suite with three modules of its own, an app of its own that ships a dock naming them,
	and no opinion about anybody else's."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls._fixtures = ExitStack()
		for module in TRIO:
			cls._fixtures.enter_context(sidebarless_module(module))
		cls._fixtures.enter_context(shipped_dock({APP: [sidebar(module) for module in TRIO]}))

	@classmethod
	def tearDownClass(cls):
		cls._fixtures.close()
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

	def test_a_saved_layer_is_exactly_the_rail(self):
		"""A person's saved layer *is* their rail. What they left out is not behind what they
		kept -- it is off, and it comes back by being added rather than by turning up.

		Predictable rails over automatic updates, and it costs them nothing they were seeing:
		the editor shows every entry, hidden ones included, so a save names all of them.
		"""
		self.set_site_order(BETA, ALPHA, GAMMA)

		frappe.set_user(self.DESK_USER)
		save_user_dock(APP, payload(GAMMA))

		self.assertEqual(names(dock_for(self.DESK_USER)), [GAMMA])

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

	def test_an_entry_the_app_adds_later_waits_to_be_added(self):
		"""The cost of "a saved layer is exactly the rail", on the record. An entry the app ships
		after the site has arranged its rail does **not** appear on it. It appears in Manage
		Dock -- which reads the app's own dock, not the resolved rail -- as something to add.
		"""
		self.set_site_order(BETA, ALPHA)

		self.assertEqual(names(dock_for(self.DESK_USER)), [BETA, ALPHA])
		self.assertIn(GAMMA, names(get_app_dock_layer(APP)))

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
		self.assertEqual(names(dock_for()), [ALPHA])

	def test_both_writable_layers_round_trip_a_row(self):
		"""Written whole, read back whole -- at the site's layer and at a person's own.

		The person's row *adds*, because the site's saved layer left `ALPHA` off the rail and a
		saved layer is exactly the rail. So it carries its own icon and title, and the site's
		row -- which references what the app ships -- carries neither.
		"""
		self.set_site_order(BETA)

		frappe.set_user(self.DESK_USER)
		save_user_dock(APP, payload(added(sidebar(ALPHA))))
		frappe.set_user("Administrator")

		self.assertEqual(get_site_dock(APP), [stored(sidebar(BETA))])
		self.assertEqual(get_user_dock(APP, self.DESK_USER), [stored(added(sidebar(ALPHA)), added=1)])

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
		save_user_dock(APP, payload(added(sidebar(BETA))))
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

	def test_the_base_is_the_record_the_app_ships(self):
		"""One document, exported and re-imported. Not a hook: the projection a hook needed had
		no reader once the record is what ships, and an app that ships neither has no rail."""
		with self.ship(BETA, ALPHA):
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [BETA, ALPHA])
			self.assertEqual(frappe.get_all("Dock", filters={"app": self.APP}, pluck="standard"), [1])

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

			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [ALPHA])
			self.assertEqual(names(dock_for(self.USER, app=self.OTHER_APP)), [GAMMA, ALPHA])
			self.assertEqual(names(get_site_dock(self.OTHER_APP)), [])

	def test_the_site_arranges_what_the_app_shipped(self):
		with self.ship(BETA, ALPHA, GAMMA):
			save_site_dock(self.APP, payload(GAMMA, BETA))

			# the site's rows, in the site's order, and nothing else
			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [GAMMA, BETA])

	def test_bringing_back_what_the_site_left_off_is_an_add(self):
		"""A saved site layer *is* the rail, so from a person's side the entry is gone -- not
		hidden, gone. Putting it back is therefore their own row rather than a reference to the
		site's, which is why it carries a cross and why it has to say how it reads.

		The pool it is picked from is the app's own dock, which `get_app_dock_layer` answers
		independently of the resolved rail -- so the entry is still *offerable*, it is just not
		inheritable.
		"""
		with self.ship(BETA, ALPHA, GAMMA):
			save_site_dock(self.APP, payload(GAMMA))

			frappe.set_user(self.USER)
			# a bare reference to it says nothing: nothing below holds it any more
			self.assertRaises(
				frappe.ValidationError, save_user_dock, self.APP, payload(sidebar(ALPHA), GAMMA)
			)
			save_user_dock(self.APP, payload(added(sidebar(ALPHA)), GAMMA))
			frappe.set_user("Administrator")

			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [ALPHA, GAMMA])
			self.assertEqual([row["added"] for row in get_user_dock(self.APP, self.USER)], [1, 0])

	def test_a_module_the_app_added_later_waits_in_the_manager(self):
		"""What "a saved layer is exactly the rail" costs, said out loud. An entry no layer names
		is off the rail rather than trailing it -- and it is offered by `get_app_dock_layer`,
		which is what the manager builds its list from."""
		with self.ship(BETA, ALPHA, GAMMA):
			save_site_dock(self.APP, payload(GAMMA, BETA))

			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [GAMMA, BETA])
			self.assertIn(ALPHA, names(get_app_dock_layer(self.APP)))

	def test_hiding_is_stored_rather_than_being_the_absence_of_a_row(self):
		"""Hiding is a decision. A row saying so persists, and the payload keeps it -- which is
		what lets the manager render it and bring it back, and is the one thing the dock does
		differently from a sidebar."""
		with self.ship(BETA, ALPHA):
			save_site_dock(self.APP, payload(sidebar(BETA, hidden=1), sidebar(ALPHA, hidden=0)))

			hidden = hidden_by_name(dock_for(self.USER, app=self.APP))
			self.assertEqual(hidden[BETA], 1)
			self.assertEqual(hidden[ALPHA], 0)

	def test_a_row_opening_a_kind_the_dock_does_not_have_is_refused_at_save(self):
		"""What retiring `check_dock_hooks` loses, which is nothing: a bad row used to fail
		silently in `hooks.py` and be reported at migrate. A record catches it at Save, in front
		of the author, quoting the row they are looking at."""
		doc = frappe.new_doc("Dock")
		doc.app = "frappe"
		doc.append("items", {"link_type": "Report", "link_to": "ToDo"})
		doc.append("items", {"sidebar": ALPHA})

		self.assertRaisesRegex(frappe.ValidationError, "Row #1", doc.save, ignore_permissions=True)

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

	def test_a_base_entry_no_layer_names_is_off_the_rail(self):
		"""Where the sidebar keeps such an entry, the dock drops it. The merge takes a
		*don't keep unnamed* parameter, and the dock is what passes it: a saved layer states the
		whole rail, so what it left out it left out."""
		with shipped_dock({self.APP: [sidebar(GAMMA), sidebar(BETA), sidebar(ALPHA)]}):
			save_site_dock(self.APP, payload(ALPHA))

			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [ALPHA])

	def test_a_layer_that_names_nothing_says_nothing(self):
		"""The one thing *don't keep unnamed* must not do: an empty layer means "no opinion",
		not "an empty rail". Read the other way it would empty every app the moment a layer
		existed for it at all."""
		with shipped_dock({self.APP: [sidebar(GAMMA), sidebar(BETA)]}):
			save_site_dock(self.APP, payload(GAMMA, BETA))
			save_site_dock(self.APP, "[]")

			self.assertEqual(names(dock_for(self.USER, app=self.APP)), [GAMMA, BETA])

	def test_the_walked_case(self):
		"""Ten shipped entries, a site that named four of them and hid one of those.

		The rail is the four, in the site's order, with the hidden one carrying its flag. The
		six the site never named are off it -- and are what the manager offers to add back.
		"""
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
			[shipped[3], shipped[1], shipped[7], shipped[0]],
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

			save_site_dock(self.APP, payload(added(sidebar(BETA)), added(sidebar(ALPHA))))
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
			save_site_dock(self.APP, payload(added(workspace(ALPHA)), added(sidebar(ALPHA))))

			self.assertEqual(
				get_site_dock(self.APP),
				[stored(added(workspace(ALPHA)), added=1), stored(added(sidebar(ALPHA)), added=1)],
			)
			self.assertEqual(
				[
					(r["sidebar"], r["link_to"])
					for r in dock_for(among=None, app=self.APP)
					if ALPHA in (r["sidebar"], r["link_to"])
				],
				[(None, ALPHA), (ALPHA, None)],
			)


class TestWhatACustomisationMayDo(DockTestCase):
	"""What a layer above the app may say about a rail: its order, its visibility and its label
	-- and it may add. What it may never do is re-point a row.

	*Never add* was stated in two comments and implemented nowhere: `apply_dock_row` never
	returned `None`, and the save path checked kind, existence and reach but never base
	membership. Only the manager's UI made the rule look true. So refusing adds was the option
	that would have cost new enforcement code, next to a sidebar that already answers yes.
	"""

	MANAGER = "test-dock-may@example.com"
	PERSON = "test-dock-may-person@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		for email, roles in (
			(self.MANAGER, ["Desk User", "Workspace Manager"]),
			(self.PERSON, ["Desk User"]),
		):
			if not frappe.db.exists("User", email):
				frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": email.split("@")[0],
						"send_welcome_email": 0,
						"roles": [{"role": role} for role in roles],
					}
				).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		clear_arrangements()
		for email in (self.MANAGER, self.PERSON):
			frappe.delete_doc("User", email, force=True, ignore_missing=True)

	def make_workspace(self, title, module, roles=None):
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": title,
				"module": module,
				"public": 1,
				"content": "[]",
				"roles": [{"role": role} for role in roles or []],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", doc.name, force=True, ignore_missing=True)
		frappe.local.request_cache.clear()
		return doc.name

	# -- both upper layers may add -------------------------------------------------------

	def test_a_site_and_a_person_may_each_add_what_they_can_reach(self):
		page = self.make_workspace("Test Dock May Add", ALPHA)

		frappe.set_user(self.MANAGER)
		save_site_dock(APP, payload(ALPHA, added(workspace(page))))
		frappe.set_user(self.PERSON)
		save_user_dock(APP, payload(ALPHA, added({"link_type": "URL", "url": "https://frappe.io"})))
		frappe.set_user("Administrator")

		self.assertEqual(names(dock_for(self.PERSON, among=None)), [ALPHA, "https://frappe.io"])

	def test_an_unreachable_add_is_refused(self):
		"""The bound is reach, and it is the only bound. A person may name anything they can
		already navigate to -- and nothing else, which is what stops an add being a way past
		permissions."""
		page = self.make_workspace("Test Dock May Not Add", ALPHA, roles=["Workspace Manager"])

		frappe.set_user(self.PERSON)
		save_user_dock(APP, payload(ALPHA, added(workspace(page))))
		frappe.set_user("Administrator")

		self.assertEqual(names(get_user_dock(APP, self.PERSON)), [ALPHA])

	def test_a_persons_add_and_a_later_identical_app_row_merge_into_one_entry(self):
		"""A pleasant property of identity being the destination. A person pins a workspace; the
		app later ships a row for the same one. Same key, so the two are one entry with the
		person's position winning, rather than the rail drawing it twice."""
		page = self.make_workspace("Test Dock May Merge", ALPHA)

		frappe.set_user(self.PERSON)
		save_user_dock(APP, payload(added(workspace(page)), ALPHA))
		frappe.set_user("Administrator")

		with shipped_dock({APP: [sidebar(module) for module in TRIO] + [workspace(page)]}):
			rendered = names(dock_for(self.PERSON, among=None))

		self.assertEqual(rendered.count(page), 1)
		self.assertEqual(rendered, [page, ALPHA])

	# -- re-labelling --------------------------------------------------------------------

	def test_icon_and_title_may_be_restated_at_both_upper_layers(self):
		frappe.set_user(self.MANAGER)
		save_site_dock(APP, payload(sidebar(ALPHA, icon="star", title="Ours")))
		frappe.set_user("Administrator")

		row = dock_for(self.PERSON)[0]
		self.assertEqual((row["icon"], row["title"]), ("star", "Ours"))

	def test_a_row_nobody_touched_keeps_receiving_the_apps_relabels(self):
		"""The failure that killed full-body storage in the sidebar, and one 06 made urgent here
		by giving every row a stored icon and title: left alone, one reorder would freeze the
		app's label forever. A value equal to what the saver was *shown* is not an opinion."""
		with shipped_dock({APP: [sidebar(ALPHA, icon="box", title="First")]}):
			frappe.set_user(self.MANAGER)
			# the client echoes back what it was showing, which is the app's own label
			save_site_dock(APP, payload(sidebar(ALPHA, icon="box", title="First")))
			frappe.set_user("Administrator")

			stored_rows = get_site_dock(APP)
			self.assertEqual((stored_rows[0]["icon"], stored_rows[0]["title"]), (None, None))

		# ...so when the app relabels, the relabel reaches them
		with shipped_dock({APP: [sidebar(ALPHA, icon="star", title="Renamed")]}):
			row = dock_for(self.PERSON)[0]
			self.assertEqual((row["icon"], row["title"]), ("star", "Renamed"))

	def test_a_reference_to_a_deleted_row_does_not_resurrect_as_a_labelless_button(self):
		"""What the `added` flag is required for. A reference carries no icon and no title of its
		own, so if it stood in for a row the app has since deleted it would render a destination
		with no label at all."""
		frappe.set_user(self.MANAGER)
		save_site_dock(APP, payload(ALPHA, BETA))
		frappe.set_user("Administrator")

		with shipped_dock({APP: [sidebar(ALPHA)]}):
			self.assertEqual(names(dock_for(self.PERSON, among=None)), [ALPHA])

	def test_an_added_row_needs_an_icon_and_a_title(self):
		page = self.make_workspace("Test Dock May Blank", ALPHA)

		self.assertRaises(frappe.ValidationError, save_site_dock, APP, payload(ALPHA, workspace(page)))

	# -- no re-pointing ------------------------------------------------------------------

	def test_hide_and_add_is_how_a_layer_re_points_a_row(self):
		"""The key *is* the destination, so a layer changing it has not edited the row -- it has
		named a different one. Both coexist: the app's, hidden; the site's own, shown."""
		page = self.make_workspace("Test Dock May Repoint", ALPHA)

		frappe.set_user(self.MANAGER)
		save_site_dock(APP, payload(sidebar(ALPHA, hidden=1), added(workspace(page)), BETA))
		frappe.set_user("Administrator")

		hidden = hidden_by_name(dock_for(self.PERSON, among=None))
		self.assertEqual(hidden[ALPHA], 1)
		self.assertEqual(hidden[page], 0)

	# -- reset ---------------------------------------------------------------------------

	def test_reset_for_everyone_drops_every_non_standard_layer_for_the_app(self):
		"""The one act that reaches past the site's own layer: a Workspace Manager who
		re-curates the site's rail reaches nobody who has arranged their own."""
		from frappe.desk.doctype.dock.dock import reset_dock_for_everyone

		frappe.set_user(self.MANAGER)
		save_site_dock(APP, payload(GAMMA, BETA))
		frappe.set_user(self.PERSON)
		save_user_dock(APP, payload(BETA))
		frappe.set_user(self.MANAGER)

		reset_dock_for_everyone(APP)
		frappe.set_user("Administrator")

		self.assertEqual(frappe.get_all("Dock", filters={"app": APP, "standard": 0}), [])
		self.assertEqual(names(dock_for(self.PERSON)), [ALPHA, BETA, GAMMA])

	def test_reset_for_everyone_is_workspace_manager_only(self):
		from frappe.desk.doctype.dock.dock import reset_dock_for_everyone

		frappe.set_user(self.PERSON)
		try:
			self.assertRaises(frappe.PermissionError, reset_dock_for_everyone, APP)
		finally:
			frappe.set_user("Administrator")

	def test_reset_for_everyone_deletes_row_by_row(self):
		"""Each `on_trash` has to run: only the document knows whose boot cache to invalidate,
		and a bulk delete would leave those people booting a rail that is no longer there."""
		from frappe.desk.doctype.dock.dock import get_dock_layers, reset_dock_for_everyone

		frappe.set_user(self.PERSON)
		save_user_dock(APP, payload(BETA))
		frappe.set_user(self.MANAGER)
		reset_dock_for_everyone(APP)
		frappe.set_user("Administrator")

		self.assertNotIn((APP, self.PERSON, 0), get_dock_layers())


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
			payload(
				added(sidebar(ALPHA)),
				added(workspace(page)),
				added(sidebar(BETA, link_type="Workspace", link_to=page)),
			),
		)

		self.assertEqual(
			[(r["sidebar"], r["link_to"]) for r in get_site_dock(APP)],
			[(ALPHA, None), (None, page), (BETA, page)],
		)

	def test_two_rows_into_one_module_key_apart(self):
		"""`Stock` and `Stock Analytics`: the module's own button, and a second button into the
		same shell that opens a particular page."""
		page = self.make_workspace("Test Dock Shape Second", ALPHA)

		save_site_dock(
			APP, payload(added(sidebar(ALPHA)), added(sidebar(ALPHA, link_type="Workspace", link_to=page)))
		)

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

		save_site_dock(APP, payload(added(sidebar(BETA, link_type="Workspace", link_to=page))))

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

		save_site_dock(
			APP, payload(added(sidebar("Users", link_type="Workspace", link_to="Welcome Workspace")))
		)

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

		save_site_dock(
			APP, payload(added(sidebar(GAMMA, link_type="Workspace", link_to=page)), added(workspace(page)))
		)

		# the workspace is permitted, the shell is not, so the conjunction refuses the row -- and
		# the bare pin at the same workspace still renders
		rendered = [
			(r["sidebar"], r["link_to"]) for r in dock_for(self.USER, among=None) if r["link_to"] == page
		]
		self.assertEqual(rendered, [(None, page)])

	def test_a_url_row_is_ungated(self):
		"""Nothing proves a web address and nothing gates one. It leaks no permission, and it is
		not new -- a person can already store an arbitrary URL in their own sidebar layer."""
		save_user_dock(
			APP, payload(added({"link_type": "URL", "url": "https://example.com", "title": "Out"}))
		)

		self.assertIn("https://example.com", names(dock_for(among=None)))

	def test_a_shell_is_proved_by_a_sidebar_document_or_a_module(self):
		"""Both, because most modules have a computed base and no `Sidebar` row -- and since a
		sidebar may be named something other than its module, asking `Module Def` alone would
		reject exactly the capability 01 added."""
		from frappe.desk.doctype.dock.dock import shell_exists

		self.assertTrue(shell_exists(ALPHA), "a module with no Sidebar document")
		self.assertTrue(shell_exists("Build"), "a Sidebar named something other than its module")
		self.assertFalse(shell_exists("Test Dock Shape Not A Shell"))

	# -- what the contract left --------------------------------------------------------

	def test_the_old_columns_are_gone_from_the_schema(self):
		"""The contract half of the pair 06 opened. Nothing reads them, and the translation that
		existed only because a child row's own primary key made `name` unusable goes with them."""
		meta = frappe.get_meta("Dock Item")
		self.assertIsNone(meta.get_field("type"))
		self.assertIsNone(meta.get_field("link_name"))

	def test_a_blank_column_reads_as_unset(self):
		"""What `stored_row` is still for once there is nothing to translate: the schema writes
		an empty string where every reader wants "unset", and a key built from two spellings of
		nothing would key one row two ways."""
		self.assertEqual(dock_key(stored_row({"sidebar": ALPHA, "url": ""})), dock_key(sidebar(ALPHA)))


class TestTheCompanionMount(DockTestCase):
	"""A companion app -- one with no rail of its own -- declaring that with **one column on its
	own record** rather than a flag on its rows.

	The reframe that settled it: the host lookup never read the hook's fragment, it read the
	rows, took the first host and broke. So what the hook carried was a one-per-companion
	*identity claim*, which is a record-level fact. A per-row host column would hold one value in
	every companion row and be blank in every other.
	"""

	HOST = "zz-dock-host"
	COMPANION = "zz-dock-companion"
	OTHER_COMPANION = "zz-dock-companion-two"
	USER = "test-dock-mount@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("User", self.USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self.USER,
					"first_name": "Dock Mount",
					"send_welcome_email": 0,
					"roles": [{"role": "Desk User"}],
				}
			).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		clear_arrangements()
		frappe.delete_doc("User", self.USER, force=True, ignore_missing=True)

	def host_and_companion(self, host_rows=None, companion_rows=None, mount_on=None):
		return shipped_dock(
			{
				self.HOST: [sidebar(ALPHA)] if host_rows is None else host_rows,
				self.COMPANION: {
					"items": [sidebar(BETA)] if companion_rows is None else companion_rows,
					"mount_on": self.HOST if mount_on is None else mount_on,
				},
			}
		)

	# -- the column ----------------------------------------------------------------------

	def test_a_dock_declares_the_app_it_mounts_on_as_an_app_name(self):
		"""Not a Link to a record: every consumer wants a string, and every app has three `Dock`
		records, so a mount aimed at a record would be a mount aimed at a *layer*."""
		field = frappe.get_meta("Dock").get_field("mount_on")

		self.assertEqual(field.fieldtype, "Autocomplete")
		self.assertEqual(field.options, "Installed Applications")

	def test_the_column_is_blank_on_an_ordinary_dock(self):
		with self.host_and_companion():
			self.assertIsNone(frappe.db.get_value("Dock", self.HOST, "mount_on"))
			self.assertEqual(frappe.db.get_value("Dock", self.COMPANION, "mount_on"), self.HOST)

	def test_the_column_is_blanked_on_a_layer_that_is_not_app_content(self):
		"""`depends_on` hides it on the two writable layers; it does not stop an API write, and a
		site row carrying a mount would put one person's arrangement on somebody else's rail."""
		with self.host_and_companion():
			save_site_dock(self.HOST, payload(ALPHA))
			doc = frappe.get_doc("Dock", frappe.db.get_value("Dock", {"app": self.HOST, "standard": 0}))
			doc.mount_on = self.COMPANION
			doc.save(ignore_permissions=True)

			self.assertIsNone(doc.mount_on)

	# -- what a mount does ---------------------------------------------------------------

	def test_a_companions_rows_land_appended_on_the_hosts_rail(self):
		"""Appended rather than positioned: a companion is not asserting an opinion into an
		arrangement that is not its."""
		with self.host_and_companion():
			self.assertEqual(names(dock_for(self.USER, among=None, app=self.HOST)), [ALPHA, BETA])

	def test_a_companion_has_no_rail_of_its_own(self):
		with self.host_and_companion():
			self.assertNotIn(self.COMPANION, resolve_dock())

	def test_appending_is_a_default_the_site_may_reorder(self):
		"""The reason it is only a default: the host's file is authored before the companion
		exists on any site, so where a companion's entries sit is the site's business."""
		with self.host_and_companion():
			save_site_dock(self.HOST, payload(BETA, ALPHA))

			self.assertEqual(names(dock_for(self.USER, among=None, app=self.HOST)), [BETA, ALPHA])

	def test_two_companions_mount_in_installation_order(self):
		with shipped_dock(
			{
				self.HOST: [sidebar(ALPHA)],
				self.COMPANION: {"items": [sidebar(BETA)], "mount_on": self.HOST},
				self.OTHER_COMPANION: {"items": [sidebar(GAMMA)], "mount_on": self.HOST},
			}
		):
			self.assertEqual(names(dock_for(self.USER, among=None, app=self.HOST)), [ALPHA, BETA, GAMMA])

	def test_a_mount_costs_the_apps_screen_slot(self):
		from frappe.boot import get_app_rail_host_map

		with self.host_and_companion():
			hosts = get_app_rail_host_map()

		self.assertEqual(hosts.get(self.COMPANION), self.HOST)
		self.assertNotIn(self.HOST, hosts)

	# -- a mount is conditional ----------------------------------------------------------

	def test_a_companion_whose_host_is_not_installed_is_an_ordinary_app(self):
		"""The invisible-companion bug. Resolution dropped the pin deliberately, but the boot
		path checked only the declarer -- so installing a companion without its host took its
		apps-screen slot away and gave it nothing."""
		from frappe.boot import get_app_rail_host_map

		with shipped_dock({self.COMPANION: {"items": [sidebar(BETA)], "mount_on": "not-an-app"}}):
			self.assertEqual(get_app_rail_host_map(), {})
			self.assertEqual(names(dock_for(self.USER, among=None, app=self.COMPANION)), [BETA])

	def test_a_companion_whose_host_ships_no_dock_is_an_ordinary_app(self):
		"""Mount onto a dock-less host and its rail becomes *entirely another app's entries*,
		with no route to its own module and the switcher gone -- and the common dock-less app
		ships exactly one module, so this is not an edge."""
		from frappe.boot import get_app_rail_host_map

		with shipped_dock({self.HOST: [], self.COMPANION: {"items": [sidebar(BETA)], "mount_on": self.HOST}}):
			self.assertEqual(get_app_rail_host_map(), {})
			self.assertEqual(names(dock_for(self.USER, among=None, app=self.COMPANION)), [BETA])
			self.assertNotIn(self.HOST, resolve_dock())

	def test_a_companion_that_ships_no_rows_is_an_ordinary_app(self):
		from frappe.boot import get_app_rail_host_map

		with self.host_and_companion(companion_rows=[]):
			self.assertEqual(get_app_rail_host_map(), {})

	def test_the_condition_reads_the_hosts_own_dock_rather_than_its_rail(self):
		"""So it does not go circular: resolving the host's rail is what wants this answer."""
		with self.host_and_companion():
			# the site hides everything the host ships; the mount still lands, because what it
			# asks about is the record rather than what this person ends up seeing
			save_site_dock(self.HOST, payload(sidebar(ALPHA, hidden=1)))

			self.assertEqual(mounted_apps().get(self.COMPANION), self.HOST)


class TestAnAppWithNoDock(DockTestCase):
	"""What an app that ships no `Dock` record resolves to: nothing at all.

	Zero entries rather than "every module it owns", which is what the entry set used to mean.
	That is what makes an app *dock-less* -- a state ticket 12 renders as no rail and a switcher
	in the sidebar header, rather than as a chrome-only stripe.
	"""

	APP = "zz-dock-none"
	USER = "test-dock-none@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("User", self.USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self.USER,
					"first_name": "Dock None",
					"send_welcome_email": 0,
					"roles": [{"role": "Desk User"}],
				}
			).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		clear_arrangements()

	def test_an_app_with_no_record_resolves_to_zero_entries(self):
		with shipped_dock({self.APP: []}):
			self.assertEqual(get_app_dock(self.APP), [])
			self.assertEqual(get_app_entry_set(self.APP), [])
			self.assertNotIn(self.APP, resolve_dock())

	def test_a_module_the_record_never_names_is_not_in_the_entry_set(self):
		"""Tier 3. Un-hiding is how a layer rescues an entry, and there is nothing to un-hide:
		the entry set is the record's rows, so the manager never offers the module and no
		hidden flag anywhere can bring it back."""
		with shipped_dock({self.APP: [sidebar(ALPHA)]}):
			self.assertEqual(names(get_app_entry_set(self.APP)), [ALPHA])
			self.assertNotIn(BETA, names(get_app_dock(self.APP)))

			# and un-hiding it says nothing, because nothing below holds it
			save_site_dock(self.APP, payload(added(sidebar(BETA, hidden=0))))
			self.assertNotIn(BETA, names(get_app_entry_set(self.APP)))

	def test_a_module_the_record_ships_hidden_can_be_rescued_by_either_layer(self):
		"""Tier 2, which needs no machinery of its own: the hidden map is seeded from the base,
		so one row above naming the entry with hiding off is the whole of bringing it back."""
		for layer, save in (("site", save_site_dock), ("person", save_user_dock)):
			with self.subTest(layer=layer), shipped_dock({self.APP: [sidebar(BETA, hidden=1)]}):
				save(self.APP, payload(sidebar(BETA, hidden=0)))

				self.assertEqual(hidden_by_name(dock_for(among=None, app=self.APP))[BETA], 0)
				clear_arrangements()

	def test_a_module_the_record_omits_is_still_navigable(self):
		"""Reachability is narrowed to discovery, not lost: the boot's sidebars are built from
		the navigable-modules list, not from the dock, so an omitted module still opens by
		route and still catches the entity resolver."""
		from frappe.desk.doctype.sidebar.sidebar import get_navigable_modules

		with shipped_dock({self.APP: [sidebar(ALPHA)]}):
			self.assertNotIn(BETA, names(get_app_entry_set(self.APP)))

		self.assertIn(BETA, get_navigable_modules())


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

	def test_a_foreign_row_is_dropped_and_named(self):
		"""A projection, not a refusal: a row that lives in another app's files is not this
		app's to ship, and saying which app it came from is what stops "some rows are missing"
		being something an author has to work out by diffing."""
		with sidebarless_module("Test Dock Emit Foreign", app=self.COMPANION) as foreign:
			page = frappe.get_doc(
				{
					"doctype": "Workspace",
					"title": "Test Dock Emit Foreign Page",
					"label": "Test Dock Emit Foreign Page",
					"module": foreign,
					"public": 1,
					"content": "[]",
				}
			).insert(ignore_permissions=True)
			self.addCleanup(frappe.delete_doc, "Workspace", page.name, force=True, ignore_missing=True)
			frappe.local.request_cache.clear()

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


class TestTheLandingFloor(IntegrationTestCase):
	"""Where an app's icon takes you stops being partly a guess.

	The ladder is *explicit route -> first visible rail entry -> first navigable module*, and the
	middle two are resolved on the client, late, so reordering a rail moves the landing with it.
	What the server owes it is the top of the ladder and the floor -- and the deletion of the
	fourth source that used to sit between them.
	"""

	def app_entry(self, app_name: str) -> dict:
		from frappe.boot import get_app_data
		from frappe.desk.desktop import get_workspaces

		pages = [page.name for page in get_workspaces()["pages"]]
		return next(app for app in get_app_data(pages) if app["app_name"] == app_name)

	def test_an_explicitly_declared_route_is_carried(self):
		"""The top of the ladder: an app may have a front door outside its rail, or outside the
		desk entirely, and this is the only way to have one."""
		self.assertEqual(self.app_entry("frappe")["app_route"], "/app/build")

	def test_the_derived_first_workspace_guess_is_gone(self):
		"""It picked a workspace by `sequence_id`, which was always a guess -- and this model
		makes it a worse one, because that workspace may sit in a module the app's record never
		names, so the icon would land somewhere the rail refuses to acknowledge."""
		with patch.object(frappe, "get_hooks", _no_app_home()):
			self.assertEqual(self.app_entry("frappe")["app_route"], "")

	def test_an_app_with_no_resolvable_landing_still_appears_on_the_apps_screen(self):
		"""The floor's reason for existing. An app that resolves to nothing used to be filtered
		off the screen, which was survivable while every app's rail was every module it owned --
		now it would leave a dock-less app with no rail *and* no icon, and no way in at all."""
		with patch.object(frappe, "get_hooks", _no_app_home()):
			self.assertTrue(self.app_entry("frappe")["on_apps_screen"])

	def test_the_switchers_first_module_is_the_landing_floor(self):
		"""The floor and the switcher's list are the same list, so the icon and the switcher's
		first row cannot disagree about where the app starts."""
		self.assertEqual(get_app_modules("frappe")[0], sorted_modules_of("frappe")[0])


def _no_app_home():
	"""`frappe.get_hooks` with frappe's own front door taken away, so the ladder's floor shows."""
	real = frappe.get_hooks

	def patched(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if hook in ("app_home", "add_to_apps_screen") and app_name == "frappe":
			return [] if hook == "app_home" else [{"name": "frappe", "title": "Framework"}]
		return real(hook, default, app_name)

	return patched


def sorted_modules_of(app: str) -> list[str]:
	"""The app's navigable modules in `modules.txt` order, worked out here rather than asked of
	the thing under test."""
	from frappe.app_state import get_disabled_modules
	from frappe.utils.modules import get_code_only_modules, get_visible_modules

	modules = get_visible_modules(frappe.get_all("Module Def", filters={"app_name": app}, pluck="name"))
	skip = get_disabled_modules() | set(get_code_only_modules())
	declared = {name: idx for idx, name in enumerate(frappe.get_module_list(app))}
	return sorted(
		(m for m in modules if m not in skip),
		key=lambda module: (declared.get(module, len(declared)), module),
	)


class TestTheAppsEntrySet(IntegrationTestCase):
	"""The order an app's modules take when nothing arranges them.

	Not the arrangement: where a module *sits* is `add_to_dock`, an ordered list in the app's
	`hooks.py`. This is the entry set that list orders, and an entry it never names trails the
	ones it does, in this order.
	"""

	def app_order(self, app: str = "frappe") -> list[str]:
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
		"""The site builds a rail for an app that ships none, which is what an author has in
		front of them before the dock is promoted to app content.

		Every row *adds*: there is nothing below to reference, so each carries its own icon and
		title -- which is also what the Add dialog asks for.
		"""
		save_site_dock(self.APP, payload(*[added(sidebar(module)) for module in modules]))

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
		save_user_dock(self.APP, payload(added(sidebar(self.TWO))))

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
			self.author(self.ONE)

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
