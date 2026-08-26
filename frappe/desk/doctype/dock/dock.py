# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _

# The same flags `Sidebar` reads, because they answer the same question: is the system placing
# app content on a site, or is a user editing? Shared rather than copied, so a route added to one
# list but not the other cannot break one doctype and not the other on customer sites.
from frappe.desk.doctype.sidebar.sidebar import SYSTEM_WRITE_FLAGS
from frappe.desk.doctype.workspace.workspace import check_workspace_manager, is_workspace_manager
from frappe.desk.layers import resolve_layers
from frappe.model.document import Document

# Cached address of every `Dock` on the site (app, user and standard), so resolving one costs a
# redis read instead of a query. Same approach as `Custom Sidebar`'s customized-keys cache, and it
# pays off more here: a site nobody has arranged and whose apps ship no dock holds no `Dock` row
# at all, so the whole lookup is free.
DOCK_LAYERS_CACHE_KEY = "dock_layers"

# A blank `user`, which every layer except a user's own carries. Named so it reads as a value
# rather than a falsy string. `standard` tells the other two apart: the app's own dock, or the
# site's arrangement of it.
SITE_LAYER = ""

# What a dock entry points at.
#
# Clicking an entry does two things: it opens a page and it swaps the shell. Either can happen
# without the other. A URL row is a page with no shell; a module row is a shell with no particular
# page. That is why these are separate columns rather than one typed pair.
#
#   sidebar                              a module's rail button
#   sidebar + link_type/link_to          a second button into one module
#   link_type/link_to                    a pin; the shell is derived from what it opens
#   link_type=URL + url                  a link out; no shell at all
#
# These columns are the entry's identity: `dock_key` joins exactly these and stores nothing. It is
# the same rule as the sidebar's `LINKED_IDENTITY_FIELDS`: use the columns the row already has, so
# there is no second copy to keep in step and a rename does not break it. It needs no stored-key
# fallback, because the sidebar's fallback is for rows that link nowhere (a Section Break) and the
# dock has none: all four blank is not an entry.
#
# Two consequences. `icon` and `title` are outside this list, so re-labelling cannot detach a row
# from itself. `sidebar` and `link_to` are inside it, so re-pointing a row makes it a different
# row rather than an edit of the same one.
DESTINATION_FIELDS = ("sidebar", "link_type", "link_to", "url")

# What a row may say about how an entry looks, as opposed to where it goes. Blank means inherit;
# filled means override. These are outside `DESTINATION_FIELDS` on purpose, so re-labelling an
# entry does not detach its customizations.
#
# Required when a row adds an entry, because nothing below it holds one. Optional when the row
# references an entry, which is where the inheritance happens.
REFERENCE_FIELDS = ("icon", "title")

# The two kinds of page a row may open. Only these two: a Report or a DocType list belongs in a
# module's sidebar, not on a rail of about a dozen destinations, and `Report` would also need new
# boot payload. Adding more later costs a Select value, not a column.
#
# `Sidebar` is not a value here. A module entry is a row with `sidebar` filled and no target, so
# naming the module in a type value would say it twice.
DOCK_LINK_TYPES = frozenset({"Workspace", "URL"})

# What each filled column must point at, in words. This is the message an author sees when their
# row names nothing. `entry_exists` runs the actual checks.
#
# `sidebar` is satisfied by either a `Sidebar` document or a `Module Def`. Most modules have a
# computed base with no document, so checking the `Sidebar` table alone would reject the common
# case. Since 01 a `Sidebar` may be named something other than its module, so checking
# `Module Def` alone would reject the new capability.
#
# `url` is checked against nothing, on purpose. See `is_reachable`.
PROVED_BY = {
	"sidebar": "Sidebar or Module Def",
	"Workspace": "Workspace",
}

# The columns a stored `Dock Item` carries. One list, so copying a row between layers, which is
# what promoting the site's arrangement to app content does, cannot silently drop a column
# someone added to the schema.
DOCK_ITEM_FIELDS = (*DESTINATION_FIELDS, *REFERENCE_FIELDS, "added", "hidden")


