# SETTINGS — the settings dialog's panes, merged from every app's `Settings Dialog` record.

# Unfiltered, so one merge can be cached for every user; who sees which pane is decided per
# request, after this. Only the app layer is read: the site and user layers are not built.

import hashlib

import frappe
from frappe import _
from frappe.desk.doctype.rail.rail import NO_HOST, SITE_LAYER
from frappe.desk.layers import anchor_attempts, place_by_anchors
from frappe.desk.settings_records import shipped_records
from frappe.desk.settings_rules import Block, Problem, SettingsRules, report

from .boot import report_oversized_keys
from .doctypes import metadata_version
from .permissions import may_enter_any_prefix
from .settings_filter import SettingsFilter
from .titles import app_screen

PANES_CACHE_KEY = "shell_settings_panes"


@frappe.desk_v2_only
@frappe.whitelist(methods=["GET"])
def get_panes() -> dict:
	"""The panes this user may see, their search label index and their apps' titles, read on first open."""
	if not may_enter_any_prefix():
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	visible = SettingsFilter().filter(get_cached_panes())
	visible["titles"] = {app: app_screen(app)["title"] for app in {pane["app"] for pane in visible["panes"]}}
	report_oversized_keys(visible, None, reply="settings")
	return visible


def get_cached_panes() -> list[dict]:
	"""The merged, unfiltered panes, cached on `metadata_version` and a digest of the stored records."""
	# The stamp is read in the merge's transaction and before it, so a merge of old rows never carries
	# a current stamp, whatever snapshot the request began with.
	version = f"{metadata_version()}:{_records_stamp()}"
	cached = frappe.client_cache.get_value(PANES_CACHE_KEY)

	if isinstance(cached, dict) and cached.get("version") == version:
		return cached["panes"]

	panes = resolve_panes()
	frappe.client_cache.set_value(PANES_CACHE_KEY, {"version": version, "panes": panes})
	return panes


def check_shipped_records():
	"""After migrate: report the blocks of every active app that clash with another record's or name a pane the host lacks."""
	report([problem for problem in merge_shipped()[1] if problem.across])


def _records_stamp() -> str:
	"""A digest of every app-layer record's name and `modified`, which any save or delete of one moves."""
	# Every record, not the latest `modified`: a save committed after a later one would not move a maximum.
	records = frappe.get_all(
		"Settings Dialog",
		filters={"standard": 1, "user": SITE_LAYER},
		fields=["name", "modified"],
		order_by="name asc",
		as_list=True,
	)
	return hashlib.sha256(repr(records).encode()).hexdigest()


def resolve_panes(apps: list[str] | None = None) -> list[dict]:
	"""Every app's panes in run order, each holding its host's blocks and then every extending app's."""
	resolved, problems = merge_shipped(apps)

	for problem in problems:
		_warn(problem)

	return resolved


def merge_shipped(apps: list[str] | None = None) -> tuple[list[dict], list[Problem]]:
	"""The merged panes and the problems of the blocks it left out."""
	records = _shipped_records(apps or frappe.get_active_apps(_ensure_on_bench=True))
	rules = SettingsRules()
	resolved, problems = [], []

	for host in records:
		if host.extends:
			continue

		contributors = [host] + [record for record in records if record.extends == host.app]
		pane_list = [_pane(host.app, row) for row in host.panes]
		vetting = rules.vet({pane["key"] for pane in pane_list}, contributors)
		_fill(pane_list, vetting.accepted)
		problems += vetting.problems
		resolved += [pane for pane in pane_list if pane["blocks"]]

	return resolved, problems


def _fill(pane_list: list[dict], accepted: list[Block]):
	"""Put every accepted block in its pane, then move the anchored ones."""
	by_key = {pane["key"]: pane for pane in pane_list}
	anchored: dict[str, list[tuple[dict, list[dict]]]] = {}

	for block in accepted:
		wire = _block(block)
		by_key[block.pane]["blocks"].append(wire)

		if block.record.extends and (attempts := _placements(block.row.anchors)):
			anchored.setdefault(block.pane, []).append((wire, attempts))

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


def _warn(problem: Problem):
	frappe.logger("shell").warning(
		f"Settings {problem.message}; the block is left out of the settings dialog."
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


def _block(block: Block) -> dict:
	"""One accepted block as the browser gets it."""
	row = block.row
	wire = {"key": block.key, "app": block.app, "save_mode": block.save_mode}

	if row.label:
		wire["label"] = row.label
	if row.description:
		wire["description"] = row.description

	wire["roles"] = block.roles

	if row.binding_type:
		wire["binding"] = _binding(
			{"type": row.binding_type, "doctype": row.document_type, "resolver": row.name_resolver}
		)
	else:
		wire["component"] = row.component
		wire["bindings"] = {name: _binding(spec) for name, spec in block.bindings.items()}
		wire["settings"] = block.settings

	wire["fields"] = block.fields
	return {field: value for field, value in wire.items() if value or field == "key"}


def _binding(spec: dict) -> dict:
	return {field: spec[field] for field in ("type", "doctype", "resolver") if spec.get(field)}


# The stored records


def _shipped_records(apps: list[str]) -> list:
	"""The app layer of every active app, in run order; one extending an absent host is skipped."""
	position = {app: index for index, app in enumerate(apps)}

	return sorted(
		(
			record
			for record in shipped_records()
			if record.app in position and (record.extends == NO_HOST or record.extends in position)
		),
		key=lambda record: position[record.app],
	)
