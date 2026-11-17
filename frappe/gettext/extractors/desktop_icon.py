import json

from .utils import get_line_number


def extract(fileobj, *args, **kwargs):
	"""Extract messages from Desktop Icon JSON files. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if isinstance(data, list):
		return

	# Extract the label field (main translatable field for Desktop Icons)
	label = data.get("label")
	if label:
		yield get_line_number(text, "label", label), "_", label, ["Label of a Desktop Icon"]
