# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import hashlib
import json
from collections import defaultdict

import click

import frappe
from frappe import _
from frappe.desk.desk_views import DeskViews
from frappe.model.document import Document
from frappe.utils.modules import get_module_placement

# Fields copied verbatim from a source item row into a `Module Sidebar Item`.
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
	# Carried deliberately: `build_default_workspace_map` and the desk's cold-entry resolution
	# both read it, and the legacy merge path silently dropped it.
	"default_workspace",
)

# A linked row's identity *is* these columns, matched directly rather than hashed into one.
# That is what makes a customization survive a rename: `link_to` is a Dynamic Link, so
# `rename_dynamic_links` rewrites every `Module Sidebar Item` naming the renamed document in a
# single statement -- base rows and customization rows together, whichever parent they hang
# off -- with no hook, no patch and no re-keying. A hash column cannot be repaired that way.
LINKED_IDENTITY_FIELDS = ("type", "link_type", "link_to", "url")

# The merge reads from `Workspace.sidebar_items` and writes to `Module Sidebar.items`, and the
# two use different child doctypes: the legacy `Workspace Sidebar Item` is left untouched until
# the old store is retired, while `Module Sidebar Item` is the new one carrying `key` and
# `source_workspace`. Rows are copied field by field between them, never re-parented.
WORKSPACE_ITEM_DOCTYPE = "Workspace Sidebar Item"

# Writes that are the system placing app content on a site rather than a person authoring it.
# A `Module Sidebar` lives in an app's JSON and reaches a site by one of these routes, so each
# has to keep working with developer mode off -- otherwise installing or updating an app that
# ships a sidebar would fail on every customer site.
SYSTEM_WRITE_FLAGS = ("in_import", "in_fixtures", "in_migrate", "in_install", "in_patch")


