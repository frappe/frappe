import json


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from report JSON files. To be used to babel extractor
	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if isinstance(data, list):
		return

	if data.get("doctype") != "Report":
		return

	yield None, "_", data.get("report_name"), ["Name of a report"]
