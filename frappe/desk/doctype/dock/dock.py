# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.doctype.custom_sidebar.custom_sidebar import check_workspace_manager, is_workspace_manager
from frappe.desk.layers import resolve_layers
from frappe.model.document import Document

# Cached `(app, user) -> name` for every `Dock` on the site, so resolving one costs a redis read
# rather than a query. The same trick as `Custom Sidebar`'s customized-keys cache, and it earns
# more here: a site nobody has arranged holds no `Dock` at all, so the whole surface is free.
DOCK_LAYERS_CACHE_KEY = "dock_layers"

# A blank `app` and a blank `user` -- the site layer's address, spelled out so the layer reads as
# a value rather than as two falsy strings.
SITE_LAYER = ""

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
	"""One layer of the dock: an app's fragment, the site's arrangement, or one person's own.

	The three are the same shape because the rows are identical -- `app` and `user` are the whole
	difference, and the parent is what says whose an entry is. See `Custom Sidebar`, which layers
	the sidebar the same way and for the same reason.
	"""

	_DOCTYPE_NAME = "Dock"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.dock_item.dock_item import DockItem
		from frappe.types import DF

		app: DF.Autocomplete | None
		items: DF.Table[DockItem]
		user: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.validate_layer()
		self.validate_unique()
		self.anchor_the_items()

	def validate_layer(self):
		"""A document is exactly one layer, and the two columns are the address of which one.

		An app's fragment covers that app's own entries; the site's arrangement and a person's
		own span every app and name none. A document carrying both would be claiming to be two
		layers at once, and the merge would have no answer for where it goes.
		"""
		if self.app and self.user:
			frappe.throw(
				_("A dock belongs to an app or to a person, not to both."),
				title=_("Which Layer?"),
			)

	def validate_unique(self):
		existing = frappe.db.exists(
			self._DOCTYPE_NAME,
			{**layer_filter(self.app, self.user), "name": ["!=", self.name]},
		)
		if existing:
			frappe.throw(
				_("A dock for this layer already exists."),
				frappe.DuplicateEntryError,
			)

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


def layer_filter(app: str | None, user: str | None) -> dict:
	"""The filter naming one layer. A blank column is stored as `''` or `NULL` depending on how
	the row was written, so both spellings of "unset" have to match."""
	return {
		"app": app or ["in", ["", None]],
		"user": user or ["in", ["", None]],
	}


def get_dock_layers() -> set[tuple[str, str]]:
	"""Cached `(app, user)` addresses of every layer the site holds.

	This is the cost-control story: a boot on a site nobody has arranged answers all three
	layers out of one redis read, instead of a query apiece. The addresses rather than the
	names, so a stale cache can only ever cost a lookup that finds nothing -- the same negative
	filter `Custom Sidebar` keeps, and for the same reason.
	"""
	layers = frappe.cache.get_value(DOCK_LAYERS_CACHE_KEY)
	if layers is None:
		layers = [
			(row.app or SITE_LAYER, row.user or SITE_LAYER)
			for row in frappe.get_all("Dock", fields=["app", "user"])
		]
		frappe.cache.set_value(DOCK_LAYERS_CACHE_KEY, layers)
	return {tuple(layer) for layer in layers}


def get_dock(app: str | None = None, user: str | None = None) -> "Dock | None":
	"""The document holding one layer, or None. Cheap when there is none."""
	if (app or SITE_LAYER, user or SITE_LAYER) not in get_dock_layers():
		return None

	name = frappe.db.exists("Dock", layer_filter(app, user))
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


def get_app_dock() -> list[dict]:
	"""The base every site starts from: each app's own fragment, concatenated.

	An app orders its own entries and says nothing about another app's, so the fragments are
	meant not to overlap and concatenation is the whole composition. Apps-screen order decides
	which fragment comes first, so the dock reads in the same order as the screen people reach
	it from.

	*Meant* not to overlap: an entry belongs to one app, but nothing enforces that two fragments
	name different ones, and a fragment left behind by an app that is gone is free to name
	anything. Two rows under one key would render the entry twice -- the layers above dedupe
	their own rows and would not catch it, because the base is copied in whole -- so the first
	fragment to name an entry keeps it, which is the rule a layer already follows for a row it
	sees twice.

	Empty on a site where no app ships one, which is every site until an app does -- and then
	the site's layer is simply the first there is, exactly as it was before this base existed.
	"""
	fragments = {app for app, _user in get_dock_layers() if app}
	if not fragments:
		return []

	rows, seen = [], set()
	for app in sorted(fragments, key=apps_screen_sort_key()):
		for row in dock_rows(get_dock(app=app)):
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

	An app that is not installed is asked nothing: `get_hooks` imports the app to read them, so
	asking would raise rather than answer. It takes the default and trails, which is the right
	answer anyway -- a fragment left behind by an app that is gone is not one to lead the dock.
	"""
	from frappe.boot import DEFAULT_APP_SEQUENCE_ID

	installed = frappe.get_active_apps()

	def sequence(app: str) -> float:
		if app not in installed:
			return DEFAULT_APP_SEQUENCE_ID

		declared = frappe.get_hooks("add_to_apps_screen", app_name=app)
		return (declared and declared[0].get("sequence_id")) or DEFAULT_APP_SEQUENCE_ID

	def position(app: str) -> int:
		return installed.index(app) if app in installed else len(installed)

	return lambda app: (sequence(app), position(app), app)


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

	An entry no layer names is *absent from this list*, not appended to it: the client keeps it
	in its app's default order, trailing the entries a layer did name. That is what makes
	installing an app safe on a site that has already arranged its dock -- the new app's
	modules appear at the end rather than vanishing for want of a row.

	Resolved through `frappe.desk.layers`, the merge the sidebar's layers run on. An entry left
	hidden is *kept*, carrying its flag -- the dock renders a hidden entry rather than dropping
	it, which is the one thing it does differently from a sidebar.

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
	"""
	from frappe.utils.modules import is_module_visible

	if entry.get("type") == "Sidebar":
		return is_module_visible(entry.get("name"))

	if entry.get("type") == "Workspace":
		return entry.get("name") in permitted_workspaces()

	# unreachable through the whitelist, and spelled out rather than left as a fallthrough: a
	# third kind arriving here must bring its own gate rather than inherit the workspace one
	return False


def permitted_workspaces() -> set[str]:
	"""The workspaces this person may open. Only asked when a layer names one, which is never on
	a dock of nothing but modules -- and request-cached when it is."""
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
