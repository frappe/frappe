# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.doctype.workspace.workspace import check_workspace_manager, is_workspace_manager
from frappe.desk.layers import resolve_layers
from frappe.model.document import Document

# Cached `user` for every `Dock` on the site, so resolving one costs a redis read rather than a
# query. The same trick as `Custom Sidebar`'s customized-keys cache, and it earns more here: a
# site nobody has arranged holds no `Dock` at all, so the whole surface is free.
DOCK_LAYERS_CACHE_KEY = "dock_layers"

# A blank `user` -- the site layer's address, spelled out so the layer reads as a value rather
# than as a falsy string.
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
# A `Sidebar` is proved by its `Module Def`, not by a `Sidebar` document. A sidebar's name *is*
# its module's name (`autoname: field:module`), and most modules have a computed base with no
# document at all -- so asking the `Sidebar` table would drop the common case.
PROVED_BY = {
	"Sidebar": "Module Def",
	"Workspace": "Workspace",
}
DOCK_TYPES = frozenset(PROVED_BY)

# `Dock Item` stores the second half of the pair as `link_name`, while every dict this module
# hands out or takes in calls it `name`. The column cannot be called `name`: on a child row that
# attribute is the row's own primary key, and autoname overwrites whatever is in it the moment the
# row is inserted. The translation is confined to `dock_rows` on the way out and `_save_layer` on
# the way in, so nothing above either has to know.


class Dock(Document):
	"""One of the dock's two stored layers: the site's arrangement, or one person's own.

	The two are the same shape because the rows are identical -- `user` is the whole difference,
	and the parent is what says whose an entry is. See `Custom Sidebar`, which layers the sidebar
	the same way and for the same reason.

	The layer below both of these is not a document at all: an app declares its fragment through
	the `add_to_dock` hook (see `get_app_dock`). The asymmetry with `Sidebar` / `Custom Sidebar`
	is deliberate -- a dock row accumulates no state a hook cannot express, whereas a sidebar
	carries sections, links and icons.
	"""

	_DOCTYPE_NAME = "Dock"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.dock_item.dock_item import DockItem
		from frappe.types import DF

		items: DF.Table[DockItem]
		user: DF.Link
	# end: auto-generated types

	def validate(self):
		# One spelling of "the site's layer", so the column's unique index can see two of them.
		# The column is also declared not-nullable, which is what makes this stick: a blank
		# `unique` column is written as `NULL`, and every NULL is distinct to an index -- which
		# would let the site layer exist twice while reading as one address to `layer_filter`.
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
		frappe.cache.delete_value(DOCK_LAYERS_CACHE_KEY)
		if self.user:
			# a person's own arrangement only invalidates their boot
			frappe.cache.hdel("bootinfo", self.user)
		else:
			frappe.cache.delete_key("bootinfo")


# One layer per address is enforced by the schema -- `user` is `unique` and not-nullable in the
# doctype -- rather than by a `validate` hook. A hook is bypassable (`db_insert`, a bulk write,
# anything that skips the document), and two documents at one address would give the merge two
# answers for the same layer.
#
# Declared on the field rather than added by an `on_doctype_update` hook because the two disagree:
# a column the doctype does not call `unique` has its index dropped on every migrate, and the hook
# would add it straight back, so each migrate would churn the table for nothing.


def layer_filter(user: str | None) -> dict:
	"""The filter naming one layer. The column is not-nullable, so the site layer is stored as
	`''` and there is only one spelling of "unset" to match."""
	return {"user": user or SITE_LAYER}


def get_dock_layers() -> set[str]:
	"""Cached addresses of every layer the site holds -- each person who has arranged their
	dock, plus `SITE_LAYER` if anyone has arranged the site's.

	This is the cost-control story: a boot on a site nobody has arranged answers both layers out
	of one redis read, instead of a query apiece. The addresses rather than the names, so a stale
	cache can only ever cost a lookup that finds nothing -- the same negative filter
	`Custom Sidebar` keeps, and for the same reason.
	"""
	layers = frappe.cache.get_value(DOCK_LAYERS_CACHE_KEY)
	if layers is None:
		layers = [row.user or SITE_LAYER for row in frappe.get_all("Dock", fields=["user"])]
		frappe.cache.set_value(DOCK_LAYERS_CACHE_KEY, layers)
	return set(layers)


def get_dock(user: str | None = None) -> "Dock | None":
	"""The document holding one layer, or None. Cheap when there is none."""
	if (user or SITE_LAYER) not in get_dock_layers():
		return None

	name = frappe.db.exists("Dock", layer_filter(user))
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

			if not frappe.db.exists(PROVED_BY[entry["type"]], entry["name"]):
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