class ModuleSidebar(Document, DeskViews):
	_DOCTYPE_NAME = "Module Sidebar"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.module_sidebar_item.module_sidebar_item import ModuleSidebarItem
		from frappe.types import DF

		app: DF.Autocomplete | None
		header_icon: DF.Icon | None
		items: DF.Table[ModuleSidebarItem]
		merged_from: DF.LongText | None
		module: DF.Link
		standard: DF.Check
		title: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self.validate_app_content()

		if not self.title:
			self.title = self.module

		self.validate_standard()
		self.clear_stored_keys()

	def clear_stored_keys(self):
		"""A base row's identity is derived from its own columns, so it stores no `key`.

		The column is only ever meaningful on a `Custom Module Sidebar` row, where a reference
		to a Section Break has nothing else to name it by. Left on a base row it would be a
		second, staler answer to the same question -- and rows shipped before the derivation
		changed still carry one, so this is what retires them: every import runs `validate`, so
		an app's next update takes the dead values out with it.
		"""
		for item in self.items:
			item.key = None

	def validate_app_content(self):
		"""A `Module Sidebar` is app content, and only developer mode authors app content.

		The invariant this buys is what makes app updates safe: *on a non-developer-mode site
		every sidebar document arrived by import*, so an app overwriting its own sidebar costs
		the site nothing. A site that wants a different sidebar says so where site intent
		already lives -- `Custom Module Sidebar`, at the site-wide layer or the user's own --
		and that path is untouched by this gate.

		Developer mode is the whole gate; there is no role check, so any developer on a
		developer-mode site may author one. Who may reach the doctype at all is the doctype's
		own permissions, where `Desk User` holds `read` and nothing more.

		Deleting is deliberately not gated here: removing a document cannot put site intent
		into app content, and the paths that delete one -- a module going away, orphan removal
		-- have to keep working on a customer site.
		"""
		if frappe.conf.developer_mode:
			return

		if any(frappe.flags.get(flag) for flag in SYSTEM_WRITE_FLAGS):
			return

		frappe.throw(
			_(
				"{0} belongs to its app and can only be edited in developer mode. "
				"Customize the sidebar instead to change it for this site."
			).format(frappe.bold(self.module or self.name)),
			title=_("Not Editable"),
		)

	def validate_standard(self):
		"""`standard` means "backed by a JSON file in an app", and only developer mode writes
		one. Marking a sidebar standard without being able to export it produces a row that
		`remove_orphan_entities` deletes on the very next `bench migrate` -- a standard record
		whose file is missing is by definition an orphan. Refuse rather than let someone create
		a row that quietly destroys itself.
		"""
		if not self.standard or not self.has_value_changed("standard"):
			return

		check_developer_mode()

		if not self.module:
			frappe.throw(_("A standard sidebar needs a module to be written to."))

		try:
			frappe.get_module_path(self.module)
		except Exception:
			frappe.throw(
				_(
					"Module {0} has no folder in an app, so a standard sidebar cannot be written to it."
				).format(frappe.bold(self.module))
			)

	# No uniqueness validator. Identity is now the row's own columns, so two rows that share
	# one *are* the same item -- something a document may honestly contain (two workspaces of
	# a module listing the same report) and which nothing downstream has to be protected from:
	# the resolution keeps the first of them and drops the rest. Refusing the save instead
	# would reject app content that renders fine.

	def on_update(self):
		self.export_sidebar()

	def export_sidebar(self):
		"""Export to `<app>/<module>/module_sidebar/<name>/<name>.json`.

		A module-level path, unlike the legacy app-level one. That matters: orphan removal
		derives a record's file path as `<...>/<scrub(name)>.json`, so an app-level flat
		folder whose filenames don't match the record names deletes rows on the next migrate.
		Here filename and record name agree by construction.
		"""
		from frappe.modules.export_file import export_to_files

		allow_export = (
			self.standard and self.module and not frappe.flags.in_import and frappe.conf.developer_mode
		)
		if allow_export:
			export_to_files(record_list=[["Module Sidebar", self.name]], record_module=self.module)

	def exported_file_path(self) -> str:
		"""Where `export_to_files` writes this sidebar. Mirrors `check_if_record_exists`, which
		is what orphan removal uses to decide whether a standard record still has a file."""
		import os

		scrubbed = frappe.scrub(self.name)
		return os.path.join(
			frappe.get_module_path(self.module), "module_sidebar", scrubbed, f"{scrubbed}.json"
		)

	def is_exported(self) -> bool:
		"""Whether the file backing this sidebar is actually there.

		This is the question orphan removal asks, so it is the one `mark_as_standard` has to
		answer before claiming the sidebar is shipped. A module that resolves to no folder at
		all answers it the same way: no folder, no file.
		"""
		import os

		if self.is_new() or not self.module:
			return False

		try:
			return os.path.exists(self.exported_file_path())
		except Exception:
			return False


# ---------------------------------------------------------------------------------------
# The export switch -- what `standard` means, and the two actions that flip it
# ---------------------------------------------------------------------------------------


