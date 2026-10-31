import json
from pathlib import Path

from .utils import get_line_number


def extract(fileobj, *args, **kwargs):
	"""Extract the label of an app's view file. To be used by babel extractor.

	:param fileobj: the file-like object the messages should be extracted from
	:rtype: `iterator`
	"""
	text = fileobj.read().decode()
	data = json.loads(text)
	if not isinstance(data, dict) or not isinstance(label := data.get("label"), str) or not label:
		return

	key = Path(getattr(fileobj, "name", "")).stem
	yield get_line_number(text, "label", label), "_", label, [f"Label of the {key} view"]
