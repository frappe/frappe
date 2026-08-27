# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Picks Insights or the legacy renderer for a desk dashboard.

Desk dashboards move to Insights across v16. Both renderers run side by side for
that time, and every condition behind the choice lives in this module.

The setting gates rendering surfaces only. Insights' own app, its content and the
island plumbing ignore the setting, and Insights depends on none of it.

Retirement: in v17 `get_dashboard_renderer` becomes `return INSIGHTS`. This module,
its call sites and the System Settings field then go. Neither step needs an
Insights release.
"""

import frappe
from frappe.utils import cint

# The two answers. `frappe.ui.get_dashboard_renderer` returns the same strings.
INSIGHTS = "insights"
LEGACY = "legacy"

# A System Settings field, so that a site turns the renderer on from the desk and
# needs no bench access. Unset means off.
SETTINGS_FIELD = "render_dashboards_with_insights"

INSIGHTS_APP = "insights"
INSIGHTS_DASHBOARD_DOCTYPE = "Insights Dashboard v3"


def get_dashboard_renderer(doctype: str) -> str:
	"""Which renderer draws a dashboard of `doctype`: `INSIGHTS` or `LEGACY`."""
	if doctype != INSIGHTS_DASHBOARD_DOCTYPE:
		return LEGACY

	# Framework's own installed-apps list, never an Insights import. This function
	# must answer on a site that does not have Insights at all.
	if INSIGHTS_APP not in frappe.get_installed_apps():
		return LEGACY

	if not cint(frappe.get_system_settings(SETTINGS_FIELD)):
		return LEGACY

	return INSIGHTS


@frappe.whitelist()
def get_renderer_for_reference(reference: str) -> str:
	"""Which renderer draws the dashboard a desk route names.

	Insights wins a collision. A reference Insights resolves goes to Insights even
	when a legacy `Dashboard` carries that name, which is how a route moves to
	Insights without editing the route or deleting the document behind it. Insights
	resolves a logical id, a docname, a slug or a v2 name. Legacy keeps the
	references only it answers for, and Insights still owns the state a reference
	that names nothing lands on.
	"""
	# The bare route names no dashboard. The legacy page's own flow picks one.
	if not reference:
		return LEGACY

	if get_dashboard_renderer(INSIGHTS_DASHBOARD_DOCTYPE) == LEGACY:
		return LEGACY

	if _insights_resolves(reference):
		return INSIGHTS

	return LEGACY if frappe.db.exists("Dashboard", reference) else INSIGHTS


def _insights_resolves(reference: str) -> bool:
	"""Whether Insights holds a dashboard for this reference.

	Reached only once `get_dashboard_renderer` has answered Insights, which already
	established that the app is installed. The lookup asks for no permission on
	purpose: one route must reach the same page for every user, and Insights draws
	its own not-available state for a reader who may not open the dashboard.
	"""
	resolve = frappe.get_attr("insights.resolver.resolve")
	return bool(resolve(INSIGHTS_DASHBOARD_DOCTYPE, reference))


def get_insights_rendered_doctype() -> str | None:
	"""The doctype desk renders with Insights, or `None` when the setting is off.

	Boot carries this answer, not the raw conditions, so no page reassembles the
	decision from parts. A site that renders no dashboard with Insights then
	answers on the client with no round trip.
	"""
	return (
		INSIGHTS_DASHBOARD_DOCTYPE if get_dashboard_renderer(INSIGHTS_DASHBOARD_DOCTYPE) == INSIGHTS else None
	)
