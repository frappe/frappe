# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.desk.doctype.workspace.workspace import check_workspace_manager, is_workspace_manager
from frappe.desk.layers import resolve_layers
from frappe.model.document import Document

# Cached address of every `Dock` on the site -- app, user and standard -- so resolving one costs a
# redis read rather than a query. The same trick as `Custom Sidebar`'s customized-keys cache, and
# it earns more here: a site nobody has arranged and whose apps ship no dock holds no `Dock` at
# all, so the whole surface is free.
DOCK_LAYERS_CACHE_KEY = "dock_layers"

# A blank `user` -- the address every layer but a person's own carries, spelled out so it reads as
# a value rather than as a falsy string. `standard` is what tells the two of them apart: the app's
# own dock, or the site's arrangement of it.
SITE_LAYER = ""

# The hook an app declares its own dock fragment through: an ordered list of typed rows.
#
#   add_to_dock = [
#       {"type": "Sidebar", "name": "Stock"},
#       {"type": "Workspace", "name": "GST", "app": "erpnext"},
#   ]
#
# A row carrying `app` joins *that* app's fragment -- how a companion pins a workspace onto a
# host's rail. Absent means "my own fragment". Rows are dicts, never bare strings: a name on its
# own no longer says what kind of thing it names.
DOCK_HOOK = "add_to_dock"

# The kinds of thing a dock entry may name, and what proves the thing it names exists.
#
# `Dock Item.type` is an open Link to `DocType`, so the schema is no longer what closes the set --
# this is, at both ends: a `Dock` refuses a row naming any other doctype, and a saved arrangement
# drops one. Adding a third kind of entry is a row here rather than a column there.
#
# What proves the thing an entry names is really there, in words -- this is what an author is told
# when their row names nothing, and `entry_exists` is where each one is actually asked.
#
# A `Sidebar` row names a **shell**, and a shell is proved by *either* a `Sidebar` document or a
# `Module Def`: most modules have a computed base with no document at all, so asking the `Sidebar`
# table alone would drop the common case, while asking `Module Def` alone drops a sidebar that is
# named something other than its module (`Build`, under `Build Tools`). `module_of_shell` answers
# both at once, and is also what says which module's visibility gates the row.
PROVED_BY = {
	"Sidebar": "Sidebar or Module Def",
	"Workspace": "Workspace",
}
DOCK_TYPES = frozenset(PROVED_BY)

# `Dock Item` stores the second half of the pair as `link_name`, while every dict this module
# hands out or takes in calls it `name`. The column cannot be called `name`: on a child row that
# attribute is the row's own primary key, and autoname overwrites whatever is in it the moment the
# row is inserted. The translation is confined to `dock_rows` on the way out and `_save_layer` on
# the way in, so nothing above either has to know.


class Dock(Document):
	"""One layer of one app's dock: the app's own, the site's arrangement of it, or one person's.

	All three are the same shape because the rows are identical -- `app`, `user` and `standard`
	are the whole difference, and the parent is what says whose an entry is. See `Custom Sidebar`,
	which layers the sidebar the same way, in a table of its own.

	One table rather than a doctype per layer, which is where ADR 0004 is consciously amended:
	`Workspace`, `Report`, `Print Format`, `Notification` and `Dashboard Chart` all mix exported
	and site-created rows in one table, and the app layer's read-only-ness is a code guard
	(`validate_app_content`) rather than a permission row.

	A dock belongs to an app. Storing every app's rows in one flat pair of layers was already
	friction -- the manager edits one app at a time and had to avoid copying the site's rows for
	*other* apps into a person's own layer -- and per-app records delete that dance outright.
	"""

	_DOCTYPE_NAME = "Dock"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.dock_item.dock_item import DockItem
		from frappe.types import DF

		app: DF.Autocomplete
		items: DF.Table[DockItem]
		standard: DF.Check
		user: DF.Link
	# end: auto-generated types

	def autoname(self):
		"""An app's own dock is named after the app; everything else takes a hash.

		Forced by the export road, where the record's name *is* the path: a hash-named standard
		record would write `<app>/dock/6a1f9c2e/6a1f9c2e.json`, and a re-export from a fresh
		bench would mint a second file with the first left as a permanent orphan.

		An opaque name costs the other two layers nothing, because a layer is looked up by
		filter and never by name. Leaving `self.name` unset here is what falls through to the
		doctype's own `autoname: hash`.
		"""
		if self.standard:
			self.name = self.app

	def validate(self):
		# One spelling of "not a person's own layer", so the composite index can see two of them.
		# The column is also declared not-nullable, which is what makes this stick: a blank column
		# in a unique index is written as `NULL`, and every NULL is distinct to an index -- which
		# would let one app hold two site layers while both read as one address to `layer_filter`.
		self.user = self.user or SITE_LAYER
		self.anchor_the_items()

	def anchor_the_items(self):
		"""Every entry points at exactly one thing, and the typed pair is what says which.

		A row missing either half says nothing at all -- half a pair names nothing -- and is
		dropped rather than refused, the way a `Custom Sidebar` reference anchored to nothing is.
		This is also what empties a row written before the pair existed rather than corrupting
		it: its old columns are not read, so it reads as anchorless and falls out.

		A whole row whose `type` is a doctype the dock does not have is different. It *does* say
		something, and what it says is not storable, so it is refused rather than quietly kept
		for a reader that will never know what to do with it.

		The refusal runs first so the row number it quotes is the one the author is looking at:
		re-setting the table renumbers `idx`, and a message pointing at a row that has already
		moved is worse than no message.
		"""
		for row in self.items:
			if row.type and row.link_name and row.type not in DOCK_TYPES:
				frappe.throw(
					_("Row #{0}: a dock entry names a Sidebar or a Workspace, not a {1}.").format(
						row.idx, row.type
					)
				)

		self.set("items", [row for row in self.items if row.type and row.link_name])

	def _validate_links(self):
		"""A row *names* something to navigate to; it does not reference it.

		The same call `Custom Sidebar` makes, for the same reason: one deleted workspace would
		otherwise turn every later write to this layer into an error. A row naming something
		that is gone stops applying when the dock resolves, which is already what happens to a
		row whose target the reader may not see.

		It is also what lets a `Sidebar` row name a module whose sidebar is a computed base: the
		`Sidebar` table holds no document for it, and a Dynamic Link would refuse it.
		"""
		return

	def on_update(self):
		self.clear_dock_cache()

	def on_trash(self):
		self.clear_dock_cache()

	def clear_dock_cache(self):
		drop_dock_caches(self.user)


