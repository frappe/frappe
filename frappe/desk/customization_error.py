# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Error Log rows for the customization failures the record page reports."""

import hashlib

import frappe
from frappe import _
from frappe.monitor import get_trace_id
from frappe.rate_limiter import rate_limit
from frappe.utils import cstr
from frappe.utils.error import get_error_metadata

TIER_LABELS = {
	"client_script": "Client Script",
	"file_script": "File Script",
	"extension": "Extension",
}
FIELD_LIMIT = 140
MESSAGE_LIMIT = 1000
STACK_LIMIT = 4000
REPEAT_WINDOW_SECONDS = 10 * 60
REPORTS_PER_MINUTE = 30


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=REPORTS_PER_MINUTE, seconds=60, methods="POST")
def report_customization_error(
	source: str,
	tier: str,
	event: str,
	message: str,
	doctype: str = "",
	stack: str = "",
	record: str = "",
	route: str = "",
) -> str | None:
	"""Write one Error Log row for a failed script; return its name, or None for a repeat."""
	report = CustomizationErrorReport(
		source=source,
		tier=tier,
		event=event,
		message=message,
		doctype=doctype,
		stack=stack,
		record=record,
		route=route,
	)
	return report.file()


class CustomizationErrorReport:
	def __init__(self, *, source, tier, event, message, doctype, stack, record, route):
		self.tier = cstr(tier)
		if self.tier not in TIER_LABELS:
			frappe.throw(_("Unknown customization tier: {0}").format(self.tier[:FIELD_LIMIT]))
		self.source = one_line(source)
		self.event = one_line(event)
		self.doctype = one_line(doctype)
		self.record = one_line(record)
		self.route = one_line(route)
		self.message = cstr(message)[:MESSAGE_LIMIT]
		self.stack = cstr(stack)[:STACK_LIMIT]

	def file(self) -> str | None:
		if self.is_repeat():
			return None
		error_log = frappe.get_doc(
			doctype="Error Log",
			method=self.title(),
			error=self.body(),
			reference_doctype=self.reference_doctype(),
			reference_name=self.record or None,
			trace_id=get_trace_id(),
			metadata=get_error_metadata(),
			fingerprint=self.fingerprint(),
		)
		error_log.insert(ignore_permissions=True)
		return error_log.name

	def title(self) -> str:
		label = TIER_LABELS[self.tier]
		where = f" on {self.doctype}" if self.doctype else ""
		return f"{label} error{where}: {self.source} {self.event}"[:FIELD_LIMIT]

	def body(self) -> str:
		lines = [
			f"Source: {self.source}",
			f"Tier: {self.tier}",
			f"Event: {self.event}",
			f"Record: {self.record}",
			f"Route: {self.route}",
			"",
			self.message,
		]
		if self.stack:
			lines += ["", self.stack]
		return "\n".join(lines)

	def reference_doctype(self) -> str | None:
		if self.doctype and frappe.db.exists("DocType", self.doctype):
			return self.doctype
		return None

	def fingerprint(self) -> str:
		parts = "\n".join([self.tier, self.source, self.event, self.doctype, self.message])
		return hashlib.sha1(parts.encode(), usedforsecurity=False).hexdigest()

	def is_repeat(self) -> bool:
		# Per user, so a caller can pre-claim only their own reports; atomic, so two tabs file one row.
		claim = frappe.cache.make_key(f"customization_error:{frappe.session.user}:{self.fingerprint()}")
		# nosemgrep: frappe-cache-breaks-multitenancy
		return not frappe.cache.set(name=claim, value=1, ex=REPEAT_WINDOW_SECONDS, nx=True)


def one_line(value) -> str:
	return " ".join(cstr(value).split())[:FIELD_LIMIT]
