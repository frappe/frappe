# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Old label-keyed blocks as Widgets.

A workspace's old blocks name a row of one of its six child tables by label. A block a save adds
or edits becomes a Widget of the matching type, made from that row.
"""

from json import dumps, loads

import frappe
from frappe.desk.layouts import LABELLED_BLOCKS, with_ids

# Block type -> the Workspace child table its rows live in
WIDGET_PARENTFIELD = {
	"card": "links",
	"shortcut": "shortcuts",
	"chart": "charts",
	"quick_list": "quick_lists",
	"number_card": "number_cards",
	"custom_block": "custom_blocks",
}

# what `build_links_table_from_card` reads from a stored card's links
CARD_LINK_KEYS = ("label", "link_type", "link_to", "onboard", "only_for", "dependencies", "is_query_report")

SHORTCUT_PROPS = (
	"type",
	"link_to",
	"url",
	"doc_view",
	"kanban_board",
	"icon",
	"restrict_to_domain",
	"color",
	"format",
)
LINK_PROPS = ("link_type", "link_to", "doctype_layout", "dependencies", "only_for", "onboard", "description")
QUICK_LIST_PROPS = ("document_type", "order_by", "hide_refresh", "hide_new", "hide_view_list")
NUMBER_CARD_PROPS = (
	"type",
	"document_type",
	"parent_document_type",
	"function",
	"aggregate_function_based_on",
	"report_name",
	"report_field",
	"report_function",
	"method",
	"show_percentage_stats",
	"stats_time_interval",
	"color",
	"currency",
	"show_full_number",
)


def as_widget_blocks(blocks: list, rows: dict, module: str | None, is_new) -> list:
	"""`blocks` with each old block that `rows` holds a row for, or that `is_new`, made a Widget.

	`rows` is `{block type: [row]}`, each row keyed by the label its block names.
	"""
	converted = []
	for block in blocks:
		row = row_of(block, rows)
		if block.get("type") in LABELLED_BLOCKS and (row or is_new(block)):
			name = make_widget(block["type"], row or {}, block["data"], module)
			if not name:
				continue
			data = {key: block["data"][key] for key in ("col", "row") if key in block["data"]}
			block = {"type": "widget", "data": {**data, "widget": name}}
		converted.append(block)
	return converted


def row_of(block: dict, rows: dict) -> dict | None:
	block_type = block.get("type")
	label = (block.get("data") or {}).get(f"{block_type}_name")
	return next((row for row in rows.get(block_type) or [] if row.get("label") == label), None)


def make_widget(block_type: str, row: dict, data: dict, module: str | None) -> str | None:
	"""A Widget made from an old block's row, or None when the row names nothing that exists."""
	if not row and block_type != "onboarding":
		return None
	made = WIDGET_OF[block_type](row, data, module)
	if not made:
		return None
	widget_type, label, config = made
	widget = frappe.get_doc(
		{
			"doctype": "Widget",
			"type": widget_type,
			"label": label,
			"module": module,
			"hide_filter": row.get("hide_filter") or 0,
			"config": config,
		}
	)
	return widget.insert(ignore_permissions=True).name


def shortcut(row, data, module):
	config = {key: row.get(key) for key in SHORTCUT_PROPS}
	config["stats_filter"] = frappe.parse_json(row.get("stats_filter") or "[]")
	return "Shortcut", row["label"], config


def card(row, data, module):
	links = frappe.parse_json(row.get("links") or "[]")
	names = [make_link(link, module) for link in links if link.get("link_to")]
	config = {"widgets": [{"widget": name} for name in names], "icon": row.get("icon")}
	config["description"] = row.get("description")
	return "Card", row["label"], config


def make_link(link: dict, module: str | None) -> str:
	config = {key: link.get(key) for key in LINK_PROPS}
	widget = {"doctype": "Widget", "type": "Link", "label": link.get("label") or link["link_to"]}
	return frappe.get_doc({**widget, "module": module, "config": config}).insert(ignore_permissions=True).name


def number_card(row, data, module):
	if not frappe.db.exists("Number Card", row.get("number_card_name")):
		return None
	record = frappe.get_doc("Number Card", row["number_card_name"])
	config = {key: record.get(key) for key in NUMBER_CARD_PROPS}
	config["filters"] = frappe.parse_json(record.filters_json or "[]")
	return "Number Card", row.get("label") or record.label, config


def chart(row, data, module):
	return "Chart", row.get("label") or row["chart_name"], {"chart": row["chart_name"]}


def quick_list(row, data, module):
	config = {key: row.get(key) for key in QUICK_LIST_PROPS}
	config["filters"] = frappe.parse_json(row.get("quick_list_filter") or "[]")
	return "Quick List", row.get("label") or row["document_type"], config


def custom_block(row, data, module):
	name = row["custom_block_name"]
	return "Custom Block", row.get("label") or name, {"custom_block": name}


def onboarding(row, data, module):
	name = data["onboarding_name"]
	return "Onboarding", name, {"onboarding": name}


WIDGET_OF = {
	"shortcut": shortcut,
	"card": card,
	"number_card": number_card,
	"chart": chart,
	"quick_list": quick_list,
	"custom_block": custom_block,
	"onboarding": onboarding,
}


def changes_from_copy(base, content: list, widgets: dict) -> dict:
	"""A whole copy of a workspace's blocks as changes to its default: every default block hidden and
	every block of the copy added in order, its widgets made Widgets. A block the app adds later
	lands after the copy."""
	rows = merge_widgets(snapshot_widgets(base), widgets)
	blocks = as_widget_blocks(content, rows, None, lambda block: True)
	blocks = with_ids([block if block["type"] == "widget" else {**block, "id": None} for block in blocks])
	adds = [{"after": blocks[i - 1]["id"] if i else None, "block": block} for i, block in enumerate(blocks)]
	return {"hide": [block["id"] for block in with_ids(loads(base.content or "[]"))], "add": adds}


def merge_widgets(widgets: dict, new_widgets: dict | None) -> dict:
	"""The stored set plus more rows; a later row wins over an earlier one of its label."""
	merged = {widget_type: list(items) for widget_type, items in widgets.items()}
	for widget_type, items in (new_widgets or {}).items():
		merged.setdefault(widget_type, []).extend(items or [])
	return {
		widget_type: list({row.get("label"): row for row in rows}.values())
		for widget_type, rows in merged.items()
	}


def snapshot_widgets(doc) -> dict:
	"""A Workspace's widget tables as rows by block type."""
	widgets = {}
	for widget_type, parentfield in WIDGET_PARENTFIELD.items():
		if widget_type == "card":
			continue
		rows = [
			row.as_dict(no_default_fields=True, no_child_table_fields=True) for row in doc.get(parentfield)
		]
		if rows:
			widgets[widget_type] = rows

	cards = [
		{
			"label": card.label,
			"icon": card.icon,
			"description": card.description,
			"links": dumps([{key: link.get(key) for key in CARD_LINK_KEYS} for link in card.links]),
		}
		for card in doc.get_link_groups()
		if card.links
	]
	if cards:
		widgets["card"] = cards
	return widgets
