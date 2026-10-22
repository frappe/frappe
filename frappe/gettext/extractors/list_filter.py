import json

from .utils import get_line_number


def extract(fileobj, *args, **kwargs):
	"""Extract messages from standard List Filter JSON files. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if not isinstance(data, dict) or data.get("doctype") != "List Filter":
		return

	if filter_name := data.get("filter_name"):
		yield (
			get_line_number(text, "filter_name", filter_name),
			"_",
			filter_name,
			[f"Name of a list layout for {data.get('reference_doctype')}"],
		)
