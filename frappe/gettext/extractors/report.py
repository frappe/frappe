import json

from .utils import get_line_number


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from report JSON files. To be used to babel extractor
	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if isinstance(data, list):
		return

	if data.get("doctype") != "Report":
		return

	report_name = data.get("report_name")
	yield get_line_number(text, "report_name", report_name), "_", report_name, ["Name of a report"]
