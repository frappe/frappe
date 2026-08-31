# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""Builds a module's sidebar and resolves it for one user.

Every module in the desk has a sidebar. It starts from one of two sources:

  1. a `Sidebar` document shipped by an app as JSON, under `<app>/<module>/sidebar/`, or
     under `<app>/sidebar/` when the sidebar belongs to the app instead of a module.
  2. a computed sidebar, worked out from what the module holds: its workspaces, dashboards,
     doctypes, reports and pages.

Both sources produce the same shape, so callers do not need to know which one was used. The
only difference is the `computed` flag, which the desk reads so a display limit is not mistaken
for a user's choice.

`resolve_sidebar` then resolves that sidebar for one user, in this order:

  1. drop items the user cannot see
  2. apply the site's customizations, then the user's own (see `custom_sidebar.py`)
  3. add the user's private workspaces, which are computed rather than stored
  4. drop the module if nothing navigable is left

Building the boot payload is assembly on top of that.

Resolving seventy modules should not cost seventy times one module, so every site-wide read is
fetched once into a `SidebarContext` and the per-module work is plain Python over it.
"""

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from functools import cached_property

import frappe
from frappe import _
from frappe.app_state import get_disabled_modules
from frappe.desk.desk_views import DeskViews
from frappe.desk.utils import is_item_allowed
from frappe.model.document import Document
from frappe.model.rename_doc import rename_doc
from frappe.utils.modules import get_module_placement

# The fields copied unchanged from a source item row into a `Sidebar Item`.
SIDEBAR_ITEM_FIELDS = (
	"type",
	"label",
	"link_type",
	"link_to",
	"icon",
	"child",
	"indent",
	"collapsible",
	"keep_closed",
	"url",
	"show_arrow",
	"filters",
	"route_options",
	"navigate_to_tab",
	"open_in_new_tab",
)

# `is_default_module` is left out on purpose. An app sets it to claim "this entity belongs to
# my module", and the fixture conversion drops it rather than guessing. An app that wants the
# claim sets it in the `sidebar` file it ships.

# These columns identify a sidebar item that points somewhere. We match on the columns
# themselves instead of storing a hash of them, so customizations survive a rename: `link_to`
# is a Dynamic Link, so `rename_dynamic_links` updates every `Sidebar Item` naming the renamed
# document in one statement, base rows and customization rows alike. A stored hash could not be
# updated that way, and the customization would keep pointing at the old name.
#
# `filters` is one of them because a filtered list is a different destination, not a second name
# for the same one. A sidebar may offer both "Sales Invoice" and "Credit Note", which is the same
# doctype narrowed to returns; without the filters they share an identity and
# `filter_sidebar_items` keeps the first and silently drops the rest.
#
# The label is deliberately *not* here, though it is the other thing that tells those two rows
# apart on screen. Relabelling an item is something a `Custom Sidebar` does, so a label in the
# identity would break the very delta that set it -- `narrow_reference` stores label and icon as
# overrides for exactly that reason, and stores no filters, which is what makes filters stable
# enough to identify by.
LINKED_IDENTITY_FIELDS = ("type", "link_type", "link_to", "url", "filters")

# Flags that mean the system is installing app content, not that a user is editing.
#
# A `Sidebar` lives in an app's JSON file and reaches a site through one of these routes. Each
# has to keep working when developer mode is off, or installing or updating an app that ships a
# sidebar would fail on every customer site.
SYSTEM_WRITE_FLAGS = ("in_import", "in_fixtures", "in_migrate", "in_install", "in_patch")


class Sidebar(Document, DeskViews):
	_DOCTYPE_NAME = "Sidebar"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.sidebar_item.sidebar_item import SidebarItem
		from frappe.types import DF

		app: DF.Autocomplete | None
		header_icon: DF.Icon | None
		items: DF.Table[SidebarItem]
		merged_from: DF.LongText | None
		module: DF.Link | None
		standard: DF.Check
		title: DF.Data
	# end: auto-generated types

	def before_naming(self):
		# the name is the title, so the default has to be in place before naming reads it
		self.set_default_title()

	def validate(self):
		self.validate_app_content()
		self.set_default_title()
		self.validate_title_is_its_own()
		self.validate_standard()
		self.clear_stored_keys()

	def before_save(self):
		self.rename_to_title()

	def set_default_title(self):
		"""Title an untitled sidebar after its module.

		The default is stored, not computed on read. Every sidebar shipped today is titled after
		its module, so storing the default leaves their record names, exported paths and
		references unchanged.

		Called from `before_naming` as well as `validate` because `field:` autoname reads the
		column directly, before `validate` has filled it in.
		"""
		if not self.title:
			self.title = self.module

	def validate_title_is_its_own(self):
		"""Refuse a title that is another module's name.

		The title is the record name, and the name is the key the boot payload is built on. A
		module with no sidebar of its own gets a computed sidebar under its own name, so a
		sidebar titled after another module would claim the same key and one of the two would
		be dropped silently. We refuse it here, while the user can still pick another title.

		Titling a sidebar after its own module is the default and is allowed.
		"""
		if self.title == self.module:
			return

		if frappe.db.exists("Module Def", self.title, cache=True):
			frappe.throw(
				_("{0} is another module's name, and a sidebar's title is what the desk calls it by.").format(
					frappe.bold(self.title)
				),
				title=_("Pick another title"),
			)

	def rename_to_title(self):
		"""Rename the document when the title changes, because the name is the title.

		`field:` autoname only runs on insert. On an update the name stays as it was and
		`_sync_autoname_field` copies it back over the column, so a title edit would silently
		revert. `Workspace` handles this with explicit `rename_doc` calls at its endpoints; we
		do it inside the document so every writer gets it.

		The rename runs before the save, not after. The row is still under its old name here,
		which is what `rename_doc` needs, and the save that follows writes the rest of the edit
		to the renamed row.

		The `in_import` check is defensive. `import_doc` deletes and re-inserts with
		`ignore_validate`, so an import never reaches here, but it also leaves the flag set to
		`False` instead of restoring the previous value, and a rename here moves a folder inside
		an app.
		"""
		if frappe.flags.in_import or self.is_new() or not self.title or self.title == self.name:
			return

		# rebuild_search is off: a sidebar has no field in global search, so the rebuild this
		# would enqueue on every title edit has nothing to find
		rename_doc(self.doctype, self.name, self.title, ignore_permissions=True, rebuild_search=False)
		self.name = self.title
		# The item rows moved with the record. The save about to run writes them back under the
		# `parent` they still carry, which is the old name.
		self.set_parent_in_children()

	def after_rename(self, old_name, new_name, merge=False):
		from frappe.desk.doctype.dock.dock import rename_sidebar_rows

		rename_sidebar_rows(old_name, new_name)

	def clear_stored_keys(self):
		"""Blank the `key` column on every item.

		A base row is identified by its own columns, so it needs no stored key. The column only
		means something on a `Custom Sidebar` row, where a reference to a Section Break has no
		other way to name it.

		On a base row a stored key would be a second, possibly stale answer to the same question.
		Rows shipped before keys changed still carry one. Every import runs `validate`, so the
		app's next update clears them.
		"""
		for item in self.items:
			item.key = None

	def validate_app_content(self):
		"""Allow editing a sidebar only in developer mode, because a sidebar belongs to its app.

		This keeps app updates safe. Without developer mode, every sidebar document on the site
		got there by import, so an app overwriting its own sidebar loses nothing. A site that
		wants a different sidebar uses a `Custom Sidebar` instead, either site-wide or per user,
		and this check does not touch those.

		Developer mode is the only condition. There is no role check, so any developer on a
		developer-mode site can edit one. Access to the doctype itself is decided by its own
		permissions, where `Desk User` has read only.

		Deleting is not blocked. A delete cannot turn site intent into app content, and the
		things that delete one, such as a module going away or orphan cleanup, have to keep
		working on a customer site.
		"""
		if frappe.conf.developer_mode:
			return

		if any(frappe.flags.get(flag) for flag in SYSTEM_WRITE_FLAGS):
			return

		frappe.throw(
			_(
				"{0} belongs to its app and can only be edited in developer mode. "
				"Customize the sidebar instead to change it for this site."
			).format(frappe.bold(self.name or self.title)),
			title=_("Not Editable"),
		)

	def validate_standard(self):
		"""Refuse to mark a sidebar standard unless we can write its file.

		`standard` means a JSON file in an app backs this row, and only developer mode can write
		that file. A standard row with no file counts as an orphan, so `remove_orphan_entities`
		deletes it on the next `bench migrate`. Refusing is better than creating a row that
		deletes itself.

		This also runs when `module` or `app` changes, not only when the flag goes on. Both may
		be blank, so clearing them on an already-standard row produces the same broken row:
		standard, with nowhere to write its file. Watching the flag alone would miss that.
		"""
		if not self.standard:
			return

		if not any(self.has_value_changed(field) for field in ("standard", "module", "app")):
			return

		check_developer_mode()

		if not self.module:
			# App-rooted: there is no module folder to write into, so `app` is the whole
			# address, and it has to name an app installed on this site.
			if not self.app:
				frappe.throw(_("A standard sidebar needs a module or an app to be written to."))

			if self.app not in frappe.get_installed_apps():
				frappe.throw(
					_("App {0} is not installed, so a standard sidebar cannot be written to it.").format(
						frappe.bold(self.app)
					)
				)
			return

		try:
			frappe.get_module_path(self.module)
		except (frappe.DoesNotExistError, ImportError):
			# `get_module_app` throws instead of returning, and the message it queued would
			# reach the user next to ours, saying the same thing twice.
			frappe.clear_last_message()
			frappe.throw(
				_(
					"Module {0} has no folder in an app, so a standard sidebar cannot be written to it."
				).format(frappe.bold(self.module))
			)

	# There is no duplicate-item check on purpose.
	#
	# An item is identified by its own columns, so two rows with the same columns are the same
	# item. A document can legitimately contain that, for example two workspaces of one module
	# linking the same report. Resolving the sidebar keeps the first and drops the rest, so
	# nothing downstream breaks. Refusing the save would reject app content that renders fine.

	def on_update(self):
		self.remove_previous_export()
		self.export_sidebar()

	def remove_previous_export(self):
		"""Delete the file this sidebar was exported to under its previous name.

		A rename leaves that file behind with no row of its own, and the next `bench migrate`
		imports it back as a second sidebar.

		This runs after the save rather than next to the rename, because deleting a folder
		inside an app is the one step a failed save cannot undo. Everything else unwinds with
		the transaction. `Workspace.on_update` removes its stale folder in the same place for
		the same reason.

		Developer mode gates it, since only a developer's site has files inside an app.
		"""
		import os
		import shutil

		previous = self.get_doc_before_save()
		if not frappe.conf.developer_mode or not previous or previous.name == self.name:
			return

		if previous.standard and previous.is_exported():
			shutil.rmtree(os.path.dirname(previous.exported_file_path()), ignore_errors=True)

	def export_sidebar(self):
		"""Write this sidebar to its JSON file.

		The path is `<app>/<module>/sidebar/<name>/<name>.json` when the sidebar has a module,
		and `<app>/sidebar/<name>/<name>.json` when it has none, because that one belongs to the
		app rather than to a module.

		Both have the same shape: a folder named after the record holding a file of the same
		name. The old sidebar fixtures sat in one flat folder at the top of the app, so
		filenames did not have to match record names, and mismatched ones had their rows deleted
		on the next migrate. Orphan cleanup builds a record's path as `<...>/<scrub(name)>.json`,
		so the filename and the record name must agree, which they do under either root.
		"""
		from frappe.modules.export_file import export_to_files

		if not self.standard or frappe.flags.in_import or not frappe.conf.developer_mode:
			return

		if self.module:
			export_to_files(record_list=[["Sidebar", self.name]], record_module=self.module)
		elif self.app:
			export_to_files(record_list=[["Sidebar", self.name]], record_app=self.app)

	def exported_file_path(self) -> str:
		"""Return the path `export_to_files` writes this sidebar to.

		The export module computes it rather than this file rebuilding it, so the path checked
		here is always the path the export writes. That is also why dropping
		`autoname: field:module` changed the record name without changing how the path is built.
		"""
		from frappe.modules.export_file import export_root, exported_file_path

		root = export_root(module=self.module) if self.module else export_root(record_app=self.app)
		return exported_file_path(root, self.doctype, self.name)

	def is_exported(self) -> bool:
		"""Return whether the file behind this sidebar exists on disk.

		Orphan cleanup asks the same question, so `mark_as_standard` has to answer it before
		reporting the sidebar as shipped. A module with no folder has no file.
		"""
		import os

		if self.is_new() or not (self.module or self.app):
			return False

		try:
			return os.path.exists(self.exported_file_path())
		except (frappe.DoesNotExistError, ImportError):
			# No module folder, so no file. `get_module_app` says so by throwing and queueing a
			# message, which would otherwise surface as an error beside `mark_as_standard`'s own
			# success alert.
			frappe.clear_last_message()
			return False


# ---------------------------------------------------------------------------------------
# Marking a sidebar standard, and undoing that
#
# `standard` means an app ships this sidebar as a JSON file. The two actions below turn the
# flag on and off, and both move the file as well.
# ---------------------------------------------------------------------------------------


@frappe.whitelist()
def mark_as_standard(module: str) -> str:
	"""Make `module`'s sidebar part of its app and return the document name.

	It writes the sidebar into the module's folder so the app ships it, and `bench migrate`
	imports it back from there.

	The document is built first and exported second, so an author starts from what the system
	generated instead of an empty file. A module with no document still has a base, computed by
	`get_computed_base` from what the module holds, and that is what gets written. A document
	that already has items is shipped as it stands. See `materialize_base`.

	Developer mode is the only condition; there is no role check, because the site belongs to a
	developer. Access to the doctype is decided by its own permissions (see
	`validate_app_content`).

	We check the file was written and roll back if it was not. A standard row with no file is an
	orphan, and `remove_orphan_entities` deletes it on the next `bench migrate`.
	"""
	check_developer_mode()

	doc = materialize_base(module)

	# Already shipped, so there is nothing to do. We check the flag and the file: a standard row
	# with a missing file is the orphan this action prevents, so write it again rather than
	# report success.
	if doc.standard and doc.is_exported():
		return doc.name

	savepoint = "mark_sidebar_standard"
	frappe.db.savepoint(savepoint)
	try:
		doc.standard = 1
		doc.app = get_module_placement(module)
		# `save` inserts a freshly built base or updates an existing document. Either way,
		# `on_update` writes the file.
		doc.save()

		if not doc.is_exported():
			frappe.throw(
				_("Could not write {0} to {1}. Left unchanged.").format(
					frappe.bold(doc.name), frappe.bold(doc.app or "-")
				)
			)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise
	frappe.db.release_savepoint(savepoint)

	frappe.msgprint(
		_("{0} is now standard and exported to {1}.").format(frappe.bold(doc.name), frappe.bold(doc.app)),
		alert=True,
		indicator="green",
	)
	return doc.name


@frappe.whitelist()
def unmark_as_standard(sidebar: str) -> None:
	"""Give `sidebar` back to the site by deleting its exported file and its document.

	It names the document rather than the module, because it destroys one and a module may own
	more than one. `mark_as_standard` takes a module for the opposite reason: there may be no
	document yet and it has to build one. Both callers have a document to name: the `Sidebar`
	form's button is pressed on the one on screen, and the app layer's reset names the shell it
	arranged.

	The document is deleted rather than just unflagged. Once the app content is gone the module
	falls back to its computed base, which is worked out from the module's contents on read, so
	the module has a working sidebar again in the same request.

	Clearing the flag alone would leave a row nobody owns: not app content, because there is no
	file, and not site intent, because that lives in `Custom Sidebar`. It would be a frozen copy
	of a base that no longer follows the module.

	The file has to go too. Left on disk, the next `bench migrate` imports it again and the row
	comes back standard.
	"""
	import os
	import shutil

	check_developer_mode()

	if not frappe.db.exists("Sidebar", sidebar):
		return

	doc = frappe.get_doc("Sidebar", sidebar)
	# Only a standard sidebar belongs to an app. If it is not standard there is nothing to hand
	# back, and we should not delete a document someone is still working on.
	if not doc.standard:
		return

	path = doc.exported_file_path() if doc.is_exported() else None
	doc.delete()

	# Delete the file now rather than on commit. If someone un-marks and marks again in one
	# request, we want the file the second call wrote, not a queued delete that removes it
	# afterwards.
	if path:
		shutil.rmtree(os.path.dirname(path), ignore_errors=True)

	frappe.msgprint(
		_("{0} is no longer standard; its exported file has been removed.").format(frappe.bold(doc.name)),
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
		_(
			"Enable developer mode to change whether a sidebar is standard -- it is backed by a file in its app."
		),
		title=_("Not Editable"),
	)


def get_sidebar(module: str) -> "Sidebar | None":
	"""Return the sidebar that answers for `module`, or `None`.

	A module may own several sidebars, since a sidebar is named by its title. The one that
	answers for the module is the one named after it. Any other sidebar under that module is
	reached by a dock row that names it. This is why there is no `is_default` column: the name
	says which one it is.

	`None` is the usual answer. Nothing creates a sidebar document for a module automatically,
	so most modules have none and get a computed base instead. So does a module whose only
	sidebar is named something else.
	"""
	name = frappe.db.get_value("Sidebar", {"name": module, "module": module})
	return frappe.get_doc("Sidebar", name) if name else None


def get_module_shell(module: str) -> "Sidebar | None":
	"""Return the stored sidebar an action on `module` writes to, or `None` when there is none.

	`get_sidebar` answers the naming rule alone, and a module whose sidebar was renamed has no
	answer there. It still has a sidebar, and that one is what the desk draws and what the editor
	arranges, so an action that writes an arrangement, or undoes one, has to reach the same
	document rather than work against a name nothing holds.

	The order is `get_module_base`'s, and deliberately the same one: the shell named after the
	module when there is one, and otherwise the first by name. A module owning two renamed shells
	has no single answer, and `get_module_base` picks one anyway so the editor has something to
	show; because this picks the same one, what a save writes and what a reset deletes is the
	document that was on screen. Answering differently here is what would reach a document nobody
	was looking at.

	This asks the table instead of going through `get_module_base`, which computes a base from
	the module's contents to answer, because the answer here is only ever a document that already
	exists.
	"""
	name = frappe.db.get_value("Sidebar", {"name": module, "module": module}) or frappe.db.get_value(
		"Sidebar", {"module": module}, order_by="name asc"
	)
	return frappe.get_doc("Sidebar", name) if name else None


def materialize_base(module: str) -> "Sidebar":
	"""Return the module's base as a document, ready to be exported.

	This is the only place a computed base becomes a stored one.

	A document that already has items was written by someone, so it is returned as it stands.
	Otherwise, whether there is no document or one with an empty items table, we fill it from
	the computed base. That is what the desk shows for the module today (see
	`get_sidebar_bases`); an empty file would not match the navigation it came from.

	The rows are copied unchanged, which keeps existing customizations working. An item is
	identified by the columns being copied, so an item someone hid stays hidden and nothing
	needs re-keying.
	"""
	doc = get_sidebar(module)
	if doc and doc.items:
		return doc

	base = get_computed_base(module)
	if not doc:
		doc = frappe.new_doc("Sidebar")
		doc.module = module
		doc.title = base.title
		doc.header_icon = base.header_icon

	for row in base.rows:
		# Copy each row: `append` writes doctype and parent keys into the dict it is given, and
		# these rows belong to the cached base, which must not be modified.
		doc.append("items", dict(row))
	return doc


# ---------------------------------------------------------------------------------------
# The app layer: reading, writing and resetting the sidebar an app ships
#
# One editor arranges all three of a sidebar's layers (`frappe.ui.SidebarManager`), so all three
# answer the same three questions in the same shapes. The two above are `Custom Sidebar`
# documents and live in `custom_sidebar.py`; this one is the `Sidebar` document itself, so it
# lives here.
#
# Every one of them is developer mode only, which is the gate `validate_app_content` already
# puts on writing a `Sidebar` by any other route. There is no role check, for the same reason
# there is none there: a site running in developer mode belongs to a developer.
# ---------------------------------------------------------------------------------------

# What the editor shows and hands back, under the names the boot payload uses. Each is a
# `Sidebar Item` column of the same name, except `navigate_to_tab`, which the payload calls
# `tab` and which is therefore carried on its own.
#
# These and the three `app_item` sets itself are every column the child table has, which is what
# lets a save rebuild the table from what the client sent instead of merging into what was
# already stored. A column added to `Sidebar Item` and not added here would be dropped by the
# next save, and `test_the_editor_round_trips_every_column` is the only thing that would say so.
#
# Not `SIDEBAR_ITEM_FIELDS`, which answers a different question: what the fixture conversion
# copies out of a workspace row. That set drops `is_default_module` because a conversion cannot
# guess an app's claim on an entity; this one keeps it, because a claim the app already made has
# to survive being arranged.
ARRANGED_ITEM_FIELDS = (
	"type",
	"label",
	"link_type",
	"link_to",
	"icon",
	"child",
	"indent",
	"collapsible",
	"keep_closed",
	"url",
	"show_arrow",
	"filters",
	"route_options",
	"open_in_new_tab",
	"is_default_module",
)


@frappe.whitelist()
def get_app_sidebar_layer(module: str) -> list[dict]:
	"""Return the sidebar `module`'s app ships, as the editor arranges it.

	This is a third answer to "what does this module's sidebar look like", beside the two in
	`custom_sidebar.py`, and it is the bottom one: the base, with no layer over it. A module no
	app shipped a `Sidebar` for answers with its computed base, which is what the desk draws for
	it today and what the first save turns into a document.

	Hidden rows are kept, the same as in the layers above, since an editor that cannot see a
	hidden row cannot offer to bring it back.

	There is no permission filter, the same as the site layer's read and for the same reason:
	this editor writes the whole arrangement, so a row filtered off the screen would be dropped
	from the document on the next save.
	"""
	from frappe.desk.doctype.custom_sidebar.custom_sidebar import check_module

	check_developer_mode()
	check_module(module)

	base = get_module_base(module)
	# `is_item_allowed` is a method on `DeskViews`, so the filter needs a context object even
	# when it is not going to check anything with it: one throwaway `Workspace`, the same as
	# `layer_arrangement` builds.
	items = filter_sidebar_items(base.rows, frappe.new_doc("Workspace"), check_permission=False)

	# `added` is what a row in a layer above a base says: "I bring my own item". Every row here
	# is the base, so none of them adds anything to anything, and the editor treats them all as
	# rows it may hide rather than rows it may delete.
	return [{**item, "hidden": int(item.get("hidden") or 0), "added": 0} for item in items]


@frappe.whitelist()
def save_app_sidebar(module: str, items: list | str) -> dict:
	"""Store the arrangement on screen as the sidebar `module`'s app ships, and export it.

	`items` is the whole ordered arrangement rather than a delta, the same as the two saves
	above. Unlike them, every row is the item itself: this is the base, so there is nothing
	underneath for a row to refer to.

	The document is made standard here rather than by a later step. The layer is named after the
	app, and a document that is not standard is not the app's: no file backs it, no migrate
	re-imports it, and orphan cleanup is not looking for it. A row like that would also replace
	the computed base on this site while leaving nothing in git to say so. `on_update` writes
	the file, so the export follows from the flag.
	"""
	from frappe.desk.doctype.custom_sidebar.custom_sidebar import check_module, module_payload

	check_developer_mode()
	check_module(module)

	if isinstance(items, str):
		items = json.loads(items)

	doc = app_document(module)
	doc.set("items", [])
	for row in items:
		doc.append("items", app_item(row))

	doc.standard = 1
	doc.app = get_module_placement(module)
	doc.save()

	return module_payload()


@frappe.whitelist()
def reset_app_sidebar(module: str) -> dict:
	"""Drop the sidebar `module`'s app ships, so the module goes back to its computed one.

	The two resets above drop a layer and let the one below show through. This is the bottom
	layer, and what shows through is the computed base, which is worked out from the module's
	contents on read and is therefore there again in the same request.

	`unmark_as_standard` does the work: the document and its exported file both go, because a
	standard row with no file is an orphan and a file with no row comes back on the next migrate.
	It is named the shell rather than the module, since it deletes what it is given.

	Which shell that is has one answer, `get_module_shell`, shared with the read and the save.
	The three have to agree: this drops what the person on screen arranged, so resolving it any
	other way here would delete a document they were not looking at. A module owning nothing to
	drop, which is the ordinary state of one whose base is computed, is left alone.
	"""
	from frappe.desk.doctype.custom_sidebar.custom_sidebar import check_module, module_payload

	check_developer_mode()
	check_module(module)

	shell = get_module_shell(module)
	if shell:
		unmark_as_standard(shell.name)

	return module_payload()


def app_document(module: str) -> "Sidebar":
	"""Return the document the app layer writes to, materializing it if there is none.

	It addresses the shell the read addressed rather than asking the naming rule, so a module
	whose sidebar has been renamed is arranged, saved and reset in the same place.
	`get_sidebar` answers `None` for that module, and `materialize_base` would then build a
	second sidebar under it instead of writing the one the editor was showing.
	"""
	return get_module_shell(module) or materialize_base(module)


def app_item(row: dict) -> dict:
	"""Return one arranged row as a `Sidebar Item` on the app's own document."""
	item = {field: row.get(field) for field in ARRANGED_ITEM_FIELDS}

	# The payload calls it `tab`. The column does not.
	item["navigate_to_tab"] = row.get("tab")
	item["hidden"] = int(bool(row.get("hidden")))
	# `added` belongs to a row in a layer above a base, where it says the row brings its own
	# item. A base row is the item, so the flag has nothing to say here. The `key` the editor
	# sent is dropped by `clear_stored_keys` on save, for the reason it explains.
	item["added"] = 0

	return item


