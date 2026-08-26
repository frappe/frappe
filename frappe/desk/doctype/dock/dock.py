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

# What a row may say about how an entry *reads*, as opposed to where it goes. Blank means "no
# opinion, inherit"; filled is an override. Outside `DESTINATION_FIELDS` on purpose: re-labelling
# an entry must never detach the customisations of it.
#
# Required when a row **adds** an entry, because nothing below it holds one; optional when it
# references one, which is the whole of the inheritance.
REFERENCE_FIELDS = ("icon", "title")

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
DOCK_ITEM_FIELDS = (*DESTINATION_FIELDS, *REFERENCE_FIELDS, "added", "hidden")


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
		mount_on: DF.Autocomplete | None
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
		# would let one app hold two site layers while both read as one address to `get_dock`.
		self.user = self.user or SITE_LAYER
		self.validate_app_content()
		self.validate_standard()
		self.blank_the_mount()
		self.anchor_the_items()

	def blank_the_mount(self):
		"""Mounting is an app-layer claim, so no other layer may hold one.

		`depends_on` hides the field on the two writable layers; it does not stop an API write,
		and a site row carrying a mount would put a person's arrangement on somebody else's rail.
		"""
		if not self.standard:
			self.mount_on = None

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
		self.set("items", [row for row in self.items if points_somewhere(stored_row(row))])
		self.validate_added_rows()

	def validate_added_rows(self):
		"""A row with nothing below it has to say how it reads; a reference need not.

		Two ways a row can have nothing below it, and both would otherwise put a **label-less
		button** on the rail:

		- it **adds** an entry, so no lower layer holds one for it to inherit from;
		- it is on the **app's own dock**, which is the bottom of the stack. Every row there is a
		  base row whatever its `added` flag says -- and the flag reads 0 on one promoted from the
		  site's layer, where it really was a reference to something that is no longer beneath it.

		A reference at an upper layer inherits both, which is the whole of what blank means there.
		"""
		for row in self.items:
			if (self.standard or row.added) and not (row.icon and row.title):
				frappe.throw(
					_("Row #{0}: an entry on this dock needs an icon and a title of its own.").format(row.idx)
				)

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
		#
		# **Resolved rather than copied raw.** A site row may be a *reference* -- blank icon and
		# title, inheriting from the layer below -- and there is no layer below the app's own
		# dock. Copied verbatim, those rows would ship with no label at all, which is the
		# label-less button the whole reference/add split exists to prevent.
		#
		# Resolving also means a reference to a dock that is *gone* -- unmark, then mark again --
		# contributes nothing rather than a blank, and that is what the refusal below is for: the
		# author is told their layer names a rail that no longer exists, instead of quietly
		# shipping an empty one.
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

	Its own pass, not a fallback any more. `Dock Item.sidebar` is an ordinary `Link`, so nothing
	the framework does on rename touches it -- `rename_dynamic_links` walks Dynamic Links, which
	is what the retired `link_name` column was. So this is the only thing carrying a shell rename
	onto the rails that name it.

	The rows are updated in place rather than through their parent. A `Dock` is one layer of one
	app's dock, and re-saving one to correct a name it holds would re-run validation nobody asked
	for -- including the export, on an app's own record. Invalidating is then this function's own
	job: `get_dock` reads a `Dock` through `get_cached_doc`, so the document's cache entry is the
	one that goes stale. `rename_doc` happens to flush the whole site cache a few lines after
	`after_rename` returns, which would cover it -- but a helper that leaves its own writes
	visibly stale is only correct while its one caller stays the way it is, and this one costs two
	queries.
	"""
	named = {"parenttype": "Dock", "sidebar": old_name}
	layers = frappe.get_all("Dock Item", filters=named, pluck="parent", distinct=True)
	if not layers:
		return

	frappe.db.set_value("Dock Item", named, "sidebar", new_name, update_modified=False)

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
	# ...and the per-request memo built off it, so a save answering with the rail it just wrote
	# does not resolve against the dock as it was before
	frappe.local.dock_cache = {"app_dock": {}, "mounts": None}
	if user:
		# a person's own arrangement only invalidates their boot
		frappe.cache.hdel("bootinfo", user)
	else:
		frappe.cache.delete_key("bootinfo")


def request_cache_for_docks() -> dict:
	"""Per-request memo for the two reads the rail asks over and over.

	`get_app_dock` and `mounted_apps` are each called once per app *and* once per app per app --
	`get_app_base` asks `mounted_apps`, which asks `get_app_dock` for every shipped dock -- so
	without this a twenty-app bench pays hundreds of lookups to draw its rails. Quadratic in the
	number of apps, on every boot.

	Request-scoped and hand-rolled rather than `@request_cache`, because it has to be *dropped*:
	a save inside the same request (`_save_layer` answers with the rail it just wrote) would
	otherwise resolve against the dock as it was before. `drop_dock_caches` is where that
	happens, which is already the one place that runs on every write.
	"""
	if not hasattr(frappe.local, "dock_cache"):
		frappe.local.dock_cache = {"app_dock": {}, "mounts": None}
	return frappe.local.dock_cache


def dock_records() -> list[dict]:
	"""Cached address of every layer the site holds -- name, app, user, standard -- plus the
	mount an app's own dock declares.

	This is the cost-control story: a boot on a site nobody has arranged answers every layer of
	every app out of one redis read, instead of a query apiece. `mount_on` rides it for the same
	reason -- the boot asks who mounts on whom on every request, and that used to be a cached
	hooks read.

	Addresses rather than documents, so a stale cache can only ever cost a lookup that finds
	nothing -- the same negative filter `Custom Sidebar` keeps.
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
	"""Every layer address the site holds, mapped to the document that holds it."""
	return {(row["app"], row["user"], row["standard"]): row["name"] for row in dock_records()}