@frappe.whitelist()
def mark_as_standard(module: str) -> str:
	"""Adopt `module`'s sidebar as app content: write it into the module's folder so the app
	ships it, and let `bench migrate` re-import it from there. Returns the document's name.

	Materialize *then* export, which is what lets an author start from what the system
	generated rather than from nothing: a module with no document has a base all the same --
	computed from its contents by `get_computed_base` -- and that is what gets written. A
	document with items of its own is shipped as it stands; see `materialize_base` for where
	the line falls.

	Developer mode is the gate and there is no role check. The old `Workspace Manager` one is
	gone: what makes this write legitimate is that the site is a developer's, and who may
	reach the doctype at all is the doctype's own permissions (see `validate_app_content`).

	Verified rather than assumed, and rolled back if it cannot be: a standard row whose file
	is missing is by definition an orphan, and `remove_orphan_entities` deletes it on the very
	next `bench migrate`. A mark that wrote no file therefore has to leave no row either.
	"""
	check_developer_mode()

	doc = materialize_base(module)

	# Already shipped, so there is nothing to do. Standard *and exported*, though: a standard
	# row whose file has gone missing is the orphan this action exists to prevent, and it gets
	# written again rather than reported as done.
	if doc.standard and doc.is_exported():
		return doc.name

	savepoint = "mark_module_sidebar_standard"
	frappe.db.savepoint(savepoint)
	try:
		doc.standard = 1
		doc.app = get_module_placement(module)
		# `save` inserts a materialized base and updates an existing document; either way
		# `on_update` is what writes the file.
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
def unmark_as_standard(module: str) -> None:
	"""Hand `module`'s sidebar back to the site: remove its exported file and delete the
	document.

	The document goes rather than the flag being cleared. What is left when app content goes
	away is the *computed* base, produced from the module's contents on read -- so the module
	is back to its base in this same request. Clearing the flag would instead leave a row
	nobody owns: not app content (no file), not site intent (that lives in
	`Custom Module Sidebar`), and a frozen copy of a base that has stopped tracking the module.

	The file has to go with it. Left behind, the next `bench migrate` re-imports it and the
	row comes back standard, so deleting the document alone would not survive a migrate.
	"""
	import os
	import shutil

	check_developer_mode()

	doc = get_sidebar(module)
	# Only a standard sidebar is app content; there is nothing to hand back otherwise, and a
	# document somebody is still authoring is not this action's to delete.
	if not doc or not doc.standard:
		return

	path = doc.exported_file_path() if doc.is_exported() else None
	doc.delete()

	# Now, not on commit: un-marking and marking again within one request has to end with the
	# file the second call wrote, not with a queued delete that removes it afterwards.
	if path:
		shutil.rmtree(os.path.dirname(path), ignore_errors=True)

	frappe.msgprint(
		_("{0} is no longer standard; its exported file has been removed.").format(frappe.bold(doc.name)),
		alert=True,
		indicator="orange",
	)


def check_developer_mode() -> None:
	"""`standard` means a file inside an app, and only a developer's site writes app files."""
	if frappe.conf.developer_mode:
		return

	frappe.throw(
		_(
			"Enable developer mode to change whether a sidebar is standard -- it is backed by a file in its app."
		),
		title=_("Not Editable"),
	)


def get_sidebar(module: str) -> "ModuleSidebar | None":
	"""`module`'s sidebar document, or `None` -- which is the ordinary state, since nothing
	persists a base on a module's behalf."""
	name = frappe.db.get_value("Module Sidebar", {"module": module})
	return frappe.get_doc("Module Sidebar", name) if name else None


def materialize_base(module: str) -> "ModuleSidebar":
	"""The module's base as a document ready to be exported -- the one place a base crosses
	from computed to shipped.

	A document with items of its own is authored content and is returned as it stands. Anything
	else -- no document, or one with an empty items table -- is filled from the computed base,
	because that is exactly what the desk renders for it (see `boot.get_sidebar_bases`) and
	shipping it empty would ship a file that does not match the navigation it came from.

	The base carries over verbatim, which is all it takes to keep existing customization deltas
	anchored: a row's identity is the columns being copied, so a user who hid an item keeps it
	hidden through the adoption without anything being re-keyed.
	"""
	doc = get_sidebar(module)
	if doc and doc.items:
		return doc

	base = get_computed_base(module)
	if not doc:
		doc = frappe.new_doc("Module Sidebar")
		doc.module = module
		doc.title = base.title
		doc.header_icon = base.header_icon

	for row in base.rows:
		# a copy: `append` writes doctype and parent keys into the dict it is handed, and these
		# rows belong to the cached base
		doc.append("items", dict(row))
	return doc


def is_linked(item) -> bool:
	"""Whether this row points somewhere. A Section Break or a spacer does not."""
	return bool(item.get("link_to") or item.get("url"))