class Dock(Document):
	"""One layer of one app's dock: the app's own, the site's arrangement of it, or one user's.

	All three have the same shape because the rows are identical. `app`, `user` and `standard` are
	the only difference, and the parent says who an entry belongs to. `Custom Sidebar` layers the
	sidebar the same way, in its own table.

	This uses one table rather than a doctype per layer, which amends ADR 0004. `Workspace`,
	`Report`, `Print Format`, `Notification` and `Dashboard Chart` all mix exported and
	site-created rows in one table, and the app layer is kept read-only by a code guard
	(`validate_app_content`) rather than by permissions.

	A dock belongs to an app. Storing every app's rows in one flat pair of layers caused friction:
	the manager edits one app at a time and had to avoid copying the site's rows for other apps
	into a user's own layer. Per-app records remove that.
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
		mount_on: DF.Autocomplete | None
		standard: DF.Check
		user: DF.Link
	# end: auto-generated types

	def autoname(self):
		"""Name an app's own dock after the app; everything else gets a hash.

		The export path requires it, because the record name is the file path. A hash-named
		standard record would write `<app>/dock/6a1f9c2e/6a1f9c2e.json`, and a re-export from a
		fresh bench would create a second file, leaving the first as a permanent orphan.

		An opaque name costs the other two layers nothing, because a layer is looked up by filter
		and never by name. Leaving `self.name` unset falls through to the doctype's own
		`autoname: hash`.
		"""
		if self.standard:
			self.name = self.app

	def validate(self):
		# One spelling of "not a user's own layer", so the composite index can compare them. The
		# column is also not-nullable, which is what makes this stick: a blank column in a unique
		# index is stored as `NULL`, and every NULL is distinct to an index, so one app could
		# hold two site layers that both look like one address to `get_dock`.
		self.user = self.user or SITE_LAYER
		self.validate_app_content()
		self.validate_standard()
		self.blank_the_mount()
		self.anchor_the_items()

	def blank_the_mount(self):
		"""Clear `mount_on` outside the app layer, because mounting is an app-layer claim.

		`depends_on` hides the field on the two writable layers but does not stop an API write,
		and a site row carrying a mount would put a user's arrangement on another app's rail.
		"""
		if not self.standard:
			self.mount_on = None

	def validate_app_content(self):
		"""Allow only developer mode to set or clear the standard flag, because it is app content.

		This check is conditional where `Sidebar`'s equivalent applies to every write. It has to
		be: all three layers live in one table, and the site's and each user's rows must stay
		writable at runtime, so a blanket guard would refuse every `save_user_dock`. With no guard
		at all, a Workspace Manager, who has `write` on `Dock`, could take an app's row, clear the
		flag, and turn git-versioned app content into a site row they own.

		The `is_new()` check matters: on an unsaved document `has_value_changed` returns True for
		every field, so without it every site- and user-layer row would be refused outside
		developer mode.

		The system-write flags are needed too. Each is a real route by which an app's dock reaches
		a site, and without them, installing or updating an app that ships one fails on every
		customer site.
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
		"""Refuse to mark a dock standard unless we can write its file.

		`standard` means a JSON file in an app backs this row. A row with a missing file counts as
		an orphan, and `remove_orphan_entities` deletes it on the next `bench migrate`. Refusing
		is better than creating a row that deletes itself.

		`Sidebar` checks that a module resolves to a folder; this checks that the app is
		installed, because an app-rooted record has no module folder and the app is the whole
		address.

		A system write skips the developer-mode check for the same reason as in
		`validate_app_content`: an app install or migrate places a row whose file is already on
		disk, so requiring developer mode would refuse the write the file exists for. The app
		check still runs, because it is about whether the file can be written at all.
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
		"""Drop entries that name neither a shell nor a page.

		A row needs a `sidebar`, a target, or both. The old typed pair required both halves, but
		the two things a click does are separable, so a row filling only one of them is normal.

		An anchorless row is dropped rather than refused, the same as a `Custom Sidebar` reference
		anchored to nothing. That also clears a row written before these columns existed that does
		not carry the old pair either.

		A row whose `link_type` is outside the allowed set is refused instead. It says something
		we cannot store, so keeping it would leave a reader with a row it cannot interpret.

		The refusal runs first so the row number in the message matches what the author sees:
		re-setting the table renumbers `idx`, and a message pointing at a moved row is worse than
		no message.
		"""
		for row in self.items:
			if row.link_type and row.link_type not in DOCK_LINK_TYPES:
				frappe.throw(
					_("Row #{0}: a dock entry opens a Workspace or a web address, not a {1}.").format(
						row.idx, row.link_type
					)
				)
		self.set("items", [row for row in self.items if points_somewhere(stored_row(row))])
		self.validate_added_rows()

	def validate_added_rows(self):
		"""Require an icon and title on a row that has nothing below it to inherit from.

		A row can have nothing below it in two ways, and both would otherwise put an unlabelled
		button on the rail:

		1. It adds an entry, so no lower layer holds one to inherit from.
		2. It is on the app's own dock, the bottom of the stack. Every row there is a base row
		   whatever its `added` flag says, and the flag reads 0 on a row promoted from the site's
		   layer, where it referenced something that is no longer beneath it.

		A reference at an upper layer inherits both, which is what blank means there.
		"""
		for row in self.items:
			if (self.standard or row.added) and not (row.icon and row.title):
				frappe.throw(
					_("Row #{0}: an entry on this dock needs an icon and a title of its own.").format(row.idx)
				)

	def _validate_links(self):
		"""Skip link validation, because a row names a navigation target rather than referencing it.

		`Custom Sidebar` does the same, for the same reason: one deleted workspace would otherwise
		turn every later write to this layer into an error. A row naming something that is gone
		stops applying when the dock resolves, which is already what happens to a row whose target
		the user may not see.

		It also lets a `Sidebar` row name a module whose sidebar is a computed base. The `Sidebar`
		table holds no document for it, so a Dynamic Link would refuse it.
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
		"""Write this dock to its file. Every save keeps the file current, so authoring in Manage
		Dock and shipping the result are one step.

		The path is `<app>/dock/<app>/<app>.json`: the usual per-record folder, rooted at the app
		instead of a module. That shape is all the export needs. The import walk and orphan
		cleanup work on it without extra machinery, because the filename and the record name
		agree, which is what the old hand-written app-level fixtures got wrong.
		"""
		from frappe.modules.export_file import export_to_files

		if not self.standard or frappe.flags.in_import or not frappe.conf.developer_mode:
			return

		export_to_files(record_list=[["Dock", self.name]], record_app=self.app)

	def exported_file_path(self) -> str:
		"""Return the path `export_to_files` writes this dock to.

		The export module computes it rather than this file rebuilding it, so the path checked
		here is always the path the export writes.
		"""
		from frappe.modules.export_file import export_root, exported_file_path

		return exported_file_path(export_root(record_app=self.app), self.doctype, self.name)

	def is_exported(self) -> bool:
		"""Return whether the file behind this dock exists on disk.

		Orphan cleanup asks the same question, so `mark_as_standard` has to answer it before
		reporting the dock as shipped.
		"""
		import os

		if self.is_new() or not self.app:
			return False

		try:
			return os.path.exists(self.exported_file_path())
		except (frappe.DoesNotExistError, ImportError):
			# No app on the bench, so no file. `get_app_path` reports that by throwing.
			frappe.clear_last_message()
			return False


def on_doctype_update():
	"""Enforce one layer per address in the schema rather than in a `validate` hook.

	A hook can be bypassed by `db_insert`, a bulk write, or anything that skips the document, and
	two documents at one address would give the merge two answers for the same layer.

	The index is composite because an address is three columns. `user` alone worked while a layer
	spanned every app; with per-app records it would let one user arrange only one app's rail.
	`standard` is in the index because an app's own dock and the site's arrangement of it are two
	documents at the same `(app, user)`: one shipped, one curated. `Reset for everyone` drops the
	site's without touching the app's.
	"""
	frappe.db.add_unique("Dock", ("app", "user", "standard"), constraint_name="unique_layer_address")


