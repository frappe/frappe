# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""The app tier of `Form Layout`: one JSON file per layout type in a DocType's `frontend/layouts/` folder.

A file holds a list of `{title?, condition?, layout, omitted, size?}` entries, at most one with no
condition. A file of one bare entry, the shape before titled layouts, reads as a list of one.
"""

import functools
import hashlib
import json
import os
from typing import NamedTuple

import frappe
from frappe import _
from frappe.modules.utils import get_doc_path
from frappe.utils import get_bench_path


class AppLayout(NamedTuple):
	title: str | None
	condition: str | None
	layout: str
	omitted: tuple[str, ...]
	size: str | None


class AppLayouts(NamedTuple):
	entries: tuple[AppLayout, ...]
	version: str


def read_app_layouts(dt: str, type: str) -> AppLayouts | None:
	"""The app's layouts of `type` for `dt`, or `None` when its DocType folder has no such file."""
	key = app_layout_key(dt, type)
	return load_app_layouts(*key) if key else None


def app_layout_key(dt: str, type: str) -> tuple[str, int, int] | None:
	"""The file's cache key: its path, modified time and size, so an edited file is read again."""
	path = app_layout_path(dt, type)
	return app_layout_key_of(path) if path else None


def app_layout_key_of(path: str) -> tuple[str, int, int] | None:
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


def content_hash(content: bytes) -> str:
	return hashlib.sha256(content).hexdigest()


@functools.lru_cache(maxsize=256)
def load_app_layouts(path: str, mtime_ns: int, size: int) -> AppLayouts:
	# App source path from the DocType's module; never request-derived.
	with open(path, "rb") as f:  # nosemgrep
		content = f.read()
	data = json.loads(content)
	entries = tuple(entry_of(item) for item in (data if isinstance(data, list) else [data]))
	if sum(1 for entry in entries if not entry.condition) > 1:
		frappe.throw(
			_("The layout file {0} has more than one layout with no condition.").format(shown_path(path)),
			title=_("Invalid Layout File"),
		)
	return AppLayouts(entries=entries, version=content_hash(content))


def entry_of(data: dict) -> AppLayout:
	if not isinstance(data, dict):
		frappe.throw(_("Each layout in a layout file must be an object."), title=_("Invalid Layout File"))
	return AppLayout(
		title=data.get("title") or None,
		condition=data.get("condition") or None,
		layout=json.dumps(data.get("layout") or []),
		omitted=tuple(data.get("omitted") or []),
		size=data.get("size"),
	)


def shown_path(path: str) -> str:
	return os.path.relpath(path, os.path.join(get_bench_path(), "apps"))
