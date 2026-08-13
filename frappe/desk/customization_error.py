# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The reporter for client-side customization failures.

Page Scripts, third-party extensions and an app's own file scripts all break the
same way — silently, in someone else's browser — so all three report here and land
as ordinary Error Log rows. Neutral ground rather than the Page Script doctype,
because only one of the three tiers has a document to hang this off.

Deliberately not `frappe.log_error`: that helper fingerprints a live Python
traceback and stamps metadata from the current request, so a client-reported JS
error would land with a null fingerprint and metadata describing this call.
"""

import hashlib
import json

import frappe
from frappe import _

TIERS = ("page_script", "extension", "file_script")

PAGE_SCRIPT_PREFIX = "page-script:"

MESSAGE_LIMIT = 1000
STACK_LIMIT = 4000
# `ErrorLog.validate` caps `method` at 140 by prepending the overflow to `error`.
FIELD_LIMIT = 140
ROUTE_LIMIT = 500

# The client already reports at most once per (source, event) per page session;
# this is the backstop against a caller that doesn't.
REPORTS_PER_HOUR = 20
RATE_WINDOW = 60 * 60


@frappe.whitelist(methods=["POST"])
def report_customization_error(
	source: str,
	tier: str,
	event: str,
	doctype: str = "",
	message: str = "",
	stack: str = "",
	record: str = "",
	route: str = "",
) -> None:
	"""Record one customization failure as an Error Log row.

	Open to every logged-in user, deliberately: gating this to script authors would
	silence exactly the script that breaks for end users only, which is the common
	shape now that scripts branch on `page.roles`. Guest is refused by the whitelist.
	"""
	source = _text(source, FIELD_LIMIT)
	tier = _text(tier, 32)
	event = _text(event, FIELD_LIMIT)
	doctype = _text(doctype, FIELD_LIMIT)
	message = _text(message, MESSAGE_LIMIT)
	stack = _text(stack, STACK_LIMIT)
	record = _text(record, FIELD_LIMIT)
	route = _text(route, ROUTE_LIMIT)

	if not source or tier not in TIERS:
		frappe.throw(_("Unknown customization source"), frappe.ValidationError)

	_enforce_user_rate_limit()

	frappe.get_doc(
		doctype="Error Log",
		method=f"Customization: {source} ({event})",
		error=f"{message}\n\n{stack}",
		fingerprint=_fingerprint(tier, source, event, doctype, message),
		metadata=_metadata(tier, source, doctype, record, route),
		**_reference(source),
	).deferred_insert()


def _text(value: str, limit: int) -> str:
	"""Truncate defensively — the client's own caps are not trusted. Type is not
	rechecked here: `frappe.whitelist` validates every annotated parameter against
	its hint before the body runs, so a non-string is already a 417."""
	return value.strip()[:limit]


def _fingerprint(tier: str, source: str, event: str, doctype: str, message: str) -> str:
	"""Group one bug across browsers and versions: the stack is deliberately excluded,
	so the same break does not fragment per user agent."""
	first_line = message.splitlines()[0] if message else ""
	identity = "|".join([tier, source, event, doctype, first_line])
	return hashlib.sha1(identity.encode(), usedforsecurity=False).hexdigest()


def _reference(source: str) -> dict:
	"""The broken customization, not the record being viewed — so the desk list links
	straight to it. Only a Page Script has a document; the other two tiers are
	identified by `method` alone."""
	name = source[len(PAGE_SCRIPT_PREFIX) :] if source.startswith(PAGE_SCRIPT_PREFIX) else ""
	if not name:
		return {}
	return {"reference_doctype": "Page Script", "reference_name": name}


def _metadata(tier: str, source: str, doctype: str, record: str, route: str) -> str:
	"""Reproduction context belongs here, not in the reference fields."""
	agent = frappe.request.headers.get("User-Agent", "") if frappe.request else ""
	return json.dumps(
		{
			"tier": tier,
			"source": source,
			"record": {"doctype": doctype, "name": record},
			"route": route,
			"user_agent": agent,
		}
	)


def _enforce_user_rate_limit() -> None:
	"""Per user, not per IP: an office behind one NAT is many readers of one broken
	script, and each of them is the signal wanted. `rate_limit(key=...)` reads
	`form_dict`, which the hand-rolled caller this guards against can spell however it
	likes, so the counter is keyed on the session instead.
	"""
	if not frappe.request:
		return
	key = frappe.cache.make_key(f"rl:customization_error:{frappe.session.user}")
	if not frappe.cache.get(key):
		frappe.cache.setex(key, RATE_WINDOW, 0)
	if frappe.cache.incrby(key, 1) > REPORTS_PER_HOUR:
		frappe.throw(
			_("You hit the rate limit because of too many requests. Please try after sometime."),
			frappe.RateLimitExceededError,
		)