# ---------------------------------------------------------------------------------------
# Making a dock app content, and undoing that
#
# `standard` means an app ships this dock as a JSON file. The two actions below turn the flag on
# and off, and both move the file as well.
#
# There is no bench command or CI check for this on purpose. Three existing mechanisms cover it:
# `validate_standard` refuses the flag unless the file can be written, `is_exported` verifies the
# write landed and rolls back if it did not, and the reaper deletes a row whose file went away.
# Drift also self-heals: `on_update` re-exports on save, and a hand-edited file is re-imported on
# migrate. A command would report a state the system already prevents.
# ---------------------------------------------------------------------------------------


@frappe.whitelist()
def mark_as_standard(app: str) -> str:
	"""Make `app`'s dock part of the app and return the document name.

	It writes the dock into the app's folder so the app ships it, and `bench migrate` imports it
	back from there.

	The flag and the file are set together, and the row is rolled back if the write did not land.
	A standard row with no file is the orphan the next `bench migrate` deletes, so a mark that
	wrote nothing must leave no row behind.

	There is no materialize step, unlike `Sidebar`'s version. A sidebar has a computed base to
	ship when no document holds one; a dock has none. A dock-less app gets no rail, so there is
	nothing to promote until someone has authored rows.
	"""
	app = check_docked_app(app)
	check_developer_mode()

	doc = get_dock(app, standard=1)
	if doc:
		doc = frappe.get_doc("Dock", doc.name)
		# Already shipped, so there is nothing to do. We check the flag and the file: a standard
		# row with a missing file is the orphan this action prevents, so write it again rather
		# than report success.
		if doc.is_exported():
			return doc.name
	else:
		# The site's arrangement is what the author has been editing, so that is what gets
		# shipped. The rows are copied rather than re-parented, so the site's own layer stays
		# where it is and unmarking leaves the site as it was before the promotion.
		#
		# The rows are resolved, not copied raw. A site row may be a reference, with blank icon
		# and title inherited from the layer below, and there is no layer below the app's own
		# dock. Copied verbatim those rows would ship with no label, which is what the
		# reference/add split exists to prevent.
		#
		# Resolving also means a reference to a dock that is gone, after an unmark and a second
		# mark, contributes nothing instead of a blank row. The refusal below then tells the
		# author their layer names a rail that no longer exists, rather than shipping an empty
		# one.
		rail = resolve_app_dock(app, gated=False)
		if not rail:
			frappe.throw(
				_("There is nothing to export for {0}. Put some entries on its dock first.").format(
					frappe.bold(app)
				)
			)

		doc = frappe.new_doc("Dock")
		doc.app = app
		for row in rail:
			doc.append("items", {field: row.get(field) for field in DOCK_ITEM_FIELDS})

	savepoint = "mark_dock_standard"
	frappe.db.savepoint(savepoint)
	try:
		doc.standard = 1
		# `save` inserts a freshly built record or updates an existing one. Either way,
		# `on_update` writes the file.
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
	"""Give `app`'s dock back to the site by deleting its exported file and its document.

	The document is deleted rather than just unflagged. Once the app content is gone the app has
	nothing to fall back to, because a dock has no computed base, so the app now has no rail.
	`Sidebar`'s unmark differs here: there, the module falls back to its computed base.

	The file has to go too. Left on disk, the next `bench migrate` imports it again and the row
	comes back standard.
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
	# request, we want the file the second call wrote, not a queued delete that removes it
	# afterwards.
	if path:
		shutil.rmtree(os.path.dirname(path), ignore_errors=True)

	frappe.msgprint(
		_("{0} now has no rail; its exported dock has been removed.").format(frappe.bold(app)),
		alert=True,
		indicator="orange",
	)


def check_developer_mode() -> None:
	"""Throw unless developer mode is on.

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
	"""Point every dock row naming a sidebar at that sidebar's new name.

	This is its own pass. `Dock Item.sidebar` is an ordinary `Link`, so nothing the framework does
	on rename touches it: `rename_dynamic_links` walks Dynamic Links, which is what the retired
	`link_name` column was. So this is the only thing that carries a shell rename onto the rails
	naming it.

	The rows are updated in place rather than through their parent. A `Dock` is one layer of one
	app's dock, and re-saving one to fix a name it holds would re-run validation, including the
	export on an app's own record. That makes cache invalidation this function's job: `get_dock`
	reads a `Dock` through `get_cached_doc`, so the document's cache entry goes stale.
	`rename_doc` does flush the whole site cache shortly after `after_rename` returns, which would
	cover it, but relying on that would only be correct while its one caller stays as it is, and
	doing it here costs two queries.
	"""
	named = {"parenttype": "Dock", "sidebar": old_name}
	layers = frappe.get_all("Dock Item", filters=named, pluck="parent", distinct=True)
	if not layers:
		return

	frappe.db.set_value("Dock Item", named, "sidebar", new_name, update_modified=False)

	# Read name and user together: `drop_dock_caches` needs the user, and fetching each layer as
	# a document would pull all its item rows along for one column.
	for layer in frappe.get_all("Dock", filters={"name": ["in", layers]}, fields=["name", "user"]):
		frappe.clear_document_cache("Dock", layer.name)
		drop_dock_caches(layer.user)


def drop_dock_caches(user: str | None) -> None:
	"""Drop the caches a dock layer is read from, for the user who holds it.

	This is a module function rather than only a method, because a rename edits the rows in place
	and never loads the parent, and reading a whole `Dock` to find out whose it is would be a
	document fetch for one column.
	"""
	frappe.cache.delete_value(DOCK_LAYERS_CACHE_KEY)
	# Also drop the per-request memo built from it, so a save that answers with the rail it just
	# wrote does not resolve against the dock as it was before.
	frappe.local.dock_cache = {"app_dock": {}, "mounts": None}
	if user:
		# A user's own arrangement only invalidates their boot.
		frappe.cache.hdel("bootinfo", user)
	else:
		frappe.cache.delete_key("bootinfo")


