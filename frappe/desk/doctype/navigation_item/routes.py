# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Where an item that stores a record rather than a URL leads."""

from urllib.parse import quote


def doctype_route(doctype: str) -> str:
	"""The path a doctype's list opens at."""
	return f"/{quote(doctype or '', safe='')}"
