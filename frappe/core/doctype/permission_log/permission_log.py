# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PermissionLog(Document):
	@property
	def changed_by(self):
		return self.owner

	@property
	def changed_at(self):
		return self.creation


def make_perm_log(doc: Document, for_delete: bool = False):
	def get_action():
		if not for_delete:
			if doc.is_new():
				return "Create"
			return "Update"
		return "Remove"

	changes = get_changes(doc, for_delete)
	if not changes["from"] and not changes["to"]:
		return

	frappe.get_doc(
		{
			"doctype": "Permission Log",
			"owner": frappe.session.user,
			"for_doctype": doc.doctype,
			"for_document": doc.name,
			"for_parenttype": getattr(doc, "parenttype", None),
			"for_parent": getattr(doc, "parent", None),
			"action": get_action(),
			"changes": frappe.as_json(changes, indent=0),
		}
	).db_insert()


def get_changes(doc: Document, for_delete):
	current_changes = doc.as_dict(
		no_default_fields=True, no_child_table_fields=True, no_private_properties=True
	)

	if not doc.get_doc_before_save():
		if for_delete:
			return {"from": current_changes, "to": dict.fromkeys(current_changes, None)}
		return {"from": dict.fromkeys(current_changes, None), "to": current_changes}

	previous_changes = doc.get_doc_before_save().as_dict(
		no_default_fields=True, no_child_table_fields=True, no_private_properties=True
	)

	return get_changes_dict(current_changes, previous_changes)


def get_changes_dict(current_changes, previous_changes):
	changes = {"from": {}, "to": {}}

	def set_changes(key, current, previous):
		changes["from"][key] = previous
		changes["to"][key] = current

	for k, v in current_changes.items():
		if isinstance(v, list):
			if v and previous_changes.get(k, None):
				i_set = {frozenset(row.items()) for row in v}
				a_set = {frozenset(row.items()) for row in previous_changes[k]}

				if len(i_set) == len(a_set) and not (i_set - a_set):
					continue

				set_changes(k, v, previous_changes[k])
			else:
				if not v and not previous_changes.get(k, None):
					continue

				set_changes(k, v, previous_changes[k])
		elif previous_changes.get(k, None) != v:
			set_changes(k, v, previous_changes[k])

	return changes