def request_cache_for_docks() -> dict:
	"""Per-request memo for the two reads the rail repeats.

	`get_app_dock` and `mounted_apps` are each called once per app, and once more per app per app:
	`get_app_base` asks `mounted_apps`, which asks `get_app_dock` for every shipped dock. Without
	this a twenty-app bench pays hundreds of lookups per boot to draw its rails, quadratic in the
	number of apps.

	It is request-scoped and hand-rolled rather than `@request_cache` because it has to be
	dropped: a save in the same request (`_save_layer` answers with the rail it just wrote) would
	otherwise resolve against the dock as it was before. `drop_dock_caches` does that, and it
	already runs on every write.
	"""
	if not hasattr(frappe.local, "dock_cache"):
		frappe.local.dock_cache = {"app_dock": {}, "mounts": None}
	return frappe.local.dock_cache


def dock_records() -> list[dict]:
	"""Return the cached address of every layer the site holds (name, app, user, standard), plus
	the mount an app's own dock declares.

	This keeps boot cheap: on a site nobody has arranged, every layer of every app is answered
	from one redis read instead of a query each. `mount_on` is included for the same reason, since
	the boot asks who mounts on whom on every request and that used to be a cached hooks read.

	It stores addresses, not documents, so a stale cache can only cost a lookup that finds
	nothing. `Custom Sidebar` uses the same negative filter.
	"""
	records = frappe.cache.get_value(DOCK_LAYERS_CACHE_KEY)
	if records is None:
		records = [
			{
				"name": row.name,
				"app": row.app,
				"user": row.user or SITE_LAYER,
				"standard": int(row.standard or 0),
				"mount_on": row.mount_on or None,
			}
			for row in frappe.get_all("Dock", fields=["name", "app", "user", "standard", "mount_on"])
		]
		frappe.cache.set_value(DOCK_LAYERS_CACHE_KEY, records)
	return records


def get_dock_layers() -> dict[tuple[str, str, int], str]:
	"""Return every layer address the site holds, mapped to the document that holds it."""
	return {(row["app"], row["user"], row["standard"]): row["name"] for row in dock_records()}


def mounted_apps() -> dict[str, str]:
	"""Map each companion app to the host whose rail it mounts on, for mounts that take effect.

	Memoised per request: `get_app_base` asks this once per app, and each answer walks every
	shipped dock.

	A companion app has no rail of its own; its entries live on a host's. Declaring a mount is a
	request, not a guarantee. Three conditions must hold, and each prevents a real failure:

	1. The host is installed. A companion installed without its host is invisible: resolution
	   drops the pin, and the boot path takes its apps-screen slot away.
	2. The host ships a dock of its own. Mounting onto a dock-less host would make its rail
	   entirely another app's entries, with no route to its own module and no switcher. The
	   common dock-less app ships exactly one module, so this happens easily.
	3. The companion ships rows. Nothing to mount is not a mount.

	The second test reads the host's own dock rather than its resolved rail, so it does not
	recurse: resolving the host's rail is what asks for this answer.

	The host cannot veto a mount, but the site can. A host's file is authored before the companion
	exists on any site, so a veto would be blind. Refusing a mount is done by hiding it at the
	site layer.
	"""
	memo = request_cache_for_docks()
	if memo["mounts"] is not None:
		return memo["mounts"]

	shipped = {row["app"]: row for row in dock_records() if row["standard"]}
	installed = frappe.get_active_apps()

	mounts = {}
	for app, row in shipped.items():
		host = row["mount_on"]
		if not host or host == app or host not in installed or app not in installed:
			continue
		if host not in shipped or not get_app_dock(host):
			continue
		if not get_app_dock(app):
			continue
		mounts[app] = host

	memo["mounts"] = mounts
	return mounts


def get_dock(app: str, user: str | None = None, standard: int = 0) -> "Dock | None":
	"""Return the document holding one layer of one app's dock, or None.

	The name comes from the cache rather than a lookup. It used to be a filtered `db.exists`,
	which is a query the cache had already answered and which cannot itself be cached, because
	redis caching does not work with filters. A boot resolves three layers per app, so that cost
	three queries per app for something already in redis.
	"""
	name = get_dock_layers().get((app, user or SITE_LAYER, standard))
	return frappe.get_cached_doc("Dock", name) if name else None


def stored_row(row) -> dict:
	"""Return one stored `Dock Item` as the dict every reader here works with.

	It reads the columns and nothing else, now that the old typed pair is gone. It stays a
	function rather than a dict comprehension at each call site because it also normalises a blank
	column to `None`: the schema writes `""` where a reader wants unset, and `dock_key` would
	otherwise be built from two spellings of nothing.
	"""
	return {
		**{field: row.get(field) or None for field in DESTINATION_FIELDS},
		"icon": row.get("icon") or None,
		"title": row.get("title") or None,
		"added": int(row.get("added") or 0),
		"hidden": int(row.get("hidden") or 0),
	}


def points_somewhere(entry) -> bool:
	"""Return whether a row names something a rail can act on: a shell, a page, or both.

	A page is its `link_type` plus whichever column that type fills, so a `link_type` on its own
	is as anchorless as a blank row. A `URL` row is anchored by its `url`, not by a `link_to` it
	never has.
	"""
	if entry.get("sidebar"):
		return True
	if entry.get("link_type") == "URL":
		return bool(entry.get("url"))
	return bool(entry.get("link_type") and entry.get("link_to"))


def dock_rows(dock: "Dock | None") -> list[dict]:
	"""Return one layer's stored rows in row order. Row order is the arrangement.

	Anchorless rows are dropped again rather than left to `validate`, which only ran on layers
	this site saved after the columns existed.
	"""
	if not dock:
		return []

	rows = [stored_row(row) for row in dock.items]
	return [row for row in rows if points_somewhere(row)]


