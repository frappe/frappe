# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _

# The same flags `Sidebar` reads, because they answer the same question: is the system placing
# app content on a site, or is a person editing? Shared rather than copied -- a route added to one
# list and not the other would break exactly one of the two doctypes on customer sites.
from frappe.desk.doctype.sidebar.sidebar import SYSTEM_WRITE_FLAGS
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

# What a dock entry points at, and what proves each half of it is really there.
#
# An entry does **two** things when clicked: it opens a **page** and it swaps the **shell**. Each
# exists without the other -- a URL row is a page with no shell, a module row is a shell with no
# particular page -- which is why they are separate columns rather than one typed pair.
#
#   sidebar                              a module's rail button
#   sidebar + link_type/link_to          a second button into one module
#   link_type/link_to                    a pin; the shell is derived from what it opens
#   link_type=URL + url                  a link out; no shell at all
#
# `DESTINATION_FIELDS` is the identity: `dock_key` joins exactly these and stores nothing. The
# direct generalisation of the sidebar's `LINKED_IDENTITY_FIELDS` -- "the columns it already has,
# so there is no second copy to keep in step and nothing for a rename to break". It needs no
# stored-key fallback the way the sidebar does, because the sidebar's second shape is for a row
# that links nowhere (a Section Break) and the dock has none: all four blank is not an entry.
#
# Two things it settles by construction rather than by policy. `icon` and `title` are **outside**
# it, so re-labelling cannot detach a row from itself; `sidebar` and `link_to` are **inside** it,
# so re-pointing is not an edit -- it names a different row.
DESTINATION_FIELDS = ("sidebar", "link_type", "link_to", "url")

# The two kinds of page a row may open. Only these: a Report or a DocType list belongs inside a
# module's sidebar, not on a rail of roughly a dozen destinations -- and `Report` is the one kind
# that would need new boot payload. Widening later costs a Select value, not a column.
#
# `Sidebar` is deliberately *not* a value here. A module entry is a row with `sidebar` filled and
# no target; naming the module in a type value as well would say it twice.
DOCK_LINK_TYPES = frozenset({"Workspace", "URL"})

# What proves each filled column is really there, in words -- this is what an author is told when
# their row names nothing, and `entry_exists` is where each one is actually asked.
#
# `sidebar` is proved by *either* a `Sidebar` document or a `Module Def`. Most modules have a
# computed base with no document at all, so asking the `Sidebar` table alone would drop the common
# case; and since 01 a `Sidebar` may be named something other than its module, so asking
# `Module Def` alone would reject exactly the new capability.
#
# `url` is proved by nothing, which is not an oversight -- see `is_reachable`.
PROVED_BY = {
	"sidebar": "Sidebar or Module Def",
	"Workspace": "Workspace",
}

# The columns a stored `Dock Item` carries. One list, so copying a row from one layer to another
# -- which is what promoting the site's arrangement to app content is -- cannot quietly drop a
# column somebody added to the schema.
DOCK_ITEM_FIELDS = (*DESTINATION_FIELDS, "icon", "title", "added", "hidden")

