# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import hashlib
import json
from collections import Counter, defaultdict

import click

import frappe
from frappe import _
from frappe.desk.desk_views import DeskViews
from frappe.model.document import Document

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

# How boot decides two authored rows are the same item. Reproduced exactly so a merged
# sidebar contains what the desk renders today -- the tables carry duplicates boot filters
# out, and copying rows straight across would surface them.
BOOT_DEDUPE_FIELDS = ("type", "label", "link_type", "link_to")

# The merge reads from `Workspace.sidebar_items` and writes to `Module Sidebar.items`, and the
# two use different child doctypes: the legacy `Workspace Sidebar Item` is left untouched until
# the old store is retired, while `Module Sidebar Item` is the new one carrying `key` and
# `source_workspace`. Rows are copied field by field between them, never re-parented.
WORKSPACE_ITEM_DOCTYPE = "Workspace Sidebar Item"


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
		home_workspace: DF.Link | None
		items: DF.Table[ModuleSidebarItem]
		merged_from: DF.LongText | None
		module: DF.Link
		module_onboarding: DF.Link | None
		standard: DF.Check
		title: DF.Data | None
	# end: auto-generated types

	def validate(self):
		if not self.title:
			self.title = self.module

		self.validate_standard()
		self.validate_home_workspace()
		assign_keys(self.items)
		self.validate_unique_keys()

	def validate_standard(self):
		"""`standard` means "backed by a JSON file in an app", and only developer mode writes
		one. Marking a sidebar standard without being able to export it produces a row that
		`remove_orphan_entities` deletes on the very next `bench migrate` -- a standard record
		whose file is missing is by definition an orphan. Refuse rather than let someone create
		a row that quietly destroys itself.
		"""
		if not self.standard or not self.has_value_changed("standard"):
			return

		if not frappe.conf.developer_mode:
			frappe.throw(
				_("Enable developer mode to make a sidebar standard -- it has to be written to its app.")
			)

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

	def validate_home_workspace(self):
		if not self.home_workspace:
			return

		workspace = frappe.db.get_value("Workspace", self.home_workspace, ["public", "module"], as_dict=True)
		if not workspace:
			return
		if not workspace.public:
			frappe.throw(_("Home Workspace {0} must be public.").format(self.home_workspace))
		if workspace.module and workspace.module != self.module:
			frappe.throw(
				_("Home Workspace {0} belongs to module {1}, not {2}.").format(
					self.home_workspace, workspace.module, self.module
				)
			)

	def validate_unique_keys(self):
		seen = set()
		for item in self.items:
			if item.key in seen:
				frappe.throw(_("Duplicate sidebar item key {0}.").format(item.key))
			seen.add(item.key)

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

	@frappe.whitelist()
	def mark_as_standard(self):
		"""Adopt this sidebar as app-owned content: write it to its module's folder so the app
		ships it, and let `bench migrate` re-import it from there.

		This is the one flag that means anything: standard is app-owned and file-backed,
		everything else belongs to the site -- whether it was merged from workspaces, built
		from the module's contents, or edited by hand here.
		"""
		import os

		if not is_workspace_manager():
			frappe.throw(_("You need to be Workspace Manager to do this."), frappe.PermissionError)

		if self.standard:
			return self

		self.standard = 1
		self.app = get_module_app(self.module)
		self.save()

		# Verify rather than assume. If the export silently did nothing, the row is standard with
		# no file -- an orphan that the next migrate deletes. Raising here rolls the whole thing
		# back, so the failure is loud and now instead of quiet and later.
		if not os.path.exists(self.exported_file_path()):
			frappe.throw(
				_("Could not write {0} to {1}. Left unchanged.").format(
					frappe.bold(self.name), frappe.bold(self.app or "-")
				)
			)

		frappe.msgprint(
			_("{0} is now standard and exported to {1}.").format(
				frappe.bold(self.name), frappe.bold(self.app)
			),
			alert=True,
			indicator="green",
		)
		return self

	@frappe.whitelist()
	def unmark_as_standard(self):
		"""Hand the sidebar back to the site: stop shipping it and remove its exported file.

		The file has to go. Left behind, the next `bench migrate` re-imports it and marks the
		row standard again, so clearing the flag alone would not survive a migrate.
		"""
		import os
		import shutil

		if not is_workspace_manager():
			frappe.throw(_("You need to be Workspace Manager to do this."), frappe.PermissionError)

		if not self.standard:
			return self

		path = None
		if self.module:
			try:
				path = self.exported_file_path()
			except Exception:
				path = None

		self.standard = 0
		self.save()

		if path and os.path.exists(path):
			shutil.rmtree(os.path.dirname(path), ignore_errors=True)

		frappe.msgprint(
			_("{0} is no longer standard; its exported file has been removed.").format(
				frappe.bold(self.name)
			),
			alert=True,
			indicator="orange",
		)
		return self


