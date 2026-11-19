"""Named parts a v2 read returns beside its data.

`GET /api/v2/document/<doctype>/<name>?include=permissions,seen` adds each named
part under its own top-level key. `GET /api/v2/doctype/<doctype>/meta?include=children`
does the same for the child-table doctypes, and `GET /api/v2/document/<doctype>?include=count`
adds a capped row count beside the list.
"""

from collections.abc import Iterable

import frappe
from frappe import _
from frappe.api.link_marks import get_link_marks, mark_link_fields
from frappe.desk.doctype.favourite.favourite import get_favourites as get_favourite_rows
from frappe.desk.form.document_follow import is_document_followed
from frappe.desk.form.load import (
	get_attachments,
	get_comments,
	get_title_values_for_link_and_dynamic_link_fields,
	get_title_values_for_table_and_multiselect_fields,
)
from frappe.model.document import Document
from frappe.model.workflow import get_workflow_name, get_workflow_names, get_workflow_state_field
from frappe.permissions import get_doc_permissions
from frappe.share import _get_users as get_shares


def parse_include(value) -> list[str]:
	"""The part names from `include`, a comma-separated string."""
	if value is None:
		return []
	if not isinstance(value, str):
		raise frappe.ValidationError(_("'include' must be a comma-separated string"))
	return [part.strip() for part in value.split(",") if part.strip()]


def add_document_parts(doc: Document, include: list[str]) -> None:
	"""Put each named part of `doc` on `frappe.response` under its own key; an unknown name raises."""
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
	"""Put each named part of the doctype's meta on `frappe.response`; an unknown name raises."""
	for part in include:
		if part not in META_PARTS:
			raise UnknownPartError(part, META_PARTS)
	for part in include:
		frappe.response[part] = META_PARTS[part](doctype)


def add_list_parts(doctype: str, include: list[str], filters, or_filters, group_by: str | None) -> None:
	"""Put each named part of a list read on `frappe.response`; an unknown name raises."""
	for part in include:
		if part not in LIST_PARTS and part not in ROW_PARTS:
			raise UnknownPartError(part, [*LIST_PARTS, *ROW_PARTS])
	for part in include:
		if part in LIST_PARTS:
			LIST_PARTS[part](doctype, filters, or_filters, group_by)


def add_row_parts(doctype: str, include: list[str], rows: list) -> None:
	"""Put each named part that reads the page's rows on `frappe.response`; run after the rows are read."""
	for part in include:
		if part in ROW_PARTS:
			ROW_PARTS[part](doctype, rows)


class UnknownPartError(frappe.ValidationError):
	http_status_code = 417

	def __init__(self, part: str, known: Iterable[str]):
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


def get_tag_colors(doc: Document) -> dict[str, str]:
	return colors_of_tags(get_tags(doc))


def colors_of_tags(tags: Iterable[str]) -> dict[str, str]:
	"""The stored colour of each named tag; `""` for one without (it draws gray), so a cleared colour clears."""
	names = sorted(set(tags))
	if not names:
		return {}
	rows = frappe.get_list("Tag", filters={"name": ("in", names)}, fields=["name", "color"])
	return {row.name: row.color or "" for row in rows}


def get_favourites(doc: Document) -> list[dict]:
	return get_favourite_rows(doc.doctype, doc.name)


def get_follows(doc: Document) -> bool:
	"""Whether the caller follows the document."""
	return bool(is_document_followed(doc.doctype, doc.name, frappe.session.user))


def get_link_titles(doc: Document) -> dict:
	titles = get_title_values_for_link_and_dynamic_link_fields(doc)
	titles.update(get_title_values_for_table_and_multiselect_fields(doc))
	return titles


USERS_PART = "users"
# the parts that name users, and the row key that holds the id (`None`: the row is the id)
USER_ROW_KEY = {
	"attachments": "owner",
	"assignments": "user",
	"shares": "user",
	"favourites": "user",
	"comments": "owner",
	"seen": None,
}


def get_users(doc: Document, include: list[str]) -> dict:
	parts = {part: frappe.response.get(part) for part in include if part in USER_ROW_KEY}
	return users_named_by(doc, parts)


def users_named_by(doc: Document, parts: dict[str, list]) -> dict:
	"""Names and images keyed by user; the v2 keys are `full_name` and `user_image`, not v1's `fullname`/`image`."""
	# a never-saved Single has no modified_by
	names = {user for user in (doc.owner, doc.modified_by) if user}
	for part, rows in parts.items():
		key = USER_ROW_KEY[part]
		for row in rows or []:
			user = row if key is None else row.get(key)
			if user:
				names.add(user)
	names.discard("everyone")
	# a single that was never saved has no `modified_by`
	names.discard(None)
	users = frappe.get_all(
		"User",
		fields=["name", "full_name", "user_image"],
		filters={"name": ("in", sorted(names))},
	)
	return {u.name: {"full_name": u.full_name, "user_image": u.user_image} for u in users}


def mark_seen(doc: Document) -> list[str]:
	seen = frappe.parse_json(doc.get("_seen") or "[]")
	# the same guard as add_seen, which writes after the response; the list is composed here
	writes = doc.meta.track_seen and not frappe.flags.read_only and not doc.meta.issingle
	if writes and frappe.session.user not in seen:
		doc.add_seen()
		seen.append(frappe.session.user)
	return seen


