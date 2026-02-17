import json


def extract(fileobj, *args, **kwargs):
	"""Extract messages from Workspace Sidebar JSON files. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	# Extract the title field (main translatable field for Workspace Sidebar)
	title = data.get("title")
	if title:
		yield None, "_", title, ["Title of a Workspace Sidebar"]

	# Extract labels from items list
	items = data.get("items", [])
	if isinstance(items, list):
		for item in items:
			label = item.get("label")
			if label:
				yield None, "_", label, ["Label of a Workspace Sidebar Item"]
