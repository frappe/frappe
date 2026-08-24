# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

"""A module's sidebar: where it comes from, and what one person actually sees.

Every module in the desk has a sidebar. It starts from one of two places:

  * an app shipped a `Sidebar` document as JSON, under `<app>/<module>/sidebar/`, or
  * nobody shipped one, so we work one out from what the module holds -- its workspaces,
    dashboards, doctypes, reports and pages.

Whichever way it starts, the result has the same shape, and nothing downstream needs to know
which of the two it was. The one exception is the `computed` flag, which the desk reads so that
a display limit is never mistaken for somebody's decision.

That starting sidebar is then resolved for one person, which means, in this order:

  1. drop the items they are not allowed to see
  2. apply the site's customizations, then their own (see `custom_sidebar.py`)
  3. add their own private workspaces, which are worked out rather than stored
  4. drop the module entirely if nothing navigable is left

`resolve_sidebar` is the one place that happens. Building the boot payload is then just
assembly.

Resolving seventy modules must not cost seventy times resolving one, so every site-wide read is
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

# `is_default_module` is missing from that list on purpose. It is the flag an app sets to say
# "this entity belongs to my module", and the fixture conversion drops it rather than guessing.
# An app that wants the claim sets it in the `sidebar` file it ships, which it can edit again
# later.

# These four columns are how we identify a sidebar item that points somewhere. We match on the
# columns themselves instead of storing a hash of them.
#
# This is what keeps a customization working after a rename. `link_to` is a Dynamic Link, so
# when a document is renamed, `rename_dynamic_links` updates every `Sidebar Item` that names it
# in one statement -- base rows and customization rows alike. A stored hash could not be
# updated that way, and the customization would end up pointing at the old name.
LINKED_IDENTITY_FIELDS = ("type", "link_type", "link_to", "url")

# Flags that mean "the system is installing app content", not "a person is editing".
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
		"""Blank the `key` column on every item.

		A base row is identified by its own columns, so it does not need a stored key. The
		column only means something on a `Custom Sidebar` row, where a reference to a Section
		Break has no other way to name it.

		Left on a base row, a stored key would be a second and possibly stale answer to the same
		question. Rows shipped before we changed how keys are worked out still carry one, and
		this is what clears them: every import runs `validate`, so the app's next update takes
		the dead values with it.
		"""
		for item in self.items:
			item.key = None

	def validate_app_content(self):
		"""Only allow editing a sidebar in developer mode, because a sidebar belongs to its app.

		This is what makes app updates safe. On a site without developer mode, every sidebar
		document got there by import, so an app overwriting its own sidebar loses the site
		nothing. A site that wants a different sidebar says so in a `Custom Sidebar` instead --
		either the site-wide layer or one person's own -- and this check does not touch that.

		Developer mode is the only condition. There is no role check, so any developer on a
		developer-mode site can edit one. Who can reach the doctype at all is decided by the
		doctype's own permissions, where `Desk User` has read and nothing else.

		Deleting is not blocked here. Deleting a document cannot turn site intent into app
		content, and the things that delete one -- a module going away, orphan cleanup -- have
		to keep working on a customer site.
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
		"""Refuse to mark a sidebar standard unless we can actually write its file.

		`standard` means "there is a JSON file in an app behind this row", and only developer
		mode can write that file. A standard row whose file is missing counts as an orphan, so
		`remove_orphan_entities` would delete it on the next `bench migrate`. Better to refuse
		than to create a row that quietly deletes itself.
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

	# There is no check for duplicate items on purpose.
	#
	# An item is identified by its own columns, so two rows sharing them are the same item. A
	# document can genuinely contain that -- two workspaces of one module linking the same
	# report -- and nothing downstream is harmed by it: when the sidebar is resolved, the first
	# of them is kept and the rest are dropped. Refusing the save would reject app content that
	# renders perfectly well.

	def on_update(self):
		self.export_sidebar()

	def export_sidebar(self):
		"""Write this sidebar to `<app>/<module>/sidebar/<name>/<name>.json`.

		The path is under the module, where the old sidebar fixtures sat in a flat folder at the
		top of the app. That matters because orphan cleanup works out a record's file path as
		`<...>/<scrub(name)>.json`. In a flat folder the filenames did not have to match the
		record names, and any that did not match got their rows deleted on the next migrate.
		Here the filename and the record name always agree.
		"""
		from frappe.modules.export_file import export_to_files

		allow_export = (
			self.standard and self.module and not frappe.flags.in_import and frappe.conf.developer_mode
		)
		if allow_export:
			export_to_files(record_list=[["Sidebar", self.name]], record_module=self.module)

	def exported_file_path(self) -> str:
		"""The path `export_to_files` writes this sidebar to.

		Built the same way as `check_if_record_exists`, which is what orphan cleanup uses to
		decide whether a standard record still has a file behind it.
		"""
		import os

		scrubbed = frappe.scrub(self.name)
		return os.path.join(frappe.get_module_path(self.module), "sidebar", scrubbed, f"{scrubbed}.json")

	def is_exported(self) -> bool:
		"""Whether the file behind this sidebar is really on disk.

		This is the question orphan cleanup asks, so `mark_as_standard` has to answer it before
		claiming the sidebar is shipped. A module with no folder at all answers it the same way:
		no folder means no file.
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
# Marking a sidebar standard, and taking it back
#
# `standard` means an app ships this sidebar as a JSON file. The two actions below turn that
# on and off, and both of them move the file as well as the flag.
# ---------------------------------------------------------------------------------------


