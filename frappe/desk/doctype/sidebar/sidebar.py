# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

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
from frappe.utils.modules import get_module_placement

# Fields copied verbatim from a source item row into a `Sidebar Item`.
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

# `Workspace Sidebar Item.default_workspace` is deliberately NOT in that list: the fixture
# conversion drops the claim flag rather than carrying it across as `is_default_module`.
#
# A claim is an app's opinion, and the app has to be able to retract it. An app that wants the
# claim states it the same way every other app does -- by flagging the row in the `sidebar`
# fixture it ships, which is a file it can edit again tomorrow.

# A linked row's identity *is* these columns, matched directly rather than hashed into one.
# That is what makes a customization survive a rename: `link_to` is a Dynamic Link, so
# `rename_dynamic_links` rewrites every `Sidebar Item` naming the renamed document in a
# single statement -- base rows and customization rows together, whichever parent they hang
# off -- with no hook, no patch and no re-keying. A hash column cannot be repaired that way.
LINKED_IDENTITY_FIELDS = ("type", "link_type", "link_to", "url")

# Writes that are the system placing app content on a site rather than a person authoring it.
# A `Sidebar` lives in an app's JSON and reaches a site by one of these routes, so each
# has to keep working with developer mode off -- otherwise installing or updating an app that
# ships a sidebar would fail on every customer site.
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

		The column is only ever meaningful on a `Custom Sidebar` row, where a reference
		to a Section Break has nothing else to name it by. Left on a base row it would be a
		second, staler answer to the same question -- and rows shipped before the derivation
		changed still carry one, so this is what retires them: every import runs `validate`, so
		an app's next update takes the dead values out with it.
		"""
		for item in self.items:
			item.key = None

	def validate_app_content(self):
		"""A `Sidebar` is app content, and only developer mode authors app content.

		The invariant this buys is what makes app updates safe: *on a non-developer-mode site
		every sidebar document arrived by import*, so an app overwriting its own sidebar costs
		the site nothing. A site that wants a different sidebar says so where site intent
		already lives -- `Custom Sidebar`, at the site-wide layer or the user's own --
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
		except (frappe.DoesNotExistError, ImportError):
			# `get_module_app` throws rather than returns, so the message it queued would reach
			# the user alongside ours and say the same thing twice, in framework words.
			frappe.clear_last_message()
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
		"""Export to `<app>/<module>/sidebar/<name>/<name>.json`.

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
			export_to_files(record_list=[["Sidebar", self.name]], record_module=self.module)

	def exported_file_path(self) -> str:
		"""Where `export_to_files` writes this sidebar. Mirrors `check_if_record_exists`, which
		is what orphan removal uses to decide whether a standard record still has a file."""
		import os

		scrubbed = frappe.scrub(self.name)
		return os.path.join(frappe.get_module_path(self.module), "sidebar", scrubbed, f"{scrubbed}.json")

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
		except (frappe.DoesNotExistError, ImportError):
			# No module folder, so no file. `get_module_app` says so by throwing and queueing a
			# message, which would otherwise surface as an error beside `mark_as_standard`'s own
			# success alert.
			frappe.clear_last_message()
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

	savepoint = "mark_sidebar_standard"
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
	`Custom Sidebar`), and a frozen copy of a base that has stopped tracking the module.

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


def get_sidebar(module: str) -> "Sidebar | None":
	"""`module`'s sidebar document, or `None` -- which is the ordinary state, since nothing
	persists a base on a module's behalf."""
	name = frappe.db.get_value("Sidebar", {"module": module})
	return frappe.get_doc("Sidebar", name) if name else None


def materialize_base(module: str) -> "Sidebar":
	"""The module's base as a document ready to be exported -- the one place a base crosses
	from computed to shipped.

	A document with items of its own is authored content and is returned as it stands. Anything
	else -- no document, or one with an empty items table -- is filled from the computed base,
	because that is exactly what the desk renders for it (see `get_sidebar_bases`) and
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
		doc = frappe.new_doc("Sidebar")
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
	row derives it and stores nothing -- `Sidebar.clear_stored_keys` keeps that true, and
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


# ---------------------------------------------------------------------------------------
# The merge -- one module's several sources folded into a single sidebar
#
# Conversion only, and both callers are conversions: `convert_fixtures`, where an app's old
# fixtures were one file per *workspace* and a module that had four of them still ships one
# sidebar, and `patches.v16_0.convert_sidebar_forks`, where one person could have forked
# several of a module's sidebars and now has a single layer to become. Nothing on a running
# site merges anything, so this lives beside the model it writes rather than in it, and it goes
# when that batch does (see `frappe/desk/RETIRING.md`).
# ---------------------------------------------------------------------------------------


def majority_module_of(rows) -> str | None:
	"""The module most of these rows point at -- what a sidebar that never declared one is for.

	A source that declared no module has to be placed somewhere, and a sidebar with no module
	has nowhere to be merged into.
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

	def take(item, force_child=False):
		key = item_key(item)
		if key in seen:
			return
		seen.add(key)
		row = {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS}
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
	"""The Sidebar this module's workspaces merge into, as a plain dict."""
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