def on_doctype_update():
	"""One layer per address, enforced by the schema rather than by a `validate` hook.

	A hook is bypassable (`db_insert`, a bulk write, anything that skips the document), and two
	documents at one address would give the merge two answers for the same layer.

	Composite, because an address is three columns now. `user` alone was right while a layer
	spanned every app; per-app records make it wrong -- it would let one person arrange exactly
	one app's rail. And `standard` is in the index because an app's own dock and the site's
	arrangement of it are two documents at the same `(app, user)`: one shipped, one curated, and
	the site's is what `Reset for everyone` drops without touching the app's.
	"""
	frappe.db.add_unique("Dock", ("app", "user", "standard"), constraint_name="unique_layer_address")


def rename_sidebar_rows(old_name: str, new_name: str) -> None:
	"""Point every dock row naming a sidebar at what that sidebar is called now.

	Mostly a **fallback**, not the only pass. `rename_doc` runs `rename_dynamic_links` before it
	calls `after_rename`, and `Dock Item.link_name` is a Dynamic Link, so the framework normally
	does this already. Normally: that pass walks `get_dynamic_link_map()`, which is derived from
	the distinct `type` values already in the table and cached for twelve hours -- so on a site
	whose map was built before any dock row was a `Sidebar`, it does nothing at all. This is what
	makes the outcome the same either way.

	The rows are updated in place rather than through their parent. A `Dock` is the site's
	arrangement or one person's own, and re-saving one to correct a name it holds would re-run
	validation nobody asked for. Invalidating is then this function's own job: `get_dock` reads
	a `Dock` through `get_cached_doc`, so the document's cache entry is the one that goes stale.
	`rename_doc` happens to flush the whole site cache a few lines after `after_rename` returns,
	which would cover it -- but a helper that leaves its own writes visibly stale is only correct
	while its one caller stays the way it is, and this one costs two queries.
	"""
	named = {"parenttype": "Dock", "type": "Sidebar", "link_name": old_name}
	layers = frappe.get_all("Dock Item", filters=named, pluck="parent", distinct=True)
	if not layers:
		return

	frappe.db.set_value("Dock Item", named, "link_name", new_name, update_modified=False)
	# name *and* user in one read: `drop_dock_caches` wants the user, and fetching each layer as
	# a document to get it would pull every one of its item rows along for a single column
	for layer in frappe.get_all("Dock", filters={"name": ["in", layers]}, fields=["name", "user"]):
		frappe.clear_document_cache("Dock", layer.name)
		drop_dock_caches(layer.user)


def drop_dock_caches(user: str | None) -> None:
	"""Drop the caches a dock layer is read out of, for whoever holds it.

	A module function rather than only a method, because a rename edits the rows in place and
	never loads the parent -- and reading a whole `Dock` to find out whose it is would be a
	document fetch for one column.
	"""
	frappe.cache.delete_value(DOCK_LAYERS_CACHE_KEY)
	if user:
		# a person's own arrangement only invalidates their boot
		frappe.cache.hdel("bootinfo", user)
	else:
		frappe.cache.delete_key("bootinfo")


def layer_filter(app: str, user: str | None, standard: int = 0) -> dict:
	"""The filter naming one layer. The columns are not-nullable, so every layer but a person's
	own is stored with `user = ''` and there is only one spelling of "unset" to match."""
	return {"app": app, "user": user or SITE_LAYER, "standard": standard}