@frappe.whitelist()
def mark_as_standard(module: str) -> str:
	"""Make `module`'s sidebar part of its app: write it into the module's folder so the app
	ships it, and let `bench migrate` import it back from there. Returns the document's name.

	We build the document first and export second. That way an author starts from what the
	system already generated instead of from an empty file. A module with no document still has
	a base -- `get_computed_base` works one out from what the module holds -- and that is what
	gets written. A document that already has items of its own is shipped as it stands. See
	`materialize_base` for exactly where that line falls.

	Developer mode is the only condition; there is no role check. What makes this write okay is
	that the site belongs to a developer. Who can reach the doctype at all is decided by the
	doctype's own permissions (see `validate_app_content`).

	We check that the file was really written, and roll back if it was not. A standard row with
	no file counts as an orphan, and `remove_orphan_entities` deletes it on the next
	`bench migrate` -- so a mark that wrote no file must leave no row behind either.
	"""
	check_developer_mode()

	doc = materialize_base(module)

	# Already shipped, so there is nothing to do. We check the flag *and* the file: a standard
	# row whose file has gone missing is exactly the orphan this action exists to prevent, so
	# we write it again rather than report success.
	if doc.standard and doc.is_exported():
		return doc.name

	savepoint = "mark_sidebar_standard"
	frappe.db.savepoint(savepoint)
	try:
		doc.standard = 1
		doc.app = get_module_placement(module)
		# `save` inserts a freshly built base and updates an existing document. Either way it is
		# `on_update` that writes the file.
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
	"""Give `module`'s sidebar back to the site: delete its exported file and its document.

	We delete the document rather than just clearing the flag. Once the app content is gone the
	module falls back to its computed base, which is worked out from the module's contents when
	it is read -- so the module is back to a working sidebar in this same request.

	Clearing the flag instead would leave a row nobody owns. It would not be app content, since
	there is no file. It would not be site intent, since that lives in `Custom Sidebar`. It
	would just be a frozen copy of a base that had stopped following the module.

	The file has to go too. Left on disk, the next `bench migrate` imports it again and the row
	comes back standard, so deleting the document on its own would not survive a migrate.
	"""
	import os
	import shutil

	check_developer_mode()

	doc = get_sidebar(module)
	# Only a standard sidebar belongs to an app. If it is not standard there is nothing to hand
	# back, and a document somebody is still working on is not ours to delete.
	if not doc or not doc.standard:
		return

	path = doc.exported_file_path() if doc.is_exported() else None
	doc.delete()

	# Delete the file now rather than on commit. If someone un-marks and marks again in one
	# request, we want to end up with the file the second call wrote -- not with a queued delete
	# that removes it afterwards.
	if path:
		shutil.rmtree(os.path.dirname(path), ignore_errors=True)

	frappe.msgprint(
		_("{0} is no longer standard; its exported file has been removed.").format(frappe.bold(doc.name)),
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
		_(
			"Enable developer mode to change whether a sidebar is standard -- it is backed by a file in its app."
		),
		title=_("Not Editable"),
	)


def get_sidebar(module: str) -> "Sidebar | None":
	"""`module`'s sidebar document, or `None`.

	`None` is the normal answer. Nothing creates a sidebar document for a module on its behalf,
	so most modules have none and get a computed base instead.
	"""
	name = frappe.db.get_value("Sidebar", {"module": module})
	return frappe.get_doc("Sidebar", name) if name else None


