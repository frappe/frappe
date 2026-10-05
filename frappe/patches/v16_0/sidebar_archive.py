"""Helpers for the patches that turn v16 sidebars into v17 ones.

v16 kept every sidebar as a `Workspace Sidebar` row. These rows are now read only during the
upgrade, by four patches that each handle one kind of row:

	convert_sidebars                 an app's sidebar that the app no longer ships
	convert_custom_sidebars          a sidebar the site made, which becomes a custom module
	move_custom_sidebar_workspaces   that sidebar's workspace, which moves into the new module
	convert_personal_sidebars        a user's personal copy, which becomes their `Custom Sidebar`

This file is not a patch, so it is not listed in `patches.txt`.
"""

import hashlib
import json
from collections import defaultdict

import frappe
from frappe.desk.doctype.sidebar.sidebar import (
	LINKED_IDENTITY_FIELDS,
	SIDEBAR_ITEM_FIELDS,
	is_linked,
	item_key,
	majority_module_of,
	options_as_filters,
	routable_title,
)

# The v16 sidebar store. Nothing reads or writes it at runtime any more; these patches only read.
ARCHIVE_DOCTYPE = "Workspace Sidebar"
ARCHIVE_ITEM_DOCTYPE = "Workspace Sidebar Item"

# v16 hung a user's private workspaces off a sidebar titled "My Workspaces". Nothing in it was
# authored and those links are derived on read now, so it is skipped rather than converted.
PRIVATE_CONTAINER_TITLE = "my workspaces"


def archive_exists() -> bool:
	return bool(frappe.db.exists("DocType", ARCHIVE_DOCTYPE))


def site_rows() -> list[frappe._dict]:
	"""The archive's site-level rows, with their items, minus the private containers.

	`module` is what the row said, or else the module most of its links point at.
	"""
	rows = frappe.get_all(
		ARCHIVE_DOCTYPE,
		filters={"for_user": ["is", "not set"]},
		fields=["name", "title", "module", "app", "standard", "header_icon as icon", "creation", "modified"],
		order_by="creation asc",
	)

	converted = []
	for row in rows:
		if is_private_container(row):
			continue

		row.rows = archive_items(row.name)
		# the archive has no `sequence_id`; the `creation` order stands in for it
		row.sequence_id = 0
		row.module = row.module or majority_module_of(row.rows)
		if row.rows:
			converted.append(row)

	return converted


def is_custom(row) -> bool:
	"""Whether the site made this sidebar itself.

	When v16 imported a sidebar from an app, it set `standard` and `app` on the row. A row with
	neither was made on the site.
	"""
	return not row.standard and not row.app


def converted_module_of(title: str) -> str | None:
	"""The module the v16 sidebar `title` was converted into on its own, as `merged_from` records.

	Compared as JSON rather than as text, so a `merged_from` written with other spacing still
	matches.
	"""
	return next(iter(modules_converted_from(title)), None)


def modules_converted_from(title: str) -> list[str]:
	"""Every module holding a sidebar converted from the v16 sidebar `title` alone, oldest first."""
	return [
		sidebar.module
		for sidebar in frappe.get_all(
			"Sidebar", filters={"standard": 0}, fields=["module", "merged_from"], order_by="creation asc"
		)
		if parse_json_list(sidebar.merged_from) == [title]
	]


def custom_module_of(title: str) -> str | None:
	"""The custom module a site's own v16 sidebar `title` became, if it has become one.

	Only a custom module counts: a sidebar converted alone into an app's module is a base, not a
	custom sidebar's home.
	"""
	return next(
		(
			module
			for module in modules_converted_from(title)
			if frappe.db.get_value("Module Def", module, "custom")
		),
		None,
	)


def parse_json_list(value: str | None) -> list:
	try:
		parsed = json.loads(value or "[]")
	except ValueError:
		return []
	return parsed if isinstance(parsed, list) else []


def module_holding(title: str) -> str | None:
	"""The module the v16 sidebar `title` lives in now.

	That is the module it was converted into, or else the module of the app's sidebar with the
	same title. The second covers an app that moved a sidebar: if `Books` was under `Library` in
	v16 and the app now ships it under `Catalog`, this returns `Catalog`.
	"""
	return converted_module_of(title) or frappe.db.get_value("Sidebar", title, "module")


def is_private_container(sidebar) -> bool:
	return PRIVATE_CONTAINER_TITLE in (sidebar.title or sidebar.name or "").lower()


def is_module(module: str | None) -> bool:
	"""Return whether the site still has this module. A sidebar outlives the app that authored
	it."""
	return bool(module) and bool(frappe.db.exists("Module Def", module))