def mounted_apps() -> dict[str, str]:
	"""Companion app -> the host whose rail it mounts on, for the mounts that actually **land**.

	Memoised per request: `get_app_base` asks this once per app, and each answer walks every
	shipped dock.

	A companion app has no rail of its own; its entries live on a host's. Declaring that is an
	aspiration, not a renunciation -- three conditions have to hold, and each of them prevents a
	real failure:

	1. **the host is installed.** A companion installed without its host is invisible today:
	   resolution drops the pin, but the boot path takes its apps-screen slot away anyway.
	2. **the host ships a dock of its own.** Mount onto a dock-less host and its rail becomes
	   *entirely another app's entries*, with no route to its own module and the switcher gone --
	   and the common dock-less app ships exactly one module, so this is not an edge.
	3. **the companion ships rows.** Nothing to mount is not a mount.

	The second test is on the host's **own** dock rather than on its resolved rail, so it does
	not go circular -- resolving the host's rail is what wants this answer.

	The host has no say; the site does. A host's file is authored before the companion exists on
	any site, so a veto would be exercised blind. Refusal is **hiding**, at the site layer.
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
	"""The document holding one layer of one app's dock, or None.

	The **name comes off the cache** rather than out of a lookup. It used to be a filtered
	`db.exists`, which is a query the cache had already answered -- and one that cannot itself be
	cached, since redis caching does not work with filters. A boot resolves three layers for every
	app, so that was three queries per app for something already in redis.
	"""
	name = get_dock_layers().get((app, user or SITE_LAYER, standard))
	return frappe.get_cached_doc("Dock", name) if name else None


def stored_row(row) -> dict:
	"""One stored `Dock Item`, read as the dict every reader above here works in.

	A read of the columns and nothing else, now that the old typed pair is gone. It stays a
	function rather than becoming a dict comprehension at each call site because it is also what
	normalises a blank column to `None` -- the schema writes `""` where a reader wants "unset",
	and `dock_key` would otherwise be built from two different spellings of nothing.
	"""
	return {
		**{field: row.get(field) or None for field in DESTINATION_FIELDS},
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
	"""One app's own dock, with the rows of every companion mounted on it appended.

	Appended rather than positioned, and **as a default**: a companion is not asserting an
	opinion into an arrangement that is not its, and the site and the person may then reorder
	the lot. Two companions mounting on one host land in installation order rather than fighting
	for a slot.
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
	"""Every entry `app`'s dock offers this person, before any layer arranges them.

	What the boot payload carries as `app_data[].dock` and what the manager builds its panes
	from. Filtered by reach and by nothing else: which of them are *on* the rail, and in what
	order, is the layers' business and is answered by `resolve_app_dock`.
	"""
	return [rail_entry(row) for row in get_app_base(app) if is_reachable(row)]


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
	"""Every app whose rail could resolve to something: one that ships a record, or one some
	layer on this site has an opinion about.

	Both come off the same cached read, which is what keeps a boot on a site nobody has arranged
	free. Asking every installed app instead would be correct and nearly as cheap, but it would
	walk apps that have never had a rail on any site.

	**Narrowed to apps that are actually here.** Nothing reaps a site's or a person's layer when
	its app is uninstalled -- only a *standard* row is an orphan candidate -- so a bench that has
	ever removed an app holds rows naming one that is gone. Left in, the sort key asks that app
	for its hooks and the boot dies with `ModuleNotFoundError`.

	A companion whose mount lands is left out too: its entries render on the host's rail, and it
	has no rail of its own for anything to resolve to.
	"""
	installed = set(frappe.get_active_apps())
	mounted = mounted_apps()
	apps = {row["app"] for row in dock_records() if row["app"] in installed} - set(mounted)
	return sorted(apps, key=apps_screen_sort_key())