def get_app_dock(app: str) -> list[dict]:
	"""Return an app's dock, which is exactly its record's rows. Empty when it ships none.

	This is the entry set, not just an order over one. A module this record never names is off
	this app's rail permanently: no layer above can bring it back, because there is nothing to
	name. An author picks from three tiers:

	    named, hidden: 0     on the rail
	    named, hidden: 1     off the rail, and the site or the user can bring it back
	    not named            off the rail, and nobody can

	The middle tier needs no extra machinery: `resolve_layers` seeds its hidden map from the base,
	so one row above naming that entry with hiding off brings it back.

	Omitting an entry only affects discovery, not reachability. The boot's sidebars are built from
	the navigable-modules list rather than the dock, so a module this record omits still has a
	sidebar in the payload, still opens by route, and still resolves as an entity. It only loses
	the rail as a place to find it.

	The rows are deduped, because a record may name one entry twice. Two rows under one key would
	render the entry twice, and the layers above dedupe their own rows without catching it, since
	the base is copied whole. The first row named wins, the same rule a layer follows.
	"""
	memo = request_cache_for_docks()["app_dock"]
	if app not in memo:
		memo[app] = build_app_dock(app)
	return memo[app]


def build_app_dock(app: str) -> list[dict]:
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


def get_app_base(app: str) -> list[dict]:
	"""Return one app's own dock with the rows of every companion mounted on it appended.

	Companion rows are appended rather than positioned, and only as a default: a companion does
	not push an opinion into an arrangement that is not its own, and the site and the user can
	reorder afterwards. Two companions mounting on one host land in installation order rather than
	competing for a slot.
	"""
	own = get_app_dock(app)
	mounts = mounted_apps()
	if app not in set(mounts.values()):
		return own

	rows, seen = list(own), {dock_key(row) for row in own}
	for companion in sorted(mounts, key=frappe.get_active_apps().index):
		if mounts[companion] != app:
			continue
		for row in get_app_dock(companion):
			key = dock_key(row)
			if key in seen:
				continue
			seen.add(key)
			rows.append(row)
	return rows


def get_app_entry_set(app: str) -> list[dict]:
	"""Return every entry `app`'s dock offers this user, before any layer arranges them.

	The boot payload carries this as `app_data[].dock`, and the manager builds its panes from it.
	It is filtered by reach only. Which entries are on the rail, and in what order, is decided by
	the layers in `resolve_app_dock`.
	"""
	return [rail_entry(row) for row in get_app_base(app) if is_reachable(row)]


def apps_screen_sort_key():
	"""Return a sort key that orders apps the way the apps screen lists them.

	It uses the same two keys as that screen: the `sequence_id` an app declares in
	`add_to_apps_screen`, then installation order for apps that declare none.

	Only installed apps are passed in, because the declaration is a hook and a hook belongs to an
	installed app.
	"""
	from frappe.boot import DEFAULT_APP_SEQUENCE_ID

	installed = frappe.get_active_apps()

	def sequence(app: str) -> float:
		declared = frappe.get_hooks("add_to_apps_screen", app_name=app)
		return (declared and declared[0].get("sequence_id")) or DEFAULT_APP_SEQUENCE_ID

	return lambda app: (sequence(app), installed.index(app), app)


def get_site_dock(app: str) -> list[dict]:
	"""Return the site's arrangement of one app's dock, curated by a Workspace Manager and
	applying to everyone."""
	return dock_rows(get_dock(app))


def get_user_dock(app: str, user: str | None = None) -> list[dict]:
	"""Return one user's own arrangement of one app's dock.

	The dock manager round-trips this. It replaces the layer whole, so it has to see the layer it
	is editing rather than the resolved dock, which also carries the site's rows and would copy
	them into the user's own layer on the next save.
	"""
	return dock_rows(get_dock(app, user=user or frappe.session.user))


def resolve_dock() -> dict[str, list[dict]]:
	"""Return the dock as the session user sees it: one resolved rail per app, keyed by app.

	It is keyed by app because a `Dock` is per app. The two stored layers used to be one flat
	cross-app list, and the client had to intersect it with each app's entry set to find the rows
	for the rail on screen. With a layer addressed by app plus user, the rail is its app's entry
	and no intersection is needed.

	Three classes of entry come out of this, which is how a shipped order and an arrangement live
	together:

	1. Named by a layer. These come first, in the order the layers left them.
	2. In the base but named by no layer. These follow the named ones, at their real index in base
	   order. This is what makes an app's shipped order apply to entries nobody rearranged;
	   without it, shipping an order would only reach a fresh install.
	3. In neither. These are absent from this list rather than appended. The client keeps such an
	   entry in its app's own order, behind both classes above (`MAX_SAFE_INTEGER` on the client).
	   That makes installing an app safe on a site that has already arranged its dock: the new
	   app's modules appear at the end rather than disappearing for want of a row.

	Resolution runs through `frappe.desk.layers`, the same merge the sidebar's layers use. An
	entry left hidden stays in this list carrying its flag, and the client drops it from the rail.
	The dock manager's Hidden pane needs that, since it cannot render what the payload discarded.
	This is the one place the dock differs from a sidebar, which drops a hidden item outright.

	Every entry carries the whole destination it was stored with, plus its icon and title. The
	client keys on the destination, so two rows into one module stay two entries on the rail.

	Apps that resolve to nothing are left out rather than carried as empty lists. The payload is
	read by key, so an absent key and an empty list mean the same thing.
	"""
	resolved = {}
	for app in docked_apps():
		rail = resolve_app_dock(app)
		if rail:
			resolved[app] = rail
	return resolved


def docked_apps() -> list[str]:
	"""Return every app whose rail could resolve to something: an app that ships a record, or one
	some layer on this site has an opinion about.

	Both come from the same cached read, which keeps boot free on a site nobody has arranged.
	Asking every installed app would be correct and nearly as cheap, but it would walk apps that
	have never had a rail on any site.

	Only installed apps are returned. Nothing deletes a site's or a user's layer when its app is
	uninstalled, because only a standard row is an orphan candidate, so a bench that ever removed
	an app holds rows naming one that is gone. Left in, the sort key would ask that app for its
	hooks and the boot would fail with `ModuleNotFoundError`.

	A companion whose mount takes effect is also left out: its entries render on the host's rail,
	so it has no rail of its own to resolve.
	"""
	installed = set(frappe.get_active_apps())
	mounted = mounted_apps()
	apps = {row["app"] for row in dock_records() if row["app"] in installed} - set(mounted)
	return sorted(apps, key=apps_screen_sort_key())


