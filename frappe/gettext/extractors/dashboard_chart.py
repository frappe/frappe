import json

from .utils import get_line_number

FIELDS = {
	"chart_name": "Name of a Dashboard Chart",
	"report_name": "Name of a report",
	"empty_state_message": "Message shown when a Dashboard Chart has no data",
}


def extract(fileobj, *args, **kwargs):
	"""
	Extract messages from Dashboard Chart JSON files. To be used to babel extractor
	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if isinstance(data, list):
		return

	if data.get("doctype") != "Dashboard Chart":
		return

	for key, comment in FIELDS.items():
		if value := data.get(key):
			yield get_line_number(text, key, value), "_", value, [comment]
