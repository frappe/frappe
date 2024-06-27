import json

from .utils import extract_messages_from_docfield, extract_messages_from_links


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from DocType JSON files. To be used to babel extractor
	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	doctype = data.get("name")

	yield None, "_", doctype, ["Name of a DocType"]

	doctype_description = data.get("description")
	if doctype_description:
		yield None, "_", doctype_description, ["Description of a DocType"]

	messages = []

	for field in data.get("fields", []):
		messages.extend(extract_messages_from_docfield(doctype, field))

	messages.extend(extract_messages_from_links(doctype, data.get("links", [])))

	yield from ((None, "_", message, [comment]) for message, comment in messages)

	# Role names do not get context because they are used with multiple doctypes
	yield from (
		(None, "_", perm["role"], ["Name of a role"])
		for perm in data.get("permissions", [])
		if "role" in perm
	)
