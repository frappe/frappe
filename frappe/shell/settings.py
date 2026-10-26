# SETTINGS — the settings dialog's panes, merged from every app's `Settings Dialog` record.

# Unfiltered, so one merge can be cached for every user; who sees which pane is decided per
# request, after this. Only the app layer is read: the site and user layers are not built.

import json

import frappe
from frappe.desk.doctype.rail.rail import NO_HOST, SITE_LAYER
from frappe.desk.layers import anchor_attempts, place_by_anchors


def resolve_panes() -> list[dict]:
	"""Every app's panes in run order, each holding its host's blocks and then every extending app's."""
	apps = frappe.get_active_apps(_ensure_on_bench=True)
	records = _shipped_records(apps)
	panes = _rows_by_parent("Settings Pane", records)
	blocks = _rows_by_parent("Settings Block", records)
	installed = _installed_doctypes(blocks)

	resolved = []

	for host in records:
		if host.extends:
			continue

		contributors = [host] + [record for record in records if record.extends == host.app]
		pane_list = [_pane(host.app, row) for row in panes.get(host.name, [])]
		_fill(pane_list, contributors, blocks, installed)
		resolved += [pane for pane in pane_list if pane["blocks"]]

	return resolved


def _fill(pane_list: list[dict], contributors: list, blocks: dict[str, list], installed: set[str]):
	"""Put every contributor's blocks in the host's panes, then move the anchored ones."""
	by_key = {pane["key"]: pane for pane in pane_list}
	anchored: dict[str, list[tuple[dict, list[dict]]]] = {}

	for record in contributors:
		for row in blocks.get(record.name, []):
			pane = by_key.get(row.pane)
			if pane is None or not _binds_installed(row, installed):
				continue

			if any(block["key"] == row.key for block in pane["blocks"]):
				_warn_duplicate(record.app, row, pane)
				continue

			block = _block(record.app, row)
			pane["blocks"].append(block)

			if record.extends and (attempts := _placements(row.anchors)):
				anchored.setdefault(pane["key"], []).append((block, attempts))

	for key, placed in anchored.items():
		_place(by_key[key]["blocks"], placed)


def _place(blocks: list[dict], placed: list[tuple[dict, list[dict]]]):
	"""Move each anchored block to the first `after` or `before` that names a block in the pane."""
	present = {block["key"] for block in blocks}
	place_by_anchors(
		blocks,
		placed,
		key=lambda block: block["key"],
		target_key=lambda _block, name: name if name in present else None,
	)

	# `place_by_anchors` serves nested lists and stamps the row's parent; a pane is flat.
	for block in blocks:
		block.pop("parent_key", None)


def _placements(raw) -> list[dict]:
	"""A block's anchors, keeping only `after` and `before`: a pane's blocks do not nest."""
	return [attempt for attempt in anchor_attempts(raw) if attempt["after"] or attempt["before"]]


def _warn_duplicate(app: str, row, pane: dict):
	frappe.logger("shell").warning(
		f"Settings block {row.key!r} from {app!r} repeats a key in pane {pane['app']}/{pane['key']}; "
		"the block earlier in run order is kept."
	)


# The wire shape


def _pane(app: str, row) -> dict:
	pane = {"app": app, "key": row.key, "label": row.label}

	if row.icon:
		pane["icon"] = row.icon
	if row.description:
		pane["description"] = row.description

	pane["blocks"] = []
	return pane


def _block(app: str, row) -> dict:
	"""One block as the browser gets it: a generated `binding`, or a `component` with named `bindings`."""
	block = {"key": row.key, "app": app, "save_mode": row.save_mode or "auto"}

	if row.label:
		block["label"] = row.label
	if row.description:
		block["description"] = row.description

	if row.binding_type:
		block["binding"] = _binding(row.binding_type, row.document_type, row.name_resolver)
		if fields := _json(row.fields):
			block["fields"] = fields
		return block

	block["component"] = row.component
	if bindings := _json(row.bindings):
		block["bindings"] = {
			name: _binding(binding["type"], binding["doctype"], binding.get("resolver"))
			for name, binding in bindings.items()
		}
	if settings := _json(row.settings):
		block["settings"] = settings

	return block


def _binding(binding_type: str, doctype: str, resolver: str | None) -> dict:
	binding = {"type": binding_type, "doctype": doctype}

	if resolver:
		binding["resolver"] = resolver

	return binding


def _json(raw):
	"""A JSON column the controller already checked on save."""
	return json.loads(raw) if raw else None


# The stored records


def _shipped_records(apps: list[str]) -> list:
	"""The app layer of every active app, in run order; one extending an absent host is skipped."""
	position = {app: index for index, app in enumerate(apps)}
	records = frappe.get_all(
		"Settings Dialog",
		filters={"standard": 1, "user": SITE_LAYER},
		fields=["name", "app", "extends"],
	)

	return sorted(
		(
			record
			for record in records
			if record.app in position and (record.extends == NO_HOST or record.extends in position)
		),
		key=lambda record: position[record.app],
	)


def _rows_by_parent(doctype: str, records: list) -> dict[str, list]:
	if not records:
		return {}

	rows: dict[str, list] = {}

	for row in frappe.get_all(
		doctype,
		filters={"parenttype": "Settings Dialog", "parent": ("in", [record.name for record in records])},
		fields=["*"],
		order_by="parent asc, idx asc",
	):
		rows.setdefault(row.parent, []).append(row)

	return rows


def _installed_doctypes(blocks: dict[str, list]) -> set[str]:
	"""Of the doctypes the blocks bind, the ones this site has."""
	named = {doctype for rows in blocks.values() for row in rows for doctype in _bound_doctypes(row)}
	if not named:
		return set()

	return set(frappe.get_all("DocType", filters={"name": ("in", list(named))}, pluck="name"))


def _binds_installed(row, installed: set[str]) -> bool:
	return all(doctype in installed for doctype in _bound_doctypes(row))


def _bound_doctypes(row) -> list[str]:
	if row.binding_type:
		return [row.document_type]

	return [binding["doctype"] for binding in (_json(row.bindings) or {}).values()]
