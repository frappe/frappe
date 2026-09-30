import json


def extract(fileobj, *args, **kwargs):
	"""Extract messages from standard List Filter JSON files. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if not isinstance(data, dict) or data.get("doctype") != "List Filter":
		return

	if filter_name := data.get("filter_name"):
		yield None, "_", filter_name, [f"Name of a list layout for {data.get('reference_doctype')}"]