# The old pair, kept beside the new columns until 08 contracts them. `type` was a `DocType` link
# whose being filled said which kind of thing, and `link_name` the name of that thing. Every
# reader prefers the new columns when a row carries them and falls back to these when it does not,
# so a layer stored before this release keeps working.
#
# `link_name` and not `name`, for the record: on a child row `name` is the row's own primary key,
# and autoname overwrites whatever is in it the moment the row is inserted.
LEGACY_TYPES = {"Sidebar", "Workspace"}


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
		self.validate_app_content()
		self.validate_standard()
		self.anchor_the_items()

	def validate_app_content(self):
		"""Only developer mode may set or clear the standard flag, because it is app content.

		Conditional, where `Sidebar`'s equivalent is blanket. It has to be: all three layers live
		in this one table, and the site's and each person's rows have to stay writable at
		runtime -- a blanket guard would refuse every `save_user_dock`. Without *any* guard, a
		Workspace Manager (who holds `write` on `Dock`) could take an app's row, clear the flag,
		and convert git-versioned app content into a site row they own.

		`is_new()` is load-bearing: on an unsaved document `has_value_changed` answers True for
		every field, so without it every site- and user-layer row would be refused outside
		developer mode.

		The system-write flags are not optional either -- each of them is a real route by which
		an app's dock reaches a site, and without the escape, installing or updating an app that
		ships one fails on every customer site.
		"""
		if not (self.standard or (not self.is_new() and self.has_value_changed("standard"))):
			return

		if frappe.conf.developer_mode:
			return

		if any(frappe.flags.get(flag) for flag in SYSTEM_WRITE_FLAGS):
			return

		frappe.throw(
			_(
				"{0}'s dock belongs to its app and can only be authored in developer mode. "
				"Arrange the dock instead to change it for this site."
			).format(frappe.bold(self.app)),
			title=_("Not Editable"),
		)

	def validate_standard(self):
		"""Refuse to mark a dock standard unless we can actually write its file.

		`standard` means "there is a JSON file in an app behind this row", and a row whose file
		is missing counts as an orphan -- `remove_orphan_entities` would delete it on the next
		`bench migrate`. Better to refuse than to create a row that quietly deletes itself.

		Where `Sidebar` checks that a module resolves to a folder, this checks that the app is
		installed: an app-rooted record has no module folder to find, and the app is the whole
		address.

		A system write is exempt from the developer-mode half for the same reason
		`validate_app_content` is: an app install or a migrate places a row whose file is already
		on disk, so demanding developer mode would refuse the very write the file exists for.
		The app check still runs, because that one is about the file being writable at all.
		"""
		if not self.standard:
			return

		if not self.has_value_changed("standard") and not self.has_value_changed("app"):
			return

		if not any(frappe.flags.get(flag) for flag in SYSTEM_WRITE_FLAGS):
			check_developer_mode()

		if self.app not in frappe.get_installed_apps():
			frappe.throw(
				_("App {0} is not installed, so a standard dock cannot be written to it.").format(
					frappe.bold(self.app)
				)
			)

	def anchor_the_items(self):
		"""Every entry names a shell, a page, or both. One that names neither says nothing.

		The rule the typed pair used to state as "a row needs both halves". A row now needs a
		`sidebar`, a target, or both -- because the two things a click does are separable, and a
		row filling only one of them is the ordinary case rather than half of something.

		An anchorless row is dropped rather than refused, the way a `Custom Sidebar` reference
		anchored to nothing is. That is also what quietly empties a row written before these
		columns existed but *not* carrying the old pair either.

		A row whose `link_type` is outside the set is different. It *does* say something, and what
		it says is not storable, so it is refused rather than quietly kept for a reader that will
		never know what to do with it.

		The refusal runs first so the row number it quotes is the one the author is looking at:
		re-setting the table renumbers `idx`, and a message pointing at a row that has already
		moved is worse than no message.
		"""
		for row in self.items:
			if row.link_type and row.link_type not in DOCK_LINK_TYPES:
				frappe.throw(
					_("Row #{0}: a dock entry opens a Workspace or a web address, not a {1}.").format(
						row.idx, row.link_type
					)
				)
			# the old column carried the same closed set, and is refused on the same terms while
			# it is still read
			if row.type and row.link_name and row.type not in LEGACY_TYPES:
				frappe.throw(
					_("Row #{0}: a dock entry names a Sidebar or a Workspace, not a {1}.").format(
						row.idx, row.type
					)
				)

		self.set("items", [row for row in self.items if points_somewhere(stored_row(row))])

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
		self.export_dock()

	def on_trash(self):
		self.clear_dock_cache()

	def clear_dock_cache(self):
		drop_dock_caches(self.user)

	def export_dock(self):
		"""Write this dock to its file. Every Save keeps the file current, which is what makes
		authoring in Manage Dock and shipping the result one thing rather than two.

		`<app>/dock/<app>/<app>.json`: the ordinary per-record folder, rooted at the app instead
		of at a module. That shape is the whole of the export road -- the import walk and orphan
		cleanup work on it with no machinery of their own, because the filename and the record
		name agree, which is exactly what the old hand-written app-level fixtures got wrong.
		"""
		from frappe.modules.export_file import export_to_files

		if not self.standard or frappe.flags.in_import or not frappe.conf.developer_mode:
			return

		export_to_files(record_list=[["Dock", self.name]], record_app=self.app)

	def exported_file_path(self) -> str:
		"""The path `export_to_files` writes this dock to.

		Asked of the export module rather than rebuilt here, so the file this checks for is by
		construction the file the export writes.
		"""
		from frappe.modules.export_file import export_root, exported_file_path

		return exported_file_path(export_root(record_app=self.app), self.doctype, self.name)

	def is_exported(self) -> bool:
		"""Whether the file behind this dock is really on disk.

		This is the question orphan cleanup asks, so `mark_as_standard` has to answer it before
		claiming the dock is shipped.
		"""
		import os

		if self.is_new() or not self.app:
			return False

		try:
			return os.path.exists(self.exported_file_path())
		except (frappe.DoesNotExistError, ImportError):
			# no app on the bench, so no file -- `get_app_path` says so by throwing
			frappe.clear_last_message()
			return False


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


