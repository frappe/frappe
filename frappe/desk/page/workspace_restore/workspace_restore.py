# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Bring back a site's pre-upgrade edits to standard workspaces.

On v15 and v16 a Workspace Manager could edit an app-shipped workspace in place, and every save
wrote a Version row. The upgrade re-imports the workspace from the app's JSON, which wipes the
edit from the live row but keeps the Version rows: a reload-delete never touches them. This page
reads those rows back and writes the edit as a Custom Workspace, the delta develop uses for all
site edits, so the workspace renders as it did before the upgrade at the same URL.
"""

from json import JSONDecodeError, dumps, loads

import frappe
from frappe import _
from frappe.desk.doctype.custom_workspace.custom_workspace import (
	WIDGET_PARENTFIELD,
	_get_or_new,
	_prune_widgets,
	get_customization,
)
from frappe.desk.doctype.workspace.workspace import check_workspace_manager, workspace_payload

PARENTFIELD_WIDGET = {parentfield: widget for widget, parentfield in WIDGET_PARENTFIELD.items()}

# Columns a Version row dict carries that describe the old row, not the widget.
BOOKKEEPING_KEYS = frozenset(
	{
		"name",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
		"idx",
		"parent",
		"parentfield",
		"parenttype",
		"doctype",
	}
)

# The link fields `Workspace.build_links_table_from_card` reads back from a card config.
LINK_KEYS = ("label", "link_type", "link_to", "onboard", "only_for", "dependencies", "is_query_report")

# Workspace fields the delta can carry besides the layout.
PROPERTY_FIELDS = ("icon", "indicator_color")

# Fields whose change says nothing about the layout and needs no warning.
SILENT_FIELDS = frozenset({"name", "docstatus", "is_hidden", "sequence_id", "content"})


@frappe.whitelist()
def get_restorable_workspaces() -> list[dict]:
	"""Standard workspaces whose Version rows hold a pre-upgrade layout edit, with their state."""
	check_workspace_manager(_("You need the Workspace Manager role to see pre-upgrade workspace edits."))

	# In developer mode the editor writes the base row, so every Version here is an app author's
	# own edit, already exported to the app's JSON. There is nothing a customization should carry.
	if frappe.conf.developer_mode:
		return []

	workspaces = {
		ws.name: ws
		for ws in frappe.get_all(
			"Workspace",
			filters={"standard": 1},
			fields=["name", "title", "module", "content"],
		)
	}
	if not workspaces:
		return []

	rows = []
	for name, versions in get_versions(list(workspaces)).items():
		replay = replay_versions(versions, frappe.get_cached_doc("Workspace", name))
		if replay.content is None:
			continue

		workspace = workspaces[name]
		last = versions[-1]
		rows.append(
			{
				"workspace": name,
				"title": workspace.title,
				"module": workspace.module,
				"last_edited_on": last.creation,
				"last_edited_by": last.owner,
				"state": get_state(workspace, replay),
				"summary": summarize(replay),
				"warnings": replay.warnings,
			}
		)

	rows.sort(key=lambda row: row["last_edited_on"], reverse=True)
	return rows


@frappe.whitelist()
def restore_workspace_edits(workspace: str) -> dict:
	"""Write the replayed edit as the workspace's Custom Workspace and return the desk payload."""
	check_workspace_manager(_("You need the Workspace Manager role to restore workspace edits."))

	if frappe.conf.developer_mode:
		frappe.throw(
			_(
				"In developer mode a standard workspace's edits belong to the app's JSON, not to a customization."
			)
		)

	if not frappe.db.get_value("Workspace", workspace, "standard"):
		frappe.throw(_("{0} is not a standard workspace.").format(frappe.bold(workspace)))

	base = frappe.get_doc("Workspace", workspace)
	replay = replay_versions(get_versions([workspace]).get(workspace, []), base)
	if replay.content is None:
		frappe.throw(_("No pre-upgrade layout edit is recorded for {0}.").format(frappe.bold(workspace)))

	customization = _get_or_new(workspace)
	customization.content = dumps(replay.content)
	customization.widgets = dumps(replay.widgets)
	customization.set("added_roles", [{"role": role} for role in replay.added_roles])
	customization.set("removed_roles", [{"role": role} for role in replay.removed_roles])
	for field, value in replay.properties.items():
		customization.set(field, value)
	customization.save(ignore_permissions=True)

	return workspace_payload(warnings=replay.warnings)


