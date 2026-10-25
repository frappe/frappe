import json

from .utils import extract_messages_from_docfield, extract_messages_from_links, get_line_number


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

	doctype = data.get("name")

	yield get_line_number(text, "name", doctype), "_", doctype, ["Name of a DocType"]

	doctype_description = data.get("description")
	if doctype_description:
		yield (
			get_line_number(text, "description", doctype_description),
			"_",
			doctype_description,
			["Description of a DocType"],
		)

	messages = []

	for field in data.get("fields", []):
		messages.extend(extract_messages_from_docfield(doctype, field, text))

	messages.extend(extract_messages_from_links(doctype, data.get("links", []), text))

	yield from ((lineno, "_", message, [comment]) for lineno, message, comment in messages)

	# Role names do not get context because they are used with multiple doctypes
	yield from (
		(get_line_number(text, "role", perm["role"]), "_", perm["role"], ["Name of a role"])
		for perm in data.get("permissions", [])
		if "role" in perm
	)