# ---------------------------------------------------------------------------------------
# Making a dock app content, and taking it back
#
# `standard` means an app ships this dock as a JSON file. The two actions below turn that on
# and off, and both of them move the file as well as the flag.
#
# There is no bench command and no CI check to go with them, deliberately. The "standard check"
# is three existing mechanisms at three moments: `validate_standard` refuses the flag unless the
# file can be written, `is_exported` verifies the write landed and rolls back if it did not, and
# the reaper deletes a row whose file went away. Drift self-heals on this road -- `on_update`
# re-exports on Save, a hand-edited file is re-imported on migrate -- so a command would report a
# state the system already prevents.
# ---------------------------------------------------------------------------------------


@frappe.whitelist()
def mark_as_standard(app: str) -> str:
	"""Make `app`'s dock part of the app: write it into the app's folder so the app ships it,
	and let `bench migrate` import it back from there. Returns the document's name.

	One act, not two. The flag and the file go together, and the row is rolled back if the write
	did not land -- a standard row with no file is exactly the orphan the next `bench migrate`
	deletes, so a mark that wrote nothing must leave no row behind either.

	**No materialize step**, which is where this parts company with `Sidebar`'s: a sidebar has a
	computed base to be shipped when no document holds one, and a dock has none. A dock-less app
	gets no rail, so there is nothing to promote until somebody has authored rows.
	"""
	app = check_docked_app(app)
	check_developer_mode()

	doc = get_dock(app, standard=1)
	if doc:
		doc = frappe.get_doc("Dock", doc.name)
		# Already shipped, so there is nothing to do. We check the flag *and* the file: a standard
		# row whose file has gone missing is exactly the orphan this action exists to prevent, so
		# we write it again rather than report success.
		if doc.is_exported():
			return doc.name
	else:
		# The site's arrangement is what an author has been editing, so that is what gets shipped.
		# Copied rather than re-parented: the site's own layer stays where it is, so unmarking
		# leaves the site exactly as it was before the promotion.
		site = get_dock(app)
		doc = frappe.new_doc("Dock")
		doc.app = app
		for row in site.items if site else []:
			doc.append("items", {field: row.get(field) for field in DOCK_ITEM_FIELDS})

	savepoint = "mark_dock_standard"
	frappe.db.savepoint(savepoint)
	try:
		doc.standard = 1
		# `save` inserts a freshly built record and updates an existing one. Either way it is
		# `on_update` that writes the file.
		doc.save(ignore_permissions=True)

		if not doc.is_exported():
			frappe.throw(_("Could not write {0}'s dock to it. Left unchanged.").format(frappe.bold(app)))
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise
	frappe.db.release_savepoint(savepoint)

	frappe.msgprint(
		_("{0}'s dock is now standard and exported to the app.").format(frappe.bold(app)),
		alert=True,
		indicator="green",
	)
	return doc.name


