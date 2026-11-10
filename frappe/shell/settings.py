# SETTINGS — the settings dialog's panes, merged from every app's `Settings Dialog` record.

# Unfiltered, so one merge can be cached for every user; who sees which pane is decided per
# request, after this. Only the app layer is read: the site and user layers are not built.

import hashlib

import frappe
from frappe import _
from frappe.desk.doctype.rail.rail import NO_HOST, SITE_LAYER
from frappe.desk.settings_block import Block
from frappe.desk.settings_records import shipped_records
from frappe.desk.settings_rules import Problem, SettingsRules, report

from .boot import report_oversized_keys
from .doctypes import metadata_version
from .permissions import may_enter_any_prefix
from .settings_filter import SettingsFilter
from .settings_sidebar import Resolved, resolve_sidebars
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
	return _cached_merge()["panes"]


def get_cached_sidebars() -> dict[str, dict]:
	"""The resolved sidebar of each prefix, unfiltered, from the same cache entry as the panes."""
	return _cached_merge()["sidebars"]


def _cached_merge() -> dict:
	# The stamp is read in the merge's transaction and before it, so a merge of old rows never carries
	# a current stamp, whatever snapshot the request began with.
	version = f"{metadata_version()}:{_records_stamp()}"
	cached = frappe.client_cache.get_value(PANES_CACHE_KEY)

	if isinstance(cached, dict) and cached.get("version") == version and "sidebars" in cached:
		return cached

	resolved = resolve_settings()
	cached = {"version": version, "panes": resolved.panes, "sidebars": resolved.sidebars}
	frappe.client_cache.set_value(PANES_CACHE_KEY, cached)
	return cached


def check_shipped_records():
	"""After migrate: report the blocks and arrangements of every active app that clash with another record's or name what the site lacks."""
	resolved = merge_settings()
	report([problem for problem in resolved.problems if problem.across])

	for notices in resolved.notices.values():
		for notice in notices:
			print(f"Settings sidebar notice: {notice}")


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
	return resolve_settings(apps).panes


def resolve_settings(apps: list[str] | None = None) -> Resolved:
	"""The merge with every problem logged: the panes, and the sidebar of each desk."""
	resolved = merge_settings(apps)

	for problem in resolved.problems:
		_warn(problem)

	return resolved


def merge_shipped(apps: list[str] | None = None) -> tuple[list[dict], list[Problem]]:
	"""The merged panes and the problems of what it left out."""
	resolved = merge_settings(apps)
	return resolved.panes, resolved.problems


def merge_settings(apps: list[str] | None = None) -> Resolved:
	"""The merged panes, the sidebars resolved over them, and the problems and notices of both."""
	apps = apps or frappe.get_active_apps(_ensure_on_bench=True)
	records = _shipped_records(apps)
	panes, problems = _merge_panes(records)

	resolved = resolve_sidebars(panes, records, apps)
	resolved.panes = panes
	resolved.problems = [*problems, *resolved.problems]
	return resolved


def _merge_panes(records: list) -> tuple[list[dict], list[Problem]]:
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
	"""Put every accepted block in its pane."""
	by_key = {pane["key"]: pane for pane in pane_list}

	for block in accepted:
		by_key[block.pane]["blocks"].append(_block(block))


def _warn(problem: Problem):
	frappe.logger("shell").warning(f"Settings {problem.message}; it is left out of the settings dialog.")


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

	if not block.is_component:
		wire["binding"] = _binding(
			{"type": row.binding_type, "doctype": row.document_type, "resolver": row.name_resolver}
		)
	else:
		wire["component"] = row.component
		wire["bindings"] = {name: _binding(spec) for name, spec in block.bindings.items()}
		wire["settings"] = block.search_entries

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
