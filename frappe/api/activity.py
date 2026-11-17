"""Read handler for the activity part of a v2 document route."""

import frappe
from frappe.desk.form.activity_page import PAGE_SIZE

METHOD = "frappe.desk.form.activity.get_activity_timeline"


def read(doctype: str, name: str) -> dict:
	"""One page of the merged feed: the newest rows, or the rows older than `before`."""
	args = frappe.form_dict
	# an app override of the method (Helpdesk strips email recipients) applies here too; the path comes from hooks
	return frappe.call(  # nosemgrep
		frappe.override_whitelisted_method(METHOD),
		doctype=doctype,
		name=name,
		visible_types=args.get("types"),
		limit=args.get("limit") or PAGE_SIZE,
		before=args.get("before"),
	)