def is_linked(item) -> bool:
	"""Return whether this row links somewhere. A Section Break or a spacer does not."""
	return bool(item.get("link_to") or item.get("url"))


def item_key(item) -> str:
	"""Return the identity of one sidebar item. A customization row uses this to name the item
	it refers to.

	There are two shapes, one per kind of row:

	- A row that links somewhere is identified by the columns it already has, so nothing extra
	  is stored and a rename does not break it. See `LINKED_IDENTITY_FIELDS`.
	- A row that links nowhere, such as a Section Break or a spacer, is identified by a hash of
	  its type and label. Using the label is safe: the section labels we generate are constants
	  in the code, at most three per module, and all different.

	Only a customization row stores that hash. A reference to a Section Break has nothing else
	to name it by, and the reference is allowed to override the label. A base row computes its
	key each time and stores nothing, which `Sidebar.clear_stored_keys` enforces and boot never
	reads. So a stored key reaching here always came from a customization, never from an older
	version of this function.

	This function only reads columns the rows already carry, so importing the same JSON twice
	produces the same identities. Standard child rows are hash-named and recreated on every
	import, which is why a customization can never point at a row's `name`.
	"""
	if is_linked(item):
		return "|".join(item.get(field) or "" for field in LINKED_IDENTITY_FIELDS)

	return item.get("key") or unlinked_key(item)


