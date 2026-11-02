import json

from .utils import get_line_number


def extract(fileobj, *args, **kwargs):
	"""Extract messages from standard Kanban Board JSON files. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)

	if not isinstance(data, dict) or data.get("doctype") != "Kanban Board":
		return

	if board_name := data.get("kanban_board_name"):
		yield (
			get_line_number(text, "kanban_board_name", board_name),
			"_",
			board_name,
			[f"Name of a Kanban board for {data.get('reference_doctype')}"],
		)