def derive_key(item, counter: Counter) -> str:
	"""Stable identity for a sidebar item, used to anchor per-user customization.

	Deliberately excludes `label`, so an app author renaming an item does not orphan every
	user's delta. The cost is that items differing only by label collide -- a Section Break
	carries nothing else at all -- so an ordinal suffix separates them within a parent.

	Consequence worth knowing: renaming a section preserves deltas (the point), but
	inserting or deleting one re-anchors the deltas of every section after it. An author who
	needs stability across a reshuffle sets `key` explicitly on the row; that pin wins and
	this derivation is only the fallback.

	Pure, so re-importing the same JSON regenerates the same keys even though the child rows
	are hash-named and recreated on every import. That is the entire reason the field exists.
	"""
	base = "|".join(
		[
			item.get("type") or "",
			item.get("link_type") or "",
			item.get("link_to") or "",
			item.get("url") or "",
		]
	)
	ordinal = counter[base]
	counter[base] += 1
	return f"{hashlib.sha1(base.encode()).hexdigest()[:10]}-{ordinal}"


def assign_keys(items):
	"""Fill in `key` on any row lacking one. An explicitly authored key is left alone."""
	counter = Counter()
	pinned = {item.key for item in items if item.get("key")}

	for item in items:
		if item.get("key"):
			continue
		key = derive_key(item, counter)
		# A derived key must never collide with an author's pin.
		while key in pinned:
			key = derive_key(item, counter)
		item.key = key


def boot_dedupe_key(item) -> tuple:
	return tuple(item.get(field) for field in BOOT_DEDUPE_FIELDS)


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
			"module_onboarding",
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

	Deduped on boot's key across the whole merged list, which drops both the duplicate rows
	the desk already hides and the genuine overlap between two workspaces of one module.
	Including `label` in that key is what preserves deliberate duplicates, such as a doctype
	deliberately listed under two different sections.
	"""
	merged = []
	seen = set()

	def take(item, source: str, force_child=False):
		key = boot_dedupe_key(item)
		if key in seen:
			return
		seen.add(key)
		row = {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS}
		row["source_workspace"] = source
		# An authored key is a pin and must survive the merge; a derived one is re-derived
		# over the merged list, where the ordinals differ.
		if item.get("key"):
			row["key"] = item.get("key")
		if force_child:
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
		seen.add(boot_dedupe_key(frappe._dict(section)))
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
			"home_workspace": primary.name,
			"module_onboarding": next(
				(ws.module_onboarding for ws in workspaces if ws.module_onboarding), None
			),
			"app": get_module_app(module),
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


def get_module_app(module: str) -> str | None:
	"""The app owning `module`, tolerating a Module Def that exists only in the DB."""
	app = frappe.local.module_app.get(frappe.scrub(module))
	return app or frappe.db.get_value("Module Def", module, "app_name")


def is_workspace_manager() -> bool:
	return "Workspace Manager" in frappe.get_roles()


# ---------------------------------------------------------------------------------------
# Generated sidebars -- the other half of "1:1 with Module Def"
# ---------------------------------------------------------------------------------------

# A sidebar built from a module's contents is a real row now, not a throwaway assembled at
# boot, so it can afford to list more than the three doctypes the old in-memory fallback
# showed. Per-user hide deltas trim it from there.
GENERATED_DOCTYPE_LIMIT = 15


def sync_module_sidebars(module: str | None = None) -> list[str]:
	"""Give every Module Def a `Module Sidebar`, building one from the module's contents.

	Idempotent, and never touches a row that already exists -- so an authored sidebar, or one
	a user has since edited, is safe. Returns the modules it created rows for.
	"""
	filters = {"name": module} if module else {}
	modules = frappe.get_all("Module Def", filters=filters, pluck="name")
	existing = set(frappe.get_all("Module Sidebar", pluck="module"))

	created = []
	for module_name in modules:
		if module_name in existing:
			continue
		try:
			doc = frappe.new_doc("Module Sidebar")
			doc.module = module_name
			doc.title = module_name
			doc.header_icon = "hammer"
			doc.standard = 0
			doc.app = get_module_app(module_name)
			for item in generate_items(module_name):
				doc.append("items", item)
			doc.insert(ignore_permissions=True)
			created.append(module_name)
		except frappe.DoesNotExistError:
			continue

	return created


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

	module_info["DocType"] = (module_info.get("DocType") or [])[:GENERATED_DOCTYPE_LIMIT]
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
# Build entry point -- shared by the patch, migrate, and the dry run
# ---------------------------------------------------------------------------------------


def build_all(dry_run: bool = False) -> dict:
	"""Merge every module's authored sidebars into one `Module Sidebar` each, then generate
	the rest.

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
					"home_workspace",
					"module_onboarding",
					"app",
					"standard",
					"merged_from",
				)
			}
		)
		for item in plan["items"]:
			doc.append("items", item)
		doc.insert(ignore_permissions=True)

	generated = []
	if dry_run:
		covered = existing | set(by_module)
		generated = [m for m in frappe.get_all("Module Def", pluck="name") if m not in covered]
	else:
		generated = sync_module_sidebars()

	return {"merged": merged, "generated": generated, "skipped": skipped}


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

	click.secho(f"\nGenerated (module ships no sidebar): {len(result['generated'])}", bold=True)
	click.echo("  " + ", ".join(result["generated"][:20]) + (" ..." if len(result["generated"]) > 20 else ""))

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
	click.echo(f"  modules getting a generated row : {len(result['generated'])}")
	click.echo("")
