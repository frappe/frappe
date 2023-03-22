# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

from difflib import HtmlDiff

import frappe
from frappe.model.document import Document


class PermissionLog(Document):
	@property
	def changed_by(self):
		return self.owner

	@property
	def changed_at(self):
		return self.creation


def make_perm_log(
	doc: Document,
	doc_before_save: Document = None,
	filters: list | tuple = None,
	for_delete: bool = False,
):
	def get_action():
		if not for_delete:
			if doc.is_new():
				return "Create"
			return "Update"
		return "Remove"

	current, previous = get_changes(doc, doc_before_save, filters, for_delete)
	if not previous and not current:
		return

	frappe.get_doc(
		{
			"doctype": "Permission Log",
			"owner": frappe.session.user,
			"for_doctype": doc.doctype,
			"for_document": doc.name,
			"action": get_action(),
			"changes": frappe.as_json({"from": previous, "to": current}, indent=0),
		}
	).db_insert()


def get_changes(doc: Document, doc_before_save=None, filters=None, for_delete=False):
	current_changes = get_filtered_changes(
		doc.as_dict(
			no_default_fields=True,
			no_child_table_fields=not (doc.doctype == "Custom DocPerm"),
			no_private_properties=True,
		),
		filters,
	)

	if not doc_before_save:
		empty_state = dict.fromkeys(current_changes, None)
		return (empty_state, current_changes) if for_delete else (current_changes, empty_state)

	previous_changes = get_filtered_changes(
		doc_before_save.as_dict(
			no_default_fields=True,
			no_child_table_fields=not (doc.doctype == "Custom DocPerm"),
			no_private_properties=True,
		),
		filters,
	)

	return clean_changes(current_changes, previous_changes)


def clean_changes(current_changes, previous_changes):
	current_values = {}
	previous_values = {}

	for k, current_val in current_changes.items():
		if isinstance(current_val, list):
			# for child table docs
			if current_val and previous_changes.get(k, None):
				current = {frozenset(row.items()) for row in current_val}
				previous = {frozenset(row.items()) for row in previous_changes[k]}
				if len(current) == len(previous) and not (current - previous):
					continue

			elif not current_val and not previous_changes.get(k, None):
				continue

		elif previous_changes.get(k, None) == current_val:
			continue

		previous_values[k] = previous_changes[k]
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
