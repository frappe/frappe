# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import json
from typing import Optional

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import comma_and, cstr, escape_html, get_fullname, get_link_to_form

TIMELINE_LOG_LIMIT = 20


class PermissionLog(Document):
	_DOCTYPE_NAME = "Permission Log"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		changed_at: DF.Datetime | None
		changed_by: DF.Link | None
		changes: DF.Text | None
		for_doctype: DF.Link
		for_document: DF.DynamicLink
		reference: DF.DynamicLink | None
		reference_type: DF.Link | None
		status: DF.Literal["Updated", "Removed", "Added", "Reset"]
	# end: auto-generated types

	@property
	def changed_at(self):
		return self.creation


def make_perm_log(doc, method=None):
	if not hasattr(doc, "get_permission_log_options"):
		return
	# During reset we insert a single "Reset" log; skip per-Custom-DocPerm "Removed" logs
	if (
		method == "after_delete"
		and doc.doctype == "Custom DocPerm"
		and getattr(frappe.flags, "skip_perm_log_for_doctype", None) == doc.parent
	):
		return

	params = doc.get_permission_log_options(method) or {}
	if not getattr(doc, "_no_perm_log", False):
		insert_perm_log(doc, doc.get_doc_before_save(), **params)


def insert_perm_log(
	doc: Document,
	doc_before_save: Document = None,
	for_doctype: str | None = None,
	for_document: str | None = None,
	fields: list | tuple | None = None,
	custom_changes: dict | None = None,
):
	"""Log a permission change. When custom_changes is provided (e.g. for reset-to-standard),
	it must be {"from": {...}, "to": {...}} and optionally "status"; doc is used for
	reference/owner only."""
	if frappe.flags.in_install or frappe.flags.in_migrate:
		# no need to log changes when migrating or installing app/site
		return

	if custom_changes is not None:
		previous = custom_changes.get("from", {})
		current = custom_changes.get("to", {})
		status = custom_changes.get("status", "Updated")
	else:
		current, previous = get_changes(doc, doc_before_save, fields)
		if not previous and not current:
			return
		status = "Updated" if doc_before_save else ("Added" if doc.flags.in_insert else "Removed")
		# Ensure role (and parent) are always in changes for Custom DocPerm so the UI can show them
		if doc.doctype == "Custom DocPerm":
			previous["role"] = previous.get("role") or (
				doc_before_save and getattr(doc_before_save, "role", None)
			)
			current["role"] = current.get("role") or getattr(doc, "role", None)
			previous["parent"] = previous.get("parent") or (
				doc_before_save and getattr(doc_before_save, "parent", None)
			)
			current["parent"] = current.get("parent") or getattr(doc, "parent", None)

	frappe.get_doc(
		{
			"doctype": "Permission Log",
			"owner": frappe.session.user,
			"changed_by": frappe.session.user,
			"reference_type": for_doctype and doc.doctype,
			"reference": for_document and doc.name,
			"for_doctype": for_doctype or doc.doctype,
			"for_document": for_document or doc.name,
			"status": status,
			"changes": frappe.as_json({"from": previous, "to": current}, indent=0),
		}
	).db_insert()


def get_timeline_content(doctype: str, docname: str) -> list[dict]:
	"""Permission changes of a document for its form timeline (`additional_timeline_content` hook)."""
	if not frappe.has_permission("Permission Log", "read"):
		return []

	logs = frappe.get_list(
		"Permission Log",
		filters={"for_doctype": doctype, "for_document": docname},
		fields=["name", "owner", "creation", "changes"],
		order_by="creation desc",
		limit=TIMELINE_LOG_LIMIT,
	)

	meta = frappe.get_meta(doctype)
	timeline_content = []
	for log in logs:
		if phrases := describe_log(log, meta):
			timeline_content.append(
				{"icon": "lock", "creation": log.creation, "content": format_timeline_text(log, phrases)}
			)

	return timeline_content