def unlinked_key(item) -> str:
	"""Compute the key for an unlinked row when nothing has stored one for it.

	The key has no position number. The old version used one to tell apart rows that collided
	because the label was left out. Including the label removes those collisions, and dropping
	the position number stops every customization below an inserted row from being re-pointed.
	"""
	identity = f"{item.get('type') or ''}|{item.get('label') or ''}"
	return hashlib.sha1(identity.encode()).hexdigest()[:10]


# ---------------------------------------------------------------------------------------
# The merge: folding a module's several old sidebars into one
#
# Only data conversion uses this. Both callers are conversions:
#
#   * `convert_fixtures`, where an app's old fixtures were one file per workspace, so a module
#     with four workspaces has to end up with one sidebar.
#   * `patches.v16_0.convert_sidebars`, where a user may have forked several of a module's
#     sidebars and now needs a single customization layer.
#
# Nothing on a running site merges. That is why this sits beside the model rather than inside
# it, and why it goes away when the conversion does (see `frappe/desk/RETIRING.md`).
# ---------------------------------------------------------------------------------------


def majority_module_of(rows) -> str | None:
	"""Return the module most of these rows point at.

	Used to work out which module an old sidebar belonged to when it did not say. Every sidebar
	must belong to a module now, and one with no module has nothing to merge into.
	"""
	modules = []
	for row in rows:
		if not row.get("link_to") or row.get("link_type") in (None, "", "URL"):
			continue
		if not frappe.db.exists("DocType", row.link_type):
			continue
		if module := frappe.db.get_value(row.link_type, row.link_to, "module"):
			modules.append(module)

	counts = Counter(modules)
	return counts.most_common(1)[0][0] if counts else None


