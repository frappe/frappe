import json
from pathlib import Path

from .utils import get_line_number


def extract(fileobj, *args, **kwargs):
	"""The label of an app's view file, for the babel extractor."""
	text = fileobj.read().decode()
	data = json.loads(text)
	if not isinstance(data, dict) or not isinstance(label := data.get("label"), str) or not label:
		return

	key = Path(getattr(fileobj, "name", "")).stem
	yield get_line_number(text, "label", label), "_", label, [f"Label of the {key} view"]
