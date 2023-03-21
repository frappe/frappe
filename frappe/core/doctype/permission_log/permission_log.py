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

	perm_log = frappe.get_doc(
		{
			"doctype": "Permission Log",
			"owner": frappe.session.user,
			"for_doctype": doc.doctype,
			"for_document": doc.name,
			"action": get_action(),
			"changes": get_changes(doc),
		}
	)

	if parenttype := getattr(doc, "parenttype", None):
		perm_log.for_parenttype = parenttype
		perm_log.for_parent = doc.parent

	perm_log.db_insert()


def get_changes(doc: Document):
	current_changes = doc.as_dict(
		no_default_fields=True, no_child_table_fields=True, convert_dates_to_str=True
	)
	if not doc.get_doc_before_save():
		return current_changes

	changes = {}
	previous_changes = doc.get_doc_before_save().as_dict(
		no_default_fields=True, no_child_table_fields=True, convert_dates_to_str=True
	)
	for k, v in current_changes.items():
		if previous_changes.get(k, None) != v:
			changes[k] = v

	return frappe.as_json(changes, indent=0)