def get_dock_layers() -> set[tuple[str, str, int]]:
	"""Cached addresses of every layer the site holds: `(app, user, standard)`, one per document.

	This is the cost-control story: a boot on a site nobody has arranged answers every layer of
	every app out of one redis read, instead of a query apiece. The addresses rather than the
	names, so a stale cache can only ever cost a lookup that finds nothing -- the same negative
	filter `Custom Sidebar` keeps, and for the same reason.
	"""
	layers = frappe.cache.get_value(DOCK_LAYERS_CACHE_KEY)
	if layers is None:
		layers = [
			[row.app, row.user or SITE_LAYER, int(row.standard or 0)]
			for row in frappe.get_all("Dock", fields=["app", "user", "standard"])
		]
		frappe.cache.set_value(DOCK_LAYERS_CACHE_KEY, layers)
	return {tuple(layer) for layer in layers}


def get_dock(app: str, user: str | None = None, standard: int = 0) -> "Dock | None":
	"""The document holding one layer of one app's dock, or None. Cheap when there is none."""
	if (app, user or SITE_LAYER, standard) not in get_dock_layers():
		return None

	name = frappe.db.exists("Dock", layer_filter(app, user, standard))
	return frappe.get_cached_doc("Dock", name) if name else None


def dock_rows(dock: "Dock | None") -> list[dict]:
	"""One layer's stored rows, in row order. Row order is the arrangement.

	Where the stored `link_name` column becomes the `name` half of the pair every reader above
	here works in. Half-written rows are dropped again rather than trusted to `validate`, which
	only ran on the layers this site has saved since the pair existed.
	"""
	if not dock:
		return []

	return [
		{"type": row.type, "name": row.link_name, "hidden": int(row.hidden or 0)}
		for row in dock.items
		if row.type and row.link_name
	]


def hook_row(row, declared_by: str) -> dict | None:
	"""One `add_to_dock` entry as the merge takes it, or None if it says nothing storable.

	Rows are dicts, never bare strings -- a name on its own no longer says what kind of thing it
	names. `declared_by` rides along because the walk already knows it: the projection Ship emits
	is then exact rather than derived from where a module's files happen to live.

	Hiding travels with the row, which is what lets an app ship an entry off by default. The
	layers above may bring it back; see `resolve_layers`, which seeds its hidden map from here.
	"""
	if not isinstance(row, dict):
		return None

	entry = points_at(row)
	if entry["type"] not in DOCK_TYPES or not entry["name"]:
		return None

	return {**entry, "hidden": int(row.get("hidden") or 0), "declared_by": declared_by}


def dock_fragments() -> dict[str, list[dict]]:
	"""Each app's fragment: the rows it declared for itself, then the pins aimed at it.

	A row carrying `app` joins *that* app's fragment rather than its declarer's, which is how a
	companion's workspace reaches a host's rail. It is appended after the host's own entries
	rather than positioned among them -- a companion is not asserting a default into an
	arrangement that is not its, and two companions pinning into one host land in installation
	order rather than fighting for a slot.

	Attribution is forced rather than chosen: a row grouped under its declarer would never render
	on the host's rail at all, which is precisely the bug the pin has always had.
	"""
	installed = frappe.get_active_apps()
	own: dict[str, list[dict]] = {}
	pinned: dict[str, list[dict]] = {}

	for app in installed:
		for raw in frappe.get_hooks(DOCK_HOOK, app_name=app) or []:
			row = hook_row(raw, declared_by=app)
			if not row:
				continue
			# a pin at a host that is not here names no fragment, so it joins none -- the same
			# silence a row naming a workspace nobody may open resolves to
			host = raw.get("app")
			if host and host not in installed:
				continue
			(pinned if host else own).setdefault(host or app, []).append(row)

	return {app: own.get(app, []) + pinned.get(app, []) for app in own.keys() | pinned.keys()}


def check_dock_hooks() -> list[str]:
	"""Every `add_to_dock` row an app declared that the dock cannot use, described in words.

	Nothing reads a dock hook except the boot, and the boot's answer to a row it does not
	understand is to leave it out. That is the right answer at boot -- one bad row must not cost
	an app its whole rail -- but it means an author who typed `"Sidbar"` or named a module that
	has since been renamed sees no error at all, just a rail button that never appears. This is
	where they are told.

	Run at migrate, which is when an author has just edited `hooks.py`, and after the modules
	have been synced -- so a row naming a module the app added in this very release is not
	reported as naming a module that does not exist.

	Returns descriptions rather than printing them, so the caller decides where they go and a
	test can read them.
	"""
	problems = []
	installed = frappe.get_active_apps()

	for app in installed:
		for raw in frappe.get_hooks(DOCK_HOOK, app_name=app) or []:
			if not isinstance(raw, dict):
				problems.append(f"{app}: {raw!r} is not a row -- a dock entry is a dict, not a bare name")
				continue

			entry = points_at(raw)
			if entry["type"] not in DOCK_TYPES:
				kinds = " or ".join(sorted(DOCK_TYPES))
				problems.append(f"{app}: {raw!r} names a {entry['type']!r}, and a dock entry is a {kinds}")
				continue

			if not entry["name"]:
				problems.append(f"{app}: {raw!r} names nothing")
				continue

			# A pin at an app that is not installed is silence by design, not a mistake: a
			# companion may be installed before or without its host.
			host = raw.get("app")
			if host and host not in installed:
				continue

			if not entry_exists(entry):
				proof = PROVED_BY[entry["type"]]
				problems.append(f"{app}: {raw!r} names a {proof} that does not exist on this site")

	return problems


