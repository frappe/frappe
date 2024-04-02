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
			"pgettext",
			(link.get("link_to") if link.get("link_type") == "DocType" else None, link.get("label")),
			[f"Label of a {link.get('type')} in the {workspace_name} Workspace"],
		)
		for link in data.get("links", [])
	)
	yield from (
		(
			None,
			"pgettext",
			(shortcut.get("link_to") if shortcut.get("type") == "DocType" else None, shortcut.get("label")),
			[f"Label of a shortcut in the {workspace_name} Workspace"],
		)
		for shortcut in data.get("shortcuts", [])
	)
