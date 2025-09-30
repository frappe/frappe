import importlib
from pathlib import Path

from frappe.utils import get_bench_path


def extract(fileobj, *args, **kwargs):
	"""Extract standard navbar and help items from a python file.

	:param fileobj: file-like object to extract messages from. Should be a
	    python file containing two global variables `standard_navbar_items` and
	    `standard_help_items` which are lists of dicts.
	"""
	module = get_module(fileobj.name)

	if hasattr(module, "standard_navbar_items"):
		standard_navbar_items = module.standard_navbar_items
		for nav_item in standard_navbar_items:
			if label := nav_item.get("item_label"):
				item_type = nav_item.get("item_type")
				yield (
					None,
					"_",
					label,
					[
						"Label of a standard navbar item",
						f"Type: {item_type}",
					],
				)

	if hasattr(module, "standard_help_items"):
		standard_help_items = module.standard_help_items
		for help_item in standard_help_items:
			if label := help_item.get("item_label"):
				item_type = help_item.get("item_type")
				yield (
					None,
					"_",
					label,
					[
						"Label of a standard help item",
						f"Type: {item_type}",
					],
				)


def get_module(path):
	_path = Path(path)
	rel_path = _path.relative_to(get_bench_path())
	import_path = ".".join(rel_path.parts[2:]).rstrip(".py")
	return importlib.import_module(import_path)