def pick_primary(module: str, workspaces: list[frappe._dict]) -> frappe._dict:
	"""Return the workspace whose sidebar becomes the module's own.

	A workspace named after the module wins, so `Stock` beats `Stock Reports`. Otherwise the
	biggest sidebar wins, since it holds the module's fullest set of links and pushing it into
	a collapsed section would be the most disruptive result.

	`sequence_id` only breaks ties. As the main signal it picks close to at random, because on a
	real site nearly every workspace shares one: it gives module Accounts to Invoicing(28) over
	Accounting(49), and module Core to Build(14) over System(76).
	"""
	for workspace in workspaces:
		if workspace.name == module:
			return workspace
	return sorted(
		workspaces,
		key=lambda ws: (-len(ws.rows), ws.sequence_id or 0, ws.creation),
	)[0]


def display_title(module: str, primary: frappe._dict, is_merge: bool) -> str:
	"""Return the label the dock shows for this module.

	A module with one source keeps that workspace's title, so existing labels do not change:
	module `Loan Management` still reads "Lending". A module built from several sources uses the
	module name instead, because one source's title would misdescribe the others.
	"""
	return module if is_merge else (primary.title or primary.name)


def merge_items(primary: frappe._dict, secondaries: list[frappe._dict]) -> list[dict]:
	"""Return the primary's items, then each other source under its own collapsed section.

	Duplicates are dropped across the whole merged list using the same `item_key` the desk uses
	when it resolves a sidebar. That removes the duplicate rows the desk already hides and the
	overlap between two workspaces of one module. Sharing the identity means the merge cannot
	produce a row the desk would drop again: two rows pointing at one target are one item,
	whatever the two workspaces called them.
	"""
	merged = []
	seen = set()

	def take(item, force_child=False):
		key = item_key(item)
		if key in seen:
			return
		seen.add(key)
		row = {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS}
		# There is no key to copy: a linked row is identified by the columns copied above, and
		# an unlinked row by its type and label.
		#
		# Only links get nested. A source's own Section Breaks stay top-level, because the desk
		# draws only one level of nesting and a Section Break marked `child` would claim a
		# parent it never gets.
		if force_child and item.get("type") != "Section Break":
			row["child"] = 1
		merged.append(row)

	for item in primary.rows:
		take(item)

	for secondary in secondaries:
		section = {
			"type": "Section Break",
			"label": secondary.title or secondary.name,
			"collapsible": 1,
			"keep_closed": 1,
		}
		merged.append(section)
		seen.add(item_key(section))
		for item in secondary.rows:
			take(item, force_child=True)

	return merged


def build_sidebar(module: str, workspaces: list[frappe._dict]) -> frappe._dict:
	"""Return the sidebar this module's workspaces merge into, as a plain dict."""
	primary = pick_primary(module, workspaces)
	secondaries = [ws for ws in workspaces if ws.name != primary.name]

	return frappe._dict(
		{
			"module": module,
			"title": display_title(module, primary, bool(secondaries)),
			"header_icon": primary.icon,
			# No home link and no onboarding link. The primary's items come first, so the module
			# opens on the first of them. Which onboarding a module offers depends on the user,
			# and `get_permitted_onboardings` answers that when the sidebar is read.
			"app": get_module_placement(module),
			# Never standard, even if the source workspaces were.
			#
			# `standard` means a JSON file in an app backs this row, and orphan cleanup deletes
			# a standard row with no file. A merged sidebar is built from this site's own
			# workspaces and has no file, so marking it standard would get it deleted on the
			# next `bench migrate`. It becomes standard only when an app exports it.
			"standard": 0,
			"merged_from": json.dumps([ws.name for ws in workspaces]),
			"items": merge_items(primary, secondaries),
			"primary": primary.name,
			"secondaries": [ws.name for ws in secondaries],
		}
	)


# ---------------------------------------------------------------------------------------
# What a module holds, which is what a computed sidebar is built from
# ---------------------------------------------------------------------------------------

# The kinds of entity a module can hold, in the order a computed sidebar lists them.
# Workspaces come first, because a module that has one should open there.
MODULE_CONTENT_ENTITIES = ("Workspace", "Dashboard", "DocType", "Report", "Page")

# How many of a module's doctypes a computed sidebar lists.
#
# This is a display limit only. Without it, a module with sixty doctypes would draw sixty
# top-level links.
#
# It must only affect what is drawn, never where a document opens. See the `computed` flag on a
# resolved sidebar for how routing is kept independent of it.
COMPUTED_DOCTYPE_LIMIT = 15

# Where `arrange_contents` records how many doctypes the limit dropped, so `generate_items` can
# say so. Not an entity, so every reader of a contents dict skips it by name.
OVERFLOW_KEY = "_dropped_doctypes"

# The icon a module gets in the dock when it specifies none.
DEFAULT_HEADER_ICON = "hammer"


def get_module_contents(modules: list[str]) -> dict[str, dict[str, list]]:
	"""Return what each of `modules` holds, using five queries for the whole set, one per entity.

	The query count does not grow with the number of modules. One module at a time cost five
	queries each, so a boot building forty sidebars paid two hundred.
	"""
	contents = {module: {entity: [] for entity in MODULE_CONTENT_ENTITIES} for module in modules}

	for entity in MODULE_CONTENT_ENTITIES:
		filters = {"module": ["in", modules]}
		fields = ["name", "module"]

		if entity == "DocType":
			filters["istable"] = 0
		if entity == "Workspace":
			# Public workspaces only. A private page belongs to the user who made it and reaches
			# their sidebar through `get_private_workspaces` instead.
			filters["public"] = 1
			# Read for one row only: the module's own page, whose icon is the module's icon.
			# See `own_page_icon`.
			fields.append("icon")
		if entity == "Page":
			fields.append("title")

		for row in frappe.get_all(entity, filters=filters, fields=fields, order_by="creation asc"):
			if bucket := contents.get(row.module):
				bucket[entity].append(row)

	return {module: arrange_contents(held) for module, held in contents.items()}