def report_dock_hook_problems() -> None:
	"""Print what `check_dock_hooks` found. Nothing at all when there is nothing to say."""
	problems = check_dock_hooks()
	if not problems:
		return

	import click

	click.secho("\nSome add_to_dock rows will not render:", fg="yellow", bold=True)
	for problem in problems:
		click.secho(f"  {problem}", fg="yellow")
	click.secho("")


def get_dock_workspaces() -> dict[str, list[str]]:
	"""App -> the workspaces its fragment names, in fragment order.

	What folds a companion's pin into the host's entry set, and the whole of what the pin needed:
	a row grouped under its declarer would never render on the host's dock at all, which is the
	bug the hook has carried since it was written. An app's own `Workspace` rows land here too --
	the pin is a row-level difference, not a second mechanism.

	Names only, because that is all the boot payload's entry set is. Whether a person may open one
	is the caller's to apply, so a pin is gated by its workspace's own Roles table like any other.
	"""
	return {
		app: list(dict.fromkeys(row["name"] for row in rows if row["type"] == "Workspace"))
		for app, rows in dock_fragments().items()
	}


def get_app_dock(app: str) -> list[dict]:
	"""The base one app's layers are laid over: the rows that app's fragment declares.

	Per app, because a `Dock` is. The old cross-app concatenation existed only because the two
	stored layers spanned every app and had to be laid over one list; with a layer addressed by
	app plus user there is nothing to concatenate, and two apps' arrangements can no longer reach
	each other at all.

	Empty for an app that declares no fragment -- and then that app's site layer is simply the
	first there is, exactly as it was before this base existed.

	*Deduped*, because a fragment may name one entry twice: two rows under one key would render
	the entry twice, and the layers above dedupe their own rows without catching it, since the
	base is copied in whole. First named keeps it, which is the rule a layer already follows.
	"""
	rows, seen = [], set()
	for row in dock_fragments().get(app, []):
		key = dock_key(row)
		if key in seen:
			continue
		seen.add(key)
		rows.append(row)
	return rows


def apps_screen_sort_key():
	"""Sort key putting apps in the order the apps screen lists them.

	The same two keys that screen sorts on -- the `sequence_id` an app declares in
	`add_to_apps_screen`, then installation order for the apps that declare none.

	Only installed apps are ever asked: a fragment is a hook, and a hook belongs to an app that
	is here to declare it.
	"""
	from frappe.boot import DEFAULT_APP_SEQUENCE_ID

	installed = frappe.get_active_apps()

	def sequence(app: str) -> float:
		declared = frappe.get_hooks("add_to_apps_screen", app_name=app)
		return (declared and declared[0].get("sequence_id")) or DEFAULT_APP_SEQUENCE_ID

	return lambda app: (sequence(app), installed.index(app), app)


def get_site_dock(app: str) -> list[dict]:
	"""The site's arrangement of one app's dock, curated by a Workspace Manager and applying to
	everyone."""
	return dock_rows(get_dock(app))


def get_user_dock(app: str, user: str | None = None) -> list[dict]:
	"""One person's own arrangement of one app's dock.

	What the dock manager round-trips: it replaces the layer whole, so it has to see the layer it
	is editing rather than the resolved dock, which carries the site's rows too and would copy
	them into the person's own layer on the next save.
	"""
	return dock_rows(get_dock(app, user=user or frappe.session.user))


def resolve_dock() -> dict[str, list[dict]]:
	"""The dock as the session user sees it: one resolved rail per app, keyed by app.

	Keyed by app because a `Dock` is per app. One flat cross-app list was what the two stored
	layers used to be, and the client had to intersect it with each app's entry set to find the
	rows meant for the rail on screen; with a layer addressed by app plus user, the rail *is*
	its app's entry and no intersection is needed.

	**Three classes of entry come out of this, not two.** The distinction is the whole of how a
	shipped order and an arrangement live together, and this is the only place it is written
	down:

	1. **Named by a layer.** At the front, in the order the layers left them.
	2. **In the base but named by no layer.** Present, trailing the named ones, at their real
	   index in base order. This is what makes an app's shipped order apply to the entries
	   nobody rearranged -- without it, shipping an order would only ever reach a fresh install.
	3. **In neither.** *Absent from this list*, not appended to it: the client keeps such an
	   entry in its app's own order, behind both classes above (`MAX_SAFE_INTEGER` on the
	   client). That is what makes installing an app safe on a site that has already arranged
	   its dock -- the new app's modules appear at the end rather than vanishing for want of a
	   row.

	Resolved through `frappe.desk.layers`, the merge the sidebar's layers run on. **An entry left
	hidden stays in this list, carrying its flag**, and the client drops it from the rail. That
	is forced by the dock manager's Hidden pane, which cannot render what the payload has already
	discarded -- and it is the one thing the dock does differently from a sidebar, which drops a
	hidden item outright.

	Every entry carries the typed pair it was stored as. The client keys on both halves, so a
	`Sidebar` and a `Workspace` of one name stay two entries all the way to the rail.

	Apps that resolve to nothing are left out rather than carried as empty lists: the payload is
	read by key, and an absent key and an empty list say the same thing to every reader.
	"""
	resolved = {}
	for app in docked_apps():
		rail = resolve_app_dock(app)
		if rail:
			resolved[app] = rail
	return resolved


