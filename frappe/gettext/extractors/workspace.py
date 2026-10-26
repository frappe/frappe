import json

from .utils import get_line_number


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from DocType JSON files. To be used to babel extractor
	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if isinstance(data, list):
		return

	if data.get("doctype") != "Workspace":
		return

	workspace_name = data.get("label")

	yield get_line_number(text, "label", workspace_name), "_", workspace_name, ["Name of a Workspace"]
	yield from extract_layout(
		data,
		data.get("content") or "[]",
		f"the {workspace_name} Workspace",
		lambda key, value: get_line_number(text, key, value),
		get_line_number(text, "content", data.get("content", "[]")),
	)

	# A role layout holds the same tables in its `widgets`, so its strings point at its row.
	for row in data.get("variants", []):
		widgets = json.loads(row.get("widgets") or "{}")
		lineno = get_line_number(text, "widgets", row.get("widgets"))
		yield from extract_layout(
			tables_from_widgets(widgets),
			row.get("content") or "[]",
			f"the {workspace_name} Workspace ({row.get('role')} layout)",
			lambda key, value, lineno=lineno: lineno,
			get_line_number(text, "content", row.get("content")),
		)


def extract_layout(tables, content_json, where, line_of, content_lineno):
	yield from (
		(line_of("label", chart.get("label")), "_", chart.get("label"), [f"Label of a chart in {where}"])
		for chart in tables.get("charts", [])
		if chart.get("label")
	)
	yield from (
		(
			line_of("label", number_card.get("label")),
			"_",
			number_card.get("label"),
			[f"Label of a number card in {where}"],
		)
		for number_card in tables.get("number_cards", [])
		if number_card.get("label")
	)
	yield from (
		(
			line_of("label", link.get("label")),
			"_",
			link.get("label"),
			[f"Label of a {link.get('type')} in {where}"],
		)
		for link in tables.get("links", [])
		if link.get("label")
	)
	yield from (
		(
			line_of("description", link.get("description")),
			"_",
			link.get("description"),
			[f"Description of a {link.get('type')} in {where}"],
		)
		for link in tables.get("links", [])
		if link.get("description")
	)
	yield from (
		(
			line_of("label", shortcut.get("label")),
			"_",
			shortcut.get("label"),
			[f"Label of a shortcut in {where}"],
		)
		for shortcut in tables.get("shortcuts", [])
		if shortcut.get("label")
	)
	yield from (
		(
			line_of("format", shortcut.get("format")),
			"_",
			shortcut.get("format"),
			[f"Count format of shortcut in {where}"],
		)
		for shortcut in tables.get("shortcuts", [])
		if shortcut.get("format")
	)
	yield from (
		(
			line_of("label", quick_list.get("label")),
			"_",
			quick_list.get("label"),
			[f"Label of a quick_list in {where}"],
		)
		for quick_list in tables.get("quick_lists", [])
		if quick_list.get("label")
	)

	for item in json.loads(content_json):
		item_type = item.get("type")
		if item_type in ("header", "paragraph"):
			if text := item.get("data", {}).get("text"):
				yield (content_lineno, "_", text, [f"{item_type.title()} text in {where}"])


def tables_from_widgets(widgets: dict) -> dict:
	"""A role layout's `widgets` laid out as the workspace's own tables."""
	links = []
	for card in widgets.get("card", []):
		links.append({**card, "type": "Card Break"})
		card_links = card.get("links") or "[]"
		links.extend(
			{**link, "type": "Link"}
			for link in (json.loads(card_links) if isinstance(card_links, str) else card_links)
		)
	return {
		"charts": widgets.get("chart", []),
		"number_cards": widgets.get("number_card", []),
		"links": links,
		"shortcuts": widgets.get("shortcut", []),
		"quick_lists": widgets.get("quick_list", []),
	}