def materialize_base(module: str) -> "Sidebar":
	"""The module's base as a document, ready to be exported.

	This is the one place a base goes from being computed to being shipped.

	If a document already has items of its own, somebody wrote them, and it is returned as it
	stands. Otherwise -- no document, or a document with an empty items table -- we fill it from
	the computed base. That is exactly what the desk shows for the module today
	(see `get_sidebar_bases`), and shipping an empty file would ship something that does not
	match the navigation it came from.

	The rows are copied across unchanged, which is all it takes to keep existing customizations
	working. An item is identified by the columns being copied, so someone who had hidden an
	item still has it hidden afterwards, with nothing to re-key.
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
		# Copy each row. `append` writes doctype and parent keys into the dict it is given, and
		# these rows belong to the cached base, which we must not modify.
		doc.append("items", dict(row))
	return doc


def is_linked(item) -> bool:
	"""Whether this row leads somewhere. A Section Break or a spacer does not."""
	return bool(item.get("link_to") or item.get("url"))


def item_key(item) -> str:
	"""How we identify one sidebar item. This is what a customization row names when it wants
	to say something about that item.

	There are two shapes, because the two kinds of row have different things to be named by:

	- A row that **links** somewhere is identified by the columns it already has. Nothing extra
	  is stored, so there is no second copy to keep in step and nothing for a rename to break.
	  See `LINKED_IDENTITY_FIELDS`.
	- A row that links **nowhere** -- a Section Break or a spacer -- is identified by a hash of
	  its type and its label. Including the label is safe: the section labels we generate are
	  constants in the code, at most three per module, and all different.

	Only a customization row stores that hash. A reference to a Section Break has nothing else
	to name it by, and its own label is a field the reference is allowed to override. A base row
	works its key out each time and stores nothing -- `Sidebar.clear_stored_keys` keeps that
	true, and boot never reads the column. So a stored key that reaches here always came from a
	customization, never from an older version of this function.

	This function only reads columns the rows already carry, so importing the same JSON twice
	produces the same identities. That matters because standard child rows are hash-named and
	recreated on every import, which is why a customization can never point at a row's `name`.
	"""
	if is_linked(item):
		return "|".join(item.get(field) or "" for field in LINKED_IDENTITY_FIELDS)

	return item.get("key") or unlinked_key(item)


def unlinked_key(item) -> str:
	"""The key we work out for an unlinked row when nothing has stored one for it.

	There is no position number in the key. The old version had one, to tell apart rows that
	collided because the label was left out. Including the label removes the collisions, and
	the position number could go with it -- it was re-pointing every customization below any
	row somebody inserted.
	"""
	identity = f"{item.get('type') or ''}|{item.get('label') or ''}"
	return hashlib.sha1(identity.encode()).hexdigest()[:10]


# ---------------------------------------------------------------------------------------
# The merge: folding a module's several old sidebars into one
#
# This is only used when converting old data, and both callers are conversions:
#
#   * `convert_fixtures`, where an app's old fixtures were one file per workspace, so a module
#     with four workspaces still has to end up with one sidebar.
#   * `patches.v16_0.convert_sidebars`, where one person could have forked several of a
#     module's sidebars and now has a single customization layer to become.
#
# Nothing on a running site merges anything. That is why this sits beside the model rather than
# inside it, and why it goes away when the conversion does (see `frappe/desk/RETIRING.md`).
# ---------------------------------------------------------------------------------------


def majority_module_of(rows) -> str | None:
	"""The module most of these rows point at.

	Used to work out which module an old sidebar was for when it never said. Every sidebar has
	to belong to a module now, and one with no module has nothing to be merged into.
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
	"""Which workspace's sidebar becomes the module's own.

	A workspace named after the module wins, so `Stock` beats `Stock Reports`. Failing that, the
	biggest sidebar wins: it is the module's fullest set of links, and pushing it down into a
	collapsed section would be the most disruptive thing we could do.

	`sequence_id` only breaks ties. Used as the main signal it picks more or less at random,
	because on a real site nearly every workspace has the same one -- it gives module Accounts
	to Invoicing(28) over Accounting(49), and module Core to Build(14) over System(76).
	"""
	for workspace in workspaces:
		if workspace.name == module:
			return workspace
	return sorted(
		workspaces,
		key=lambda ws: (-len(ws.rows), ws.sequence_id or 0, ws.creation),
	)[0]


def display_title(module: str, primary: frappe._dict, is_merge: bool) -> str:
	"""The label the dock shows for this module.

	A module with only one source keeps that workspace's title, so existing labels survive
	unchanged -- module `Loan Management` still reads "Lending". A module built from several
	sources takes the module name instead: four sidebars merged together are not "Accounting"
	or "Build", and using one source's title would misdescribe the rest.
	"""
	return module if is_merge else (primary.title or primary.name)


