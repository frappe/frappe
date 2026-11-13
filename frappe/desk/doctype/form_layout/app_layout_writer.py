# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""Writes an app layout file, after each entry passes the checks a `Form Layout` save runs."""

import json
import os

import frappe
from frappe import _
from frappe.desk.doctype.form_layout import app_layout
from frappe.desk.doctype.form_layout.form_layout import (
	OMITTING_LAYOUT_TYPES,
	omitted_fieldnames,
	parse_layout,
	parse_omitted,
	validate_target,
)


def write_app_layouts(dt: str, type: str, entries: list[dict]) -> str:
	"""Write `dt`'s layouts of `type` as its app file; return the file's hash, the new base_version."""
	validate_target(dt, type)
	path = app_layout.app_layout_path(dt, type)
	if not path:
		frappe.throw(_("{0} is a custom DocType and has no app files.").format(frappe.bold(dt)))
	content = (frappe.as_json(checked_entries(dt, type, entries)) + "\n").encode()
	os.makedirs(os.path.dirname(path), exist_ok=True)
	# App source path from the DocType's module; never request-derived.
	with open(path, "wb") as f:  # nosemgrep
		f.write(content)
	return app_layout.content_hash(content)


def checked_entries(dt: str, type: str, entries: list[dict]) -> list[dict]:
	if not isinstance(entries, list):
		frappe.throw(_("App layouts must be a list."), title=_("Invalid Layout"))
	checked = [checked_entry(dt, type, entry) for entry in entries]
	if sum(1 for entry in checked if not entry.get("condition")) > 1:
		frappe.throw(
			_("Only one {0} layout of {1} can have no condition. Add a condition to the others.").format(
				_(type), frappe.bold(dt)
			),
			title=_("Invalid Layout"),
		)
	return checked


def checked_entry(dt: str, type: str, entry: dict) -> dict:
	"""The entry as the file stores it: containers named, `omitted` computed without site custom fields."""
	if not isinstance(entry, dict):
		frappe.throw(_("Each app layout must be an object."), title=_("Invalid Layout"))
	row = frappe.new_doc("Form Layout")
	row.update(
		{
			"dt": dt,
			"type": type,
			"layout": frappe.as_json(entry.get("layout") or []),
			"omitted": frappe.as_json(entry.get("omitted") or []),
		}
	)
	row.validate_layout()
	layout = parse_layout(row.layout)
	omitted = (
		omitted_fieldnames(dt, layout, custom=False)
		if type in OMITTING_LAYOUT_TYPES
		else parse_omitted(row.omitted)
	)
	checked = {"layout": json.loads(row.layout), "omitted": omitted}
	for key in ("title", "condition"):
		if value := entry.get(key):
			if not isinstance(value, str):
				frappe.throw(_("An app layout's {0} must be text.").format(key), title=_("Invalid Layout"))
			checked[key] = value
	if type == "Quick Entry" and entry.get("size"):
		checked["size"] = checked_size(entry["size"])
	return checked


def checked_size(size: str) -> str:
	if size not in frappe.get_meta("Form Layout").get_field("dialog_size").options.split("\n")[1:]:
		frappe.throw(_("{0} is not a dialog size.").format(frappe.bold(size)), title=_("Invalid Layout"))
	return size