DOCUMENT_PARTS = {
	"permissions": get_doc_permissions,
	"attachments": lambda doc: get_attachments(doc.doctype, doc.name),
	"assignments": get_assignments,
	"shares": get_share_rows,
	"tags": get_tags,
	"tag_colors": get_tag_colors,
	"favourites": get_favourites,
	"follows": get_follows,
	"comments": lambda doc: get_comments(doc.doctype, doc.name),
	"seen": mark_seen,
	"link_titles": get_link_titles,
	"link_marks": get_link_marks,
}


def get_children(doctype: str) -> list[dict]:
	meta = frappe.get_meta(doctype)
	# two table fields can share one child doctype
	children = {df.options for df in meta.get_table_fields(include_computed=True)}
	return [serialize_meta(frappe.get_meta(child), parenttype=doctype) for child in sorted(children)]


def serialize_meta(meta, parenttype: str | None = None) -> dict:
	"""The meta as the route sends it, with the fields masked for the caller."""
	d = meta.as_dict(no_nulls=True)
	if parenttype is None:
		mark_link_fields(d["fields"])
	d["masked_fields"] = [df.fieldname for df in meta.get_masked_fields(parenttype=parenttype)]
	return d


def get_doctype_state_field(doctype: str) -> str | None:
	"""The field holding the state under the doctype's active workflow, or None."""
	name = get_workflow_name(doctype)
	return get_workflow_state_field(name) if name else None


def get_workflow_state_styles(doctype: str) -> dict[str, str]:
	"""The style of each state of the doctype's active workflows, for the states that have one."""
	states = {
		row.state
		for name in get_workflow_names(doctype)
		for row in frappe.get_cached_doc("Workflow", name).states
	}
	if not states:
		return {}
	rows = frappe.get_all(
		"Workflow State", filters={"name": ("in", sorted(states))}, fields=["name", "style"]
	)
	return {row.name: row.style for row in rows if row.style}


META_PARTS = {"children": get_children}


# a list count stops here; the client shows "1000+" past it. The query reads one row
# past the cap so a list of exactly COUNT_CAP rows is not reported as capped
COUNT_CAP = 1000


def add_count(doctype: str, filters, or_filters, group_by: str | None) -> None:
	"""`count` (at most COUNT_CAP) and `count_capped` for the list's filters; `count` is None when the one-second timeout hits."""
	from frappe.desk.reportview import count_rows

	count = count_rows(
		doctype=doctype,
		filters=filters,
		or_filters=or_filters,
		group_by=group_by,
		limit=COUNT_CAP + 1,
	)
	capped = count is not None and count > COUNT_CAP
	frappe.response["count"] = COUNT_CAP if capped else count
	frappe.response["count_capped"] = capped


LIST_PARTS = {"count": add_count}


def add_starred(doctype: str, rows: list) -> None:
	"""`favourites`: the names among the page's rows that the session user starred."""
	names = [str(row["name"]) for row in rows if isinstance(row, dict) and row.get("name") is not None]
	starred = (
		frappe.get_all(
			"Favourite",
			filters={
				"user": frappe.session.user,
				"reference_doctype": doctype,
				"reference_name": ("in", names),
				"view": "",
			},
			pluck="reference_name",
		)
		if names
		else []
	)
	frappe.response["favourites"] = sorted(starred)


def _user_ids(stored) -> list[str]:
	"""The user ids a `_assign` or `_liked_by` value holds; a malformed value holds none."""
	try:
		ids = frappe.parse_json(stored or "[]")
	except ValueError:
		return []
	return [user for user in ids if isinstance(user, str) and user] if isinstance(ids, list) else []


def add_row_users(doctype: str, rows: list) -> None:
	"""`users`: full name and image of each user the page's `_assign` and `_liked_by` columns name."""
	names: set[str] = set()
	for row in rows:
		if not isinstance(row, dict):
			continue
		for column in ("_assign", "_liked_by"):
			names.update(_user_ids(row.get(column)))
	users = frappe.get_all(
		"User",
		fields=["name", "full_name", "user_image"],
		filters={"name": ("in", sorted(names))},
	)
	frappe.response[USERS_PART] = {
		u.name: {"full_name": u.full_name, "user_image": u.user_image} for u in users
	}


def add_comment_counts(doctype: str, rows: list) -> None:
	"""`comment_counts`: the comment count of each of the page's rows. `_comments` stays unreadable as a field."""
	names = [str(row["name"]) for row in rows if isinstance(row, dict) and row.get("name") is not None]
	if not names or frappe.get_meta(doctype).is_virtual or not frappe.db.has_column(doctype, "_comments"):
		frappe.response["comment_counts"] = {}
		return
	# like desk v1's list: a comment is one "name" key, so counting keys skips parsing the JSON
	stored = frappe.db.get_values(doctype, {"name": ("in", names)}, ["name", "_comments"])
	frappe.response["comment_counts"] = {name: (comments or "").count('"name"') for name, comments in stored}


def add_row_tag_colors(doctype: str, rows: list) -> None:
	"""`tag_colors`: the stored colour of each tag the page's `_user_tags` column names."""
	tags: set[str] = set()
	for row in rows:
		stored = row.get("_user_tags") if isinstance(row, dict) else None
		if isinstance(stored, str):
			tags.update(tag for tag in stored.split(",") if tag)
	frappe.response["tag_colors"] = colors_of_tags(tags)


ROW_PARTS = {
	"favourites": add_starred,
	USERS_PART: add_row_users,
	"comment_counts": add_comment_counts,
	"tag_colors": add_row_tag_colors,
}