def arrange_contents(held: dict[str, list]) -> dict[str, list]:
	"""Return one module's contents, trimmed to the display limit and ordered as the sidebar
	lists them.

	`generate_items` walks this dict in order, so the key order is the sidebar order. A module
	with a workspace leads with it. A module without one leads with its doctypes, which are then
	the first thing to land on.
	"""
	dropped = max(0, len(held["DocType"]) - COMPUTED_DOCTYPE_LIMIT)
	held["DocType"] = held["DocType"][:COMPUTED_DOCTYPE_LIMIT]

	if not held["Workspace"]:
		held = {"DocType": held["DocType"], **held}

	# Carried so the sidebar can say what it left out. A limit that draws fewer doctypes than the
	# module holds is fine; one that does it silently is not, because the reading it invites is
	# that the module does not hold them.
	if dropped:
		held[OVERFLOW_KEY] = dropped

	return held


def generate_items(held: dict[str, list], module: str | None = None) -> list[dict]:
	"""Build sidebar items for one module from what it holds.

	Reports, dashboards and pages go under a collapsible section. Workspaces and doctypes are
	listed flat, since they are what users mostly navigate a module by.

	`module` is only used to recognise the module's own workspace. See the label below.
	"""
	items = []
	sections = {"Report": "Reports", "Dashboard": "Dashboards", "Page": "Pages"}
	icons = {"Report": "table", "Page": "panel-top", "Workspace": "wallpaper"}

	for entity, rows in held.items():
		if entity == OVERFLOW_KEY or not rows:
			continue

		# A single dashboard or page needs no section. A report always gets one, because
		# reports come in numbers and read badly mixed in with everything else.
		sectioned = entity in sections and (entity == "Report" or len(rows) > 1)
		if sectioned:
			items.append({"type": "Section Break", "label": sections[entity], "indent": 1, "collapsible": 1})

		for row in rows:
			item = {
				"type": "Link",
				"link_type": entity,
				"link_to": row.name,
				"label": row.title if entity == "Page" else row.name,
				"icon": icons.get(entity),
			}
			# The module's own workspace is where the module opens, and it is labelled "Home",
			# the same label every shipped `Sidebar` uses (`('Home', 'Workspace', 'Website')`
			# is the first row of the one the website module ships). Labelling it with the
			# module name would repeat the module name: once in the header, once in the list.
			if entity == "Workspace" and module and row.name == module:
				item["label"] = _("Home")
			if entity == "DocType" and "settings" in row.name.lower():
				item["icon"] = "settings"
			# A report always sits under its section. A dashboard or page only does when there
			# were enough of them to get one.
			if entity == "Report" or sectioned:
				item["child"] = 1

			items.append(item)

		# Said once, right after the doctypes it applies to. A computed sidebar draws at most
		# COMPUTED_DOCTYPE_LIMIT of them, and the rest were reachable but unlisted, which reads
		# as the module not holding them.
		#
		# It links to the full list rather than being a dead label, and it is an ordinary
		# `DocType` item, so `is_item_allowed` filters it away for anyone without read access to
		# `DocType`. That is the intended audience: the row is only actionable by someone who
		# can ship the module a `Sidebar` or reorganise it, and it would be noise for everyone
		# else.
		if entity == "DocType" and held.get(OVERFLOW_KEY):
			items.append(
				{
					"type": "Link",
					"link_type": "DocType",
					"link_to": "DocType",
					"label": _("{0} more not shown").format(held[OVERFLOW_KEY]),
					"icon": "more-horizontal",
					"filters": json.dumps([["DocType", "module", "=", module]]) if module else None,
				}
			)

	return items


# ---------------------------------------------------------------------------------------
# Computed sidebars: what a module gets when no app shipped it one
# ---------------------------------------------------------------------------------------

COMPUTED_BASE_CACHE_KEY = "sidebar_computed_base"

# The doctypes a computed sidebar is built from, which is what `get_module_contents` reads.
# Each of them clears this cache from its own `clear_cache`, the way Assignment Rule and
# Milestone Tracker clear theirs. The two lists have to stay in step, or cached sidebars go
# out of date.
#
# The `app` on a base comes from the `Module Def` and needs nothing here: editing one calls
# `frappe.clear_cache()`, which drops every key on the site.
MODULE_CONTENT_DOCTYPES = MODULE_CONTENT_ENTITIES


def get_computed_bases(modules: list[str]) -> dict[str, frappe._dict]:
	"""Return a computed sidebar for each of `modules`, built from what the module holds.

	A sidebar comes from one of two sources: an app shipped it as JSON, or it is computed from
	the module's contents. This is the second.

	It returns plain dicts and inserts nothing, which has two effects. An app that stops
	shipping a sidebar falls back here in the same request instead of leaving its module
	unnavigable until the next migrate, and there is nothing to clean up when a module or app
	goes away.

	The dicts have the same shape as a row read by `get_sidebar_bases`, item rows included, so
	callers cannot tell which source a sidebar came from.

	Results are cached per module, and anything missing from the cache is built in one batch. A
	module's contents change far less often than the desk boots, and a boot building forty
	sidebars should not pay per module.
	"""
	bases = {}
	missing = []
	for module in modules:
		cached = frappe.cache.hget(COMPUTED_BASE_CACHE_KEY, module)
		if cached is None:
			missing.append(module)
		else:
			bases[module] = copy_of(cached)

	if missing:
		contents = get_module_contents(missing)
		for module in missing:
			base = build_computed_base(module, contents[module])
			frappe.cache.hset(COMPUTED_BASE_CACHE_KEY, module, base)
			# `hset` also puts this object into `frappe.local.cache`, so a freshly built base
			# has to be copied on the way out for the same reason a cached one does.
			bases[module] = copy_of(base)

	return bases


def copy_of(base: frappe._dict) -> frappe._dict:
	"""Return the caller its own copy of a cached sidebar.

	`frappe.cache.hget` keeps a copy in `frappe.local.cache` and returns the same object every
	time within a request, so a caller writing to what it got back writes into the cache.
	`get_sidebar_bases` does write to it, stamping `computed` on every sidebar it returns.

	The rows are shared rather than copied, because nothing edits a row in place: the boot path
	builds new dicts from them, and `materialize_base` copies each row before appending it to a
	document.
	"""
	return frappe._dict({**base, "rows": list(base.rows)})


def get_computed_base(module: str) -> frappe._dict:
	"""Return one module's computed sidebar. Use `get_computed_bases` for a whole set."""
	return get_computed_bases([module])[module]


def build_computed_base(module: str, held: dict[str, list]) -> frappe._dict:
	"""Build one module's computed sidebar. This is the value the cache stores."""
	return frappe._dict(
		{
			# No `name`, because there is no document. Callers must not need one.
			"module": module,
			"title": module,
			"app": get_module_placement(module),
			"header_icon": own_page_icon(module, held) or DEFAULT_HEADER_ICON,
			# Called `rows`, not `items`, because `frappe._dict` inherits `dict.items()` and
			# `items` would resolve to the method instead of the list.
			"rows": [frappe._dict(item) for item in generate_items(held, module)],
		}
	)


def own_page_icon(module: str, held: dict[str, list]) -> str | None:
	"""Return the icon of the module's own workspace, which is the module's icon.

	A shipped `Sidebar` states its header icon. A computed one has nowhere to state it, so it
	reads the icon off the page named after the module, the same page `pick_primary` treats as
	the module's own and `generate_items` labels "Home".

	Nothing else on a module carries an icon. A module added on the site gets one this way: the
	icon chosen while adding it is stored on the page it opens on, and this is what puts it on
	the dock. Otherwise the caller falls back to `DEFAULT_HEADER_ICON`.
	"""
	for row in held.get("Workspace", []):
		if row.name == module:
			return row.get("icon")

	return None


def clear_computed_base_cache(module: str) -> None:
	"""Drop one module's cached sidebar. The cache key is in `global_cache_keys`, so
	`bench clear-cache` drops all of them."""
	frappe.cache.hdel(COMPUTED_BASE_CACHE_KEY, module)


def clear_computed_base_for(doc: Document) -> None:
	"""Drop the cached sidebar of every module `doc` has belonged to.

	Called from `clear_cache` on each doctype in `MODULE_CONTENT_DOCTYPES`. The framework runs
	that for both a save (`run_post_save_methods`) and a delete (`delete_doc`), which covers a
	module gaining or losing something. A rename needs no call, because `rename_doc` finishes
	with `frappe.clear_cache()`.

	It clears two modules, not one: moving a document between modules means one lost what the
	other gained, and `doc` only carries its current module.
	"""
	modules = {doc.get("module")}
	if previous := doc.get_doc_before_save():
		modules.add(previous.get("module"))

	for module in modules:
		if module:
			clear_computed_base_cache(module)


