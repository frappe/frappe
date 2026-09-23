"""Read handler for the activity part of a v2 document route."""

import frappe
from frappe.desk.form.activity import get_activity_timeline
from frappe.desk.form.activity_page import PAGE_SIZE


def read(doctype: str, name: str) -> dict:
	"""One page of the merged feed: the newest rows, or the rows older than `before`."""
	args = frappe.form_dict
	return get_activity_timeline(
		doctype, name, args.get("types"), limit=args.get("limit") or PAGE_SIZE, before=args.get("before")
	)
