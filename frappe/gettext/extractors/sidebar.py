import json

from .utils import get_line_number


def extract(fileobj, *args, **kwargs):
	"""Extract messages from Sidebar JSON files. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if isinstance(data, list):
		return

	# the dock label; defaults to the module name, but an app may override it
	title = data.get("title")
	if title:
		yield get_line_number(text, "title", title), "_", title, ["Title of a Sidebar"]

	items = data.get("items", [])
	if isinstance(items, list):
		for item in items:
			label = item.get("label")
			if label:
				yield get_line_number(text, "label", label), "_", label, ["Label of a Sidebar Item"]