def docked_apps() -> list[str]:
	"""Every app whose dock could resolve to something: one that ships a fragment, or one some
	layer on this site has an opinion about.

	Asking every installed app instead would be correct and nearly as cheap -- both reads below
	are cached -- but it would walk apps that have never had a rail on any site.
	"""
	apps = set(dock_fragments()) | {app for app, _user, _standard in get_dock_layers()}
	return sorted(apps, key=apps_screen_sort_key())


def resolve_app_dock(app: str) -> list[dict]:
	"""One app's rail for the session user: its own dock, then the site's, then their own."""
	resolved, hidden = resolve_layers(
		get_app_dock(app),
		[get_site_dock(app), get_user_dock(app)],
		key=dock_key,
		apply_row=apply_dock_row,
	)
	# Applied last, so no layer can name its way past the gates -- an arrangement is navigation
	# reach, and reach is decided by module visibility and workspace permissions alone.
	return [
		{**points_at(entry), "hidden": int(hidden.get(dock_key(entry), 0))}
		for entry in resolved
		if is_reachable(entry)
	]


def dock_key(entry) -> str:
	"""What a dock entry is identified by: the thing it points at, kind and name together.

	The degenerate case of the sidebar's `item_key`. That one has two shapes because a sidebar
	row may point nowhere and needs an identity anyway; a dock entry always points somewhere, so
	nothing is stored. Both halves, because the two kinds do not share a namespace: a `Sidebar`
	and a `Workspace` called "Stock" are two entries, not one.
	"""
	return f"{entry.get('type')}::{entry.get('name')}"


def apply_dock_row(row, entry: dict | None) -> dict:
	"""What one layer row does to the dock entry it names: it is the entry.

	Never skipped, unlike a sidebar row, because a row here carries the whole entry -- so a row
	naming something no layer below it mentioned is an entry the dock has, not a reference to
	one that is missing. And nothing to override: the row carries what it points at and a
	hidden flag, and the flag is the merge's business rather than the entry's.
	"""
	return points_at(row)


def points_at(entry) -> dict:
	"""The typed pair that says where an entry goes. Always both halves: the name on its own no
	longer says what kind of thing it names, which is the point of typing the row."""
	return {"type": entry.get("type"), "name": entry.get("name")}


def entry_exists(entry) -> bool:
	"""Whether the thing an entry names is on this site.

	Existence, not reach -- `is_reachable` is the per-user question and asks this first. A
	`Sidebar` row is answered by `module_of_shell`, which says `None` for a shell that is not
	there and the module for one that is, so one call proves both halves.
	"""
	from frappe.desk.doctype.sidebar.sidebar import module_of_shell

	if entry.get("type") == "Sidebar":
		return bool(module_of_shell(entry.get("name")))

	if entry.get("type") == "Workspace":
		return bool(frappe.db.exists("Workspace", entry.get("name"), cache=True))

	return False


def is_reachable(entry) -> bool:
	"""Whether the session user may go where the entry points.

	Two gates because there are two kinds of entry, and each is the gate that already decides
	the thing it points at: module visibility for a sidebar -- a row of that kind names a shell,
	and a shell belongs to exactly one module -- and the permitted workspace list for a
	workspace. Neither is anything the dock decides for itself, and a third kind would bring its
	own rather than reuse one of these.

	Existence is asked first, and only of the sidebar half. `is_module_visible` answers "not
	blocked", which a module that does not exist answers just as happily as one that does -- so
	on its own it lets a row naming a deleted or renamed shell render an entry that leads
	nowhere. `shape_dock_rows` already proves existence on the way in, but the two paths that
	skip it are exactly the ones that go stale: a row stored before the shell went away, and
	an `add_to_dock` row from an app whose module has been renamed since. The workspace half
	needs no equivalent -- `permitted_workspaces` is a membership test against real rows.
	"""
	from frappe.desk.doctype.sidebar.sidebar import module_of_shell
	from frappe.utils.modules import is_module_visible

	if entry.get("type") == "Sidebar":
		module = module_of_shell(entry.get("name"))
		return bool(module) and is_module_visible(module)

	if entry.get("type") == "Workspace":
		return entry.get("name") in permitted_workspaces()

	# unreachable through the whitelist, and spelled out rather than left as a fallthrough: a
	# third kind arriving here must bring its own gate rather than inherit the workspace one
	return False


def permitted_workspaces() -> set[str]:
	"""The workspaces this person may open.

	Asked on any site where a fragment or a layer names one, which is every site carrying a pin.
	It costs nothing: it rides the request-cached workspace list the sidebar already computes on
	every boot.
	"""
	from frappe.desk.desktop import get_workspaces

	return {page.name for page in get_workspaces()["pages"]}


