from collections import defaultdict

import click

import frappe
from frappe.desk.doctype.sidebar.sidebar import (
	LINKED_IDENTITY_FIELDS,
	SIDEBAR_ITEM_FIELDS,
	build_sidebar,
	get_sidebar_bases,
	is_linked,
	item_key,
	majority_module_of,
)

# The v16 sidebar store. Nothing reads or writes it at runtime any more; this patch only reads.
ARCHIVE_DOCTYPE = "Workspace Sidebar"
ARCHIVE_ITEM_DOCTYPE = "Workspace Sidebar Item"

# v16 hung a user's private workspaces off a sidebar titled "My Workspaces". Nothing in it was
# authored and those links are derived on read now, so it is skipped rather than converted.
PRIVATE_CONTAINER_TITLE = "my workspaces"


def execute():
	"""Carry every sidebar a v16 site holds into the documents that hold one now.

	Site-level rows become each module's `Sidebar`; a user's forked copy becomes their
	`Custom Sidebar`. The old rows are left untouched, so this is safe to re-run.
	"""
	if not frappe.db.exists("DocType", ARCHIVE_DOCTYPE):
		return

	converted = convert_site_sidebars()
	forks = convert_forks()

	if converted or forks:
		click.secho(
			f"Sidebars: {len(converted)} module(s) carried over, {len(forks)} personal arrangement(s) kept.",
			fg="green",
		)


# ---------------------------------------------------------------------------------------
# The base -- what this site showed everybody
# ---------------------------------------------------------------------------------------


def convert_site_sidebars() -> list[str]:
	"""Merge each module's site-level rows into one `Sidebar`, unless the module already has one."""
	converted = []
	for module, sources in sorted(site_sources().items()):
		# a sidebar already there is the current statement about this module, whoever made it
		if frappe.db.exists("Sidebar", {"module": module}):
			continue

		plan = build_sidebar(module, sources)
		write_base(module, plan, written_as_of(sources))
		converted.append(module)

		if plan["secondaries"]:
			click.secho(
				f"Module '{module}': merged {plan['primary']} <- {', '.join(plan['secondaries'])}",
				fg="yellow",
			)

	return converted


def write_base(module: str, plan, as_of) -> None:
	"""Write the merged list as the module's base sidebar."""
	doc = frappe.new_doc("Sidebar")
	doc.module = module
	# the site's own name for the module: one sidebar keeps its workspace's title, a merge of
	# several takes the module name
	doc.title = plan["title"]
	doc.header_icon = plan["header_icon"]
	doc.standard = 0
	doc.merged_from = plan["merged_from"]
	# no `app`: nothing here came from an app's file
	for item in plan["items"]:
		doc.append("items", {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS})
	doc.insert(ignore_permissions=True)

	# Stamped with what it was converted from, not with today: `import_file` skips a file older
	# than the row it overwrites, so a row stamped `now` would keep the app's own sidebar out.
	frappe.db.set_value("Sidebar", doc.name, "modified", as_of, update_modified=False)


def written_as_of(sources: list[frappe._dict]):
	"""When v16 last wrote any of these rows."""
	return max(source.modified for source in sources)


def site_sources() -> dict[str, list[frappe._dict]]:
	"""The archive's site-level rows, grouped by the module each belongs to."""
	rows = frappe.get_all(
		ARCHIVE_DOCTYPE,
		filters={"for_user": ["is", "not set"]},
		fields=["name", "title", "module", "header_icon as icon", "creation", "modified"],
		order_by="creation asc",
	)

	by_module = defaultdict(list)
	for row in rows:
		if is_private_container(row):
			continue

		row.rows = archive_items(row.name)
		# the archive has no `sequence_id`; the `creation` order stands in for it
		row.sequence_id = 0
		module = row.module or majority_module_of(row.rows)
		if not row.rows or not is_module(module):
			continue

		by_module[module].append(row)

	return by_module


# ---------------------------------------------------------------------------------------
# User layers -- what one person did to what everybody was shown
# ---------------------------------------------------------------------------------------


