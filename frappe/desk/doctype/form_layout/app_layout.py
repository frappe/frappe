# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""The app tier of `Form Layout`: one JSON file per layout type in a DocType's `frontend/layouts/` folder."""

import functools
import json
import os
from typing import NamedTuple

import frappe
from frappe.modules.utils import get_doc_path


class AppLayout(NamedTuple):
	layout: str
	omitted: tuple[str, ...]


def read_app_layout(dt: str, type: str) -> AppLayout | None:
	"""The app's layout of `type` for `dt`, or `None` when its DocType folder has no such file."""
	key = app_layout_key(dt, type)
	return load_app_layout(*key) if key else None


def app_layout_key(dt: str, type: str) -> tuple[str, int, int] | None:
	"""The file's cache key: its path, modified time and size, so an edited file is read again."""
	path = app_layout_path(dt, type)
	if not path:
		return None
	try:
		stat = os.stat(path)
	except FileNotFoundError:
		return None
	return path, stat.st_mtime_ns, stat.st_size


def app_layout_path(dt: str, type: str) -> str | None:
	meta = frappe.get_meta(dt)
	if meta.custom:
		return None
	return os.path.join(
		get_doc_path(meta.module, "DocType", dt), "frontend", "layouts", f"{frappe.scrub(type)}.json"
	)


@functools.lru_cache(maxsize=256)
def load_app_layout(path: str, mtime_ns: int, size: int) -> AppLayout:
	# App source path from the DocType's module; never request-derived.
	with open(path) as f:  # nosemgrep
		data = json.load(f)
	return AppLayout(layout=json.dumps(data.get("layout") or []), omitted=tuple(data.get("omitted") or []))