def shape_dock_rows(items: list | str, require_visible: bool) -> list[dict]:
	"""One saved arrangement, narrowed to rows that can be stored.

	`items` is the whole ordered arrangement the client is showing -- the shape a Sortable
	produces -- not a delta. A row is a typed pair: `{"type": "Sidebar", "name": "Stock"}` or
	`{"type": "Workspace", "name": "Payables", "hidden": 1}`. The bare-name shorthand went with
	the untyped row, because a name on its own no longer says what it names.

	A row missing either half, or naming a kind that is not on the whitelist, is dropped -- the
	same treatment a row naming nothing has always had. The set is closed here as well as in
	`Dock.validate` because these rows never pass through a document until after they are shaped.

	Existence is checked separately from visibility because `is_module_visible` answers a
	different question -- an unknown module is simply "not blocked", so it passes that check
	and would then name nothing when the dock resolved. One lookup against the doctype the row's
	kind is proved by, where there used to be a hand-written check per column.

	`require_visible` is what the two writable layers disagree about. A person's own arrangement
	is filtered by their reach, so it can never resurface something permissions hide. The
	site's is not: it is written for everyone, and dropping the rows the saver personally cannot
	see would let one Workspace Manager's blocked module quietly delete the site's intent for
	it. Reach is applied to the *resolved* dock either way.
	"""
	shaped, seen = [], set()

	for row in frappe.parse_json(items) or []:
		if not isinstance(row, dict):
			continue

		entry = points_at(row)
		# Both halves have to be a non-empty string. These rows are client JSON, so this is also
		# what keeps a dict out of the lookup below: `frappe.db.exists` reads one as *filters*
		# rather than as a name, which would turn a saved arrangement into a query surface.
		if not all(isinstance(half, str) and half for half in (entry["type"], entry["name"])):
			continue
		if entry["type"] not in DOCK_TYPES:
			continue
		if not entry_exists(entry):
			continue

		key = dock_key(entry)
		if key in seen:
			continue
		if require_visible and not is_reachable(entry):
			continue

		seen.add(key)
		shaped.append({**entry, "hidden": int(row.get("hidden") or 0)})

	return shaped


# ---------------------------------------------------------------------------------------
# Write API
# ---------------------------------------------------------------------------------------


@frappe.whitelist()
def save_user_dock(app: str, items: list | str):
	"""Persist this person's own arrangement of `app`'s dock, applied on top of the site's."""
	return _save_layer(app, items, user=frappe.session.user, require_visible=True)


@frappe.whitelist()
def save_site_dock(app: str, items: list | str):
	"""Persist the site's arrangement of `app`'s dock, for everyone.

	The site layer's whole point: "Accounts first, for everyone" is not expressible by any
	number of per-person arrangements. A person's own still lands on top of it.
	"""
	check_workspace_manager(_("You need to be Workspace Manager to change the dock for everyone."))
	return _save_layer(app, items, user=None, require_visible=False)


def _save_layer(app: str, items: list | str, user: str | None, require_visible: bool):
	"""Replace one layer of one app's dock with `items`, and answer with the rail it leaves.

	The whole layer, not a slice of it. A `Dock` is per app, so the rows the client sends are
	the only rows this document holds -- which is what retires the dance the flat list needed,
	where a save had to carry every *other* app's rows through untouched or lose them.
	"""
	app = check_docked_app(app)

	doc = get_dock(app, user=user)
	if doc:
		doc = frappe.get_doc("Dock", doc.name)
	else:
		doc = frappe.new_doc("Dock")
		doc.app = app
		doc.user = user or SITE_LAYER

	doc.set("items", [])
	for row in shape_dock_rows(items, require_visible=require_visible):
		# the shaped row's `name` lands in the `link_name` column -- see the note beside
		# `PROVED_BY` for why the column cannot be called what the pair calls it
		doc.append("items", {"type": row["type"], "link_name": row["name"], "hidden": row["hidden"]})

	# ignore_permissions: a person arranging their own dock need not hold write access to this
	# doctype, and the site layer's gate is the role check its endpoint already made. The
	# arrangement is re-filtered through reach on every boot regardless of what is stored here.
	doc.save(ignore_permissions=True)

	# Both saves answer with this app's resolved rail, so it can be redrawn in place whichever
	# layer was written. This app's and no other: the save touched one document.
	return resolve_app_dock(app)


def check_docked_app(app: str | None) -> str:
	"""The app a layer is being written for, refused unless it is installed.

	`app` arrives from the client on every write and every layer read, and it is stored: an
	unchecked value would let a layer be filed under an app that does not exist, where nothing
	would ever resolve it and nothing would ever reap it.

	Active rather than merely installed, which is the same set `dock_fragments` and
	`apps_screen_sort_key` already walk: a disabled app has no rail to arrange.
	"""
	app = (app or "").strip()
	if not app or app not in frappe.get_active_apps():
		frappe.throw(_("{0} is not an app on this site.").format(frappe.bold(app or "-")))
	return app


# A layer's raw rows, for the editor that is about to replace them. Not the resolved dock: an
# editor saves back the whole arrangement, so it has to be shown the layer it will overwrite.
# Kept out of the boot payload because it is only wanted the moment someone opens the manager.
#
# One endpoint per layer, each carrying its own gate, like the sidebar's saves and resets -- a
# single endpoint taking "which layer" would carry the gate in a branch instead.


