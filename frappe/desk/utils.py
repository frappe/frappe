# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def validate_route_conflict(doctype, name):
	"""
	Raises exception if name clashes with routes from other documents for /app routing
	"""

	all_names = []
	for _doctype in ["Page", "Workspace", "DocType"]:
		try:
			all_names.extend(
				[
					slug(d) for d in frappe.get_all(_doctype, pluck="name") if (doctype != _doctype and d != name)
				]
			)
		except frappe.db.TableMissingError:
			pass

	if slug(name) in all_names:
		frappe.msgprint(frappe._("Name already taken, please set a new name"))
		raise frappe.NameError


def slug(name):
	return name.lower().replace(' ', '-')


def check_enqueue_action(doctype, action) -> bool:
	doc = frappe.db.get_list("Enqueue Selected Action", fields=["*"])
	for d in doc:
		if d.document_type == doctype:
			if action == "submit" and d.submit_action:
				return True
			if action == "cancel" and d.cancel_action:
				return True
			if action == "delete" and d.delete_action:
				return True
			if action == "rename" and d.rename_action:
				return True
	return False
