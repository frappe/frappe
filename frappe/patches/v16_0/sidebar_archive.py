"""Helpers shared by the patches that turn a v16 site's `Workspace Sidebar` rows into v17 sidebars,
one patch per kind of row:

	convert_sidebars                 app rows the app no longer ships a sidebar for
	convert_custom_sidebars          a site's own sidebars, into a custom module each
	move_custom_sidebar_workspaces   the workspace such a sidebar opened on, into that module
	convert_personal_sidebars        a user's personal copy, into their `Custom Sidebar`
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
	"""The site-level v16 rows with their items, skipping "My Workspaces"."""
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
	"""Whether the site made this sidebar: v16 set `standard` and `app` on an app's rows."""
	return not row.standard and not row.app


def converted_module_of(title: str) -> str | None:
	"""The module the v16 sidebar `title` was converted into on its own."""
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
	"""The custom module a site's own v16 sidebar `title` became, if any."""
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
	"""The module the v16 sidebar `title` lives in now, following an app that moved it."""
	return converted_module_of(title) or frappe.db.get_value("Sidebar", title, "module")


def is_private_container(sidebar) -> bool:
	return PRIVATE_CONTAINER_TITLE in (sidebar.title or sidebar.name or "").lower()


def is_module(module: str | None) -> bool:
	"""Whether the site still has this module."""
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
		# a spacer is keyed by its label, so each needs one no other sidebar's spacer shares
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
	# a title is a URL segment now, so one like `Buying / Selling` is repaired rather than refused
	doc.title = routable_title(plan["title"], module)
	doc.header_icon = plan["header_icon"]
	doc.standard = 0
	doc.merged_from = plan["merged_from"]
	# no `app`: nothing here came from an app's file
	for item in plan["items"]:
		doc.append("items", {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS})

	# a v16 row can point at something since deleted, and one dead link must not stop the migrate
	doc.insert(ignore_permissions=True, ignore_links=True)

	# dated as v16 last wrote it, or `import_file` would skip the app's own sidebar as older
	frappe.db.set_value("Sidebar", doc.name, "modified", as_of, update_modified=False)


def write_user_layer(module: str, user: str, rows: list[dict]) -> None:
	"""Store one user's arrangement of `module`'s sidebar, without renaming it."""
	doc = frappe.new_doc("Custom Sidebar")
	doc.module = module
	doc.user = user
	for row in rows:
		doc.append("sidebar_items", row)
	# the same dead links as `write_base`
	doc.insert(ignore_permissions=True, ignore_links=True)


def layer_rows(items: list[dict], below: list, dropped: set[str] | None = None) -> list[dict]:
	"""`items` as a layer over `below`: kept items by reference, new ones whole, dropped ones hidden."""
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
