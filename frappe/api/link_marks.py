"""The mark a Link value shows before it, read from the target doctype's meta.

A target with a `color` field gives a dot; otherwise its `image_field` gives an avatar.
"""

import frappe
from frappe.model import get_permitted_fields
from frappe.model.document import Document

COLOR_FIELDTYPES = ("Select", "Color", "Data")


def mark_link_fields(fields: list[dict]) -> None:
	"""Add `link_mark: {kind, field}` to each Link field whose target gives the caller a mark."""
	marks = {}
	for df in fields:
		if df.get("fieldtype") != "Link" or not df.get("options"):
			continue
		if df["options"] not in marks:
			marks[df["options"]] = readable_mark(df["options"])
		if mark := marks[df["options"]]:
			df["link_mark"] = mark


def get_link_marks(doc: Document) -> dict:
	"""The mark values (a colour or an image) of the document's Link values, keyed `Doctype::name`, read with the caller's permissions."""
	names: dict[str, set] = {}
	targets: dict[str, dict | None] = {}
	for df in frappe.get_meta(doc.doctype).get_link_fields():
		if not (value := doc.get(df.fieldname)):
			continue
		if df.options not in targets:
			targets[df.options] = readable_mark(df.options)
		if targets[df.options]:
			names.setdefault(df.options, set()).add(value)

	marks = {}
	for target, values in names.items():
		field = targets[target]["field"]
		rows = frappe.get_list(target, filters={"name": ("in", sorted(values))}, fields=["name", field])
		marks.update({f"{target}::{row.name}": row[field] for row in rows if row[field]})
	return marks


def readable_mark(target: str) -> dict | None:
	"""The first mark of the target the caller may read."""
	readable = get_permitted_fields(target, ignore_virtual=True)
	for mark in marks_of(frappe.get_meta(target)):
		if mark["field"] in readable:
			return mark


def mark_of(meta) -> dict | None:
	return next(marks_of(meta), None)


def marks_of(meta):
	color = meta.get_field("color")
	if color and color.fieldtype in COLOR_FIELDTYPES:
		yield {"kind": "color", "field": "color"}
	if meta.image_field and meta.has_field(meta.image_field):
		yield {"kind": "image", "field": meta.image_field}