@frappe.whitelist()
def unmark_as_standard(app: str) -> None:
	"""Give `app`'s dock back to the site: delete its exported file and its document.

	The document goes rather than just the flag. Once the app content is gone there is nothing
	for the app to fall back to -- a dock has no computed base -- so the honest report is that
	the app now has no rail, which is the asymmetry with `Sidebar`'s unmark: that one means "this
	module falls back to its computed base".

	The file has to go too. Left on disk, the next `bench migrate` imports it again and the row
	comes back standard, so deleting the document on its own would not survive a migrate.
	"""
	import os
	import shutil

	app = check_docked_app(app)
	check_developer_mode()

	doc = get_dock(app, standard=1)
	if not doc:
		return

	path = doc.exported_file_path() if doc.is_exported() else None
	frappe.delete_doc("Dock", doc.name, force=True, ignore_permissions=True)

	# Delete the file now rather than on commit. If someone un-marks and marks again in one
	# request, we want to end up with the file the second call wrote -- not with a queued delete
	# that removes it afterwards.
	if path:
		shutil.rmtree(os.path.dirname(path), ignore_errors=True)

	frappe.msgprint(
		_("{0} now has no rail; its exported dock has been removed.").format(frappe.bold(app)),
		alert=True,
		indicator="orange",
	)


def check_developer_mode() -> None:
	"""Refuse unless developer mode is on.

	`standard` means there is a file inside an app, and only a developer's site writes files
	into apps.
	"""
	if frappe.conf.developer_mode:
		return

	frappe.throw(
		_("Enable developer mode to change whether a dock is standard -- it is backed by a file in its app."),
		title=_("Not Editable"),
	)


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
	# Both columns, while both are read. `sidebar` is the new home of a shell name and `type` +
	# `link_name` the old one, and a site may hold rows in either shape until 08 drops the pair.
	named = [
		({"parenttype": "Dock", "sidebar": old_name}, "sidebar"),
		({"parenttype": "Dock", "type": "Sidebar", "link_name": old_name}, "link_name"),
	]

	layers = set()
	for filters, column in named:
		rows = frappe.get_all("Dock Item", filters=filters, pluck="parent", distinct=True)
		if not rows:
			continue
		frappe.db.set_value("Dock Item", filters, column, new_name, update_modified=False)
		layers.update(rows)

	if not layers:
		return

	# name *and* user in one read: `drop_dock_caches` wants the user, and fetching each layer as
	# a document to get it would pull every one of its item rows along for a single column
	for layer in frappe.get_all("Dock", filters={"name": ["in", list(layers)]}, fields=["name", "user"]):
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


def stored_row(row) -> dict:
	"""One stored `Dock Item`, read as the shape every reader above here works in.

	**This is the expand half of the pair 08 contracts.** The new columns are preferred when a row
	carries them, and the old typed pair is read when it does not -- so a layer saved before this
	release, and an app whose dock is still a hook, both keep rendering. The whole of the old form
	is these seven lines; nothing above here knows which shape it came from.

	The old pair translates one way each:

	    {"type": "Sidebar",   "name": "Stock"}  ->  sidebar = "Stock"
	    {"type": "Workspace", "name": "GST"}    ->  link_type = "Workspace", link_to = "GST"

	which is exactly what the two columns always meant, spelled where the reader can act on it.
	"""
	entry = {field: row.get(field) or None for field in DESTINATION_FIELDS}

	if not any(entry.values()):
		legacy_type, legacy_name = row.get("type"), row.get("link_name") or row.get("name")
		if legacy_type == "Sidebar":
			entry["sidebar"] = legacy_name or None
		elif legacy_type == "Workspace":
			entry["link_type"], entry["link_to"] = "Workspace", legacy_name or None

	return {
		**entry,
		"icon": row.get("icon") or None,
		"title": row.get("title") or None,
		"added": int(row.get("added") or 0),
		"hidden": int(row.get("hidden") or 0),
	}