def item_key(item) -> str:
	"""Identity of a sidebar item -- what a customization row names when it names this item.

	Two shapes, because the two kinds of row have different identities available to them:

	- a **linked** row is identified by the columns it already carries. Nothing is stored, so
	  there is no second copy to keep in step with them and nothing for a rename to orphan;
	  see `LINKED_IDENTITY_FIELDS` for why matching them directly is the whole point.
	- an **unlinked** row (Section Break, spacer) points nowhere, so it is identified by a hash
	  of its type and its label. The label is safe to include: computed section labels are code
	  constants, at most three per module and all distinct.

	Only a *customization* row stores that hash, because a reference to a Section Break has
	nothing else to name it by and its own label is a field the reference may override. A base
	row derives it and stores nothing -- `ModuleSidebar.clear_stored_keys` keeps that true, and
	boot does not even read the column. So a stored key that reaches here is always the
	customization's, never a leftover of an older derivation.

	Pure, and derived from columns the rows already carry, so re-importing the same JSON
	produces the same identities even though standard child rows are hash-named and recreated
	on every import -- which is why a delta can never anchor on a row's `name`.
	"""
	if is_linked(item):
		return "|".join(item.get(field) or "" for field in LINKED_IDENTITY_FIELDS)

	return item.get("key") or unlinked_key(item)


def unlinked_key(item) -> str:
	"""The key an unlinked row gets when nothing stored one for it.

	No ordinal. The one the old derivation carried existed to separate rows that collided
	because `label` was excluded; including the label is what removes the collision, and the
	ordinal with it -- an ordinal re-anchored every delta after any insertion.
	"""
	identity = f"{item.get('type') or ''}|{item.get('label') or ''}"
	return hashlib.sha1(identity.encode()).hexdigest()[:10]


def get_module_sidebar_sources() -> dict[str, list[frappe._dict]]:
	"""Public workspaces carrying authored sidebar items, grouped by module.

	`Workspace.sidebar_items` is the single source: it is what boot reads, so it is what the
	merge must consume. The legacy `Workspace Sidebar` table is not read here -- boot stopped
	reading it, and the app-level JSONs behind it have diverged from the live rows.
	"""
	parents = frappe.get_all(
		WORKSPACE_ITEM_DOCTYPE,
		filters={"parenttype": "Workspace", "parentfield": "sidebar_items"},
		pluck="parent",
		distinct=True,
	)
	if not parents:
		return {}

	workspaces = frappe.get_all(
		"Workspace",
		filters={"name": ["in", parents], "public": 1},
		fields=[
			"name",
			"module",
			"title",
			"icon",
			"sequence_id",
			"creation",
			"standard",
		],
		order_by="sequence_id asc, creation asc",
	)

	by_module = defaultdict(list)
	for workspace in workspaces:
		if not workspace.module:
			continue
		# not `items`: `frappe._dict` inherits `dict.items()`, so that attribute is the method
		workspace.rows = get_workspace_items(workspace.name)
		by_module[workspace.module].append(workspace)
	return by_module


def get_workspace_items(workspace: str) -> list[frappe._dict]:
	return frappe.get_all(
		WORKSPACE_ITEM_DOCTYPE,
		filters={"parenttype": "Workspace", "parentfield": "sidebar_items", "parent": workspace},
		# no `key`: only `Module Sidebar Item` carries one. A pin can therefore only come from
		# an app-shipped Module Sidebar JSON, never from a legacy workspace row.
		fields=["name", "idx", *SIDEBAR_ITEM_FIELDS],
		order_by="idx asc",
	)


