import json
from pathlib import Path

from frappe.utils import unscrub

from .utils import extract_messages_from_docfield, get_line_number

CONTAINERS = (("sections", "tab"), ("columns", "section"), ("fields", "column"))


def extract(fileobj, *args, **kwargs):
	"""Extract messages from an app's Form Layout files. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)
	if not isinstance(data, dict):
		return

	path = Path(getattr(fileobj, "name", ""))
	doctype = unscrub(path.parent.parent.parent.name)
	layout_type = unscrub(path.stem)

	for lineno, message, comment in extract_from_nodes(data.get("layout") or [], doctype, text):
		yield lineno, "_", message, [f"{comment} in the {layout_type} layout"]


def extract_from_nodes(nodes: list, doctype: str, text: str):
	"""Yield `(lineno, message, comment)` for each container label and description, and each inline field."""
	for node in nodes:
		if not isinstance(node, dict):
			continue
		children, kind = next(((key, kind) for key, kind in CONTAINERS if key in node), (None, None))
		if not kind:
			if node.get("fieldname"):
				yield from extract_messages_from_docfield(doctype, node, text)
			continue
		name = node.get("name") or kind
		for key in ("label", "description"):
			if isinstance(message := node.get(key), str) and message:
				comment = f"{key.title()} of the {name} {kind} of DocType '{doctype}'"
				yield get_line_number(text, key, message), message, comment
		yield from extract_from_nodes(node[children] or [], doctype, text)