# The doctypes a module contains, in the order a computed base lists them. `Workspace` leads
# because a module that has one wants you to land there.
MODULE_CONTENT_ENTITIES = ("Workspace", "Dashboard", "DocType", "Report", "Page")

# How many of a module's doctypes a computed base lists.
#
# A display limit and nothing more. A module with sixty doctypes would otherwise render sixty
# top-level links, which is not navigation. It must never decide anything else -- see the
# `computed` flag on a resolved sidebar for how routing is kept away from it.
COMPUTED_DOCTYPE_LIMIT = 15

# The icon a module that has said nothing about itself gets in the dock.
DEFAULT_HEADER_ICON = "hammer"


def get_module_contents(modules: list[str]) -> dict[str, dict[str, list]]:
	"""What each of `modules` holds, in five queries for the whole set -- one per kind of thing.

	Five queries however many modules are asked about. Asked one module at a time it was five
	queries each, and a boot that has to compute forty bases paid two hundred of them.
	"""
	contents = {module: {entity: [] for entity in MODULE_CONTENT_ENTITIES} for module in modules}

	for entity in MODULE_CONTENT_ENTITIES:
		filters = {"module": ["in", modules]}
		fields = ["name", "module"]

		if entity == "DocType":
			filters["istable"] = 0
		if entity == "Workspace":
			# public only; a private page belongs to the person who made it, and reaches their
			# sidebar through `get_private_workspaces` instead
			filters["public"] = 1
		if entity == "Page":
			fields.append("title")

		for row in frappe.get_all(entity, filters=filters, fields=fields, order_by="creation asc"):
			if bucket := contents.get(row.module):
				bucket[entity].append(row)

	for module, held in contents.items():
		contents[module] = arrange_contents(held)

	return contents


def arrange_contents(held: dict[str, list]) -> dict[str, list]:
	"""One module's contents, capped and put in the order its sidebar will list them.

	`generate_items` walks this dict in order, so the order of the keys is the order of the
	sidebar. A module with a workspace leads with it; a module without one leads with its
	doctypes, since those are then the first thing there is to land on.
	"""
	held["DocType"] = held["DocType"][:COMPUTED_DOCTYPE_LIMIT]

	if not held["Workspace"]:
		held = {"DocType": held["DocType"], **held}

	return held


def generate_items(held: dict[str, list]) -> list[dict]:
	"""Sidebar items for one module, built from what it holds.

	Reports, dashboards and pages get a collapsible section to sit under; workspaces and
	doctypes are listed flat, because they are what the module is mostly navigated by.
	"""
	items = []
	sections = {"Report": "Reports", "Dashboard": "Dashboards", "Page": "Pages"}
	icons = {"Report": "table", "Page": "panel-top", "Workspace": "wallpaper"}

	for entity, rows in held.items():
		if not rows:
			continue

		# A single dashboard or page does not need a section of its own; a report always gets
		# one, because reports come in numbers and read badly mixed in with everything else.
		sectioned = entity in sections and (entity == "Report" or len(rows) > 1)
		if sectioned:
			items.append({"type": "Section Break", "label": sections[entity], "collapsible": 1})

		for row in rows:
			item = {
				"type": "Link",
				"link_type": entity,
				"link_to": row.name,
				"label": row.title if entity == "Page" else row.name,
				"icon": icons.get(entity),
			}
			if entity == "DocType" and "settings" in row.name.lower():
				item["icon"] = "settings"
			# a report sits under its section; so does a dashboard or page, but only when
			# there were enough of them to be given one
			if entity == "Report" or sectioned:
				item["child"] = 1

			items.append(item)

	return items


# ---------------------------------------------------------------------------------------
# Computed bases -- the base a module gets when no app shipped it one
# ---------------------------------------------------------------------------------------

COMPUTED_BASE_CACHE_KEY = "sidebar_computed_base"

