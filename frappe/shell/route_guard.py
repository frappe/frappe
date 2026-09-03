# The runtime half of the claim surface: no website document may take a route under /apps.

# A wildcard `doc_events` validate, not a `WebsiteGenerator` guard: three of its four
# subclasses override `validate()` without calling `super()`.

import frappe
from frappe import _

from . import SHELL_ROOT

#: A closed constant, not a hook: an app must not be able to claim website routes.
RESERVED_ROUTES = frozenset({SHELL_ROOT})


class ReservedRouteError(frappe.ValidationError):
	pass


def is_reserved(route: str) -> bool:
	route = (route or "").strip("/ ")
	if not route:
		return False
	first = route.partition("/")[0]
	return first in RESERVED_ROUTES


def validate_route(doc, method=None):
	"""Refuse a document whose `route` would land inside the shell's address space."""
	# Refuse, not warn: `ShellPage` sits ahead of `StaticPage`, so the page would save and never load.
	route = getattr(doc, "route", None)
	if not route or not is_reserved(route):
		return

	# Existing claims skip migrate, patch and install, as `validate_route_conflict` does.
	if frappe.flags.in_migrate or frappe.flags.in_patch or frappe.flags.in_install:
		return

	# Name the field too: routes are autoset from titles, so the operator may be looking at Title.
	frappe.throw(
		_(
			"The route {0} is reserved by the framework — {1} is where installed apps are "
			"served. Set a different value in the <b>Route</b> field of this {2}."
		).format(frappe.bold(route), frappe.bold(f"/{SHELL_ROOT}"), _(doc.doctype)),
		exc=ReservedRouteError,
		title=_("Reserved Route"),
	)
