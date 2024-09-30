# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

from typing import Optional

import frappe
from frappe.model.document import Document


class PermissionLog(Document):
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
		status: DF.Literal["Updated", "Removed", "Added"]
	# end: auto-generated types

	@property
	def changed_at(self):
		return self.creation


def make_perm_log(doc, method=None):
	if not hasattr(doc, "get_permission_log_options"):
		return

	params = doc.get_permission_log_options(method) or {}
	if not getattr(doc, "_no_perm_log", False):
		insert_perm_log(doc, doc.get_doc_before_save(), **params)


def insert_perm_log(
	doc: Document,
	doc_before_save: Document = None,
	for_doctype: Optional["str"] = None,
	for_document: Optional["str"] = None,
	fields: Optional["list | tuple"] = None,
):
	if frappe.flags.in_install or frappe.flags.in_migrate:
		# no need to log changes when migrating or installing app/site
		return

	current, previous = get_changes(doc, doc_before_save, fields)
	if not previous and not current:
		return

	status = "Updated" if doc_before_save else ("Added" if doc.flags.in_insert else "Removed")

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