def resolve_app_dock(app: str, upto: str = "user", gated: bool = True) -> list[dict]:
	"""Return one app's rail for the session user: its own dock, then the site's, then the user's.

	`upto` names the last layer applied, and `gated` says whether the reach filter runs. Both
	exist for the save path rather than the boot. A layer being written has to be settled against
	the rail it was looking at, which is the layers below it, and unfiltered, because whether a
	row is an add depends on base membership rather than on who can see it. With the reach filter
	on, a Workspace Manager saving the site's rail with one module blocked for them personally
	would turn that module's row into an add, and an add requires an icon and title nobody typed.
	"""
	# Build only the layers the caller asked for. The list is the stack: each layer is laid over
	# the one before it, and `upto` says where to stop.
	layers = []
	if upto in ("site", "user"):
		layers.append(get_site_dock(app))
	if upto == "user":
		layers.append(get_user_dock(app))

	resolved, hidden = resolve_layers(
		get_app_base(app),
		layers,
		key=dock_key,
		apply_row=apply_dock_row,
		# A saved layer is the rail. An entry the app ships later does not appear on it; it shows
		# up in Manage Dock as something to add, and the user opts in by adding it. That is a
		# deliberate trade: predictable rails over automatic updates.
		keep_unnamed=False,
	)
	# Applied last, so no layer can name its way past the gates. An arrangement cannot grant
	# reach; reach is decided by module visibility and workspace permissions alone.
	return [
		{**rail_entry(entry), "hidden": int(hidden.get(dock_key(entry), 0))}
		for entry in resolved
		if not gated or is_reachable(entry)
	]


def dock_key(entry) -> str:
	"""Return what identifies a dock entry: the whole destination and nothing else.

	This is the same rule as the sidebar's `LINKED_IDENTITY_FIELDS`: use the columns the row
	already has, so there is no second copy to keep in step and a rename does not break it.
	Nothing is stored, and no second shape is needed, because the sidebar's second shape is for a
	row that links nowhere and a dock row that points nowhere is not an entry.

	It keeps the row shape's distinctions: `Stock` (a shell) and `Stock Analytics` (that shell
	plus a workspace) key apart, as do a bare `GST` pin and a `Welcome` row that overrides its
	shell.
	"""
	return "|".join(entry.get(field) or "" for field in DESTINATION_FIELDS)


def apply_dock_row(row, entry: dict | None) -> dict | None:
	"""Apply one layer row to the dock entry it names.

	There are two kinds of row, the same as in the sidebar. An added row is the entry: it brings a
	destination nothing below it holds, so it replaces whatever the list has under that key, which
	is usually nothing. A reference row states an opinion about an entry that is already there,
	and `overrides` keeps that opinion to the fields it sets.

	A reference naming an entry the list does not hold returns `None` and is skipped, which stops
	a reference to a row the app has since deleted from reappearing as an unlabelled button: a
	destination with no icon and no title, since a reference need not carry either.

	`added` is stored rather than inferred from the row carrying a body. Re-labelling is allowed,
	so a reference may carry a partial opinion, such as an icon and no title, and the presence of
	a body no longer tells the two apart.
	"""
	if row.get("added"):
		return rail_entry(row)

	if entry is None:
		return None

	return {**entry, **overrides(row)}


def rail_entry(entry) -> dict:
	"""Return what the rail is given: where the entry goes and how it reads."""
	return {
		**{field: entry.get(field) for field in DESTINATION_FIELDS},
		**{field: entry.get(field) for field in REFERENCE_FIELDS},
	}


def overrides(row) -> dict:
	"""Return what a reference row overrides on the entry it names. A blank field means no
	override, so the entry keeps what the layer below gave it.

	This stops one reorder from freezing the app's label forever, the failure that ruled out
	full-body storage in the sidebar. Ticket 06 made it urgent here by giving every row a stored
	icon and title.
	"""
	return {field: row.get(field) for field in REFERENCE_FIELDS if row.get(field)}


def entry_exists(entry) -> bool:
	"""Return whether everything an entry names exists on this site.

	This is existence, not reach. `is_reachable` asks the per-user question and calls this first.
	Each filled column is checked, and all must pass, because a row may fill more than one and
	every part has to exist for the click to land.

	`sidebar` is checked by `shell_exists`, which accepts either a `Sidebar` document or a
	`Module Def`. `url` only has to be non-empty, which `points_somewhere` already checked.
	"""
	if entry.get("sidebar") and not shell_exists(entry["sidebar"]):
		return False

	if entry.get("link_type") == "Workspace":
		return bool(frappe.db.exists("Workspace", entry.get("link_to"), cache=True))

	return True


def shell_exists(shell: str) -> bool:
	"""Return whether a shell exists on this site: a `Sidebar` document, or a `Module Def` whose
	sidebar is a computed base.

	Both are checked, which ticket 01 required. Most modules have no `Sidebar` row, so checking
	that table alone would reject the common case, and a sidebar may now be named something other
	than its module, so checking `Module Def` alone would reject the new capability.
	"""
	return bool(
		frappe.db.exists("Module Def", shell, cache=True) or frappe.db.exists("Sidebar", shell, cache=True)
	)