# Exactly what `get_module_contents` reads, which is what a computed base's items are built
# from. Each of these clears this cache from its own `clear_cache`, the way Assignment Rule and
# Milestone Tracker clear theirs; the two lists have to stay in step or bases go quietly stale.
# The base's `app` comes from the `Module Def` instead, and needs nothing: editing one calls
# `frappe.clear_cache()`, which drops every key this site holds.
MODULE_CONTENT_DOCTYPES = MODULE_CONTENT_ENTITIES


def get_computed_bases(modules: list[str]) -> dict[str, frappe._dict]:
	"""A computed base for each of `modules`, built from what the module holds.

	A base has two origins and only two: an app shipped it as JSON, or the system computed it.
	This is the second. It returns plain dicts rather than inserting rows, which is what makes
	an app that *stops* shipping a sidebar fall back here in the same request instead of
	leaving its module unnavigable until the next migrate -- and means there is nothing to
	orphan when a module or an app goes away.

	Shaped exactly like a row read by `get_sidebar_bases`, item rows included, so the
	resolution cannot tell which route a base arrived by.

	Cached per module, and built in one batch for whatever the cache is missing. Both halves
	matter: a module's contents change far less often than the desk boots, and a boot that has
	to build forty bases should not pay per module for it.
	"""
	bases = {}
	missing = []
	for module in modules:
		cached = frappe.cache.hget(COMPUTED_BASE_CACHE_KEY, module)
		if cached is None:
			missing.append(module)
		else:
			bases[module] = cached

	if missing:
		contents = get_module_contents(missing)
		for module in missing:
			base = build_computed_base(module, contents[module])
			frappe.cache.hset(COMPUTED_BASE_CACHE_KEY, module, base)
			bases[module] = base

	return bases


def get_computed_base(module: str) -> frappe._dict:
	"""One module's computed base. `get_computed_bases` for a whole set at once."""
	return get_computed_bases([module])[module]


