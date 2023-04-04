# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PermissionLog(Document):
	@property
	def changed_at(self):
		return self.creation


def make_perm_log(doc, method=None):
	if not getattr(doc, "log_permission", None):
		return

	params = doc.log_permission() or {}
	if not getattr(doc, "_no_perm_log", False):
		insert_perm_log(doc, doc.get_doc_before_save(), **params)


def insert_perm_log(
	doc: Document,
	doc_before_save: Document = None,
	for_doctype=None,
	for_document=None,
	fields: list | tuple = None,
):
	if doc.flags.get("in_insert", False):
		# don't log new documents
		# "update" logs will have what it was changed from and to
		return

	current, previous = get_changes(doc, doc_before_save, fields)
	if not previous and not current:
		return

	frappe.get_doc(
		{
			"doctype": "Permission Log",
			"owner": frappe.session.user,
			"changed_by": frappe.session.user,
			"reference_type": for_doctype and doc.doctype,
			"reference": for_document and doc.name,
			"for_doctype": for_doctype or doc.doctype,
			"for_document": for_document or doc.name,
			"status": "Removed" if not doc_before_save else "Updated",
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
		return dict.fromkeys(current_changes, None), current_changes

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
	def filter_child_fields(child_dicts, filter_keys):
		changes = []
		for field in child_dicts:
			temp = {}
			for key in filter_keys:
				temp[key] = field[key]
			changes.append(temp)

		return changes

	if not filters:
		return changes

	filtered_changes = {}
	for f in filters:
		if isinstance(f, (list, tuple)):
			filtered_changes[f[0]] = changes.get(f[0], [])
			if len(f) > 1:
				filtered_changes[f[0]] = filter_child_fields(changes.get(f[0], []), f[1])
		else:
			filtered_changes[f] = changes.get(f, None)

	return filtered_changes