def get_versions(names: list[str]) -> dict[str, list[frappe._dict]]:
	"""Each workspace's Version rows, oldest first, with `data` already decoded.

	Read with `get_all` on purpose: a Workspace Manager has no read permission on Version, and
	the callers return only what they derive from the rows, never the rows themselves.
	"""
	rows = frappe.get_all(
		"Version",
		filters={"ref_doctype": "Workspace", "docname": ["in", names]},
		fields=["name", "docname", "owner", "creation", "data"],
		order_by="creation asc, name asc",
	)
	by_workspace: dict[str, list[frappe._dict]] = {}
	for row in rows:
		row.diff = loads(row.data)
		row.pop("data")
		by_workspace.setdefault(row.docname, []).append(row)
	return by_workspace


def replay_versions(versions: list[frappe._dict], base) -> frappe._dict:
	"""Fold a workspace's Version rows into what a Custom Workspace can hold.

	The layout is the new side of the newest content change. Added widgets fold in order, last
	add wins, because editing a widget in the dialog re-adds it under the same label and drops
	the old row into `removed`. Roles end as a net add or remove against the live base. Whatever
	has no slot in the delta is reported in `warnings` rather than dropped quietly.
	"""
	content = None
	added: dict[str, dict[str, dict]] = {}
	role_events: dict[str, str] = {}
	changed: dict[str, object] = {}
	warnings: list[str] = []

	for version in versions:
		diff = version.diff
		if not any(diff.get(key) for key in ("changed", "added", "removed", "row_changed")):
			continue

		for field, _old, new in diff.get("changed", []):
			if field == "content":
				decoded = decode_content(new)
				if decoded is None:
					warnings.append(
						_("A layout saved on {0} could not be read and was skipped.").format(version.creation)
					)
				else:
					content = decoded
			elif field in PROPERTY_FIELDS:
				changed[field] = new
			elif field not in SILENT_FIELDS:
				warnings.append(
					_("The change to {0} cannot be carried by a customization.").format(
						field_label(base, field)
					)
				)

		link_rows = []
		for parentfield, row in diff.get("added", []):
			if parentfield == "roles":
				role_events[row["role"]] = "add"
			elif parentfield == "links":
				link_rows.append(row)
			elif parentfield in PARENTFIELD_WIDGET:
				added.setdefault(parentfield, {})[row.get("label")] = strip_row(row)
		for card in cards_from_link_rows(link_rows, warnings):
			added.setdefault("links", {})[card["label"]] = card

		for parentfield, row in diff.get("removed", []):
			if parentfield == "roles":
				role_events[row["role"]] = "remove"
			elif parentfield in PARENTFIELD_WIDGET:
				added.get(parentfield, {}).pop(row.get("label"), None)

		for parentfield, _index, _row_name, _changes in diff.get("row_changed", []):
			warnings.append(
				_("An edit to a shipped row in {0} cannot be carried by a customization.").format(
					field_label(base, parentfield)
				)
			)

	widgets = {PARENTFIELD_WIDGET[pf]: list(rows.values()) for pf, rows in added.items() if rows}
	if content is not None:
		widgets = _prune_widgets(widgets, content)
		drop_shadowed_widgets(widgets, base, warnings)
		warn_about_missing_widgets(content, widgets, base, warnings)

	base_roles = {r.role for r in base.roles}
	added_roles = sorted(
		role for role, event in role_events.items() if event == "add" and role not in base_roles
	)
	removed_roles = sorted(
		role for role, event in role_events.items() if event == "remove" and role in base_roles
	)

	return frappe._dict(
		content=content,
		widgets=widgets,
		added_roles=added_roles,
		removed_roles=removed_roles,
		properties=restorable_properties(changed, base, warnings),
		warnings=warnings,
	)


def decode_content(value: str | None) -> list | None:
	"""The block list inside a Version's content value.

	`get_diff` ran the value through `get_formatted`, which turns newlines in a Long Text into
	`<br>` unless the text has a block tag. Editor output is single-line JSON so this is rare,
	but a row written that way still has to decode.
	"""
	if not value:
		return None
	for candidate in (value, value.replace("<br>", "\n")):
		try:
			decoded = loads(candidate)
		except (JSONDecodeError, TypeError):
			continue
		if isinstance(decoded, list):
			return decoded
	return None


def strip_row(row: dict) -> dict:
	return {
		key: value for key, value in row.items() if key not in BOOKKEEPING_KEYS and not key.startswith("_")
	}


