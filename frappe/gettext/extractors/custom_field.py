import json

from .utils import extract_messages_from_docfield


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from Custom Field fixtures. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if not isinstance(data, list):
		return

	messages = []

	for custom_field in data:
		doctype = custom_field.get("dt")
		messages.extend(extract_messages_from_docfield(doctype, custom_field, text))

	yield from ((lineno, "_", message, [comment]) for lineno, message, comment in messages)