def archive_items(sidebar: str, spacer_scope: str | None = None) -> list[frappe._dict]:
	rows = frappe.get_all(
		ARCHIVE_ITEM_DOCTYPE,
		filters={"parenttype": ARCHIVE_DOCTYPE, "parentfield": "items", "parent": sidebar},
		# no `key`: only `Sidebar Item` carries one
		fields=["name", "idx", *SIDEBAR_ITEM_FIELDS],
		order_by="idx asc",
	)

	scope = hashlib.sha1((spacer_scope or sidebar).encode()).hexdigest()[:10]
	items = []
	spacers = 0
	for row in rows:
		# v16's report-group button; its doctype is gone and nothing draws the row now
		if row.type == "Sidebar Item Group":
			continue
		# an unlinked row is keyed by type and label, and a module's sidebars are merged, so an
		# unnamed spacer needs a label no other sidebar's spacer can share. The sidebar is hashed
		# because its title alone can fill the label's 140 characters.
		if row.type == "Spacer" and not row.label:
			spacers += 1
			row.label = f"Spacer {spacers} {scope}"
		options_as_filters(row)
		items.append(row)

	return items


def by_module(rows: list[frappe._dict]) -> dict[str, list[frappe._dict]]:
	grouped = defaultdict(list)
	for row in rows:
		grouped[row.module].append(row)
	return grouped


def written_as_of(sources: list[frappe._dict]):
	"""When v16 last wrote any of these rows."""
	return max(source.modified for source in sources)


def write_base(module: str, plan, as_of) -> None:
	"""Write the merged list as the module's base sidebar."""
	doc = frappe.new_doc("Sidebar")
	doc.module = module
	# the site's own name for the module: one sidebar keeps its workspace's title, a merge of
	# several takes the module name.
	#
	# A v16 title was free text, and a title is a segment of the desk URL now, so one that cannot
	# be -- `Buying / Selling`, or one slugging like another shell -- is repaired rather than
	# inserted as it stands. `insert` would refuse it, and one label must not abort a migrate
	# any more than one dead link may (see below).
	doc.title = routable_title(plan["title"], module)
	doc.header_icon = plan["header_icon"]
	doc.standard = 0
	doc.merged_from = plan["merged_from"]
	# no `app`: nothing here came from an app's file
	for item in plan["items"]:
		doc.append("items", {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS})

	# `ignore_links`, because these rows are the site's, not ours. A v16 site has been
	# accumulating them for two release lines, and some of them point at things that are gone:
	# erpnext's shipped v16 sidebars still name `Repost Accounting Ledger Settings`, a doctype it
	# deleted in April, and an uninstalled app leaves the same kind of row behind. Validating them
	# would let one dead link abort the whole migrate, and the item is worth more carried than
	# dropped -- it is a broken link on a sidebar, which the user can see and remove, rather than a
	# customer stuck partway through `bench update`.
	doc.insert(ignore_permissions=True, ignore_links=True)

	# Stamped with what it was converted from, not with today: `import_file` skips a file older
	# than the row it overwrites, so a row stamped `now` would keep the app's own sidebar out.
	frappe.db.set_value("Sidebar", doc.name, "modified", as_of, update_modified=False)


def write_user_layer(module: str, user: str, rows: list[dict]) -> None:
	"""Store one person's arrangement of `module`'s sidebar, over whatever its base is.

	No title or icon: a fork only carries v16's names, and that shouldn't rename the module.
	"""
	doc = frappe.new_doc("Custom Sidebar")
	doc.module = module
	doc.user = user
	for row in rows:
		doc.append("sidebar_items", row)
	# Same reason as `write_base`: a fork is the site's data too, and holds the same dead links.
	doc.insert(ignore_permissions=True, ignore_links=True)


def layer_rows(items: list[dict], below: list, dropped: set[str] | None = None) -> list[dict]:
	"""The merged list, expressed as a delta on what sits below it.

	An item already below is stored as a reference, so its label and link stay live; a new one is
	stored whole; a dropped one is stored hidden.
	"""
	below_keys = {item_key(row) for row in below}
	kept = {item_key(item) for item in items}

	rows = []
	for item in items:
		key = item_key(item)
		added = key not in below_keys
		row = {field: item.get(field) for field in (SIDEBAR_ITEM_FIELDS if added else LINKED_IDENTITY_FIELDS)}
		# an unlinked row is named by its key; a linked one is named by its own columns
		row["key"] = None if is_linked(item) else key
		row["added"] = int(added)
		rows.append(row)

	for item in below:
		key = item_key(item)
		if key in kept or key not in (dropped or ()):
			continue
		row = {field: item.get(field) for field in LINKED_IDENTITY_FIELDS}
		row["key"] = None if is_linked(item) else key
		row["hidden"] = 1
		rows.append(row)

	return rows