def points_somewhere(entry) -> bool:
	"""Whether a row says anything a rail can act on: a shell, a page, or both.

	A page is its `link_type` *plus* whichever column that type fills, so a `link_type` on its own
	is as anchorless as a blank row -- and a `URL` row is anchored by its `url`, not by a
	`link_to` it will never have.
	"""
	if entry.get("sidebar"):
		return True
	if entry.get("link_type") == "URL":
		return bool(entry.get("url"))
	return bool(entry.get("link_type") and entry.get("link_to"))


def dock_rows(dock: "Dock | None") -> list[dict]:
	"""One layer's stored rows, in row order. Row order is the arrangement.

	Anchorless rows are dropped again rather than trusted to `validate`, which only ran on the
	layers this site has saved since the columns existed.
	"""
	if not dock:
		return []

	rows = [stored_row(row) for row in dock.items]
	return [row for row in rows if points_somewhere(row)]


def get_app_dock(app: str) -> list[dict]:
	"""**An app's dock is exactly its record's rows.** Empty when it ships none.

	The entry set, not just an order over one. A module this record never names is off this app's
	rail for good -- no layer above can bring it back, because there is nothing there to name.
	That is the third of three tiers an author picks from:

	    named, hidden: 0     on the rail
	    named, hidden: 1     off the rail, and the site *or* the person can bring it back
	    not named            off the rail, and nobody can

	The middle tier needs no machinery of its own: `resolve_layers` seeds its hidden map from the
	base, so one row above naming that entry with hiding off is the whole of bringing it back.

	**Reachability is narrowed to discovery, not lost.** The boot's sidebars are built from the
	navigable-modules list rather than from the dock, so a module this record omits still has a
	sidebar in the payload, still opens by route, and still catches the entity resolver. What it
	loses is the rail as a place to *find* it.

	*Deduped*, because a record may name one entry twice: two rows under one key would render the
	entry twice, and the layers above dedupe their own rows without catching it, since the base is
	copied in whole. First named keeps it, which is the rule a layer already follows.
	"""
	shipped = get_dock(app, standard=1)
	if not shipped:
		return []

	rows, seen = [], set()
	for row in dock_rows(shipped):
		key = dock_key(row)
		if key in seen:
			continue
		seen.add(key)
		rows.append(row)
	return rows


def get_app_entry_set(app: str) -> list[dict]:
	"""Every entry `app`'s dock offers this person, before any layer arranges them.

	What the boot payload carries as `app_data[].dock` and what the manager builds its panes
	from. Filtered by reach and by nothing else: which of them are *on* the rail, and in what
	order, is the layers' business and is answered by `resolve_app_dock`.
	"""
	return [rail_entry(row) for row in get_app_dock(app) if is_reachable(row)]


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

	Every entry carries the whole destination it was stored with, plus its icon and title. The
	client keys on the destination, so two rows into one module stay two entries all the way to
	the rail.

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
	"""Every app whose dock could resolve to something: one that ships a record, or one some
	layer on this site has an opinion about.

	Both come off the same cached read, which is what keeps a boot on a site nobody has arranged
	free. Asking every installed app instead would be correct and nearly as cheap, but it would
	walk apps that have never had a rail on any site.
	"""
	return sorted({app for app, _user, _standard in get_dock_layers()}, key=apps_screen_sort_key())


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
		{**rail_entry(entry), "hidden": int(hidden.get(dock_key(entry), 0))}
		for entry in resolved
		if is_reachable(entry)
	]


