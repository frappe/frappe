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
	yield from (
		(
			get_line_number(text, "label", chart.get("label")),
			"_",
			chart.get("label"),
			[f"Label of a chart in the {workspace_name} Workspace"],
		)
		for chart in data.get("charts", [])
		if chart.get("label")
	)
	yield from (
		(
			get_line_number(text, "label", number_card.get("label")),
			"_",
			number_card.get("label"),
			[f"Label of a number card in the {workspace_name} Workspace"],
		)
		for number_card in data.get("number_cards", [])
		if number_card.get("label")
	)
	yield from (
		(
			get_line_number(text, "label", link.get("label")),
			"_",
			link.get("label"),
			[f"Label of a {link.get('type')} in the {workspace_name} Workspace"],
		)
		for link in data.get("links", [])
		if link.get("label")
	)
	yield from (
		(
			get_line_number(text, "description", link.get("description")),
			"_",
			link.get("description"),
			[f"Description of a {link.get('type')} in the {workspace_name} Workspace"],
		)
		for link in data.get("links", [])
		if link.get("description")
	)
	yield from (
		(
			get_line_number(text, "label", shortcut.get("label")),
			"_",
			shortcut.get("label"),
			[f"Label of a shortcut in the {workspace_name} Workspace"],
		)
		for shortcut in data.get("shortcuts", [])
		if shortcut.get("label")
	)
	yield from (
		(
			get_line_number(text, "format", shortcut.get("format")),
			"_",
			shortcut.get("format"),
			[f"Count format of shortcut in the {workspace_name} Workspace"],
		)
		for shortcut in data.get("shortcuts", [])
		if shortcut.get("format")
	)
	yield from (
		(
			get_line_number(text, "label", quick_list.get("label")),
			"_",
			quick_list.get("label"),
			[f"Label of a quick_list in the {workspace_name} Workspace"],
		)
		for quick_list in data.get("quick_lists", [])
		if quick_list.get("label")
	)

	content_json = data.get("content", "[]")
	content_lineno = get_line_number(text, "content", content_json)
	content = json.loads(content_json)
	for item in content:
		item_type = item.get("type")
		if item_type in ("header", "paragraph"):
			if text := item.get("data", {}).get("text"):
				yield (
					content_lineno,
					"_",
					text,
					[f"{item_type.title()} text in the {workspace_name} Workspace"],
				)