def resolve_app_dock(app: str, upto: str = "user", gated: bool = True) -> list[dict]:
	"""One app's rail for the session user: its own dock, then the site's, then their own.

	`upto` names the last layer applied, and `gated` says whether reach is applied. Both exist for
	the save path rather than for the boot: a layer being written has to be settled against the
	rail it was *looking at*, which is the layers **below** it -- and unfiltered, because whether
	a row is an add is a question about base membership, not about who can see it. Reach-filtered,
	a Workspace Manager saving the site's rail with one module blocked for them personally would
	turn that module's row into an add, and adds demand an icon and a title nobody typed.
	"""
	# Built for the one answer wanted, not all three. Spelled as a list that grows because that
	# *is* the stack: each layer is laid over the one before it, and `upto` says where to stop.
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
		# A saved layer *is* the rail. An entry the app ships later does not appear on it; it
		# appears in Manage Dock as something to add, and you opt in by adding it. The cost is on
		# the record and is deliberate: predictable rails over automatic updates.
		keep_unnamed=False,
	)
	# Applied last, so no layer can name its way past the gates -- an arrangement is navigation
	# reach, and reach is decided by module visibility and workspace permissions alone.
	return [
		{**rail_entry(entry), "hidden": int(hidden.get(dock_key(entry), 0))}
		for entry in resolved
		if not gated or is_reachable(entry)
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


def apply_dock_row(row, entry: dict | None) -> dict | None:
	"""What one layer row does to the dock entry it names.

	Two kinds of row, exactly as the sidebar has. An **added** row *is* the entry: it brings a
	destination nothing below it holds, so it stands in for whatever the list has under that key,
	which is usually nothing. A **reference** row states an opinion about an entry that is
	already there, and `overrides` keeps that opinion short.

	A reference naming an entry the list does not hold returns `None` and is skipped. That is
	what stops a reference to a row the app has since deleted **resurrecting as a label-less
	button** -- a destination with no icon and no title, because a reference is not required to
	carry either.

	`added` is stored rather than inferred from the row carrying a body, and that is not
	convenience: under permitted re-labelling a reference may carry a partial opinion -- an icon
	and no title -- so body-presence stops telling the two apart.
	"""
	if row.get("added"):
		return rail_entry(row)

	if entry is None:
		return None

	return {**entry, **overrides(row)}


def rail_entry(entry) -> dict:
	"""What the rail is handed: where the entry goes, and how it reads."""
	return {
		**{field: entry.get(field) for field in DESTINATION_FIELDS},
		**{field: entry.get(field) for field in REFERENCE_FIELDS},
	}


def overrides(row) -> dict:
	"""What a reference row *opines* about the entry it names. A blank field is no opinion, so
	the entry keeps whatever the layer below gave it.

	This is what stops one reorder freezing the app's label forever -- the failure that killed
	full-body storage in the sidebar, and one 06 made urgent here by giving every row a stored
	icon and title.
	"""
	return {field: row.get(field) for field in REFERENCE_FIELDS if row.get(field)}


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


def shape_dock_rows(items: list | str, require_visible: bool, below: dict[str, dict]) -> list[dict]:
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

	`below` is every entry this layer could be referencing, keyed by destination (see
	`entries_below`). It settles two things the client is not trusted to say: whether a row
	**adds**, and whether its icon and title are an *opinion* or merely what it was shown.
	"""
	shown = below
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
		shaped.append(settle_reference(entry, shown.get(key)))

	return shaped


def settle_reference(entry: dict, below: dict | None) -> dict:
	"""Say whether this row adds an entry or references one, and keep its opinion honest.

	**Adding is derived, never taken from the client.** A row whose destination nothing below it
	holds is an add: it brings the entry rather than opining about one. A pleasant consequence of
	identity being the destination -- a person pins `Payables`, the app later ships `Payables`
	itself, and the next save turns the person's add into a reference to it, so the two **merge
	into one entry with the person's position winning** rather than doubling.

	A reference blanks out what it only **echoes back**. The client sends the arrangement it is
	*showing*, which carries the labels and icons it was given; stored as-is they would stop being
	inheritance and start being opinion, and an entry the person never touched would keep the
	label it happened to have on the day they reordered -- neither the site's relabel nor the
	app's ever reaching them again.
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
	"""Every entry a layer being saved could be *referencing*, keyed by destination.

	**The rail as it was without this layer**, which is exactly what the saver was looking at --
	so what their icons and titles were echoing back, and what a row of theirs can be a
	*reference to*. A person's own save sees the app's dock with the site's arrangement on it;
	the site's sees the app's dock alone, never the curator's own arrangement, which is not
	theirs to publish.

	Anything else is an **add**: a destination the rail below did not hold. That includes a URL
	somebody typed, a workspace no dock names, and an entry the site took off -- a person
	bringing that one back is not restoring the site's row, they are putting their own there,
	which is why it carries a cross rather than an eye and why it has to say how it reads.

	Ungated on purpose -- whether a row adds is a question about membership, not about who can
	see it. Reach-filtered, a Workspace Manager saving the site's rail with one module blocked
	for them personally would turn that module's row into an add.
	"""
	below = resolve_app_dock(app, upto="user" if user else "site", gated=False)
	return {dock_key(entry): entry for entry in below}


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
	for row in shape_dock_rows(items, require_visible=require_visible, below=entries_below(app, user)):
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
def save_app_dock(app: str, items: list | str):
	"""Persist the app's **own** dock -- the layer the other two are laid over.

	The one save that is authoring rather than arrangement, which is why it is gated on developer
	mode and on nothing else: what makes this write okay is that the site belongs to a developer.
	`Dock.validate_app_content` refuses it again at the document, and `on_update` writes the file,
	so pressing Save in the manager and shipping the result are one act.

	Not offered where the app ships no dock yet -- promoting is `mark_as_standard`, which is one
	act with the file write and rolls the row back if the write does not land.
	"""
	app = check_docked_app(app)
	check_developer_mode()

	doc = get_dock(app, standard=1)
	if not doc:
		frappe.throw(_("{0} ships no dock yet. Export one to the app first.").format(frappe.bold(app)))

	doc = frappe.get_doc("Dock", doc.name)
	doc.set("items", [])
	# `below` is empty: there is nothing under the app's own dock, so every row of it adds and
	# every row carries its own icon and title. That is the same rule the layers above follow,
	# read at the bottom of the stack.
	for row in shape_dock_rows(items, require_visible=False, below={}):
		doc.append("items", {field: row[field] for field in DOCK_ITEM_FIELDS})

	doc.save(ignore_permissions=True)
	return resolve_app_dock(app)


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
	return [{**rail_entry(row), "hidden": row["hidden"]} for row in get_app_dock(check_docked_app(app))]


# ---------------------------------------------------------------------------------------
# Reset for everyone
# ---------------------------------------------------------------------------------------


@frappe.whitelist()
def reset_dock_for_everyone(app: str) -> list[dict]:
	"""Drop every non-standard `Dock` for `app` -- the site's own layer included -- so everybody
	is back on the app's exported dock.

	The argument is the sidebar's verbatim: a Workspace Manager who re-curates the site's rail
	**reaches nobody who has arranged their own**. Reset at the site layer only lifts the site's
	opinion; this is the one act that reaches past it, which is why it is an immediate confirmed
	endpoint behind Workspace Manager rather than a pane edit applied on Save.

	Deleted **row by row so each `on_trash` runs**: only the document knows whose boot cache to
	invalidate, and a bulk delete would leave every one of those people booting a rail that no
	longer exists.
	"""
	# The right first, the lookup second: an unprivileged caller should be refused for the reason
	# that applies to them, not told which apps this site has on the way.
	check_workspace_manager(_("You need to be Workspace Manager to reset the dock for everyone."))
	app = check_docked_app(app)

	for name in frappe.get_all("Dock", filters={"app": app, "standard": 0}, pluck="name"):
		frappe.delete_doc("Dock", name, force=True, ignore_permissions=True)

	return resolve_app_dock(app)


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