def dock_key(entry) -> str:
	"""What a dock entry is identified by: the whole destination, and nothing else.

	The direct generalisation of the sidebar's `LINKED_IDENTITY_FIELDS` -- the columns the row
	already has, so there is no second copy to keep in step and nothing for a rename to break.
	Nothing is stored, and no second shape is needed: the sidebar keeps one for a row that links
	nowhere, and a dock row that points nowhere is not an entry at all.

	It keeps the distinctions of the row shape real. `Stock` (a shell) and `Stock Analytics` (that
	shell plus a workspace) key apart, as do a bare `GST` pin and a `Welcome` row that overrides
	its shell.
	"""
	return "|".join(entry.get(field) or "" for field in DESTINATION_FIELDS)


def apply_dock_row(row, entry: dict | None) -> dict:
	"""What one layer row does to the dock entry it names: it is the entry.

	Never skipped, unlike a sidebar row, because a row here carries the whole entry -- so a row
	naming something no layer below it mentioned is an entry the dock has, not a reference to
	one that is missing.
	"""
	return rail_entry(row)


def rail_entry(entry) -> dict:
	"""What the rail is handed: where the entry goes, and how it reads."""
	return {**{field: entry.get(field) for field in DESTINATION_FIELDS}, **overrides(entry)}


def overrides(entry) -> dict:
	"""What a row says about how an entry reads. Blank is no opinion."""
	return {"icon": entry.get("icon"), "title": entry.get("title")}


def entry_exists(entry) -> bool:
	"""Whether everything an entry names is on this site.

	Existence, not reach -- `is_reachable` is the per-user question and asks this first. One check
	per **filled column**, conjoined, because a row may fill more than one and each half has to be
	there for the click to land.

	`sidebar` is answered by `shell_exists`, which accepts either a `Sidebar` document or a
	`Module Def`. `url` is proved by nothing but being non-empty, which `points_somewhere` has
	already asked.
	"""
	if entry.get("sidebar") and not shell_exists(entry["sidebar"]):
		return False

	if entry.get("link_type") == "Workspace":
		return bool(frappe.db.exists("Workspace", entry.get("link_to"), cache=True))

	return True


def shell_exists(shell: str) -> bool:
	"""Whether a shell is on this site: a `Sidebar` document, or a `Module Def` whose sidebar is a
	computed base.

	Both, and this is the widening ticket 01 forced. Most modules have no `Sidebar` row at all, so
	asking that table alone would drop the common case; and a sidebar may now be named something
	other than its module, so asking `Module Def` alone would reject exactly the new capability.
	"""
	return bool(
		frappe.db.exists("Module Def", shell, cache=True) or frappe.db.exists("Sidebar", shell, cache=True)
	)


