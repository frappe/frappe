"""Reading the v16 sidebar archive, and writing what comes out of it.

Shared by the patches that convert it, one per kind of row the archive holds:

	convert_sidebars                 an app's standard rows, where the app ships no sidebar now
	carry_standard_sidebar_edits     what a site changed in an app's rows, as the site's layer
	convert_custom_sidebars          a site's own public sidebars, each into a module of its own
	move_custom_sidebar_workspaces   the workspace a custom sidebar opened on, into that module
	convert_personal_sidebars        a user's forked copy, into their `Custom Sidebar`

Not a patch itself, so it is not listed in `patches.txt`.
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
	"""A sidebar the site made: v16 marked an app's own rows standard and named the app."""
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
	"""The module now holding the v16 sidebar `title`.

	Either the one it was converted into, or the module of the app's own sidebar of that title,
	which is where an app that reorganised its modules moved it: hrms's `Expenses` was under `HR`
	in v16 and is a module of its own now.
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

	return shape_rows(rows, spacer_scope or sidebar)


def shape_rows(rows: list[frappe._dict], scope: str) -> list[frappe._dict]:
	"""v16 rows in the shape they are converted in. The archive and the v16 files go through the
	same shaping, so the same row reads the same from either."""
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
			row.label = f"Spacer {spacers} {hashlib.sha1(scope.encode()).hexdigest()[:10]}"
		options_as_filters(row)
		items.append(row)

	return items


def baseline_of(row, files: dict | None = None) -> frappe._dict | None:
	"""The v16 file `row` was imported from, as the app's last v16 release shipped it.

	An app keeps its `workspace_sidebar/` folder frozen for this (see its README). A row with no
	file there has nothing to be compared against.
	"""
	if not row.app or row.app not in frappe.get_installed_apps():
		return None

	# read once per app for the whole run, rather than once per row
	files = {} if files is None else files
	if row.app not in files:
		files[row.app] = v16_files(row.app)

	fixture = files[row.app].get(row.name)
	if not fixture:
		return None

	return frappe._dict(
		fixture, rows=shape_rows([frappe._dict(item) for item in fixture.get("items") or []], row.name)
	)


def v16_files(app: str) -> dict[str, dict]:
	"""The app's frozen v16 sidebar files, by the name each one carries."""
	from frappe.modules.utils import get_app_level_files

	by_name = {}
	for path in get_app_level_files("workspace_sidebar", app):
		if not path.endswith(".json"):
			continue
		# an installed app's own folder, not anything from a request
		with open(path, encoding="utf-8") as f:  # nosemgrep
			fixture = frappe._dict(json.load(f))
		by_name[fixture.name or fixture.title] = fixture
	return by_name


# Per item, what a site layer can carry besides membership and order.
RETOUCHABLE_FIELDS = ("label", "icon")


def site_edits(row, baseline) -> frappe._dict | None:
	"""What the site changed in `row` since the app shipped it, or None when it changed nothing.

	Items are matched by identity (`item_key`), so a changed target or filter reads as one item
	removed and another added.
	"""
	shipped = first_of_each(baseline.rows)
	shipped_labels = {(item_key(item), item.label) for item in baseline.rows}
	kept = first_of_each(row.rows)

	retouched = {}
	for key, item in kept.items():
		if key not in shipped:
			continue
		changes = {
			field: item.get(field)
			for field in RETOUCHABLE_FIELDS
			if (item.get(field) or None) != (shipped[key].get(field) or None)
		}
		if changes:
			retouched[key] = changes

	edits = frappe._dict(
		row=row,
		# a second link the site added with the same identity as another, differing only in what
		# identity leaves out, such as `route_options`: a sidebar holds one, so it cannot be carried.
		# The app's own v16 files repeat links too, and those are not the site's.
		duplicates=[
			item
			for item in row.rows
			if kept[item_key(item)] is not item and (item_key(item), item.label) not in shipped_labels
		],
		added=[item for key, item in kept.items() if key not in shipped],
		removed=[key for key in shipped if key not in kept],
		retouched=retouched,
		reordered=[key for key in shipped if key in kept] != [key for key in kept if key in shipped],
		title=row.title if (row.title or None) != (baseline.title or None) else None,
		header_icon=row.icon if (row.icon or None) != (baseline.header_icon or None) else None,
	)
	changed = edits.added or edits.removed or edits.retouched or edits.reordered
	return edits if changed or edits.title or edits.header_icon or edits.duplicates else None


def first_of_each(items: list) -> dict:
	"""Items by identity, the first occurrence of each, which is the one the desk shows."""
	by_key = {}
	for item in items:
		by_key.setdefault(item_key(item), item)
	return by_key


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
		rows.append(reference_row(item, added=0) if item_key(item) in below_keys else added_row(item))

	for item in below:
		key = item_key(item)
		if key in kept or key not in (dropped or ()):
			continue
		rows.append(reference_row(item, hidden=1))

	return rows


def reference_row(item, **fields) -> dict:
	"""A layer row naming an item below it, with whatever `fields` the layer says about it.

	A linked item is named by its own columns, an unlinked one by its key.
	"""
	row = {field: item.get(field) for field in LINKED_IDENTITY_FIELDS}
	row["key"] = None if is_linked(item) else item_key(item)
	row.update(fields)
	return row


def added_row(item) -> dict:
	"""A layer row holding an item nothing below has, whole."""
	row = {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS}
	row["key"] = None if is_linked(item) else item_key(item)
	row["added"] = 1
	return row
