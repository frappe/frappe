"""Read handler for the activity part of a v2 document route."""

import frappe
from frappe import _
from frappe.desk.form.activity import (
	get_activity_timeline,
	get_more_email_activities,
	get_more_milestone_activities,
)
from frappe.utils import cint

STREAMS = {
	"emails": get_more_email_activities,
	"milestones": get_more_milestone_activities,
}


class UnknownStreamError(frappe.ValidationError):
	http_status_code = 417

	def __init__(self, stream: str):
		super().__init__(
			_("Unknown activity stream {0}. Known streams: {1}").format(stream, ", ".join(STREAMS))
		)


def read(doctype: str, name: str) -> dict:
	"""The feed's first page, or one stream's next page when `stream` is given."""
	args = frappe.form_dict
	stream = args.get("stream")
	if not stream:
		return get_activity_timeline(doctype, name, args.get("types"))
	if stream not in STREAMS:
		raise UnknownStreamError(stream)
	return STREAMS[stream](doctype, name, cint(args.get("start")))
