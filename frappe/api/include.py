"""Named parts a v2 read returns beside its data.

`GET /api/v2/document/<doctype>/<name>?include=permissions,seen` adds each named
part under its own top-level key. `GET /api/v2/doctype/<doctype>/meta?include=children`
does the same for the child-table doctypes.
"""

import frappe
from frappe import _
from frappe.desk.doctype.favourite.favourite import get_favourites as get_favourite_rows
from frappe.desk.form.load import (
	get_attachments,
	get_comments,
	get_title_values_for_link_and_dynamic_link_fields,
	get_title_values_for_table_and_multiselect_fields,
)
from frappe.model.document import Document
from frappe.permissions import get_doc_permissions
from frappe.share import _get_users as get_shares


def parse_include(value: str | list | None) -> list[str]:
	if not value:
		return []
	if isinstance(value, str):
		value = value.split(",")
	return [part.strip() for part in value if part.strip()]


def add_document_parts(doc: Document, include: list[str]) -> None:
	for part in include:
		if part not in DOCUMENT_PARTS and part != USERS_PART:
			raise UnknownPartError(part, [*DOCUMENT_PARTS, USERS_PART])
	for part in include:
		if part != USERS_PART:
			frappe.response[part] = DOCUMENT_PARTS[part](doc)
	if USERS_PART in include:
		# built last: it names everyone the other parts mention
		frappe.response[USERS_PART] = get_users(doc, include)


def add_meta_parts(doctype: str, include: list[str]) -> None:
	for part in include:
		if part not in META_PARTS:
			raise UnknownPartError(part, META_PARTS)
		frappe.response[part] = META_PARTS[part](doctype)


class UnknownPartError(frappe.ValidationError):
	http_status_code = 417

	def __init__(self, part: str, known: dict):
		super().__init__(_("Unknown include part {0}. Known parts: {1}").format(part, ", ".join(known)))


def get_assignments(doc: Document) -> list[dict]:
	return frappe.get_all(
		"ToDo",
		fields=["allocated_to as user", "description", "priority", "date"],
		filters={
			"reference_type": doc.doctype,
			"reference_name": str(doc.name),
			"status": ("not in", ("Cancelled", "Closed")),
			"allocated_to": ("is", "set"),
		},
		order_by="creation asc",
	)


def get_share_rows(doc: Document) -> list[dict]:
	# `everyone` is the reserved user for the everyone share
	return [
		{
			"user": "everyone" if row.everyone else row.user,
			"read": row.read,
			"write": row.write,
			"submit": row.submit,
			"share": row.share,
		}
		for row in get_shares(doc)
	]


def get_tags(doc: Document) -> list[str]:
	return frappe.get_all(
		"Tag Link",
		filters={"document_type": doc.doctype, "document_name": str(doc.name)},
		pluck="tag",
		order_by="creation asc",
	)


def get_favourites(doc: Document) -> list[dict]:
	return get_favourite_rows(doc.doctype, doc.name)


def get_link_titles(doc: Document) -> dict:
	titles = get_title_values_for_link_and_dynamic_link_fields(doc)
	titles.update(get_title_values_for_table_and_multiselect_fields(doc))
	return titles


USERS_PART = "users"
USER_KEYS = ("user", "owner", "modified_by", "comment_by")


def get_users(doc: Document, include: list[str]) -> dict:
	names = {doc.owner, doc.modified_by}
	for part in include:
		rows = frappe.response.get(part)
		if isinstance(rows, list):
			names.update(
				row[key] for row in rows for key in USER_KEYS if isinstance(row, dict) and row.get(key)
			)
	names.discard("everyone")
	users = frappe.get_all(
		"User",
		fields=["name", "full_name", "user_image"],
		filters={"name": ("in", sorted(names))},
	)
	return {u.name: {"full_name": u.full_name, "user_image": u.user_image} for u in users}


def mark_seen(doc: Document) -> list[str]:
	seen = frappe.parse_json(doc.get("_seen") or "[]")
	if doc.meta.track_seen and frappe.session.user not in seen:
		# add_seen writes after the response, so the list is composed here
		doc.add_seen()
		seen.append(frappe.session.user)
	return seen


DOCUMENT_PARTS = {
	"permissions": get_doc_permissions,
	"attachments": lambda doc: get_attachments(doc.doctype, doc.name),
	"assignments": get_assignments,
	"shares": get_share_rows,
	"tags": get_tags,
	"favourites": get_favourites,
	"comments": lambda doc: get_comments(doc.doctype, doc.name),
	"seen": mark_seen,
	"link_titles": get_link_titles,
}


def get_children(doctype: str) -> list[dict]:
	meta = frappe.get_meta(doctype)
	return [
		frappe.get_meta(df.options).as_dict(no_nulls=True)
		for df in meta.get_table_fields(include_computed=True)
	]


META_PARTS = {"children": get_children}