# ---------------------------------------------------------------------------------------
# Resolving a sidebar: working out what one module looks like for one person
# ---------------------------------------------------------------------------------------


@dataclass
class SidebarContext:
	"""Everything a resolution reads, fetched once for a whole set of modules.

	`resolve_sidebar` answers for one module at a time, but four of the five things it reads are
	site-wide reads: the user's workspaces, their private pages, the onboardings their roles
	allow, and the customizations that apply to them. Fetching them into a context makes
	resolving seventy modules cost the same few queries as resolving one, and the resolver does
	not have to know it is in a loop.

	A context is built for a specific set of modules and a specific user.

	`bases` is keyed by shell, not by module, because a module may own more than one. Asking
	about a shell the context was not built for raises a `KeyError` instead of returning
	nothing. `layers` stays keyed by module, because a `Custom Sidebar` is anchored to a module,
	so every shell under a module takes that module's customizations.

	`user` is checked, not trusted. Some of what is fetched here belongs to one user, such as
	their private pages and onboardings, so reusing the context for another user would show them
	someone else's private workspaces.
	"""

	user: str
	bases: dict[str, frappe._dict] = field(default_factory=dict)
	workspaces: dict[str, list[str]] = field(default_factory=dict)
	private_rows: dict[str, list[frappe._dict]] = field(default_factory=dict)
	onboardings: dict[str, str] = field(default_factory=dict)
	layers: dict[str, list] = field(default_factory=dict)
	perm_ctx: DeskViews | None = None

	@classmethod
	def for_modules(cls, modules: list[str], user: str) -> "SidebarContext":
		from frappe.desk.doctype.custom_sidebar.custom_sidebar import get_layers_for
		from frappe.desk.doctype.module_onboarding.module_onboarding import get_permitted_onboardings

		return cls(
			user=user,
			bases=get_sidebar_bases(modules),
			workspaces=get_module_workspaces(),
			private_rows=get_private_workspaces(user),
			onboardings=get_permitted_onboardings(),
			# The site's customizations and this user's own, in one query for the whole set.
			# See `get_layers_for` for why this is one read per user rather than one per
			# module.
			layers=get_layers_for(user, modules),
			# `is_item_allowed` is a method on `DeskViews`, so it needs an instance. One
			# throwaway `Workspace` is shared by every permission check below.
			perm_ctx=frappe.new_doc("Workspace"),
		)


@dataclass
class ResolvedSidebar:
	"""One module's sidebar as it looks for one user: a label, an icon, and its items.

	This is the sidebar itself, not the boot payload shape. `as_boot_entry` is one consumer of
	it, and the desk will add others.

	Everything on it is already resolved for this user: the items are filtered by permission,
	customizations are applied, and derived items are added. The label and icon are whatever
	those customizations left.

	`name` and `module` answer different questions. `name` is the shell: what the payload is
	keyed by, what a dock row selects, and what the desk calls the current sidebar. `module` is
	which module it belongs to, which is what a customization is anchored to and what a
	promotional banner reads. They are the same string unless the sidebar was renamed.
	"""

	name: str
	module: str
	label: str
	app: str | None
	header_icon: str | None
	module_onboarding: str | None
	customized: bool
	computed: bool
	workspaces: list[str]
	items: list[dict]

	@cached_property
	def landing(self) -> str | None:
		"""Return where this sidebar opens: the first item that leads anywhere.

		Computed here rather than stored, and computed here rather than by the caller, because
		the only correct list to read it from is the one resolved for this user.

		It is lazy because boot never asks for it. The boot payload carries no landing route,
		and the desktop tiles ask about a handful of modules out of seventy.
		"""
		return get_module_landing_route(self.items)

	def as_boot_entry(self) -> dict:
		"""Return this sidebar in the shape `bootinfo.module_sidebars[shell]` uses.

		The entry carries its own key. The payload is keyed by shell identity, and an entry that
		did not name its shell would force every reader to recover it from the dict position.
		"""
		return {
			"name": self.name,
			"module": self.module,
			"label": self.label,
			"app": self.app,
			"header_icon": self.header_icon,
			"module_onboarding": self.module_onboarding,
			"customized": 1 if self.customized else 0,
			# Whether these items were computed from the module's contents or shipped by an app.
			# The desk reads this when deciding where a document opens. Something missing from a
			# shipped sidebar was left out on purpose; something missing from a computed one may
			# only have fallen past the display limit.
			"computed": 1 if self.computed else 0,
			"workspaces": self.workspaces,
			"items": self.items,
		}


def resolve_sidebar(shell: str, user: str, context: SidebarContext | None = None) -> ResolvedSidebar | None:
	"""Return the `shell` sidebar as it looks for `user`, or `None` if it resolves to nothing.

	This is the only place that resolution happens, so every step runs in one order in one
	function: the permission filter, the customizations, the private pages added at the end, and
	the rule that drops a shell with nothing left to navigate to. Building the boot payload is
	assembly on top of it.

	`shell` is a shell identity, not a module: a `Sidebar` document's name, or a module's name
	where the base is computed (see `get_sidebar_bases`). The two are the same unless the
	sidebar was renamed, so most callers pass what they always passed.

	`context` is only for batching. Pass one when resolving many shells. Without it the shell is
	resolved on its own, through its own module, so a module's other shells come along and the
	answer matches what a batch would give.
	"""
	from frappe.desk.doctype.custom_sidebar.custom_sidebar import merge_layers

	if context is None:
		context = SidebarContext.for_modules([module_of_shell(shell) or shell], user)
	elif context.user != user:
		raise ValueError(f"sidebar context is {context.user}'s, and cannot answer for {user}")

	base = context.bases[shell]
	filtered = filter_sidebar_items(base.rows, context.perm_ctx)

	# Customizations are applied after the permission filter, never before, so a customization
	# cannot bring back an item the user is not allowed to see.
	#
	# Layers are anchored to the module, not the shell, because a `Custom Sidebar` is: every
	# shell under one module takes that module's layers. A site adding a second sidebar under a
	# module inherits that. Re-anchoring would change what a customization names, not how a
	# sidebar resolves.
	layers = context.layers.get(base.module, [])
	if layers:
		filtered = merge_layers(filtered, layers)
		# An added row is the one kind that gets past that check, because it brings an item the
		# base never held, so the filter above never saw it. Checking it here keeps the rule
		# true for rows that bring their own item as well as rows that name an existing one.
		filtered = [item for item in filtered if allowed_added_item(item, context.perm_ctx)]
	else:
		# No layer to fold in, but the base may still hide: an app may ship a row off by
		# default, and a module nobody has customized has to honour that. `merge_layers` gives
		# the same answer for an empty list of layers, at the cost of copying every item of
		# every module on every boot to get there.
		filtered = [item for item in filtered if not item.get("hidden")]

	# The user's private pages are added after that, which keeps them out of every stored
	# customization: a customization can only name what it was shown when it was saved, and
	# these arrive later.
	filtered = append_derived_items(filtered, context.private_rows.get(base.module), context.perm_ctx)

	# A shell needs at least one item this user can open, or it is dropped. Section Breaks do not
	# count, since a header links nowhere; private pages and added rows are already in `filtered`.
	#
	# The lower of two tiers. `User.block_modules` is the upper one, applied upstream in
	# `get_navigable_modules`; it names modules, so this is a fallback for a module-rooted shell
	# and the only gate for an app-rooted one.
	#
	# Accepted cost: a doctype curated into a foreign module makes that module visible to anyone
	# who can read it (#39868). Without the rule an unconfigured site shows every module to
	# everyone, blank.
	#
	# `is_icon_permitted` mirrors this; the two must stay in step.
	if not any(row.get("type") != "Section Break" for row in filtered):
		return None

	label = base.title or shell
	header_icon = base.header_icon
	# The same customizations the merge used, in the same order. Later ones win, so the last
	# layer that sets a label or icon is the one that stands.
	for layer in layers:
		if layer.label:
			label = layer.label
		if layer.header_icon:
			header_icon = layer.header_icon

	return ResolvedSidebar(
		name=shell,
		module=base.module,
		label=_(label),
		# This is the desk's only notion of which app you are in. The rail asks it and then
		# lists that app's other modules, or nothing when there is no answer.
		#
		# A shipped document names its own app and that wins. A document that does not, such as
		# a stub someone created or a custom module's, falls back to the module's placement,
		# which is what a computed sidebar uses.
		app=base.app or get_module_placement(base.module),
		header_icon=header_icon,
		# Computed, never stored: which onboarding this module offers this user, which is the
		# only form of the question the desk asks. `landing` works the same way. Both used to be
		# stored links on the sidebar, and a stored link resolved before the permission filter
		# runs can name something the user cannot open.
		module_onboarding=context.onboardings.get(base.module),
		customized=bool(layers),
		computed=bool(base.get("computed")),
		workspaces=context.workspaces.get(base.module, []),
		items=filtered,
	)


