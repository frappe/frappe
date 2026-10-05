from collections import defaultdict

import click

import frappe
from frappe.desk.doctype.sidebar.sidebar import get_module_base, get_sidebar_bases, item_key
from frappe.patches.v16_0.sidebar_archive import (
	added_row,
	archive_exists,
	baseline_of,
	first_of_each,
	is_custom,
	reference_row,
	site_edits,
	site_rows,
)


def execute():
	"""Carry what a site changed in an app's v16 sidebars into the site's layer over the app's
	sidebar now.

	The app's own changes keep arriving in its `Sidebar`, and the site's sit in a `Custom Sidebar`
	above it, so neither overwrites the other. An edit is told apart from what the app shipped by
	the app's frozen v16 file (`baseline_of`). The old rows are left untouched, so this is safe to
	re-run.
	"""
	if not archive_exists():
		return

	from frappe.desk.doctype.custom_sidebar.custom_sidebar import get_customization

	edits_by_module = defaultdict(list)
	no_baseline = defaultdict(list)
	files = {}
	for row in site_rows():
		if is_custom(row):
			continue

		target = app_sidebar_of(row)
		if not target:
			continue

		baseline = baseline_of(row, files)
		if not baseline:
			no_baseline[row.app or "no app"].append(row.name)
			continue

		if edits := site_edits(row, baseline):
			edits.module, edits.shell = target
			edits_by_module[edits.module].append(edits)

	for app, names in sorted(no_baseline.items()):
		click.secho(
			f"No v16 baseline in {app} for {', '.join(names)}: any site edits to them stay in the archive",
			fg="yellow",
		)

	for module, edits in sorted(edits_by_module.items()):
		# the site has arranged this module since, which is newer than anything v16 holds
		if get_customization(module, None):
			continue

		if write_site_layer(module, sorted(edits, key=lambda edit: edit.row.modified)):
			click.secho(
				f"Module '{module}': kept the site's edits to {', '.join(edit.row.name for edit in edits)}",
				fg="green",
			)
		for edit in edits:
			if edit.left:
				click.secho(
					f"Sidebar '{edit.row.name}': could not keep {', '.join(edit.left)}, which would "
					f"show on the other sidebars of '{module}' too; they stay in the archive",
					fg="yellow",
				)
			if edit.duplicates:
				click.secho(
					f"Sidebar '{edit.row.name}': could not keep "
					f"{', '.join(item.label or item.link_to or item.type for item in edit.duplicates)}, "
					"which repeat another link's target",
					fg="yellow",
				)


def app_sidebar_of(row) -> tuple[str, str | None] | None:
	"""The app sidebar `row` became, as `(module, shell)`: the one of the same title, or else its
	v16 module's own, where `shell` is None. None when the app ships neither, which
	`convert_sidebars` has made a base for."""
	if module := frappe.db.get_value("Sidebar", {"name": row.name, "standard": 1}, "module"):
		return module, row.name
	if row.module and frappe.db.exists("Sidebar", {"module": row.module, "standard": 1}):
		return row.module, None
	return None


def write_site_layer(module: str, edits: list[frappe._dict]) -> bool:
	"""Write the edits as the site's layer over `module`, oldest first so the newest edit to an
	item wins.

	Each edit is compared with the sidebar it came from, which is not always the one named after
	the module.

	It sets the order only where the site reordered (see `arranged_rows`). Everywhere else it
	relabels and hides in place and adds at the end, so the order the app ships keeps applying.

	A module's layer applies to every sidebar in it, so in a module with several, only what cannot
	show on another sidebar is carried: a relabel or hide of an item no other sidebar holds, since a
	row naming an item a sidebar lacks is skipped there. An addition, a change to an item the
	sidebars share, the order and the sidebar's own title and icon would reach them all, so those
	stay in the archive and are named in `edit.left`.
	"""
	bases = get_sidebar_bases([module])
	several = len(bases) > 1

	rows = {}
	for edit in edits:
		own = edit.shell if edit.shell in bases else module if module in bases else next(iter(bases))
		below = first_of_each(bases[own].rows)
		elsewhere = {item_key(item) for shell, base in bases.items() if shell != own for item in base.rows}
		added = {item_key(item) for item in edit.added}

		edit.left = []
		for key, item in first_of_each(edit.row.rows).items():
			if key in added:
				if several:
					edit.left.append(item.label or item.link_to or item.type)
				else:
					rows[key] = added_row(item)
			elif key in below and key in edit.retouched:
				if key in elsewhere:
					edit.left.append(item.label or item.link_to or item.type)
				else:
					rows[key] = reference_row(item, **edit.retouched[key])

		for key in edit.removed:
			if key in below:
				if key in elsewhere:
					edit.left.append(
						below[key].get("label") or below[key].get("link_to") or below[key].get("type")
					)
				else:
					rows[key] = reference_row(below[key], hidden=1)

		if several:
			edit.left += [
				what
				for what, changed in (
					("its order", edit.reordered),
					("its title", edit.title),
					("its icon", edit.header_icon),
				)
				if changed
			]

	reordered = [] if several else [edit for edit in edits if edit.reordered]
	if reordered:
		rows = arranged_rows(module, reordered[-1], rows)

	label = None if several else next((edit.title for edit in reversed(edits) if edit.title), None)
	header_icon = (
		None if several else next((edit.header_icon for edit in reversed(edits) if edit.header_icon), None)
	)
	# every edit named something the app no longer ships, or could not be carried
	if not (rows or label or header_icon):
		return False

	doc = frappe.new_doc("Custom Sidebar")
	doc.module = module
	doc.arranged = int(bool(reordered))
	doc.label = label
	doc.header_icon = header_icon
	for row in rows.values():
		doc.append("sidebar_items", row)
	# the site's rows hold the same dead links its v16 rows did; see `write_base`
	doc.insert(ignore_permissions=True, ignore_links=True)
	return True


def arranged_rows(module: str, edit: frappe._dict, rows: dict) -> dict:
	"""The layer's rows in order, for a module where the site reordered a sidebar.

	An arranged layer names everything it orders. The reordered sidebar's items go in the site's
	v16 order, as one block where the first of them stands in the app's order, and every other
	item keeps the app's order, so one reordered sidebar does not reorder the rest. One order is
	all a layer holds, so the newest reorder wins. What else the edits added or hid follows.

	Every row of an arranged layer states its section: the site's for the block, the app's for the
	rest.
	"""
	below = shell_items(module, edit.shell)
	site = first_of_each(edit.row.rows)
	block = [key for key in site if key in below or key in rows]

	keys = []
	for key in below:
		if key not in block:
			keys.append(key)
		elif not set(block) & set(keys):
			keys.extend(block)
	keys.extend(key for key in block + list(rows) if key not in keys)

	arranged = {}
	for key in keys:
		item = site[key] if key in block else below.get(key)
		row = rows.get(key) or reference_row(item)
		if item is not None and not row.get("hidden"):
			row["child"] = item.get("child")
		arranged[key] = row
	return arranged


def shell_items(module: str, shell: str | None) -> dict:
	"""The app's items in `shell`, or in the module's own sidebar, by identity and in order."""
	return first_of_each(get_module_base(module, shell).rows)
