import json


def extract(fileobj, *args, **kwargs):
	"""Extract messages from Desktop Icon JSON files. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	# Extract the label field (main translatable field for Desktop Icons)
	label = data.get("label")
	if label:
		yield None, "_", label, ["Label of a Desktop Icon"]