def pick_primary(module: str, workspaces: list[frappe._dict]) -> frappe._dict:
	"""The workspace whose sidebar becomes the module's.

	Name-matches-module first, so `Stock` wins over `Stock Reports`. Otherwise the largest
	sidebar: it is the module's fullest navigation surface, and demoting it into a collapsed
	section is the most disruptive outcome available.

	`sequence_id` is only a tie-break. As the primary signal it is near-uniform on a real
	site and picks arbitrarily -- it hands module Accounts to Invoicing(28) over
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
	"""What the dock reads for this module.

	An unmerged module keeps its workspace's title, so today's labels survive verbatim
	(`Loan Management` still reads "Lending"). A merged module takes the module name: the
	union of four sidebars is not "Accounting" or "Build", and labelling it with one source's
	title misdescribes the rest.
	"""
	return module if is_merge else (primary.title or primary.name)


def merge_items(primary: frappe._dict, secondaries: list[frappe._dict]) -> list[dict]:
	"""Primary's items, then each secondary under a collapsed Section Break of its own.

	Deduped on `item_key` across the whole merged list, which drops both the duplicate rows the
	desk already hides and the genuine overlap between two workspaces of one module. The same
	identity the resolution uses, so the merge cannot produce a row the desk would then drop:
	two rows pointing at one target are one item, whatever the two workspaces called it.
	"""
	merged = []
	seen = set()

	def take(item, source: str, force_child=False):
		key = item_key(item)
		if key in seen:
			return
		seen.add(key)
		row = {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS}
		row["source_workspace"] = source
		# Nothing to carry across for identity: a linked row's is the columns just copied, and
		# an unlinked one's falls out of its type and label. There is no key to re-derive.
		#
		# Only links nest. A secondary's own Section Breaks stay top-level sections: the desk
		# renders one level of nesting, so a Section Break marked `child` is an item that
		# claims a parent the renderer never gives it.
		if force_child and item.get("type") != "Section Break":
			row["child"] = 1
		merged.append(row)

	for item in primary.rows:
		take(item, primary.name)

	for secondary in secondaries:
		section = {
			"type": "Section Break",
			"label": secondary.title or secondary.name,
			"collapsible": 1,
			"keep_closed": 1,
			"source_workspace": secondary.name,
		}
		merged.append(section)
		seen.add(item_key(section))
		for item in secondary.rows:
			take(item, secondary.name, force_child=True)

	return merged


def build_module_sidebar(module: str, workspaces: list[frappe._dict]) -> frappe._dict:
	"""The Module Sidebar this module's workspaces merge into, as a plain dict."""
	primary = pick_primary(module, workspaces)
	secondaries = [ws for ws in workspaces if ws.name != primary.name]

	return frappe._dict(
		{
			"module": module,
			"title": display_title(module, primary, bool(secondaries)),
			"header_icon": primary.icon,
			# No home pointer and no onboarding pointer: the merge carries the primary's items
			# first, and the module opens on the first of them. Which onboarding a module offers
			# is a question about the reader, answered on read by `get_permitted_onboardings`.
			"app": get_module_placement(module),
			# Deliberately NOT standard, however standard the source workspaces were.
			# `standard` means "backed by a JSON file in an app", and that is what orphan
			# removal deletes on: a standard row with no file is an orphan. A merged sidebar
			# is derived from *this site's* workspaces and has no file, so marking it standard
			# gets it deleted by the very next `bench migrate`. It becomes standard only when
			# an app deliberately exports it.
			"standard": 0,
			"merged_from": json.dumps([ws.name for ws in workspaces]),
			"items": merge_items(primary, secondaries),
			"primary": primary.name,
			"secondaries": [ws.name for ws in secondaries],
		}
	)


# ---------------------------------------------------------------------------------------
# A module's own contents, which is what a computed base is built out of
# ---------------------------------------------------------------------------------------

# How many of a module's doctypes a computed base lists. More than the three the old
# in-memory fallback showed, since this is the module's whole navigation rather than a
# stopgap; per-user hide deltas trim it from there.
COMPUTED_DOCTYPE_LIMIT = 15

# The icon a module that has said nothing about itself gets in the dock.
DEFAULT_HEADER_ICON = "hammer"


def get_module_info(module_name: str) -> dict:
	entities = ["Workspace", "Dashboard", "DocType", "Report", "Page"]
	module_info = {}

	for entity in entities:
		filters = [{"module": module_name}]
		pluck = "name"
		fieldnames = ["name"]
		if entity == "DocType":
			filters.append({"istable": 0})
		if entity == "Workspace":
			# only surface public workspaces; private ones belong to individual users
			filters.append({"public": 1})
		if entity == "Page":
			fieldnames.append("title")
			pluck = None
		module_info[entity] = frappe.get_all(
			entity, filters=filters, fields=fieldnames, pluck=pluck, order_by="creation asc"
		)

	# with no workspace to lead with, the doctypes are the module's landing content
	if not module_info.get("Workspace"):
		module_info = {
			"DocType": module_info.get("DocType"),
			"Workspace": module_info.get("Workspace"),
			"Report": module_info.get("Report"),
			"Dashboard": module_info.get("Dashboard"),
			"Page": module_info.get("Page"),
		}

	module_info["DocType"] = (module_info.get("DocType") or [])[:COMPUTED_DOCTYPE_LIMIT]
	return module_info