def build_computed_base(module: str, held: dict[str, list]) -> frappe._dict:
	"""`get_computed_base` without the cache -- the thing being cached."""
	return frappe._dict(
		{
			# no `name`: there is no document. Whatever reads this must not need one.
			"module": module,
			"title": module,
			"app": get_module_placement(module),
			"header_icon": DEFAULT_HEADER_ICON,
			# not `items`: `frappe._dict` inherits `dict.items()`, so that attribute is the method
			"rows": [frappe._dict(item) for item in generate_items(held)],
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
# Resolution -- what a Scope resolves to, for one person
# ---------------------------------------------------------------------------------------


@dataclass
class SidebarContext:
	"""The site-wide reads a resolution needs, gathered once for a set of Scopes.

	`resolve_sidebar` answers for one Scope, but four of the five things it reads -- the user's
	workspaces, their private pages, the onboardings their roles allow, and the customization
	layers that apply to them -- are answered for the whole site in one go or not at all.
	Handing the resolver a context is what keeps resolving 70 modules the same handful of
	queries as resolving one, without the resolver itself having to know it is being called in
	a loop.

	Built for exactly the modules *and the person* it will be asked about: `bases` is keyed by
	module, so resolving a module the context was not built for is a caller error rather than
	a silently missing base, and `user` is checked rather than trusted -- half of what is
	batched here (the private pages, the onboardings) is one person's, and lending it to
	another reader would be handing out somebody else's private workspaces.
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
			# the reader's own layers and the site's, in one query for the whole set -- see
			# `get_layers_for` for why this is a read about the reader rather than per module
			layers=get_layers_for(user, modules),
			# `is_item_allowed` lives on `DeskViews`; one throwaway instance is the shared context.
			perm_ctx=frappe.new_doc("Workspace"),
		)


@dataclass
class ResolvedSidebar:
	"""What one Scope resolves to for one person: a label, an icon, a Landing, and entries.

	The arrangement itself, not the boot payload's shape -- `as_boot_entry` is one consumer of
	it and the desk will grow others. Everything on it has already been resolved *for this
	reader*: the entries are permission-filtered, layered and appended to, and the label and
	icon are whatever the layers left standing.
	"""

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
		"""Where this arrangement opens -- the first entry that leads anywhere.

		Derived rather than stored, and derived *here* rather than by the caller, because the
		only list it can honestly be derived from is the one this reader resolved. Lazy
		because boot never asks: the payload it builds carries no landing, and the tile list
		asks for a handful of modules out of seventy.
		"""
		return get_module_landing_route(self.items)

	def as_boot_entry(self) -> dict:
		"""This arrangement as `bootinfo.module_sidebars[module]`."""
		return {
			"module": self.module,
			"label": self.label,
			"app": self.app,
			"header_icon": self.header_icon,
			"module_onboarding": self.module_onboarding,
			"customized": 1 if self.customized else 0,
			# Whether these items were built from the module's contents rather than shipped by
			# an app. The desk reads it when deciding where a document opens: an entity missing
			# from a shipped sidebar was left out deliberately, while one missing from a
			# computed sidebar may just have fallen past the display limit.
			"computed": 1 if self.computed else 0,
			"workspaces": self.workspaces,
			"items": self.items,
		}


def resolve_sidebar(module: str, user: str, context: SidebarContext | None = None) -> ResolvedSidebar | None:
	"""What `module`'s sidebar resolves to for `user`, or `None` if it resolves to nothing.

	The seam. One question -- *what does this Scope resolve to, for this person* -- answered
	in one place, so that everything which shapes an answer (the permission filter, the
	customization merge, the private-page append, and the rule that drops a Scope holding
	nothing navigable) is applied in one order by one reader. The boot payload is then
	assembly and nothing more.

	`context` is a batching detail: pass one when resolving many Scopes, leave it out and the
	Scope is resolved on its own. The answer is the same either way.
	"""
	from frappe.desk.doctype.custom_sidebar.custom_sidebar import merge_layers

	if context is None:
		context = SidebarContext.for_modules([module], user)
	elif context.user != user:
		raise ValueError(f"sidebar context is {context.user}'s, and cannot answer for {user}")

	base = context.bases[module]
	filtered = filter_sidebar_items(base.rows, context.perm_ctx)

	# Deltas are applied *after* the permission filter, so a customization can never
	# resurface an item the user may not see, and an added item has already been checked.
	layers = context.layers.get(module, [])
	if layers:
		filtered = merge_layers(filtered, layers)

	# ...and the user's own private pages after *that*, which is what keeps them out of
	# every stored arrangement: a layer can only name what it was shown when it was saved,
	# and these arrive later than any of it.
	filtered = append_derived_items(filtered, context.private_rows.get(module), context.perm_ctx)

	# Same rule as the legacy builder: a sidebar with nothing but Section Breaks left is
	# a sidebar the user cannot use. Mirrored by `is_icon_permitted`; must not drift.
	# Runs after the deltas, so hiding every item genuinely hides the module.
	if not any(i["type"] != "Section Break" for i in filtered):
		return None

	label = base.title or module
	header_icon = base.header_icon
	# The same layers the merge just used, in the same order, rather than two fresh lookups for
	# them. Later layers win, so the last one holding an opinion is the one that stands.
	for layer in layers:
		if layer.label:
			label = layer.label
		if layer.header_icon:
			header_icon = layer.header_icon

	return ResolvedSidebar(
		module=module,
		label=_(label),
		# The desk's whole notion of app context: the rail asks this one question and lists
		# that app's other modules, or nothing at all when there is no answer. So it has to
		# agree with the placement `get_standalone_modules` reads -- a module both surfaces
		# call placed elsewhere would have no rail *and* no tile. A shipped document declares
		# its app and that stands; a document that doesn't (an authored stub, a custom
		# module's) falls back to the module's placement, exactly as a computed base already
		# does.
		app=base.app or get_module_placement(module),
		header_icon=header_icon,
		# Derived, never stored: the onboarding this module offers *this user*, which is the
		# only form of the question the desk ever asks. `landing` is derived for the same
		# reason -- both used to be pointers on the base, and a pointer resolved before
		# permission filtering can name something the reader cannot open.
		module_onboarding=context.onboardings.get(module),
		customized=bool(layers),
		computed=bool(base.get("computed")),
		workspaces=context.workspaces.get(module, []),
		items=filtered,
	)


def get_navigable_modules() -> list[str]:
	"""The site's modules, minus the ones this user may not navigate to.

	This is the set `get_module_sidebars` walks. It is deliberately *every* `Module Def` and
	not "every module that has a `Sidebar` row": a module the walk never enumerates can
	never be handed a sidebar, however that sidebar might be produced.

	Ordered by name. The row-driven walk it replaces inherited `get_all`'s default
	`modified desc`, so the payload reshuffled whenever anyone edited any sidebar -- an order
	nothing could have been relying on. Consumers that iterate the payload
	(`build_entity_module_map`, the desk's `get_modules_linking`) now get a stable one.
	"""
	from frappe.utils.modules import get_code_only_modules, get_visible_modules

	# Three independent gates, each answering a different question:
	# `get_visible_modules` is per-user (the user's own blocks); `get_disabled_modules` is
	# site-level -- the module's app is turned off, so nobody navigates to it regardless of
	# permissions; `get_code_only_modules` is app-level -- the app that owns the module says it
	# ships no navigation at all, having put its navigation in other modules.
	#
	# The code-only gate stops here rather than living in `is_module_visible`, which is the gate
	# a module's *contents* are behind. A code-only module keeps its workspaces, charts and
	# cards reachable; it just is not somewhere the dock can take you.
	disabled = get_disabled_modules()
	code_only = get_code_only_modules()
	visible = get_visible_modules(frappe.get_all("Module Def", pluck="name", order_by="name asc"))

	return [module for module in visible if module not in disabled and module not in code_only]


def get_sidebar_bases(modules: list[str]) -> dict[str, frappe._dict]:
	"""The sidebar base for each of `modules`, keyed by module, with its item rows.

	A base comes from one of two places: an app shipped a `Sidebar` document, or the system
	computed one from what the module holds. A module with no document is therefore not
	baseless -- it gets a computed one, in the same shape, so nothing downstream can tell which
	route a base arrived by.

	**A document with no items falls back the same way.** A sidebar with nothing in it is not
	navigation: the module would be dropped from the payload entirely, which is
	indistinguishable from having no sidebar at all. Only its *rows* are computed -- whatever
	the document says about itself (title, icon, app) is authored content and stands, so a stub
	someone created to name a module keeps its name and gains contents.

	Worth knowing: emptying a sidebar's items is no longer a way to hide a module. Hiding
	belongs to the customization layers and to `User.block_modules`, which run later and are
	per user. An empty base reads as unfinished, not as intent.

	Every base carries `computed`, which says whether its rows were built here or shipped. The
	difference matters to the desk: an entity missing from a *shipped* sidebar was left out on
	purpose, while an entity missing from a computed one may simply have fallen past
	`COMPUTED_DOCTYPE_LIMIT`. Routing reads this so a display limit cannot decide where a
	document opens.

	One query for the documents, one for their items, and one batch for whatever is left --
	whether that is one module or seventy.
	"""
	bases = frappe.get_all(
		"Sidebar",
		filters={"module": ["in", modules]},
		fields=["name", "module", "title", "app", "header_icon"],
	)

	items_by_sidebar = get_sidebar_items([base.name for base in bases])
	for base in bases:
		# not `items`: `frappe._dict` inherits `dict.items()`, so that attribute is the method
		base.rows = items_by_sidebar.get(base.name, [])
		base.computed = 0

	resolved = {base.module: base for base in bases}

	# a module with no document at all, and a document whose items table is empty, need the
	# same thing: rows built from the module's contents
	needs_computing = [module for module in modules if not resolved.get(module, {}).get("rows")]
	computed = get_computed_bases(needs_computing) if needs_computing else {}

	for module in needs_computing:
		if base := resolved.get(module):
			base.rows = computed[module].rows
			base.computed = 1
		else:
			resolved[module] = computed[module]
			resolved[module].computed = 1

	return resolved


def get_sidebar_items(sidebar_names):
	"""Every `Sidebar Item` row for the given sidebars, grouped by parent."""
	if not sidebar_names:
		return {}

	items = {}
	for item in frappe.get_all(
		"Sidebar Item",
		filters={"parenttype": "Sidebar", "parent": ["in", sidebar_names]},
		fields=[
			"parent",
			"idx",
			# no `key`: a base row's identity is derived from the columns below, and a value
			# stored in that column by an older derivation must not out-rank them. Rows written
			# before the change still hold one until their app next re-imports the sidebar.
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
		],
		order_by="idx asc",
	):
		items.setdefault(item.parent, []).append(item)

	return items


def get_module_workspaces():
	"""The workspaces of each module this user may see, in `sequence_id` order.

	Reachability, not publicness: `get_workspaces` has already answered which workspaces this
	user may open -- every public one they reach plus their own private ones -- so the filter
	is membership of that set. A private page belongs to a module like any other page, and the
	desk reads this to answer "which module does this workspace belong to" when a route names
	one; answering `None` for a private page left its owner's shell on whatever module it
	happened to be showing.

	Replaces `Workspace.get_module_wise_workspaces()`, which ordered by `creation` and was
	not permission-filtered.
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
	"""`user`'s own private workspaces, per module, shaped as sidebar item rows.

	A private page's sidebar link is **derived, never stored** (D3). Everything a link needs
	is already on the workspace -- its module, its owner, its title and its icon -- so a stored
	one was a second copy of all four, and it went into the *shared* document: the site layer
	accumulated a row per private page, so an admin curating the site's sidebar found
	strangers' pages in the document they were editing, and every one of those rows had to be
	kept in step with a workspace that could be renamed or deleted at any time.

	Read off the enumeration the payload is already built from rather than queried for, so the
	derivation costs a boot nothing -- and, more to the point, it can only ever offer a page
	`get_workspaces` has already said this user may open. Owner-scoped on top of that, which is
	what makes it safe to append after the permission filter has run.

	Pages only, mirroring the write path this replaces: a Link or a URL workspace is a shortcut
	to somewhere the sidebar already lists, and has never had a way in from here.
	"""
	from frappe.desk.desktop import get_workspaces

	rows = {}
	for page in get_workspaces()["pages"]:
		if page.public or not page.module or page.for_user != user:
			continue
		# `type` is empty on pages that predate the field, and those are ordinary workspaces
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


def filter_sidebar_items(items, perm_ctx):
	"""Shape, de-duplicate and permission-filter sidebar item rows for the boot payload.

	The dedupe is what the deleted uniqueness validator used to promise, moved to the one place
	that can keep the promise: rows reach here from a shipped document, a computed base and a
	customization's added rows alike, so no single writer could have guaranteed it. Two rows
	sharing an identity *are* the same item -- there is nothing a customization could say about
	one and not the other -- and the first position wins, which is what the desk rendered
	before.
	"""
	filtered = []
	seen = set()
	for item in items:
		key = item_key(item)
		if key in seen:
			continue
		seen.add(key)

		# The permission check comes first so that nothing below it runs for an item that is
		# about to be dropped anyway. This walks every module on every boot, so an item the
		# reader cannot see should cost no queries at all.
		if item.type != "Section Break" and not is_item_allowed(item.link_to, item.link_type, perm_ctx):
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
		# One cached read instead of three uncached ones. A report that is missing and a report
		# that is disabled answer the same way -- no `report` block -- so neither needs asking
		# about separately, and `cache=True` is what keeps the same report on ten modules'
		# sidebars from costing ten round trips.
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


def append_derived_items(items, rows, perm_ctx):
	"""Add `rows` to an already-resolved sidebar, skipping anything it already holds.

	Derived items go through the same shaping and the same permission check as a base row --
	they are items like any other once they are in the payload, and the only thing that makes
	them different is that no document anywhere holds them.

	The skip is what keeps a site that stored these rows before they were derived rendering one
	link rather than two: the stored row is already in `items`, in whatever position its layer
	put it, and the derived one is the duplicate.
	"""
	if not rows:
		return items

	seen = {item["key"] for item in items}
	for entry in filter_sidebar_items(rows, perm_ctx):
		if entry["key"] in seen:
			continue
		seen.add(entry["key"])
		# Says why it cannot be arranged or hidden: it is in no document, so no arrangement
		# can name it. The desk offers it as a link and nothing else.
		entry["derived"] = 1
		items.append(entry)

	return items


def get_module_landing_route(items: list[dict]) -> str | None:
	"""Where a module's tile leads, as far as the server can answer it.

	The rule is the desk's own (`sidebar.module_landing_route`): a module opens on **the first
	navigable item in the sidebar this user resolved**. So it is handed the resolved entries --
	already permission-filtered and already customized -- and not the module's workspaces,
	which are neither.

	Only the workspace case is answered here, because a workspace route is a slug and nothing
	more, while every other item type resolves through `frappe.utils.generate_route` on the
	client -- doc views, report types, filters as query params. The desktop asks the client's
	`module_landing_route` first and falls back to this, so this is the floor a tile has before
	the sidebar object exists, not a second implementation of routing.

	It stops at the *first* navigable item rather than scanning on for a workspace it can
	answer. A tile is a link with a click handler, and the two have to lead to the same place:
	a route found further down the sidebar would send a middle-click somewhere the ordinary
	click never goes.
	"""
	item = next((item for item in items or [] if item.get("type") == "Link"), None)
	if not item or item.get("link_type") != "Workspace" or not item.get("link_to"):
		return None

	public = frappe.db.get_value("Workspace", item["link_to"], "public")
	if public is None:
		return None

	prefix = "/desk/" if public else "/desk/private/"
	return prefix + frappe.utils.slug(item["link_to"])