def is_reachable(entry) -> bool:
	"""Return whether the session user may go where the entry points.

	One gate per filled column, and a row passes only if every column it fills passes:

	    sidebar     its module exists and is module-visible
	    Workspace   in `permitted_workspaces()`
	    URL         no gate; always passes

	Both failure directions happen, which is why this is a conjunction rather than a first-match
	branch. A blocked shell with a permitted workspace, the `Welcome` shape, would otherwise
	render the whole sidebar of a module the user has blocked, undoing the block with a row that
	points past it. A visible shell with a forbidden workspace is the stale-row failure the
	existence check prevents.

	Existence is checked first for the shell. `is_module_visible` only answers whether a module is
	blocked, and a module that does not exist is also not blocked, so on its own it would let a
	row naming a deleted or renamed shell render an entry that leads nowhere.

	A module-less shell has no module gate, the same as a URL. A `Sidebar` rooted at its app
	belongs to no module, so there is no module visibility to check and existence is the whole
	question.

	Leaving URLs ungated is deliberate and not new: a user can already store an arbitrary URL in
	their own sidebar layer, and it leaks no permission.
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
	"""Return the workspaces this user may open.

	Called on any site where a fragment or a layer names one, which is every site carrying a pin.
	It costs nothing, because it reuses the request-cached workspace list the sidebar already
	computes on every boot.
	"""
	from frappe.desk.desktop import get_workspaces

	return {page.name for page in get_workspaces()["pages"]}


def shape_dock_rows(items: list | str, require_visible: bool, below: dict[str, dict]) -> list[dict]:
	"""Narrow one saved arrangement to the rows that can be stored.

	`items` is the whole ordered arrangement the client is showing, the shape a Sortable produces,
	not a delta. A row names a shell, a page, or both:

	    {"sidebar": "Stock"}
	    {"sidebar": "Stock", "link_type": "Workspace", "link_to": "Stock Analytics"}
	    {"link_type": "Workspace", "link_to": "Payables", "hidden": 1}
	    {"link_type": "URL", "url": "https://...", "icon": "book", "title": "Docs"}

	A row naming nothing, or naming a `link_type` outside the allowed set, is dropped. The set is
	checked here as well as in `Dock.validate`, because these rows do not reach a document until
	after they are shaped.

	Existence is checked separately from visibility, because `is_module_visible` answers a
	different question: an unknown module is not blocked, so it passes that check and would then
	name nothing when the dock resolved.

	`require_visible` differs between the two writable layers. A user's own arrangement is
	filtered by their reach, so it cannot resurface something permissions hide. The site's is not,
	because it is written for everyone, and dropping rows the saver personally cannot see would
	let one Workspace Manager's blocked module delete the site's intent for it. Reach is applied
	to the resolved dock either way.

	`below` is every entry this layer could be referencing, keyed by destination (see
	`entries_below`). It decides two things the client is not trusted to report: whether a row
	adds an entry, and whether its icon and title are an override or just what it was shown.
	"""
	shown = below
	shaped, seen = [], set()

	for row in frappe.parse_json(items) or []:
		if not isinstance(row, dict):
			continue

		entry = stored_row(row)
		# Every destination column must be a non-empty string or absent. These rows are client
		# JSON, so this also keeps a dict out of the lookups below: `frappe.db.exists` reads a
		# dict as filters rather than as a name, which would turn a saved arrangement into a
		# query surface.
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
		shaped.append(settle_reference(entry, shown.get(key)))

	return shaped


def settle_reference(entry: dict, below: dict | None) -> dict:
	"""Decide whether this row adds an entry or references one, and drop echoed-back overrides.

	Whether a row adds is derived here, never taken from the client. A row whose destination
	nothing below it holds is an add: it brings the entry rather than overriding one. Because
	identity is the destination, a user who pins `Payables` before the app ships `Payables` gets
	their add turned into a reference on the next save, so the two merge into one entry with the
	user's position winning instead of appearing twice.

	A reference blanks any field that only echoes what it was given. The client sends the
	arrangement it is showing, which carries the labels and icons it received. Stored as-is those
	would become overrides rather than inheritance, and an entry the user never touched would keep
	the label it happened to have when they reordered, so neither the site's relabel nor the
	app's would ever reach them again.
	"""
	if below is None:
		return {**entry, "added": 1}

	settled = {**entry, "added": 0}
	for field in REFERENCE_FIELDS:
		inherited = below.get(field)
		if settled.get(field) and settled[field] in (inherited, _(inherited) if inherited else None):
			settled[field] = None
	return settled


def entries_below(app: str, user: str | None) -> dict[str, dict]:
	"""Return every entry a layer being saved could be referencing, keyed by destination.

	This is the rail as it was without this layer, which is what the saver was looking at, so it
	is what their icons and titles echo back and what their rows can reference. A user's own save
	sees the app's dock with the site's arrangement on it. The site's save sees the app's dock
	alone, never the curator's own arrangement, which is not theirs to publish.

	Anything else is an add: a destination the rail below did not hold. That includes a URL
	someone typed, a workspace no dock names, and an entry the site removed. A user bringing that
	last one back is not restoring the site's row but adding their own, which is why it carries a
	cross rather than an eye and why it has to state how it reads.

	It is ungated on purpose: whether a row adds depends on membership, not on who can see it.
	With the reach filter on, a Workspace Manager saving the site's rail with one module blocked
	for them personally would turn that module's row into an add.
	"""
	below = resolve_app_dock(app, upto="user" if user else "site", gated=False)
	return {dock_key(entry): entry for entry in below}


def destination(entry) -> dict:
	"""Return only the columns that say where an entry goes, which is what `dock_key` uses."""
	return {field: entry.get(field) for field in DESTINATION_FIELDS}


# ---------------------------------------------------------------------------------------
# Write API
# ---------------------------------------------------------------------------------------


@frappe.whitelist()
def save_user_dock(app: str, items: list | str):
	"""Save this user's own arrangement of `app`'s dock, applied on top of the site's."""
	return _save_layer(app, items, user=frappe.session.user, require_visible=True)


@frappe.whitelist()
def save_site_dock(app: str, items: list | str):
	"""Save the site's arrangement of `app`'s dock, for everyone.

	This is what the site layer is for: "Accounts first, for everyone" cannot be expressed by any
	number of per-user arrangements. A user's own arrangement still applies on top of it.
	"""
	check_workspace_manager(_("You need to be Workspace Manager to change the dock for everyone."))
	return _save_layer(app, items, user=None, require_visible=False)