def generate_items(module_name: str) -> list[dict]:
	"""Sidebar items built from what the module actually contains."""
	module_info = get_module_info(module_name)
	items = []
	section_entities = {"Report": "Reports", "Dashboard": "Dashboards", "Page": "Pages"}

	for entity, entries in module_info.items():
		entries = entries or []
		sectioned = False

		if entity in section_entities and entries:
			if entity == "Report" or len(entries) > 1:
				items.append(
					{
						"type": "Section Break",
						"label": section_entities[entity],
						"collapsible": 1,
					}
				)
				sectioned = entity != "Report"

		for entry in entries:
			item = {
				"type": "Link",
				"link_type": entity,
				"label": entry,
				"link_to": entry,
			}

			if entity == "Report":
				item["child"] = 1
				item["icon"] = "table"
			elif entity == "Page":
				item["label"] = entry.get("title")
				item["link_to"] = entry.get("name")
				item["icon"] = "panel-top"
			elif entity == "Workspace":
				item["icon"] = "wallpaper"
			elif entity == "DocType" and "settings" in entry.lower():
				item["icon"] = "settings"

			if sectioned:
				item["child"] = 1

			items.append(item)

	return items


# ---------------------------------------------------------------------------------------
# Computed bases -- the base a module gets when no app shipped one
# ---------------------------------------------------------------------------------------

COMPUTED_BASE_CACHE_KEY = "module_sidebar_computed_base"

# Exactly what `get_module_info` reads, which is what a computed base's *items* are a
# function of. Each of these clears this cache from its own `clear_cache`, the way
# Assignment Rule and Milestone Tracker clear theirs; the two lists have to stay in step or
# bases go quietly stale. The base's `app` comes from the `Module Def` instead, and needs
# nothing: editing one calls `frappe.clear_cache()`, which drops every key this site holds.
MODULE_CONTENT_DOCTYPES = ("DocType", "Report", "Page", "Workspace", "Dashboard")


def get_computed_base(module: str) -> frappe._dict:
	"""The base `module` gets when no app shipped it one, built from the module's contents.

	Per D4 a base has exactly two origins -- an app shipped it as JSON, or the system computed
	it -- and only the shipped route persists a document. This is the other route, and it
	deliberately returns a plain dict rather than inserting a row: with nothing persisted there
	is nothing to orphan when a module or an app goes away, and an app that *stops* shipping a
	sidebar falls back here in the same request instead of leaving its module un-navigable
	until the next migrate.

	Shaped exactly like a row read by `boot.get_sidebar_bases`, item rows included, so the
	resolution cannot tell which route a base arrived by.

	Site-cached, because it is a handful of queries per module and the contents change far
	less often than the desk boots. See `on_module_content_changed` for what busts it.
	"""
	return frappe.cache.hget(COMPUTED_BASE_CACHE_KEY, module, generator=lambda: build_computed_base(module))


def build_computed_base(module: str) -> frappe._dict:
	"""`get_computed_base` without the cache -- the thing being cached."""
	items = [frappe._dict(item) for item in generate_items(module)]

	return frappe._dict(
		{
			# no `name`: there is no document. Whatever reads this must not need one.
			"module": module,
			"title": module,
			"app": get_module_placement(module),
			"header_icon": DEFAULT_HEADER_ICON,
			# not `items`: `frappe._dict` inherits `dict.items()`, so that attribute is the method
			"rows": items,
		}
	)


def clear_computed_base_cache(module: str) -> None:
	"""Drop one module's cached base. The whole hash is in `global_cache_keys`."""
	frappe.cache.hdel(COMPUTED_BASE_CACHE_KEY, module)