def is_reachable(entry) -> bool:
	"""Whether the session user may go where the entry points.

	**One gate per filled column, conjoined: a row passes only if every column it fills passes.**

	    sidebar     its module exists and is module-visible
	    Workspace   in `permitted_workspaces()`
	    URL         none -- always passes

	Both failure directions are real, which is why it is a conjunction rather than a first-match
	branch. *Shell blocked, workspace permitted* -- the `Welcome` shape -- would otherwise render
	**the whole sidebar of a module the person has blocked**, the block undone by a row pointing
	past it. *Shell visible, workspace not* is the stale-row failure the existence check was added
	to prevent.

	Existence comes first for the shell half. `is_module_visible` answers "not blocked", which a
	module that does not exist answers just as happily as one that does -- so on its own it lets a
	row naming a deleted or renamed shell render an entry that leads nowhere.

	**A module-less shell contributes no module gate**, exactly as a URL is ungated: a `Sidebar`
	rooted at its app belongs to no module, so there is no module visibility to consult, and its
	existence is the whole of the question.

	The URL door being ungated is deliberate and is not new: a person can already store an
	arbitrary URL in their own sidebar layer. It leaks no permission.
	"""
	from frappe.desk.doctype.sidebar.sidebar import module_of_shell
	from frappe.utils.modules import is_module_visible

	if shell := entry.get("sidebar"):
		if not shell_exists(shell):
			return False
		module = module_of_shell(shell)
		if module and not is_module_visible(module):
			return False

	if entry.get("link_type") == "Workspace" and entry.get("link_to") not in permitted_workspaces():
		return False

	return True


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
	produces -- not a delta. A row names a shell, a page, or both:

	    {"sidebar": "Stock"}
	    {"sidebar": "Stock", "link_type": "Workspace", "link_to": "Stock Analytics"}
	    {"link_type": "Workspace", "link_to": "Payables", "hidden": 1}
	    {"link_type": "URL", "url": "https://...", "icon": "book", "title": "Docs"}

	A row naming nothing, or naming a `link_type` that is not on the whitelist, is dropped -- the
	same treatment a row naming nothing has always had. The set is closed here as well as in
	`Dock.validate` because these rows never pass through a document until after they are shaped.

	Existence is checked separately from visibility because `is_module_visible` answers a
	different question -- an unknown module is simply "not blocked", so it passes that check
	and would then name nothing when the dock resolved.

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

		entry = stored_row(row)
		# Every destination column has to be a non-empty string or absent. These rows are client
		# JSON, so this is also what keeps a dict out of the lookups below: `frappe.db.exists`
		# reads one as *filters* rather than as a name, which would turn a saved arrangement into
		# a query surface.
		if any(value is not None and not isinstance(value, str) for value in destination(entry).values()):
			continue
		if entry["link_type"] and entry["link_type"] not in DOCK_LINK_TYPES:
			continue
		if not points_somewhere(entry):
			continue
		if not entry_exists(entry):
			continue

		key = dock_key(entry)
		if key in seen:
			continue
		if require_visible and not is_reachable(entry):
			continue

		seen.add(key)
		shaped.append(entry)

	return shaped


def destination(entry) -> dict:
	"""Just the columns that say where an entry goes -- what `dock_key` is built from."""
	return {field: entry.get(field) for field in DESTINATION_FIELDS}


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
		doc.append("items", {field: row[field] for field in DOCK_ITEM_FIELDS})

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

	Active rather than merely installed, which is the same set `apps_screen_sort_key` already
	walks: a disabled app has no rail to arrange.
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
		{**destination(row), **overrides(row), "hidden": row["hidden"]}
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

	return workspace_payload(entry={"sidebar": module})


# ---------------------------------------------------------------------------------------
# Ship: rendering an arrangement as the hook that would produce it
# ---------------------------------------------------------------------------------------


def owners_of(rows: list[dict]) -> list[str | None]:
	"""Which app's files each row lives in, in the order they arrived.

	The module the entry is rooted in, which is what "lives in" means. The hook's own attribution
	used to come first, because it was exact -- and it went with the hook. This whole block goes
	with the manager's Ship projection in 14; it has no reader once the record is what ships.
	"""

	def owner(entry) -> str | None:
		if shell := entry.get("sidebar"):
			return frappe.db.get_value("Module Def", shell, "app_name")
		if entry.get("link_type") == "Workspace":
			module = frappe.db.get_value("Workspace", entry.get("link_to"), "module")
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
		# The block is still written in the old typed-pair spelling, because that is the shape a
		# `hooks.py` reader understands and the hook retires whole in 07 rather than growing a
		# second one. A row the pair cannot express -- a URL, or a shell override -- has no
		# rendering here and is left out by `emit_dock_hook`'s projection.
		kind = "Sidebar" if row.get("sidebar") else "Workspace"
		name = row.get("sidebar") or row.get("link_to")
		parts = [f'"type": {json.dumps(kind)}', f'"name": {json.dumps(name)}']
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
			dropped.append(
				{**destination(row), "name": row.get("sidebar") or row.get("link_to"), "declared_by": owner}
			)

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