def get_app_dock() -> list[dict]:
	"""The base every site starts from: each app's fragment, concatenated.

	An app orders its own entries and says nothing about another app's, so the fragments are
	meant not to overlap and concatenation is the whole composition. Apps-screen order decides
	which fragment comes first, so the dock reads in the same order as the screen people reach
	it from.

	*Meant* not to overlap: an entry belongs to one app, but nothing enforces that two fragments
	name different ones. Two rows under one key would render the entry twice -- the layers above
	dedupe their own rows and would not catch it, because the base is copied in whole -- so the
	first fragment to name an entry keeps it, which is the rule a layer already follows for a row
	it sees twice.

	Empty on a site where no app declares one -- and then the site's layer is simply the first
	there is, exactly as it was before this base existed.
	"""
	fragments = dock_fragments()
	if not fragments:
		return []

	rows, seen = [], set()
	for app in sorted(fragments, key=apps_screen_sort_key()):
		for row in fragments[app]:
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


def get_site_dock() -> list[dict]:
	"""The site's arrangement, curated by a Workspace Manager and applying to everyone."""
	return dock_rows(get_dock())


def get_user_dock(user: str | None = None) -> list[dict]:
	"""The session user's own arrangement.

	What the dock manager round-trips: it replaces only the current app's slice of a layer, so
	it has to see the layer it is editing rather than the resolved dock, which carries the
	site's rows too and would copy them into the person's own layer on the next save.
	"""
	return dock_rows(get_dock(user=user or frappe.session.user))


def resolve_dock() -> list[dict]:
	"""The dock as the session user sees it: app, then site, then their own.

	One flat list across every app -- a dock renders per app, but an arrangement is stored
	whole, so an app's slice can be replaced without disturbing the rest.

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
	"""
	resolved, hidden = resolve_layers(
		get_app_dock(),
		[get_site_dock(), get_user_dock()],
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


def is_reachable(entry) -> bool:
	"""Whether the session user may go where the entry points.

	Two gates because there are two kinds of entry, and each is the gate that already decides
	the thing it points at: module visibility for a sidebar -- whose name is its module's name --
	and the permitted workspace list for a workspace. Neither is anything the dock decides for
	itself, and a third kind would bring its own rather than reuse one of these.

	Existence is asked first, and only of the sidebar half. `is_module_visible` answers "not
	blocked", which a module that does not exist answers just as happily as one that does -- so
	on its own it lets a row naming a deleted or renamed module render an entry that leads
	nowhere. `shape_dock_rows` already proves existence on the way in, but the two paths that
	skip it are exactly the ones that go stale: a row stored before the module went away, and
	an `add_to_dock` row from an app whose module has been renamed since. The workspace half
	needs no equivalent -- `permitted_workspaces` is a membership test against real rows.
	"""
	from frappe.utils.modules import is_module_visible

	if entry.get("type") == "Sidebar":
		module = entry.get("name")
		return bool(frappe.db.exists("Module Def", module, cache=True)) and is_module_visible(module)

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
		if not frappe.db.exists(PROVED_BY[entry["type"]], entry["name"]):
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
def save_user_dock(items: list | str):
	"""Persist this person's own arrangement, which is applied on top of the site's."""
	return _save_layer(items, user=frappe.session.user, require_visible=True)


@frappe.whitelist()
def save_site_dock(items: list | str):
	"""Persist the site's arrangement, for everyone.

	The site layer's whole point: "Accounts first, for everyone" is not expressible by any
	number of per-person arrangements. A person's own still lands on top of it.
	"""
	check_workspace_manager(_("You need to be Workspace Manager to change the dock for everyone."))
	return _save_layer(items, user=None, require_visible=False)


def _save_layer(items: list | str, user: str | None, require_visible: bool):
	doc = get_dock(user=user)
	if doc:
		doc = frappe.get_doc("Dock", doc.name)
	else:
		doc = frappe.new_doc("Dock")
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

	# Both saves answer with the resolved dock, so the rail can be redrawn in place whichever
	# layer was written.
	return resolve_dock()


# A layer's raw rows, for the editor that is about to replace them. Not the resolved dock: an
# editor saves back the whole arrangement, so it has to be shown the layer it will overwrite.
# Kept out of the boot payload because it is only wanted the moment someone opens the manager.
#
# One endpoint per layer, each carrying its own gate, like the sidebar's saves and resets -- a
# single endpoint taking "which layer" would carry the gate in a branch instead.


@frappe.whitelist()
def get_user_dock_layer() -> list[dict]:
	"""This person's own arrangement. No gate: it is theirs, and it is all they can read."""
	return get_user_dock()


@frappe.whitelist()
def get_site_dock_layer() -> list[dict]:
	check_workspace_manager(_("You need to be Workspace Manager to see the dock's site layer."))
	return get_site_dock()


@frappe.whitelist()
def get_app_dock_layer() -> list[dict]:
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
	return [{"type": row["type"], "name": row["name"], "hidden": row["hidden"]} for row in get_app_dock()]


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
	declared = {dock_key(row): row["declared_by"] for row in get_app_dock()}

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
	import json

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