def _save_layer(app: str, items: list | str, user: str | None, require_visible: bool):
	"""Replace one layer of one app's dock with `items` and return the resulting rail.

	It replaces the whole layer, not part of it. A `Dock` is per app, so the rows the client sends
	are the only rows this document holds. The old flat list needed each save to carry every other
	app's rows through untouched or lose them.
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
	for row in shape_dock_rows(items, require_visible=require_visible, below=entries_below(app, user)):
		doc.append("items", {field: row[field] for field in DOCK_ITEM_FIELDS})

	# ignore_permissions: a user arranging their own dock does not need write access to this
	# doctype, and the site layer is gated by the role check its endpoint already made. The
	# arrangement is re-filtered by reach on every boot whatever is stored here.
	doc.save(ignore_permissions=True)

	# Both saves return this app's resolved rail, so it can be redrawn in place whichever layer
	# was written. Only this app's, because the save touched one document.
	return resolve_app_dock(app)


def check_docked_app(app: str | None) -> str:
	"""Return the app a layer is being written for, throwing unless it is installed.

	`app` comes from the client on every write and every layer read, and it is stored. An
	unchecked value would let a layer be filed under an app that does not exist, where nothing
	would resolve it and nothing would delete it.

	It checks active apps rather than merely installed ones, the same set `apps_screen_sort_key`
	walks, because a disabled app has no rail to arrange.
	"""
	app = (app or "").strip()
	if not app or app not in frappe.get_active_apps():
		frappe.throw(_("{0} is not an app on this site.").format(frappe.bold(app or "-")))
	return app


# A layer's raw rows, for the editor about to replace them. Not the resolved dock: an editor
# saves back the whole arrangement, so it has to see the layer it will overwrite. These are kept
# out of the boot payload because they are only needed when someone opens the manager.
#
# One endpoint per layer, each with its own gate, like the sidebar's saves and resets. A single
# endpoint taking a layer name would put the gate in a branch instead.


@frappe.whitelist()
def get_user_dock_layer(app: str) -> list[dict]:
	"""Return this user's own arrangement of one app's dock. No gate, because it is theirs and it
	is all they can read."""
	return get_user_dock(check_docked_app(app))


@frappe.whitelist()
def get_site_dock_layer(app: str) -> list[dict]:
	check_workspace_manager(_("You need to be Workspace Manager to see the dock's site layer."))
	return get_site_dock(check_docked_app(app))


@frappe.whitelist()
def save_app_dock(app: str, items: list | str):
	"""Save the app's own dock, the layer the other two are laid over.

	This is the one save that is authoring rather than arrangement, which is why developer mode is
	its only gate: the write is safe because the site belongs to a developer.
	`Dock.validate_app_content` checks it again at the document, and `on_update` writes the file,
	so pressing Save in the manager also ships the result.

	It is not offered where the app ships no dock yet. Promoting one is `mark_as_standard`, which
	writes the file in the same step and rolls the row back if the write fails.
	"""
	app = check_docked_app(app)
	check_developer_mode()

	doc = get_dock(app, standard=1)
	if not doc:
		frappe.throw(_("{0} ships no dock yet. Export one to the app first.").format(frappe.bold(app)))

	doc = frappe.get_doc("Dock", doc.name)
	doc.set("items", [])
	# `below` is empty: nothing sits under the app's own dock, so every row adds and every row
	# carries its own icon and title. That is the same rule the layers above follow, applied at
	# the bottom of the stack.
	for row in shape_dock_rows(items, require_visible=False, below={}):
		doc.append("items", {field: row[field] for field in DOCK_ITEM_FIELDS})

	doc.save(ignore_permissions=True)
	return resolve_app_dock(app)


@frappe.whitelist()
def get_app_dock_layer(app: str) -> list[dict]:
	"""Return what the apps ship, in the shape the manager reads: the typed pair and the hidden
	flag.

	No gate, because it reads app content, which is what every boot already carries in `app_data`
	minus the reach filter the resolved dock applies.

	This is what tells the manager who hid a row. The hidden flag alone does not say, and a user
	un-hiding something an app shipped off should be told that is what they are doing. It is a
	call rather than a doctype, because turning the hook into records to answer this one question
	is what the app layer avoids.

	`declared_by` is dropped: which app declared a row is what Ship needs, not the manager, and
	including it would put an app name in every editor payload.
	"""
	return [{**rail_entry(row), "hidden": row["hidden"]} for row in get_app_dock(check_docked_app(app))]


# ---------------------------------------------------------------------------------------
# Reset for everyone
# ---------------------------------------------------------------------------------------


@frappe.whitelist()
def reset_dock_for_everyone(app: str) -> list[dict]:
	"""Drop every non-standard `Dock` for `app`, including the site's own layer, so everyone is
	back on the app's exported dock.

	The reasoning matches the sidebar's: a Workspace Manager who re-curates the site's rail
	reaches nobody who has arranged their own. Resetting the site layer only lifts the site's
	arrangement, and this is the one action that reaches past it, which is why it is an immediate
	confirmed endpoint behind Workspace Manager rather than a pane edit applied on Save.

	The rows are deleted one at a time so each `on_trash` runs. Only the document knows whose boot
	cache to invalidate, and a bulk delete would leave those users booting a rail that no longer
	exists.
	"""
	# Check the permission before the lookup, so an unprivileged caller is refused for the reason
	# that applies to them rather than told which apps this site has.
	check_workspace_manager(_("You need to be Workspace Manager to reset the dock for everyone."))
	app = check_docked_app(app)

	for name in frappe.get_all("Dock", filters={"app": app, "standard": 0}, pluck="name"):
		frappe.delete_doc("Dock", name, force=True, ignore_permissions=True)

	return resolve_app_dock(app)


# ---------------------------------------------------------------------------------------
# Who may touch which layer
# ---------------------------------------------------------------------------------------


def has_permission(doc, ptype="read", user=None, debug=False):
	"""Allow a Workspace Manager to curate the site and the apps; everyone else gets only their
	own layer.

	This is the document-level half of the gate the endpoints hold. A `Desk User` has `read` and
	nothing more: arranging a dock goes through `save_user_dock`, which writes one user's own
	layer with `ignore_permissions`, so no write permission is needed or granted. This stops the
	read they do have from being a read of everyone else's layers.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or is_workspace_manager(user):
		return True

	return bool(doc.user) and doc.user == user


def get_permission_query_conditions(user=None):
	"""Restrict list queries so everyone but a Workspace Manager sees only their own layer.

	This pairs with `has_permission` and is not redundant: it keeps one user's arrangement out of
	everyone else's reads, since reports, the API and the desk's export go through this rather
	than the document-level check. `Custom Sidebar` carries the same two functions, because it is
	the same layering and the same gate.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or is_workspace_manager(user):
		return ""

	return f"`tabDock`.`user` = {frappe.db.escape(user)}"
