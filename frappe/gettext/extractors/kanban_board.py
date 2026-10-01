import json


def extract(fileobj, *args, **kwargs):
	"""Extract messages from standard Kanban Board JSON files. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	data = json.load(fileobj)

	if not isinstance(data, dict) or data.get("doctype") != "Kanban Board":
		return

	if board_name := data.get("kanban_board_name"):
		yield None, "_", board_name, [f"Name of a Kanban board for {data.get('reference_doctype')}"]