@frappe.whitelist()
def get_user_dock_layer(app: str) -> list[dict]:
	"""This person's own arrangement of one app's dock. No gate: it is theirs, and it is all they
	can read."""
	return get_user_dock(check_docked_app(app))


@frappe.whitelist()
def get_site_dock_layer(app: str) -> list[dict]:
	check_workspace_manager(_("You need to be Workspace Manager to see the dock's site layer."))
	return get_site_dock(check_docked_app(app))


@frappe.whitelist()
def get_app_dock_layer(app: str) -> list[dict]:
	"""What the apps ship, as the manager needs to read it: the typed pair and the hidden flag.

	No gate, because it is a read of app content -- the same thing every boot already carries in
	`app_data`, minus the reach filter the resolved dock applies.

	This is what tells the manager *who* hid a row. "Hidden" is otherwise silent about it, and a
	person un-hiding what an app deliberately shipped off should at least be told they are doing
	that. It is a **call**, not a doctype: materialising the hook into records to answer this one
	question is the mirror the app layer exists to avoid.

	`declared_by` is dropped: which app declared a row is the projection Ship needs, not the
	manager, and shipping it here would put an app name in every editor payload.
	"""
	return [
		{"type": row["type"], "name": row["name"], "hidden": row["hidden"]}
		for row in get_app_dock(check_docked_app(app))
	]


# ---------------------------------------------------------------------------------------
# Making a module of the site's own
# ---------------------------------------------------------------------------------------


@frappe.whitelist()
def create_module(module: str, app: str | None = None, icon: str | None = None) -> dict:
	"""Make a module the site is adding for itself, and hand the dock what it needs to show it.

	The page it opens on comes with it, and comes from the module rather than from here: a
	custom module makes one in `ModuleDef.after_insert`, because a module with nothing to
	navigate to is a module nobody can get to whichever end created it. So this endpoint is the
	dock's half and nothing more -- a name, a placement, and the answer the manager needs.

	`app` is placement and nothing else (see `Module Def.validate_placement`): it says whose dock
	lists the module. Left out, the module stands on its own on the desktop instead, which is
	what a dock with no app context would be adding to.

	`icon` is what the dock draws it with. It is stored on the page rather than here, because a
	computed sidebar reads its header icon off the module's own page (`own_page_icon`) -- there
	is nowhere else on a module for one to live.

	Answers with the entry the dock now offers *and* everything a workspace write invalidates
	(`workspace_payload`), so the desk can show the module without a reload. The workspace list
	is in there for a reason: a page the boot has never heard of is a page the desk cannot place,
	and it reads as one nobody but its owner can see -- which is not what was created.
	"""
	from frappe.desk.doctype.workspace.workspace import module_name_is_free, workspace_payload

	check_workspace_manager(_("You need to be Workspace Manager to add this."))
	# Two rights, because this is two things: the page the module brings with it is navigation
	# everybody boots, which is the check above, and the module itself is not that kind of thing
	# at all. Asked here rather than left to the insert, so a refusal names the right that is
	# missing instead of naming a doctype.
	if not frappe.has_permission("Module Def", "create"):
		frappe.throw(_("You need to be System Manager to add this."), frappe.PermissionError)

	module = (module or "").strip()
	if not module:
		frappe.throw(_("It needs a name."))

	# Both halves are named after it -- a `Module Def` by its module name, a `Workspace` by its
	# label -- so the name has to be free of both. Refused here rather than left to a duplicate
	# key, and refused in one sentence: which of the two holds it is a fact about how this is
	# built, and either way the answer is that the name will not do.
	#
	# A page that already names this module is not holding it: that is a module's own page, left
	# behind when the module was deleted, and making the module again takes it back.
	if not module_name_is_free(module):
		frappe.throw(_("Something here is already called {0}. Try another name.").format(module))

	doc = frappe.get_doc(
		{"doctype": "Module Def", "module_name": module, "app_name": app or None, "custom": 1}
	)
	doc.flags.page_icon = icon or None
	doc.insert()

	return workspace_payload(entry={"type": "Sidebar", "name": module})


# ---------------------------------------------------------------------------------------
# Ship: rendering an arrangement as the hook that would produce it
# ---------------------------------------------------------------------------------------


def owners_of(rows: list[dict]) -> list[str | None]:
	"""Which app's files each row lives in, in the order they arrived.

	The hook's own attribution first, because it is exact: `get_app_dock` walked the apps and
	knows which one declared each row, so a pin resolves to the companion that pinned it rather
	than to whoever owns the workspace. Everything else falls back to the module the entry is
	rooted in, which is what "lives in" means for an entry no fragment names yet.
	"""
	declared = {dock_key(row): row["declared_by"] for rows in dock_fragments().values() for row in rows}

	def owner(entry) -> str | None:
		if app := declared.get(dock_key(entry)):
			return app
		if entry.get("type") == "Sidebar":
			return frappe.db.get_value("Module Def", entry.get("name"), "app_name")
		if entry.get("type") == "Workspace":
			module = frappe.db.get_value("Workspace", entry.get("name"), "module")
			return module and frappe.db.get_value("Module Def", module, "app_name")
		return None

	return [owner(row) for row in rows]