def convert_forks() -> list[tuple[str, str]]:
	"""Turn every fork into a `Custom Sidebar` for the person who made it."""
	from frappe.desk.doctype.custom_sidebar.custom_sidebar import get_customization

	converted = []
	for (user, module), forks in sorted(forks_by_owner().items()):
		if get_customization(module, user):
			continue

		plan = build_sidebar(module, forks)
		write_user_layer(
			module,
			user,
			layer_rows(plan["items"], arrangement_below(module), dropped_keys(forks, plan["items"])),
		)
		converted.append((user, module))

		click.secho(
			f"Module '{module}': kept {user}'s own arrangement from {', '.join(f.name for f in forks)}",
			fg="green",
		)

	return converted


def forks_by_owner() -> dict[tuple[str, str], list[frappe._dict]]:
	"""Every convertible fork, grouped by the person and module it belongs to.

	One group per `(user, module)`: v16 forked per workspace sidebar, so one person can hold
	several arrangements that now have a single layer to become. They are merged, not made to compete.
	"""
	forks = frappe.get_all(
		ARCHIVE_DOCTYPE,
		filters={"for_user": ["is", "set"]},
		fields=["name", "title", "module", "header_icon as icon", "for_user", "creation"],
		order_by="creation asc",
	)

	by_owner = defaultdict(list)
	for fork in forks:
		if is_private_container(fork):
			continue

		fork.rows = archive_items(fork.name)
		fork.sequence_id = 0
		fork.source = source_of(fork)
		fork.title = fork.source or fork.title

		module = fork.module or majority_module_of(fork.rows)
		# a fork with no owner, no module or no rows has no layer to become; left in the archive
		if not fork.rows or not is_module(module):
			continue
		if not frappe.db.exists("User", fork.for_user):
			continue

		by_owner[(fork.for_user, module)].append(fork)

	return by_owner


def source_of(fork) -> str | None:
	"""The sidebar this fork was copied from -- v16 named a fork `<sidebar>-<user>`.

	Worth recovering: it is the list the person was actually looking at when they rearranged it.
	"""
	title = fork.title or fork.name
	source = title.removesuffix(f"-{fork.for_user}")
	if source == title:
		return None

	return source if frappe.db.exists(ARCHIVE_DOCTYPE, source) else None


def arrangement_below(module: str) -> list:
	"""The module's base sidebar, which a person's layer is laid over.

	Read after the base pass, so items that exist in both are stored as references and stay live.
	"""
	return get_sidebar_bases([module])[module].rows


def dropped_keys(forks: list[frappe._dict], items: list[dict]) -> set[str]:
	"""What this person took out, as opposed to what they were never offered.

	Only items the source sidebar showed them can count as removed; anything the module has
	gained since is new to them, not something they hid.
	"""
	kept = {item_key(item) for item in items}
	offered = {item_key(row) for fork in forks if fork.source for row in archive_items(fork.source)}
	return offered - kept


# ---------------------------------------------------------------------------------------
# Reading the archive, and writing what comes out of it
# ---------------------------------------------------------------------------------------


def is_private_container(sidebar) -> bool:
	return PRIVATE_CONTAINER_TITLE in (sidebar.title or sidebar.name or "").lower()


def is_module(module: str | None) -> bool:
	"""Whether the site still has this module -- a sidebar outlives the app that authored it."""
	return bool(module) and bool(frappe.db.exists("Module Def", module))


def archive_items(sidebar: str) -> list[frappe._dict]:
	return frappe.get_all(
		ARCHIVE_ITEM_DOCTYPE,
		filters={"parenttype": ARCHIVE_DOCTYPE, "parentfield": "items", "parent": sidebar},
		# no `key`: only `Sidebar Item` carries one
		fields=["name", "idx", *SIDEBAR_ITEM_FIELDS],
		order_by="idx asc",
	)


def write_user_layer(module: str, user: str, rows: list[dict]) -> None:
	"""Store one person's arrangement of `module`'s sidebar, over whatever its base is.

	No title or icon: a fork only carries v16's names, and that shouldn't rename the module.
	"""
	doc = frappe.new_doc("Custom Sidebar")
	doc.module = module
	doc.user = user
	for row in rows:
		doc.append("sidebar_items", row)
	doc.insert(ignore_permissions=True)


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
