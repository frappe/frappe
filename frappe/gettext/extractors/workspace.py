import json


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from DocType JSON files. To be used to babel extractor
	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	if data.get("doctype") != "Workspace":
		return

	workspace_name = data.get("label")

	yield None, "_", workspace_name, ["Name of a Workspace"]
	yield from (
		(None, "_", chart.get("label"), [f"Label of a chart in the {workspace_name} Workspace"])
		for chart in data.get("charts", [])
	)
	yield from (
		(None, "_", number_card.get("label"), [f"Label of a number card in the {workspace_name} Workspace"])
		for number_card in data.get("number_cards", [])
	)
	yield from (
		(
			None,
			"_",
			link.get("label"),
			[f"Label of a {link.get('type')} in the {workspace_name} Workspace"],
		)
		for link in data.get("links", [])
	)
	yield from (
		(
			None,
			"_",
			link.get("description"),
			[f"Description of a {link.get('type')} in the {workspace_name} Workspace"],
		)
		for link in data.get("links", [])
	)
	yield from (
		(
			None,
			"_",
			shortcut.get("label"),
			[f"Label of a shortcut in the {workspace_name} Workspace"],
		)
		for shortcut in data.get("shortcuts", [])
	)
	yield from (
		(
			None,
			"_",
			shortcut.get("format"),
			[f"Count format of shortcut in the {workspace_name} Workspace"],
		)
		for shortcut in data.get("shortcuts", [])
	)

	content = json.loads(data.get("content", "[]"))
	for item in content:
		item_type = item.get("type")
		if item_type in ("header", "paragraph"):
			yield (
				None,
				"_",
				item.get("data", {}).get("text"),
				[f"{item_type.title()} text in the {workspace_name} Workspace"],
			)