def fragment_app(owners: list[str | None]) -> str | None:
	"""Whose fragment an arrangement on screen is: the app most of its rows live in.

	Resolved from the rows rather than taken from the client's app name, which is the apps-screen
	title key from `add_to_apps_screen` and is not always the app whose files an entry lives in.
	Reading it here means this cannot be talked into naming a different app's `hooks.py`.

	The old "one app, else throw" guard is deliberately *not* carried over: a pin makes a
	multi-app screen legal, and refusing one would refuse exactly the case the projection exists
	for. Ties fall to first appearance, so a two-row screen still answers.
	"""
	tally: dict[str, int] = {}
	for app in owners:
		if app:
			tally[app] = tally.get(app, 0) + 1

	if not tally:
		return None

	first_seen = list(tally)
	return max(tally, key=lambda app: (tally[app], -first_seen.index(app)))


def hooks_path(app: str) -> str:
	"""Where the block belongs, relative to the bench, because that is how a person says it."""
	import os

	from frappe.utils import get_bench_path

	return os.path.relpath(frappe.get_app_path(app, "hooks.py"), get_bench_path())


def render_dock_hook(rows: list[dict]) -> str:
	"""The `add_to_dock = [...]` block for `rows`, as Python somebody pastes.

	Hiding is emitted, order is the list's, and nothing else is: a row is the typed pair plus the
	flag, which is the whole of what a fragment can say.
	"""
	lines = ["add_to_dock = ["]
	for row in rows:
		parts = [f'"type": {json.dumps(row["type"])}', f'"name": {json.dumps(row["name"])}']
		if row.get("hidden"):
			parts.append('"hidden": 1')
		lines.append("\t{" + ", ".join(parts) + "},")
	lines.append("]")
	return "\n".join(lines)


@frappe.whitelist()
def emit_dock_hook(app: str | None = None, items: list | str | None = None) -> dict:
	"""The arrangement on screen, rendered as the `add_to_dock` block that would produce it.

	**Nothing is written.** The target is `hooks.py` -- hand-authored Python with comments and
	conditionals, which the framework writes exactly once, at `bench new-app`, from a template.
	An AST-splicing emitter would be the first thing to ever edit one, for the least valuable
	inch of the operation. The drag-and-drop is where the value was, and it survives intact.

	Developer mode at both ends, and no role check. The gate is kept for meaning rather than for
	safety now that this is read-only: the action is meaningless without a `hooks.py` to paste
	into, and read-only is a property of today's implementation rather than a promise.

	Reads the arrangement **on screen**, not the layer's stored rows. These differ, and the
	difference is chosen: shipping from a user scope on a site whose site layer hid an entry
	emits it hidden. What you see is what you ship.

	Emit is a **projection**: the app's own rows in their relative order, foreign rows dropped
	and named. A companion's pin is already declared in the companion's own `hooks.py`, and a pin
	is appended rather than positioned, so where it sits on screen is layer business no block can
	state.

	It names **every entry the manager showed** -- the left pane as positions, the right pane as
	`hidden: 1` -- so ship round-trips: paste, restart, and the dock renders the screen it was
	taken from. "An unnamed entry trails" survives intact; unnamed now only ever means an entry
	the manager never showed, i.e. one the app added after the block was authored.

	`app` names the screen for the message below and decides nothing.
	"""
	from frappe.desk.doctype.sidebar.sidebar import check_developer_mode

	check_developer_mode()

	rows = shape_dock_rows(items or [], require_visible=False)
	owners = owners_of(rows)
	target = fragment_app(owners)
	if not target:
		frappe.throw(
			_("There is no order to ship for {0}.").format(frappe.bold(app or _("this app"))),
			title=_("Nothing to Ship"),
		)

	owned, dropped = [], []
	for row, owner in zip(rows, owners, strict=True):
		if owner == target:
			owned.append(row)
		else:
			dropped.append({**points_at(row), "declared_by": owner})

	return {
		"app": target,
		"code": render_dock_hook(owned),
		"path": hooks_path(target),
		"dropped": dropped,
	}


# ---------------------------------------------------------------------------------------
# Who may touch which layer
# ---------------------------------------------------------------------------------------


def has_permission(doc, ptype="read", user=None, debug=False):
	"""A Workspace Manager curates the site and the apps; everyone else has only their own layer.

	The document-level half of the gate the endpoints hold. A `Desk User` holds `read` and
	nothing more -- arranging a dock goes through `save_user_dock`, which writes one person's own
	layer with `ignore_permissions`, so no write permission has to exist for the surface to work
	and none is granted. This is what stops the read they *do* hold from being a read of
	everybody else's.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or is_workspace_manager(user):
		return True

	return bool(doc.user) and doc.user == user


def get_permission_query_conditions(user=None):
	"""Everyone but a Workspace Manager lists only their own layer.

	The pair to `has_permission`, and not redundant with it: this is what keeps one person's
	arrangement out of everybody else's *reads* -- reports, the API and the desk's export all go
	through it rather than through the document-level check. Deliberately the same two functions
	`Custom Sidebar` carries, because it is the same layering and the same gate.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or is_workspace_manager(user):
		return ""

	return f"`tabDock`.`user` = {frappe.db.escape(user)}"