def get_navigable_modules() -> list[str]:
	"""Return the site's modules, minus the ones this user cannot navigate to.

	`get_module_sidebars` walks this list. It starts from every `Module Def` rather than from
	the modules that have a `Sidebar` row, because a module missing from this list can never get
	a sidebar at all.

	Ordered by name. The older row-driven version inherited `get_all`'s default of
	`modified desc`, so the payload reshuffled whenever anyone edited any sidebar. Callers that
	walk the payload in order, such as `build_entity_module_map` and the desk's
	`get_modules_linking`, now get a stable order.
	"""
	from frappe.utils.modules import get_code_only_modules, get_visible_modules

	# Three checks, each answering a different question:
	#
	#   get_visible_modules   per user  - the user blocked the module
	#   get_disabled_modules  per site  - the module's app is turned off, so nobody sees it
	#   get_code_only_modules per app   - the app says this module ships no navigation, having
	#                                     moved its navigation into other modules
	#
	# The code-only check belongs here and not in `is_module_visible`, which guards a module's
	# contents. A code-only module keeps its workspaces, charts and cards reachable; the dock
	# just cannot take you there.
	disabled = get_disabled_modules()
	code_only = get_code_only_modules()
	visible = get_visible_modules(frappe.get_all("Module Def", pluck="name", order_by="name asc"))

	return [module for module in visible if module not in disabled and module not in code_only]


def get_sidebar_bases(modules: list[str]) -> dict[str, frappe._dict]:
	"""Return the starting sidebar for every shell under `modules`, keyed by shell identity.

	A shell is what the desk shows and what a dock row selects. Its identity is the `Sidebar`
	document's name when a document exists, and the module's name when the base was computed.
	A sidebar is named by its title and the title defaults to the module (see
	`set_default_title`), so the two are the same unless the sidebar was renamed.

	The result is keyed by shell rather than by module because a module may own more than one
	shell, and a dict keeps one value per key: keyed by module, a second sidebar under one
	module was overwritten by whichever was read last and disappeared with no error. There is no
	module-to-shell index, because the naming rule already answers that and an index would store
	something derivable.

	A sidebar comes from one of two sources: an app shipped a `Sidebar` document, or it is
	computed from what the module holds. A module with no document gets a computed sidebar in
	the same shape, and callers cannot tell the difference.

	A document with an empty items table borrows the computed rows. An empty sidebar is not
	navigation, and the shell would be dropped from the payload, which is the same as having no
	sidebar. Only the rows are computed: what the document says about itself, such as name,
	title, icon and app, was written by someone and stands. So a stub created to name a module
	keeps its name and gains contents.

	This means emptying a sidebar's items does not hide a module. Hiding is done by
	customizations and by `User.block_modules`, which run later and are per user. An empty
	sidebar means unfinished, not hidden.

	Each sidebar carries `computed`, saying whether its rows were built here or shipped by an
	app. The desk needs that difference: something missing from a shipped sidebar was left out
	on purpose, while something missing from a computed one may have fallen past
	`COMPUTED_DOCTYPE_LIMIT`. Routing reads the flag so a display limit cannot decide where a
	document opens.

	Ordered by module and then by shell name, so callers that walk the result in order, such as
	the boot payload and through it `build_entity_module_map` and the desk's
	`get_modules_linking`, get the same order every request.

	Costs one query for the documents, one for their items, and one batch for the rest, whether
	that is one module or seventy.
	"""
	documents = frappe.get_all(
		"Sidebar",
		filters={"module": ["in", modules]},
		fields=["name", "module", "title", "app", "header_icon"],
		order_by="name asc",
	)

	items_by_sidebar = get_sidebar_items([base.name for base in documents])
	shells = {}
	for base in documents:
		# Called `rows`, not `items`, because `frappe._dict` inherits `dict.items()` and `items`
		# would resolve to the method instead of the list.
		base.rows = items_by_sidebar.get(base.name, [])
		base.computed = 0
		shells.setdefault(base.module, []).append(base)

	# Two cases need rows computed from what a module holds: a module with no shipped sidebar,
	# which gets a whole computed shell, and a document with an empty items table, which keeps
	# its own identity and takes only the rows.
	documented = set(shells)
	needs_computing = [module for module in modules if module not in documented]
	needs_computing += [base.module for bases in shells.values() for base in bases if not base.rows]
	computed = get_computed_bases(sorted(set(needs_computing))) if needs_computing else {}

	resolved = {}
	for module in modules:
		for base in shells.get(module) or [computed[module]]:
			if not base.rows:
				base.rows = computed[module].rows
				base.computed = 1
			# A computed shell is keyed by its module, which is what shell identity means with
			# no document. The key is set here rather than on the base, because `name` means a
			# document exists and a computed base has none.
			resolved[base.get("name") or module] = base

	return resolved


def module_of_shell(shell: str | None) -> str | None:
	"""Return the module a shell belongs to, or `None` when there is no such shell.

	The naming rule does not answer this direction, but the shell stores it: a `Sidebar`
	document names its module in a column, and a computed shell is named after its module. So
	this is a stored read, not a scan, which is why the desk needs no module-to-shell index.

	`Module Def` is checked first because it answers for everything except renamed sidebars, so
	the common case costs one request-cached read and only a renamed shell costs two. The order
	changes no answer: a sidebar named after a module is either that module's own, where both
	branches agree, or refused by `validate_title_is_its_own`.
	"""
	if not shell:
		return None

	if frappe.db.exists("Module Def", shell, cache=True):
		return shell

	# A sidebar rooted at its app carries no module, so it answers `None` here. The boot treats
	# it the same way, since the payload is built by walking modules. A dock row naming a shell
	# is how such a sidebar becomes reachable.
	return frappe.db.get_value("Sidebar", shell, "module", cache=True) or None


def get_module_base(module: str) -> frappe._dict:
	"""Return the base a `Custom Sidebar` layer applies to: the module's own shell.

	A layer is anchored to a module, not a shell, so the editor that reads and writes one needs
	a single base however many shells the module owns. The naming rule picks the shell named
	after the module. If every shell was renamed, the first in order answers, so the editor gets
	a base instead of a `KeyError`.

	This falls back where `get_sidebar` returns `None`, on purpose. `get_sidebar` answers which
	sidebar is the module's, and a module whose sidebars are all renamed has no answer. This
	answers which base the layer being edited sits on, and a customization anchored to a module
	with exactly one shell sits on that shell whatever it is called.

	The unhandled case is a module owning two shells: the layer is one document, so editing from
	the second shell reads the first one's rows. That is a property of `Custom Sidebar`, not of
	this function.
	"""
	bases = get_sidebar_bases([module])
	return bases.get(module) or next(iter(bases.values()))


def sidebar_for_module(payload: dict, module: str) -> dict | None:
	"""Return the boot entry for `module`'s own shell from an already-built payload.

	For callers that hold a module and need the shell it leads to, such as a desktop icon or a
	dock row written before rows named shells. The naming rule answers directly for every
	sidebar that was not renamed. The fallback walks the payload for an entry carrying the
	module, which is a pass over a dict the caller already has instead of an index to maintain.
	"""
	if module in payload:
		return payload[module]

	return next((entry for entry in payload.values() if entry.get("module") == module), None)


def get_sidebar_items(sidebar_names):
	"""Return every `Sidebar Item` row for the given sidebars, grouped by sidebar."""
	if not sidebar_names:
		return {}

	items = {}
	for item in frappe.get_all(
		"Sidebar Item",
		filters={"parenttype": "Sidebar", "parent": ["in", sidebar_names]},
		fields=[
			"parent",
			"idx",
			# `key` is not read on purpose. A base row is identified by the columns below, and
			# a value left in that column by older code must not override them. Rows written
			# before that change still carry one until their app re-imports the sidebar.
			"type",
			"label",
			"link_type",
			"link_to",
			"icon",
			"child",
			"indent",
			"collapsible",
			"keep_closed",
			"url",
			"show_arrow",
			"filters",
			"route_options",
			"navigate_to_tab",
			"open_in_new_tab",
			"is_default_module",
			# Read so the base can hide, which is what the editor's app layer writes. See
			# `filter_sidebar_items`, which is where the value reaches the merge.
			"hidden",
		],
		order_by="idx asc",
	):
		items.setdefault(item.parent, []).append(item)

	return items