def cards_from_link_rows(rows: list[dict], warnings: list[str]) -> list[dict]:
	"""Regroup flat `links` rows into the card configs `build_links_table_from_card` takes.

	A card is a `Card Break` row followed by its `Link` rows, which is how both the editor and
	`build_links_table_from_card` lay them out. A Link row with no Card Break before it was added
	to a shipped card, and the delta has nowhere to put it.
	"""
	cards: list[dict] = []
	current: dict | None = None
	for row in sorted(rows, key=lambda r: r.get("idx") or 0):
		if row.get("type") == "Card Break":
			current = {
				"label": row.get("label"),
				"icon": row.get("icon"),
				"description": row.get("description"),
				"hidden": row.get("hidden") or 0,
				"links": [],
			}
			cards.append(current)
		elif current is not None:
			current["links"].append({key: row.get(key) for key in LINK_KEYS})
		else:
			warnings.append(
				_(
					"The link {0} was added to a shipped card and cannot be carried by a customization."
				).format(frappe.bold(row.get("label")))
			)

	for card in cards:
		card["link_count"] = len(card["links"])
		card["links"] = dumps(card["links"])
	return cards


def drop_shadowed_widgets(widgets: dict, base, warnings: list[str]) -> None:
	"""Drop added widgets that share a label with a shipped one.

	`_append_widgets` puts site rows after the base rows and the desk takes the first row with
	a matching label, so the shipped widget would win anyway. Cards are the exception:
	`build_links_table_from_card` replaces a shipped card with the same label.
	"""
	for widget_type in list(widgets):
		if widget_type == "card":
			continue
		base_labels = {row.label for row in base.get(WIDGET_PARENTFIELD[widget_type])}
		kept = []
		for item in widgets[widget_type]:
			if item.get("label") in base_labels:
				warnings.append(
					_("{0} is a shipped {1} edited in place; the app's version is shown.").format(
						frappe.bold(item.get("label")), widget_label(widget_type)
					)
				)
			else:
				kept.append(item)
		if kept:
			widgets[widget_type] = kept
		else:
			widgets.pop(widget_type)


def warn_about_missing_widgets(content: list, widgets: dict, base, warnings: list[str]) -> None:
	"""Name the blocks whose widget neither the app nor the edit defines any more."""
	for block in content:
		widget_type = block.get("type")
		if widget_type not in WIDGET_PARENTFIELD:
			continue
		label = (block.get("data") or {}).get(f"{widget_type}_name")
		if label in {item.get("label") for item in widgets.get(widget_type, [])}:
			continue
		if label in {row.label for row in base.get(WIDGET_PARENTFIELD[widget_type])}:
			continue
		warnings.append(
			_("The block {0} points at a {1} this version of the app no longer ships.").format(
				frappe.bold(label), widget_label(widget_type)
			)
		)


def restorable_properties(changed: dict, base, warnings: list[str]) -> dict:
	"""Icon and colour as the delta stores them. Select values were translated when the Version
	was written, so the colour is mapped back onto its options."""
	properties = {}
	if "icon" in changed and changed["icon"] != base.icon:
		properties["icon"] = changed["icon"]
	if "indicator_color" in changed:
		options = frappe.get_meta("Custom Workspace").get_options("indicator_color").split("\n")
		by_translation = {_(option, context="Custom Workspace"): option for option in options if option}
		value = changed["indicator_color"]
		color = value if value in options else by_translation.get(value)
		if color is None:
			warnings.append(_("The colour {0} is not one the desk offers and was skipped.").format(value))
		elif color != base.indicator_color:
			properties["indicator_color"] = color
	return properties


def get_state(workspace, replay) -> str:
	"""Where this workspace stands: still holding the edit, overwritten, or already restored."""
	customization = get_customization(workspace.name)
	if customization:
		same_content = loads(customization.content or "[]") == replay.content
		same_widgets = loads(customization.widgets or "{}") == replay.widgets
		return "Restored" if same_content and same_widgets else "Customized since"
	if loads(workspace.content or "[]") == replay.content:
		return "Not yet overwritten"
	return "Overwritten"


def summarize(replay) -> dict:
	return {
		"blocks": len(replay.content),
		"widgets": {widget_type: len(items) for widget_type, items in replay.widgets.items()},
		"roles": len(replay.added_roles) + len(replay.removed_roles),
	}


def field_label(base, fieldname: str) -> str:
	field = base.meta.get_field(fieldname)
	return _(field.label) if field and field.label else fieldname


def widget_label(widget_type: str) -> str:
	return _(widget_type.replace("_", " "))
