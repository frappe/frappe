# SETTINGS — the settings dialog's panes, merged from every app's `Settings Dialog` record.

# Unfiltered, so one merge can be cached for every user; who sees which pane is decided per
# request, after this. Only the app layer is read: the site and user layers are not built.

import json

import frappe
from frappe import _
from frappe.desk.doctype.rail.rail import NO_HOST, SITE_LAYER
from frappe.desk.layers import anchor_attempts, place_by_anchors
from frappe.query_builder.functions import Count, Max

from .boot import report_oversized_keys
from .doctypes import metadata_version
from .permissions import may_enter_any_prefix
from .settings_filter import SettingsFilter

PANES_CACHE_KEY = "shell_settings_panes"


@frappe.whitelist(methods=["GET"])
def get_panes() -> dict:
	"""The panes this user may see and their search label index, read when the dialog first opens."""
	if not may_enter_any_prefix():
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	visible = SettingsFilter().filter(get_cached_panes())
	report_oversized_keys(visible, None, reply="settings")
	return visible


def get_cached_panes() -> list[dict]:
	"""The merged, unfiltered panes, cached on `metadata_version` and the stored records' own stamp."""
	# The stamp is read in the merge's transaction and before it, so a merge of old rows never carries
	# a current stamp, whatever snapshot the request began with.
	version = f"{metadata_version()}:{_records_stamp()}"
	cached = frappe.client_cache.get_value(PANES_CACHE_KEY)

	if isinstance(cached, dict) and cached.get("version") == version:
		return cached["panes"]

	panes = resolve_panes()
	frappe.client_cache.set_value(PANES_CACHE_KEY, {"version": version, "panes": panes})
	return panes


def _records_stamp() -> str:
	"""How many `Settings Dialog` records there are and when one last changed; a save or delete moves it."""
	table = frappe.qb.DocType("Settings Dialog")
	count, modified = frappe.qb.from_(table).select(Count("*"), Max(table.modified)).run()[0]
	return f"{count}:{modified}"


def resolve_panes() -> list[dict]:
	"""Every app's panes in run order, each holding its host's blocks and then every extending app's."""
	apps = frappe.get_active_apps(_ensure_on_bench=True)
	records = _shipped_records(apps)
	panes = _rows_by_parent("Settings Pane", records)
	blocks = _readable_blocks(records)
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
		for row, block in blocks.get(record.name, []):
			pane = by_key.get(row.pane)
			if pane is None or not all(doctype in installed for doctype in _bound_doctypes(block)):
				continue

			if any(other["key"] == block["key"] for other in pane["blocks"]):
				_warn(
					f"block {row.key!r} from {record.app!r} repeats a key in pane {pane['app']}/{pane['key']}"
				)
				continue

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
	"""A block's anchors as `after` or `before` only: a pane's blocks do not nest."""
	return [
		{**attempt, "parent_key": None}
		for attempt in anchor_attempts(raw)
		if isinstance(attempt["after"] or attempt["before"], str)
	]


def _warn(problem: str):
	frappe.logger("shell").warning(f"Settings {problem}; the block is left out of the settings dialog.")


# The wire shape


def _pane(app: str, row) -> dict:
	pane = {"app": app, "key": row.key, "label": row.label}

	if row.icon:
		pane["icon"] = row.icon
	if row.description:
		pane["description"] = row.description

	pane["blocks"] = []
	return pane


def _block(app: str, row) -> dict | None:
	"""One block as the browser gets it, or None when a JSON column will not read."""
	# Migrate imports a shipped record without `validate`, so a hand-edited file arrives unchecked.
	block = {"key": row.key, "app": app, "save_mode": row.save_mode or "auto"}

	if row.label:
		block["label"] = row.label
	if row.description:
		block["description"] = row.description

	if row.binding_type:
		block["binding"] = _binding(
			{"type": row.binding_type, "doctype": row.document_type, "resolver": row.name_resolver}
		)
		block["fields"] = _json(row.fields, list, str)
		readable = block["binding"] is not None and block["fields"] is not None
	else:
		block["component"] = row.component
		bindings = _json(row.bindings, dict)
		block["bindings"] = bindings and {name: _binding(spec) for name, spec in bindings.items()}
		block["settings"] = _search_settings(row.settings)
		readable = (
			bool(row.component)
			and bindings is not None
			and None not in block["bindings"].values()
			and block["settings"] is not None
		)

	if not readable:
		return None

	return {field: value for field, value in block.items() if value or field == "key"}


def _binding(spec) -> dict | None:
	if not isinstance(spec, dict) or not spec.get("type") or not spec.get("doctype"):
		return None

	binding = {field: spec[field] for field in ("type", "doctype", "resolver") if spec.get(field)}
	return binding if all(isinstance(value, str) for value in binding.values()) else None


def _json(raw, shape: type, item: type | None = None):
	"""The column's value, its empty shape when blank, or None when it is not that shape of `item`s."""
	try:
		value = json.loads(raw) if raw else shape()
	except (TypeError, ValueError):
		return None

	if not isinstance(value, shape) or (item and not all(isinstance(entry, item) for entry in value)):
		return None

	return value


def _search_settings(raw) -> list | None:
	"""A component block's `settings`, each a dict with a string label, as save checks them."""
	settings = _json(raw, list, dict)
	if settings is None or not all(isinstance(setting.get("label"), str) for setting in settings):
		return None

	return settings


def _bound_doctypes(block: dict) -> list[str]:
	if "binding" in block:
		return [block["binding"]["doctype"]]

	return [binding["doctype"] for binding in block.get("bindings", {}).values()]


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


def _readable_blocks(records: list) -> dict[str, list[tuple]]:
	"""Each record's block rows with their wire shape; a row that will not read is logged and left out."""
	app_of = {record.name: record.app for record in records}
	readable: dict[str, list[tuple]] = {}

	for parent, rows in _rows_by_parent("Settings Block", records).items():
		for row in rows:
			block = _block(app_of[parent], row)
			if block is None:
				_warn(f"block {row.key!r} from {app_of[parent]!r} holds JSON that will not read")
				continue
			readable.setdefault(parent, []).append((row, block))

	return readable


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


def _installed_doctypes(blocks: dict[str, list[tuple]]) -> set[str]:
	"""Of the doctypes the blocks bind, the ones this site has."""
	named = {
		doctype for pairs in blocks.values() for _row, block in pairs for doctype in _bound_doctypes(block)
	}
	if not named:
		return set()

	return set(frappe.get_all("DocType", filters={"name": ("in", list(named))}, pluck="name"))
