# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from collections import defaultdict

import frappe

ignore_doctypes = {
	"DocType",
	"Print Format",
	"Role",
	"Module Def",
	"Communication",
	"ToDo",
	"Version",
	"Error Log",
	"Scheduled Job Log",
	"Event Sync Log",
	"Event Update Log",
	"Access Log",
	"View Log",
	"Activity Log",
	"Energy Point Log",
	"Notification Log",
	"Email Queue",
	"DocShare",
	"Document Follow",
	"Console Log",
	"User",
}


def notify_link_count(doctype, name) -> None:
	"""updates link count for given document"""

	if doctype in ignore_doctypes or not frappe.request:
		return

	if not hasattr(frappe.local, "_link_count"):
		frappe.local._link_count = defaultdict(int)
		frappe.db.after_commit.add(flush_local_link_count)

	frappe.local._link_count[(doctype, name)] += 1


def flush_local_link_count() -> None:
	"""flush from local before ending request"""
	new_links = getattr(frappe.local, "_link_count", None)
	if not new_links:
		return

	link_count = frappe.cache.get_value("_link_count") or {}

	for key, value in new_links.items():
		if key in link_count:
			link_count[key] += value
		else:
			link_count[key] = value

	frappe.cache.set_value("_link_count", link_count)
	new_links.clear()


def update_link_count():
	"""increment link count in the `idx` column for the given document"""
	link_count = frappe.cache.get_value("_link_count")

	if link_count:
		for (doctype, name), count in link_count.items():
			try:
				table = frappe.qb.DocType(doctype)
				frappe.qb.update(table).set(table.idx, table.idx + count).where(table.name == name).run()
				frappe.db.commit()
			except Exception as e:
				if not frappe.db.is_table_missing(e):  # table not found, single
					raise e
	# reset the count
	frappe.cache.delete_value("_link_count")