def clear_computed_base_for(doc: Document) -> None:
	"""Bust the computed base of every module `doc` has belonged to.

	Called from the `clear_cache` of each doctype in `MODULE_CONTENT_DOCTYPES`, which is the
	one place the framework already runs on both halves of "gains or loses": a save
	(`run_post_save_methods`) and a delete (`delete_doc`) both land here. A rename needs no
	call at all -- `rename_doc` ends in `frappe.clear_cache()`, which drops every key this
	site holds.

	Two modules, not one: moving a document between them means one lost what the other
	gained, and only the document's *current* module is on `doc`.
	"""
	modules = {doc.get("module")}
	if previous := doc.get_doc_before_save():
		modules.add(previous.get("module"))

	for module in modules:
		if module:
			clear_computed_base_cache(module)


# ---------------------------------------------------------------------------------------
# Build entry point -- shared by the patch, migrate, and the dry run
# ---------------------------------------------------------------------------------------


def build_all(dry_run: bool = False) -> dict:
	"""Merge every module's authored sidebars into one `Module Sidebar` each.

	Only a module that authored something gets a row. The rest are named under `computed` and
	left alone: their base is built from their contents on every read, so a row here would be a
	frozen copy of it -- and one more thing to clean up when the module goes away.

	`dry_run=True` reports exactly what a real run would produce and writes nothing -- run it
	before migrating a site whose sidebars matter, since the merge result depends entirely on
	that site's data rather than on what the apps ship.
	"""
	by_module = get_module_sidebar_sources()
	existing = set(frappe.get_all("Module Sidebar", pluck="module"))

	merged, skipped = [], []
	for module in sorted(by_module):
		if module in existing:
			skipped.append(module)
			continue

		plan = build_module_sidebar(module, by_module[module])
		merged.append(plan)

		if dry_run:
			continue

		doc = frappe.new_doc("Module Sidebar")
		doc.update(
			{
				field: plan[field]
				for field in (
					"module",
					"title",
					"header_icon",
					"app",
					"standard",
					"merged_from",
				)
			}
		)
		for item in plan["items"]:
			doc.append("items", item)
		doc.insert(ignore_permissions=True)

	covered = existing | set(by_module)
	computed = [m for m in frappe.get_all("Module Def", pluck="name") if m not in covered]

	return {"merged": merged, "computed": computed, "skipped": skipped}


def report():
	"""Print what `build_all` would do, without writing. See the module docstring on dry runs.

	bench --site <site> execute frappe.desk.doctype.module_sidebar.module_sidebar.report
	"""
	result = build_all(dry_run=True)

	click.secho("\n=== Module Sidebar build (dry run) ===\n", bold=True)

	for plan in result["merged"]:
		is_merge = bool(plan["secondaries"])
		colour = "yellow" if is_merge else None
		sources = json.loads(plan["merged_from"])
		click.secho(f"  {plan['module']:24} {len(sources)} -> 1   items: {len(plan['items'])}", fg=colour)
		click.secho(f"  {'':24} primary: {plan['primary']}   displays as: {plan['title']}", fg=colour)
		if is_merge:
			click.secho(f"  {'':24} sections: {', '.join(plan['secondaries'])}", fg=colour)

	click.secho(f"\nComputed (module ships no sidebar, no row written): {len(result['computed'])}", bold=True)
	click.echo("  " + ", ".join(result["computed"][:20]) + (" ..." if len(result["computed"]) > 20 else ""))

	if result["skipped"]:
		click.secho(f"\nSkipped (row already exists): {len(result['skipped'])}", fg="cyan")

	merges = [p for p in result["merged"] if p["secondaries"]]
	click.secho("\n=== Summary ===", bold=True)
	click.echo(f"  modules with authored sidebars : {len(result['merged'])}")
	click.secho(f"  modules that MERGE (>1 source)  : {len(merges)}", fg="yellow" if merges else None)
	for plan in merges:
		click.secho(
			f"      {plan['module']}: {plan['primary']} <- {', '.join(plan['secondaries'])}", fg="yellow"
		)
	click.echo(f"  modules left to a computed base : {len(result['computed'])}")
	click.echo("")