def describe_log(log, meta) -> list[str]:
	changes = json.loads(log.changes or "{}")
	previous = changes.get("from") or {}
	current = changes.get("to") or {}

	phrases = []
	for fieldname in dict.fromkeys([*current, *previous]):
		if shown_by_version(meta.get_field(fieldname)):
			continue
		label = escape_html(_(meta.get_label(fieldname)))
		phrases.extend(describe_change(label, previous.get(fieldname), current.get(fieldname)))

	return phrases


def shown_by_version(df) -> bool:
	return bool(df and (not df.hidden or df.show_on_timeline))


def describe_change(label: str, previous, current) -> list[str]:
	if isinstance(previous, list) or isinstance(current, list):
		return describe_row_changes(label, previous or [], current or [])

	if previous == current or not (previous or current):
		return []
	if not current:
		return [_("cleared {0}").format(label)]
	if not previous:
		return [_("set {0} to {1}").format(label, format_value(current))]
	return [_("changed {0} from {1} to {2}").format(label, format_value(previous), format_value(current))]


def describe_row_changes(label: str, removed_rows: list[dict], added_rows: list[dict]) -> list[str]:
	phrases = []
	if added_rows:
		phrases.append(_("added {0} to {1}").format(format_rows(added_rows), label))
	if removed_rows:
		phrases.append(_("removed {0} from {1}").format(format_rows(removed_rows), label))
	return phrases


def format_rows(rows: list[dict]) -> str:
	return comma_and(
		[format_value(", ".join(cstr(v) for v in row.values())) for row in rows], add_quotes=False
	)


def format_value(value) -> str:
	return f"<b>{escape_html(cstr(value))}</b>"


def format_timeline_text(log, phrases: list[str]) -> str:
	user = get_link_to_form("User", log.owner, escape_html(get_fullname(log.owner)))
	changes = get_link_to_form("Permission Log", log.name, comma_and(phrases, add_quotes=False))
	return f"{user} {changes}"


def get_changes(doc: Document, doc_before_save=None, fields=None):
	current_changes = get_filtered_changes(
		doc.as_dict(
			no_default_fields=True,
			no_child_table_fields=True,
			no_private_properties=True,
		),
		fields,
	)

	if not doc_before_save:
		empty_changes = dict.fromkeys(current_changes, "")
		return (current_changes, empty_changes) if doc.flags.in_insert else (empty_changes, current_changes)

	previous_changes = get_filtered_changes(
		doc_before_save.as_dict(
			no_default_fields=True,
			no_child_table_fields=True,
			no_private_properties=True,
		),
		fields,
	)

	return get_changes_diff(current_changes, previous_changes)


def get_changes_diff(current_changes, previous_changes):
	# TODO: track, added, removed and changed rows in child tables

	current_values = {}
	previous_values = {}

	for k, current_val in current_changes.items():
		if isinstance(current_val, list):
			# for child table docs
			current = {frozenset(row.items()) for row in current_val}
			previous = {frozenset(row.items()) for row in previous_changes[k]}
			if not current.symmetric_difference(previous):
				continue

			previous_values[k] = [dict(i) for i in previous - current]
			current_val = [dict(i) for i in current - previous]

		elif previous_changes.get(k, None) == current_val:
			continue

		previous_values[k] = previous_values[k] if k in previous_values else previous_changes[k]
		current_values[k] = current_val

	return current_values, previous_values


def get_filtered_changes(changes, filters=None):
	def filter_child_docs(child_docs, filter_keys):
		changes = []
		for child in child_docs:
			temp = {}
			for key in filter_keys:
				temp[key] = child[key]
			changes.append(temp)

		return changes

	if not filters:
		return changes

	filtered_changes = {}
	for f in filters:
		if isinstance(f, dict):
			# filtered child docs
			for field, cf in f.items():
				filtered_changes[field] = filter_child_docs(changes.get(field, []), cf)
		else:
			filtered_changes[f] = changes.get(f, None)

	return filtered_changes