def get_module_workspaces():
	"""Return the workspaces of each module this user can see, in `sequence_id` order.

	The test is whether the user can open the workspace, not whether it is public.
	`get_workspaces` already answers that, returning every public workspace they can reach plus
	their own private ones, so this keeps the workspaces in that set.

	Private pages are included, because a private page belongs to a module like any other. The
	desk reads this to work out which module a workspace belongs to when a route names one.
	Answering `None` for a private page used to leave its owner looking at whatever module was
	on screen.

	Replaces `Workspace.get_module_wise_workspaces()`, which ordered by `creation` and did not
	filter by permission.
	"""
	from frappe.desk.desktop import get_workspaces

	workspaces = {}
	allowed = {p.name for p in get_workspaces()["pages"]}

	for row in frappe.get_all(
		"Workspace",
		filters={"module": ["is", "set"]},
		fields=["name", "module"],
		order_by="sequence_id asc, creation asc",
	):
		if row.name in allowed:
			workspaces.setdefault(row.module, []).append(row.name)

	return workspaces


def get_private_workspaces(user: str) -> dict[str, list[frappe._dict]]:
	"""Return `user`'s private workspaces, grouped by module and shaped as sidebar item rows.

	A private page's sidebar link is computed here every time, never stored. Everything a link
	needs is already on the workspace: its module, owner, title and icon. Storing one meant
	keeping a second copy of all four in step with a workspace that could be renamed or deleted.

	The stored row also went into the shared document, so the site-wide sidebar collected a row
	per private page and an admin tidying it up found other users' pages in it.

	These rows are read off the workspace list the payload already builds rather than queried
	again, so they cost a boot nothing. It also means we can only offer a page `get_workspaces`
	says this user may open, narrowed to the pages they own, which is what makes it safe to add
	them after the permission filter has run.

	Pages only, matching the write path this replaces. A Link or URL workspace is a shortcut to
	somewhere the sidebar already lists and never had a way in here.
	"""
	from frappe.desk.desktop import get_workspaces

	rows = {}
	for page in get_workspaces()["pages"]:
		if page.public or not page.module or page.for_user != user:
			continue
		# `type` is empty on pages created before the field existed, and those are all ordinary
		# workspaces.
		if page.type and page.type != "Workspace":
			continue

		rows.setdefault(page.module, []).append(
			frappe._dict(
				{
					"type": "Link",
					"link_type": "Workspace",
					"link_to": page.name,
					"label": page.title,
					"icon": page.icon,
				}
			)
		)

	return rows


def filter_sidebar_items(items, perm_ctx, check_permission: bool = True):
	"""Turn sidebar item rows into boot payload entries, dropping duplicates and anything this
	user cannot see.

	Dropping duplicates used to be a uniqueness check on the document. It lives here because
	this is the only place that can guarantee it: rows arrive from a shipped document, from a
	computed sidebar and from a customization's added rows, so no single writer saw them all.

	Two rows with the same identity are the same item, and a customization cannot say something
	about one and not the other, so the first wins. That is what the desk drew before.

	`check_permission` is off for two callers: the editor reading the site layer, and the editor
	reading the app's own. Permission is a fact about the user, applied to what each user boots,
	so it is not part of what the site or the app arranged. Either editor writes the whole
	arrangement, so a screen with an item filtered out of it would drop that item's row on the
	next save. See `layer_arrangement` and `get_app_sidebar_layer`.
	"""
	filtered = []
	seen = set()
	for item in items:
		key = item_key(item)
		if key in seen:
			continue
		seen.add(key)

		# Check permission first, so nothing below runs for an item about to be dropped. This
		# walks every module on every boot, so an item the user cannot see should cost no
		# queries.
		if (
			check_permission
			and item.type != "Section Break"
			and not is_item_allowed(item.link_to, item.link_type, perm_ctx)
		):
			continue

		entry = {
			"key": key,
			"label": _(item.label),
			"link_to": item.link_to,
			"link_type": item.link_type,
			"type": item.type,
			"icon": item.icon,
			"child": item.child,
			"collapsible": item.collapsible,
			"indent": item.indent,
			"keep_closed": item.keep_closed,
			"url": item.url,
			"show_arrow": item.show_arrow,
			"filters": item.filters,
			"route_options": item.route_options,
			"tab": item.navigate_to_tab,
			"open_in_new_tab": item.open_in_new_tab,
			"is_default_module": item.is_default_module,
		}
		# Carried only when set, which is almost never. This runs for every item of every
		# module on every boot, and a key on each one saying "not hidden" is bytes on the
		# largest thing in the bootinfo. `resolve_layers` seeds the hidden map with `.get`, so
		# an absent key and a false one say the same thing to the merge.
		if item.hidden:
			entry["hidden"] = 1

		# One cached read instead of three uncached ones. A missing report and a disabled report
		# both end up with no `report` block, so neither needs its own check. `cache=True` stops
		# the same report on ten sidebars costing ten round trips.
		if item.link_type == "Report" and item.link_to:
			report = frappe.db.get_value(
				"Report",
				item.link_to,
				["report_type", "ref_doctype", "disabled"],
				as_dict=True,
				cache=True,
			)
			if report and not report.disabled:
				entry["report"] = {
					"report_type": report.report_type,
					"ref_doctype": report.ref_doctype,
				}

		filtered.append(entry)

	return filtered


def allowed_added_item(item: dict, perm_ctx) -> bool:
	"""Return whether an item a layer added is one this user may see.

	Only added items are checked. Everything else went through `filter_sidebar_items` already,
	and checking twice would cost a permission check per item per module on every boot.

	A row that links nowhere, such as a Section Break or a spacer, is never blocked, the same
	exception the filter makes. The check uses `is_linked`, the same test that decides a row's
	identity, rather than testing for a link type: `Sidebar Item.link_type` has a column
	default, so a section added by a layer arrives claiming to be a DocType link to nothing, and
	only Administrator may see a DocType called None.
	"""
	if not item.get("added") or not is_linked(item):
		return True

	return is_item_allowed(item.get("link_to"), item.get("link_type"), perm_ctx)


def append_derived_items(items, rows, perm_ctx):
	"""Add `rows` to an already-resolved sidebar, skipping anything it already has.

	These items go through the same shaping and permission check as any other row. Once in the
	payload they behave like any other item; the only difference is that no document holds them.

	The skip keeps a site that stored these rows before they were computed from drawing two
	links. The stored row is already in `items`, wherever its customization put it, and the
	computed one is the duplicate.
	"""
	if not rows:
		return items

	seen = {item["key"] for item in items}
	for entry in filter_sidebar_items(rows, perm_ctx):
		if entry["key"] in seen:
			continue
		seen.add(entry["key"])
		# Tells the desk this item cannot be rearranged or hidden. No document holds it, so no
		# customization can name it. The desk shows it as a link only.
		entry["derived"] = 1
		items.append(entry)

	return items


def get_module_landing_route(items: list[dict]) -> str | None:
	"""Return where a module's desktop tile leads, as far as the server can work it out.

	The rule matches the desk's own (`sidebar.module_landing_route`): a module opens on the
	first item in the sidebar that links anywhere. So this takes the resolved items, already
	filtered by permission and customized, not the module's workspaces, which are neither.

	Workspaces and doctypes get an answer. A module whose sidebar opens on a list rather than a
	workspace is ordinary -- `Bulk Transaction` has no workspace at all -- and answering `None`
	for it left its tile with nowhere to go. Reports, pages and filtered views are still left to
	`frappe.utils.generate_route` on the client, which knows about report types, doc views and
	filters as query parameters. The desktop asks the client first and falls back to this, so
	this is the answer a tile has before the sidebar object exists, not a second copy of the
	routing rules.

	It stops at the first item that links anywhere instead of reading on for one it could answer
	for. A tile is a link with a click handler and the two must agree: a route found further
	down the sidebar would send a middle-click somewhere a normal click never goes.
	"""
	item = next((item for item in items or [] if item.get("type") == "Link"), None)
	if not item or not item.get("link_to"):
		return None

	if item.get("link_type") == "Workspace":
		public = frappe.db.get_value("Workspace", item["link_to"], "public")
		if public is None:
			return None

		prefix = "/desk/" if public else "/desk/private/"
		return prefix + frappe.utils.slug(item["link_to"])

	if item.get("link_type") == "DocType":
		return doctype_landing_route(item)

	return None


def doctype_landing_route(item: dict) -> str | None:
	"""Where a sidebar item pointing at a doctype opens, matching the client's `generate_route`.

	A single opens on the document itself, since there is no list to show, and a `tab` is a
	fragment on the end. Anything the client would decorate further -- a filtered list, a
	non-default view -- is left to it, because a tile that led somewhere the sidebar item does
	not would be worse than a tile that falls back.
	"""
	meta = frappe.get_meta(item["link_to"]) if frappe.db.exists("DocType", item["link_to"]) else None
	if not meta or meta.istable:
		return None

	slug = frappe.utils.slug(item["link_to"])
	route = f"/desk/{slug}/{item['link_to']}" if meta.issingle else f"/desk/{slug}"
	if item.get("tab"):
		route += f"#{item['tab']}"

	return route
