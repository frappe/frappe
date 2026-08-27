# The runtime half of the claim surface.
#
# The install guard covers apps. It does not cover a non-developer typing a Web Page
# titled "Apps" and getting `route = "apps"`, which is what redrew the address space
# in the first place (#42074).
#
# It is a wildcard `doc_events` validate handler rather than a base-class guard,
# because `WebsiteGenerator.validate()` is only `set_route()` and **three of its four
# subclasses bypass it** — `WebPage`, `HelpArticle` and `HelpCategory` all define
# `validate()` without calling `super()`, and the latter two override `set_route()`
# too. A base-class guard would cover one generator in four and could never cover an
# app's own subclass.

import frappe
from frappe import _

from . import SHELL_ROOT

#: A closed constant, not a hook. The set exists to protect the framework's own
#: address space; letting an app extend it would let an app claim website routes,
#: which is the surface the /apps redraw removed.
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
	"""Refuse a document whose `route` would land inside the shell's address space.

	Refuse rather than report, because `ShellPage` sits ahead of `StaticPage`: a
	permitted `apps/*` route would save successfully and then silently never load.
	Silent auto-rename was rejected on #42068's "path is identity".
	"""
	route = getattr(doc, "route", None)
	if not route or not is_reserved(route):
		return

	# Existing claims skip migrate, following `validate_route_conflict`'s own
	# `in_migrate` guard: a site that already has such a row must still be able to
	# migrate, and the one-time patch reports it instead.
	if frappe.flags.in_migrate or frappe.flags.in_patch or frappe.flags.in_install:
		return

	# Name the value *and* the field: routes are autoset from titles client-side, so
	# the handler cannot tell a typed route from a derived one, and the operator may
	# be looking at a Title field wondering what went wrong.
	frappe.throw(
		_(
			"The route {0} is reserved by the framework — {1} is where installed apps are "
			"served. Set a different value in the <b>Route</b> field of this {2}."
		).format(frappe.bold(route), frappe.bold(f"/{SHELL_ROOT}"), _(doc.doctype)),
		exc=ReservedRouteError,
		title=_("Reserved Route"),
	)