def merge_items(primary: frappe._dict, secondaries: list[frappe._dict]) -> list[dict]:
	"""The primary's items first, then each other source under a collapsed section of its own.

	Duplicates are dropped across the whole merged list, using the same `item_key` the desk
	uses when it resolves a sidebar. That removes both the duplicate rows the desk already hides
	and the real overlap between two workspaces of one module. Using the same identity means the
	merge cannot produce a row the desk would only drop again: two rows pointing at one target
	are one item, whatever the two workspaces called them.
	"""
	merged = []
	seen = set()

	def take(item, force_child=False):
		key = item_key(item)
		if key in seen:
			return
		seen.add(key)
		row = {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS}
		# There is no key to copy across. A linked row is identified by the columns we just
		# copied, and an unlinked row by its type and label.
		#
		# Only links get nested. A source's own Section Breaks stay top-level sections, because
		# the desk only draws one level of nesting -- a Section Break marked `child` would claim
		# a parent it never gets.
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
	"""The sidebar this module's workspaces merge into, as a plain dict."""
	primary = pick_primary(module, workspaces)
	secondaries = [ws for ws in workspaces if ws.name != primary.name]

	return frappe._dict(
		{
			"module": module,
			"title": display_title(module, primary, bool(secondaries)),
			"header_icon": primary.icon,
			# No home link and no onboarding link. The primary's items come first, so the module
			# opens on the first of them. Which onboarding a module offers depends on who is
			# looking, and `get_permitted_onboardings` answers that when the sidebar is read.
			"app": get_module_placement(module),
			# Not standard, however standard the source workspaces were.
			#
			# `standard` means there is a JSON file in an app behind this row, and that is what
			# orphan cleanup checks: a standard row with no file gets deleted. A merged sidebar
			# is built from this site's own workspaces and has no file, so marking it standard
			# would get it deleted by the very next `bench migrate`. It only becomes standard
			# when an app deliberately exports it.
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

# The kinds of thing a module can hold, in the order a computed sidebar lists them. Workspaces
# come first, because a module that has one wants you to land there.
MODULE_CONTENT_ENTITIES = ("Workspace", "Dashboard", "DocType", "Report", "Page")

# How many of a module's doctypes a computed sidebar lists.
#
# This is a display limit and nothing else. A module with sixty doctypes would otherwise draw
# sixty top-level links, which is a list, not navigation.
#
# It must never decide anything but what is drawn. In particular it must not decide where a
# document opens -- see the `computed` flag on a resolved sidebar for how routing is kept away
# from it.
COMPUTED_DOCTYPE_LIMIT = 15

# The icon a module gets in the dock when it has said nothing about itself.
DEFAULT_HEADER_ICON = "hammer"


def get_module_contents(modules: list[str]) -> dict[str, dict[str, list]]:
	"""What each of `modules` holds: five queries for the whole set, one per kind of thing.

	It is five queries however many modules you ask about. Asked one module at a time it was
	five queries each, so a boot that had to build forty sidebars paid two hundred of them.
	"""
	contents = {module: {entity: [] for entity in MODULE_CONTENT_ENTITIES} for module in modules}

	for entity in MODULE_CONTENT_ENTITIES:
		filters = {"module": ["in", modules]}
		fields = ["name", "module"]

		if entity == "DocType":
			filters["istable"] = 0
		if entity == "Workspace":
			# Public workspaces only. A private page belongs to the person who made it and
			# reaches their sidebar through `get_private_workspaces` instead.
			filters["public"] = 1
			# read for one row only -- the module's own page, whose icon is the module's icon
			# (see `own_page_icon`)
			fields.append("icon")
		if entity == "Page":
			fields.append("title")

		for row in frappe.get_all(entity, filters=filters, fields=fields, order_by="creation asc"):
			if bucket := contents.get(row.module):
				bucket[entity].append(row)

	return {module: arrange_contents(held) for module, held in contents.items()}


def arrange_contents(held: dict[str, list]) -> dict[str, list]:
	"""One module's contents, trimmed to the display limit and put in the order the sidebar
	will list them.

	`generate_items` walks this dict in order, so the order of the keys is the order of the
	sidebar. A module with a workspace leads with it. A module without one leads with its
	doctypes, since those are then the first thing there is to land on.
	"""
	held["DocType"] = held["DocType"][:COMPUTED_DOCTYPE_LIMIT]

	if not held["Workspace"]:
		held = {"DocType": held["DocType"], **held}

	return held


def generate_items(held: dict[str, list], module: str | None = None) -> list[dict]:
	"""Sidebar items for one module, built from what it holds.

	Reports, dashboards and pages get a collapsible section to sit under. Workspaces and
	doctypes are listed flat, because they are what people mostly navigate a module by.

	`module` is only read to recognise the module's own workspace -- see the label below.
	"""
	items = []
	sections = {"Report": "Reports", "Dashboard": "Dashboards", "Page": "Pages"}
	icons = {"Report": "table", "Page": "panel-top", "Workspace": "wallpaper"}

	for entity, rows in held.items():
		if not rows:
			continue

		# A single dashboard or page does not need a section of its own. A report always gets
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
			# The module's own workspace is where the module opens, and it reads as "Home" --
			# the same word every shipped `Sidebar` gives it (`('Home', 'Workspace', 'Website')`
			# is the first row of the one the website module ships). A computed sidebar that
			# called it by the module's name would say the module's name twice: once as the
			# header above the list, once as the first thing in it.
			if entity == "Workspace" and module and row.name == module:
				item["label"] = _("Home")
			if entity == "DocType" and "settings" in row.name.lower():
				item["icon"] = "settings"
			# A report always sits under its section. A dashboard or page only does when there
			# were enough of them to be given one.
			if entity == "Report" or sectioned:
				item["child"] = 1

			items.append(item)

	return items


# ---------------------------------------------------------------------------------------
# Computed sidebars: what a module gets when no app shipped it one
# ---------------------------------------------------------------------------------------

COMPUTED_BASE_CACHE_KEY = "sidebar_computed_base"

# The doctypes whose rows a computed sidebar is built from -- exactly what `get_module_contents`
# reads. Each of them clears this cache from its own `clear_cache`, the way Assignment Rule and
# Milestone Tracker clear theirs. The two lists have to stay in step, or cached sidebars go
# quietly out of date.
#
# The `app` on a base comes from the `Module Def` instead, and needs nothing here: editing one
# calls `frappe.clear_cache()`, which drops every key on the site.
MODULE_CONTENT_DOCTYPES = MODULE_CONTENT_ENTITIES


def get_computed_bases(modules: list[str]) -> dict[str, frappe._dict]:
	"""A computed sidebar for each of `modules`, built from what the module holds.

	A sidebar comes from one of two places: an app shipped it as JSON, or we worked it out from
	the module's contents. This is the second.

	It returns plain dicts and inserts nothing. Two things follow from that. An app that stops
	shipping a sidebar falls back here in the same request, rather than leaving its module
	unnavigable until the next migrate. And there is nothing left to clean up when a module or
	an app goes away.

	The dicts have the same shape as a row read by `get_sidebar_bases`, item rows included, so
	nothing downstream can tell which of the two routes a sidebar came by.

	Results are cached per module, and whatever the cache is missing is built in one batch. Both
	halves matter: a module's contents change far less often than the desk boots, and a boot
	that has to build forty sidebars should not pay per module for it.
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
			# `hset` puts this very object into `frappe.local.cache` too, so the freshly built
			# one has to be copied on the way out for the same reason a cached one does
			bases[module] = copy_of(base)

	return bases


def copy_of(base: frappe._dict) -> frappe._dict:
	"""A caller's own copy of a cached sidebar.

	`frappe.cache.hget` keeps a copy in `frappe.local.cache` and hands back *the same object*
	every time it is asked within a request. So a caller that writes to what it got back is
	writing into the cache -- and `get_sidebar_bases` does write to it, stamping `computed` on
	every sidebar it returns.

	The rows themselves are shared rather than copied. Nothing edits a row in place: the boot
	path builds new dicts out of them, and `materialize_base` copies each one before appending
	it to a document.
	"""
	return frappe._dict({**base, "rows": list(base.rows)})


def get_computed_base(module: str) -> frappe._dict:
	"""One module's computed sidebar. Use `get_computed_bases` for a whole set at once."""
	return get_computed_bases([module])[module]


def build_computed_base(module: str, held: dict[str, list]) -> frappe._dict:
	"""Build one module's computed sidebar. This is the value the cache stores."""
	return frappe._dict(
		{
			# No `name`, because there is no document. Nothing reading this may need one.
			"module": module,
			"title": module,
			"app": get_module_placement(module),
			"header_icon": own_page_icon(module, held) or DEFAULT_HEADER_ICON,
			# Called `rows`, not `items`: `frappe._dict` inherits `dict.items()`, so `items`
			# would be the method rather than our list.
			"rows": [frappe._dict(item) for item in generate_items(held, module)],
		}
	)


def own_page_icon(module: str, held: dict[str, list]) -> str | None:
	"""The icon of the module's own workspace, which is the module's icon.

	A shipped `Sidebar` states its header icon outright; a computed one has nowhere to state
	anything, so it reads the icon off the one page that is unambiguously the module's -- the
	one named after it, which `pick_primary` already treats as the module's own and which
	`generate_items` labels "Home".

	Nothing else on a module carries an icon, and a module the site adds gets one this way: the
	icon chosen while adding it is stored on the page it opens on, and this is what puts it on
	the dock. Failing that, `DEFAULT_HEADER_ICON`.
	"""
	for row in held.get("Workspace", []):
		if row.name == module:
			return row.get("icon")

	return None


def clear_computed_base_cache(module: str) -> None:
	"""Drop one module's cached sidebar. The whole cache key is in `global_cache_keys`, so
	`bench clear-cache` drops the lot."""
	frappe.cache.hdel(COMPUTED_BASE_CACHE_KEY, module)


def clear_computed_base_for(doc: Document) -> None:
	"""Drop the cached sidebar of every module `doc` has belonged to.

	Called from `clear_cache` on each doctype in `MODULE_CONTENT_DOCTYPES`. That is the one
	place the framework already runs for both halves of "a module gained or lost something": a
	save (`run_post_save_methods`) and a delete (`delete_doc`) both end up here. A rename needs
	no call at all, because `rename_doc` finishes with `frappe.clear_cache()`.

	It clears two modules, not one. Moving a document from one module to another means one lost
	what the other gained, and `doc` only carries its current module.
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
	"""Everything a resolution needs to read, fetched once for a whole set of modules.

	`resolve_sidebar` answers for one module at a time, but four of the five things it reads
	are answered for the whole site at once or not at all: the user's workspaces, their private
	pages, the onboardings their roles allow, and the customizations that apply to them.
	Fetching them into a context is what makes resolving seventy modules cost the same handful
	of queries as resolving one, without the resolver having to know it is in a loop.

	A context is built for a specific set of modules and a specific person.

	`bases` is keyed by module, so asking about a module the context was not built for raises a
	`KeyError` rather than quietly returning nothing.

	`user` is checked rather than trusted. Half of what is fetched here belongs to one person --
	their private pages, their onboardings -- so handing the context to a different reader would
	mean showing them somebody else's private workspaces.
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
			# The site's customizations and this reader's own, in one query for the whole set.
			# See `get_layers_for` for why this is one read about the reader rather than one
			# read per module.
			layers=get_layers_for(user, modules),
			# `is_item_allowed` is a method on `DeskViews`, so we need an instance to call it
			# on. One throwaway `Workspace` is shared by every permission check below.
			perm_ctx=frappe.new_doc("Workspace"),
		)


@dataclass
class ResolvedSidebar:
	"""What one module's sidebar looks like for one person: a label, an icon, and its items.

	This is the sidebar itself, not the shape the boot payload happens to use. `as_boot_entry`
	is one consumer of it, and the desk will grow others.

	Everything on it has already been worked out for this particular reader. The items have been
	filtered by permission, had customizations applied and had derived items added. The label
	and icon are whatever those customizations left standing.
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
		"""Where this sidebar opens: the first item that leads anywhere.

		Worked out here rather than stored, and worked out here rather than by the caller,
		because the only honest list to read it off is the one this reader resolved.

		Lazy, because boot never asks for it. The boot payload carries no landing route, and the
		desktop tiles ask about a handful of modules out of seventy.
		"""
		return get_module_landing_route(self.items)

	def as_boot_entry(self) -> dict:
		"""This sidebar in the shape `bootinfo.module_sidebars[module]` uses."""
		return {
			"module": self.module,
			"label": self.label,
			"app": self.app,
			"header_icon": self.header_icon,
			"module_onboarding": self.module_onboarding,
			"customized": 1 if self.customized else 0,
			# Whether these items were worked out from the module's contents rather than shipped
			# by an app. The desk reads this when deciding where a document opens. Something
			# missing from a sidebar an app shipped was left out on purpose; something missing
			# from a computed sidebar may just not have fitted under the display limit.
			"computed": 1 if self.computed else 0,
			"workspaces": self.workspaces,
			"items": self.items,
		}


def resolve_sidebar(module: str, user: str, context: SidebarContext | None = None) -> ResolvedSidebar | None:
	"""What `module`'s sidebar looks like for `user`, or `None` if it comes out empty.

	This is the one place that question is answered, so that everything shaping the answer
	happens in one order, in one function: the permission filter, the customizations, the
	private pages added at the end, and the rule that drops a module with nothing left to
	navigate to. Building the boot payload is then just assembly.

	`context` only exists for batching. Pass one when resolving many modules; leave it out and
	the module is resolved on its own. The answer is the same either way.
	"""
	from frappe.desk.doctype.custom_sidebar.custom_sidebar import merge_layers

	if context is None:
		context = SidebarContext.for_modules([module], user)
	elif context.user != user:
		raise ValueError(f"sidebar context is {context.user}'s, and cannot answer for {user}")

	base = context.bases[module]
	filtered = filter_sidebar_items(base.rows, context.perm_ctx)

	# Customizations are applied after the permission filter, never before. That way a
	# customization can never bring back an item the user is not allowed to see.
	layers = context.layers.get(module, [])
	if layers:
		filtered = merge_layers(filtered, layers)
		# An added row is the one kind that gets past that, because it brings an item the base
		# never held and the filter above therefore never saw. So it is checked here, on its
		# own, and the rule holds for the rows that bring their own item as well as for the ones
		# that name an existing one.
		filtered = [item for item in filtered if allowed_added_item(item, context.perm_ctx)]

	# The user's own private pages come after that. This is what keeps them out of every stored
	# customization: a customization can only name what it was shown when it was saved, and
	# these are added later than anything it could have seen.
	filtered = append_derived_items(filtered, context.private_rows.get(module), context.perm_ctx)

	# A sidebar left with nothing but Section Breaks is one the user cannot use, so the module
	# is dropped. `is_icon_permitted` applies the same rule for desktop icons and the two must
	# not drift apart. This runs after customizations, so hiding every item really does hide
	# the module.
	if not any(i["type"] != "Section Break" for i in filtered):
		return None

	label = base.title or module
	header_icon = base.header_icon
	# The same customizations the merge just used, in the same order. Later ones win, so the
	# last one with an opinion about the label or icon is the one that stands.
	for layer in layers:
		if layer.label:
			label = layer.label
		if layer.header_icon:
			header_icon = layer.header_icon

	return ResolvedSidebar(
		module=module,
		label=_(label),
		# This is the desk's entire idea of "which app am I in". The rail asks this one
		# question and then lists that app's other modules, or nothing at all when there is no
		# answer.
		#
		# A shipped document names its own app and that wins. A document that does not -- a stub
		# somebody created, a custom module's -- falls back to the module's placement, which is
		# what a computed sidebar uses anyway.
		app=base.app or get_module_placement(module),
		header_icon=header_icon,
		# Worked out, never stored: which onboarding this module offers *this user*, which is
		# the only version of the question the desk ever asks. `landing` works the same way.
		# Both used to be stored links on the sidebar, and a stored link resolved before the
		# permission filter runs can name something the reader is not allowed to open.
		module_onboarding=context.onboardings.get(module),
		customized=bool(layers),
		computed=bool(base.get("computed")),
		workspaces=context.workspaces.get(module, []),
		items=filtered,
	)


def get_navigable_modules() -> list[str]:
	"""The site's modules, minus the ones this user cannot navigate to.

	This is the list `get_module_sidebars` walks. It starts from every `Module Def`, not from
	"every module that has a `Sidebar` row", because a module this list never mentions can never
	be given a sidebar however that sidebar would have been produced.

	Ordered by name. The older row-driven version inherited `get_all`'s default of
	`modified desc`, so the payload reshuffled itself whenever anybody edited any sidebar.
	Anything that walks the payload in order -- `build_entity_module_map`, the desk's
	`get_modules_linking` -- now gets a stable order.
	"""
	from frappe.utils.modules import get_code_only_modules, get_visible_modules

	# Three separate checks, each answering a different question:
	#
	#   get_visible_modules   per user  -- this person blocked the module
	#   get_disabled_modules  per site  -- the module's app is turned off, so nobody sees it
	#   get_code_only_modules per app   -- the app says this module ships no navigation, having
	#                                      moved its navigation into other modules
	#
	# The code-only check belongs here and not in `is_module_visible`, which is what guards a
	# module's *contents*. A code-only module keeps its workspaces, charts and cards reachable.
	# It just is not somewhere the dock can take you.
	disabled = get_disabled_modules()
	code_only = get_code_only_modules()
	visible = get_visible_modules(frappe.get_all("Module Def", pluck="name", order_by="name asc"))

	return [module for module in visible if module not in disabled and module not in code_only]


def get_sidebar_bases(modules: list[str]) -> dict[str, frappe._dict]:
	"""The starting sidebar for each of `modules`, keyed by module, with its item rows.

	A sidebar comes from one of two places: an app shipped a `Sidebar` document, or we worked
	one out from what the module holds. So a module with no document is not left without a
	sidebar -- it gets a computed one, in the same shape, and nothing downstream can tell the
	difference.

	A document with an empty items table falls back the same way. A sidebar with nothing in it
	is not navigation, and the module would be dropped from the payload entirely, which is the
	same as having no sidebar at all. Only its *rows* are computed: whatever the document says
	about itself -- title, icon, app -- was written by somebody and stands. So a stub created
	just to name a module keeps its name and gains contents.

	One consequence worth knowing: emptying a sidebar's items is not a way to hide a module.
	Hiding is done by customizations and by `User.block_modules`, which run later and are per
	user. An empty sidebar reads as unfinished, not as a decision.

	Each sidebar carries `computed`, saying whether its rows were built here or shipped by an
	app. The desk needs the difference: something missing from a shipped sidebar was left out on
	purpose, while something missing from a computed one may just have fallen past
	`COMPUTED_DOCTYPE_LIMIT`. Routing reads this flag so that a display limit cannot decide
	where a document opens.

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
		# Called `rows`, not `items`: `frappe._dict` inherits `dict.items()`, so `items` would
		# be the method rather than our list.
		base.rows = items_by_sidebar.get(base.name, [])
		base.computed = 0

	resolved = {base.module: base for base in bases}

	# A module with no document at all and a document with an empty items table both need the
	# same thing: rows built from what the module holds.
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
	"""Every `Sidebar Item` row for the given sidebars, grouped by the sidebar it belongs to."""
	if not sidebar_names:
		return {}

	items = {}
	for item in frappe.get_all(
		"Sidebar Item",
		filters={"parenttype": "Sidebar", "parent": ["in", sidebar_names]},
		fields=[
			"parent",
			"idx",
			# `key` is deliberately not read. A base row is identified by the columns below, and
			# a value left in that column by an older version of the code must not override
			# them. Rows written before that change still carry one until their app next
			# re-imports the sidebar.
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
	"""The workspaces of each module this user can see, in `sequence_id` order.

	The test is whether the user can open the workspace, not whether it is public.
	`get_workspaces` has already worked that out -- every public workspace they can reach, plus
	their own private ones -- so all we do here is keep the ones in that set.

	Private pages are included, because a private page belongs to a module like any other. The
	desk reads this to answer "which module does this workspace belong to" when a route names
	one, and answering `None` for a private page used to leave its owner looking at whatever
	module happened to be on screen.

	Replaces `Workspace.get_module_wise_workspaces()`, which ordered by `creation` and did not
	filter by permission at all.
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
	"""`user`'s own private workspaces, grouped by module and shaped as sidebar item rows.

	A private page's sidebar link is worked out here every time, never stored. Everything a link
	needs is already on the workspace -- its module, its owner, its title and its icon -- so
	storing one meant keeping a second copy of all four in step with a workspace that could be
	renamed or deleted at any moment.

	Worse, the stored row went into the shared document. The site-wide sidebar collected a row
	per private page, so an admin tidying up the site's sidebar found strangers' pages in the
	document they were editing.

	These are read off the workspace list the payload is already built from rather than queried
	for, so working them out costs a boot nothing. More importantly, it means we can only ever
	offer a page `get_workspaces` has already said this user may open, and we narrow that to the
	pages they own. That is what makes it safe to add these after the permission filter has run.

	Pages only, which matches the write path this replaces. A Link or URL workspace is a
	shortcut to somewhere the sidebar already lists, and never had a way in here.
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
	user is not allowed to see.

	Dropping duplicates used to be a uniqueness check on the document. It lives here instead,
	because this is the only place that can actually promise it: rows arrive from a shipped
	document, from a computed sidebar and from a customization's added rows, so no single writer
	could have guaranteed anything.

	Two rows with the same identity are the same item -- there is nothing a customization could
	say about one and not the other -- so the first one wins, which is what the desk drew before.

	`check_permission` is off for exactly one caller: the editor reading the *site* layer. Who
	may see an item is a fact about the reader, applied to what each person boots -- so it is
	not part of what the site arranged, and a curator who filtered it out of their screen would
	drop the site's rows for it on the next save. See `layer_arrangement`.
	"""
	filtered = []
	seen = set()
	for item in items:
		key = item_key(item)
		if key in seen:
			continue
		seen.add(key)

		# Check permission first, so nothing below runs for an item that is about to be dropped
		# anyway. This walks every module on every boot, so an item the reader cannot see should
		# cost no queries at all.
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
		# One cached read rather than three uncached ones. A missing report and a disabled report
		# get the same answer -- no `report` block -- so neither needs a question of its own.
		# `cache=True` is what stops the same report appearing on ten sidebars costing ten
		# round trips.
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
	"""Whether an item a layer *added* is one this reader may see.

	Only added items are asked. Everything else came through `filter_sidebar_items` and has been
	answered already, and asking twice would cost a permission check per item per module on
	every boot.

	A row leading nowhere -- a Section Break, a spacer -- is nobody's to block, which is the same
	exception the filter makes for it. Asked as `is_linked`, the same question the identity of a
	row is decided by, and not as "has a link type": `Sidebar Item.link_type` carries a column
	default, so a section a layer added arrives claiming to be a DocType link to nothing -- and
	nobody but Administrator is allowed to see a DocType called None.
	"""
	if not item.get("added") or not is_linked(item):
		return True

	return is_item_allowed(item.get("link_to"), item.get("link_type"), perm_ctx)


def append_derived_items(items, rows, perm_ctx):
	"""Add `rows` to an already-resolved sidebar, skipping anything it already has.

	These items go through the same shaping and the same permission check as any other row. Once
	they are in the payload they are items like any other; the only difference is that no
	document holds them.

	The skip is what keeps a site that stored these rows before we started working them out
	drawing one link rather than two. The stored row is already in `items`, wherever its
	customization put it, and the worked-out one is the duplicate.
	"""
	if not rows:
		return items

	seen = {item["key"] for item in items}
	for entry in filter_sidebar_items(rows, perm_ctx):
		if entry["key"] in seen:
			continue
		seen.add(entry["key"])
		# Tells the desk this item cannot be rearranged or hidden. No document holds it, so no
		# customization can name it. The desk offers it as a link and nothing more.
		entry["derived"] = 1
		items.append(entry)

	return items


def get_module_landing_route(items: list[dict]) -> str | None:
	"""Where a module's desktop tile leads, as far as the server can work it out.

	The rule is the desk's own (`sidebar.module_landing_route`): a module opens on the first
	item in the sidebar that leads anywhere. So this is given the resolved items -- already
	filtered by permission, already customized -- and not the module's workspaces, which are
	neither.

	Only workspaces are answered here. A workspace route is just a slug, while every other kind
	of item is turned into a route by `frappe.utils.generate_route` on the client, which handles
	doc views, report types and filters as query parameters. The desktop asks the client first
	and falls back to this, so this is the answer a tile has before the sidebar object exists,
	not a second copy of the routing rules.

	It stops at the first item that leads anywhere rather than reading on for a workspace it
	could answer for. A tile is a link with a click handler and the two have to agree: a route
	found further down the sidebar would send a middle-click somewhere an ordinary click never
	goes.
	"""
	item = next((item for item in items or [] if item.get("type") == "Link"), None)
	if not item or item.get("link_type") != "Workspace" or not item.get("link_to"):
		return None

	public = frappe.db.get_value("Workspace", item["link_to"], "public")
	if public is None:
		return None

	prefix = "/desk/" if public else "/desk/private/"
	return prefix + frappe.utils.slug(item["link_to"])
